import sqlite3
import time
import hashlib
import hmac
import os

def seconds_text(s):
    if s < 180:
        return str(s) + 's'
    elif s < 7200:
        return str(int(s/60)) + 'm'
    else:
        return str(int(s/3600)) + 'h'

class Rodb:

#=================================================================================

    def __init__(self):
        self.conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
        self.c = self.conn.cursor()

        self.page_lifetime = 86400 # default, changed by db
        self.c.execute("""select file_lifetime from admin""")
        for row in self.c:
            self.page_lifetime = row[0]

        # Get hmac details once (and store in self loops)
        self.c.execute("""select hmac_key from admin""")
        for row in self.c:
            hmac_string = row[0]
        hmac_string += '\n'
        self.hmac_key = bytes(hmac_string,'utf-8')

        self.docroot = '/srv/www/vhosts/tornutopia.com/'

#=================================================================================
    def get_faction_for_player(self, u):

        faction_sum = {'fid':'0', 'name':'?', 'leader':0, 'coleader':0, 'leadername':'?', 'coleadername':'?'}

        # fid from pid
        self.c.execute("""select faction_id from playerwatch where player_id=?""", (u,))
        for row in self.c:
            faction_sum['fid'] = row[0]

        if faction_sum['fid']:
            # name from fid
            self.c.execute("""select f_name from factiondisplay where f_id=?""", (faction_sum['fid'],))
            for row in self.c:
                faction_sum['name'] = row[0]
            # leader and coleader from fid XXX
            self.c.execute("""select leader_id,coleader_id from factiondisplay where f_id=?""", (faction_sum['fid'],))
            for row in self.c:
                faction_sum['leader'] = row[0]
                faction_sum['coleader'] = row[1]

        print(faction_sum)

        self.c.execute("""select name from namelevel where player_id=?""", (faction_sum['leader'],))
        for row in self.c:
            faction_sum['leadername'] = row[0]

        self.c.execute("""select name from namelevel where player_id=?""", (faction_sum['coleader'],))
        for row in self.c:
            faction_sum['coleadername'] = row[0]

        return faction_sum

#=================================================================================
    def get_player_data(self, u):

        p_id = int(u)
        page_time = int(time.time())

        # name and level
        self.c.execute("""select name,level from namelevel where player_id=?""", (p_id,))
        for row in self.c:
            name,level = row

        # crime numbers and recency
        self.c.execute("""select et,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where  player_id = ? order by et""", (p_id,))
        crim_record = [-1 ,-1, -1, -1, -1, -1, -1, -1, -1]
        timestamp = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        for row in self.c:
            new_crim_record=row[1:]
            for i in range (0,9):
                if (new_crim_record[i] > crim_record[i]) and (crim_record[i] > -1):
                    timestamp[i] = row[0]
            crim_record=new_crim_record
        #
        crime_recency = []
        for rt in timestamp:
            if rt:
                crime_recency.append(time.strftime("%Y-%m-%d", time.gmtime(rt)))
            else:
                crime_recency.append('?')
        crime_num = {}
        i = 0
        crime_num['selling illegal product'] = crim_record[i]
        i += 1
        crime_num['theft'] = crim_record[i]
        i += 1
        crime_num['auto theft'] = crim_record[i]
        i += 1
        crime_num['drug deals'] = crim_record[i]
        i += 1
        crime_num['computer crimes'] = crim_record[i]
        i += 1
        crime_num['murder'] = crim_record[i]
        i += 1
        crime_num['fraud crimes'] = crim_record[i]
        i += 1
        crime_num['other'] = crim_record[i]
        i += 1
        crime_num['total'] = crim_record[i]

        #   PSTATS
        # XXX player stats may or may not be available - it needs that player's API key
        stats = {'nerve':'?', 'jail':'?', 'bust':'?', 'failbust':'?', 'hosp':'?', 'OD':'?', 'xanax':'?'}
        stat_num = None
        nerve_details = None
        drug_details = None
        self.c.execute("""select et,xantaken from drugs where player_id=? order by et desc limit 1""", (p_id,))
        for row in self.c:
            drug_details = row
        self.c.execute("""select et,cur_nerve,max_nerve from readiness where player_id=? order by et desc limit 1""", (p_id,))
        for row in self.c:
            nerve_details = row
        self.c.execute("""select jailed,peoplebusted,failedbusts,hosp,od from pstats where player_id=? order by et desc limit 1""", (p_id,))
        for row in self.c:
            stat_num = row
        if stat_num:
            stats['jail'] = stat_num[0] 
            stats['bust'] = stat_num[1] 
            stats['failbust'] = stat_num[2]
            stats['hosp'] = stat_num[3]
            stats['OD'] = stat_num[4]
        if nerve_details and nerve_details[2]:
            stats['nerve'] = nerve_details[2]
        got_drug_bool = False
        if drug_details and drug_details[1]:
            got_drug_bool = True
            stats['xanax'] = drug_details[1]

        #   IDLE TIME
        self.c.execute("""select et,total from playercrimes where player_id=? order by et""", (p_id,))
        was, when, one_interval, longest_interval = 0, 0, 0, 0  # activity
        for row in self.c:
            if row[1] == was:
                # equal to older value
                was = row[1]
                one_interval += (row[0] - when)
                if (one_interval > longest_interval):
                    longest_interval = one_interval
            elif (row[1] < was):
                # should never happen
                one_interval=0
            else:
                # increase
                one_interval=0
            when,was=row
        most_days_idle = int(longest_interval / 86400)
        if most_days_idle > 300:
            most_days_idle = 'many'

        age_of_data = {'level':'?', 'crimes':'?'}
        self.c.execute("""select et from namelevel where player_id = ?""", (p_id,))
        for row in self.c:
            level_time = page_time - row[0]
        self.c.execute("""select latest from playerwatch where player_id=?""", (p_id,))
        for row in self.c:
            crime_time = page_time - row[0]
        age_of_data['level'] = seconds_text(level_time)
        age_of_data['crimes'] = seconds_text(crime_time)


        # Calc OC rations
        all_my_oc = {}
        crimes_done = {}
        crimes_good = {}
        self.c.execute("""select factionoc.crime_name,factionoc.success from factionoc,whodunnit where factionoc.oc_plan_id = whodunnit.oc_plan_id and  whodunnit.player_id = ? and factionoc.initiated = 1""",(p_id,))
        for row in self.c:
            # Past OC data for this player
            if not row[0] in crimes_done:
                crimes_done[row[0]] = 0
                crimes_good[row[0]] = 0
            crimes_done[row[0]] += 1
            if row[1]:
                crimes_good[row[0]] += 1
        for oc in sorted(crimes_done):
            all_my_oc[oc] = str(crimes_good[oc]) + '/' + str(crimes_done[oc])

        events = ['TBC my OC record']  # XXX


        # attacknews
        attacklinks = {}
        flask_parm = ( str(p_id) + 'attack' + str(page_time) ).encode("utf-8")
        hmac_hex = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
        attacklinks[str(flask_parm)[2:-1] + '-' +  hmac_hex]  = 'attack'
        #
        flask_parm = ( str(p_id) + 'defend' + str(page_time) ).encode("utf-8")
        hmac_hex = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
        attacklinks[str(flask_parm)[2:-1] + '-' +  hmac_hex]  = 'defend'

        js_graphs = []  # XXX
        # link to flash graphs (parameters protected by HMAC)
        # crime
        graph_selection = ( str(p_id) + 'crime' + str(page_time)).encode("utf-8")
        hmac_hex = hmac.new(self.hmac_key, graph_selection, digestmod=hashlib.sha1).hexdigest()
        js_graphs.append([str(graph_selection)[2:-1] + '-' +  hmac_hex,  'detailed crime graph'])
        # and drug graph
        if got_drug_bool:
            graph_selection = ( str(p_id) + 'drug' + str(page_time)).encode("utf-8")
            hmac_hex = hmac.new(self.hmac_key, graph_selection, digestmod=hashlib.sha1).hexdigest()
            js_graphs.append([str(graph_selection)[2:-1] + '-' +  hmac_hex,  'detailed drug graph'])

        img_graphs = []
        var_interval_no = int(time.time()/self.page_lifetime)
        fnamepre = None
        self.c.execute("""select fnamepre from admin""")
        for row in self.c:
            fnamepre = row[0]
        player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + fnamepre + str(var_interval_no), 'utf-8')).hexdigest()
        for subject in ('nerve', 'drugs', 'total_crime', 'peoplebusted', 'jail', 'organisedcrimes'):
            decorated_name = name + '[' + str(p_id) + ']'
            graphname = hashlib.sha1(bytes('player-graph-for' + str(p_id) + player_dname + subject, 'utf-8')).hexdigest()
            short_fname ="player/" + player_dname + "/" + graphname + ".png"
            long_fname = self.docroot + short_fname
            try:
                mtime = os.stat(long_fname).st_mtime
                # graph is ready
                img_graphs.append([ short_fname, subject ])
            except:
                pass # graph not ready on disk

        player = {'name':name, 'u':u, 'level':level, 'crime_num':crime_num,
                 'crime_recency':crime_recency,  'most_days_idle':most_days_idle,
                 'stats':stats, 'age_of_data':age_of_data, 'oc':all_my_oc, 'events':events,
                 'attacklinks':attacklinks, 'js_graphs':js_graphs, 'img_graphs':img_graphs,
                  'got_drug_bool':got_drug_bool}

        return player
#=================================================================================
    def get_player_table(self, faction_sum):
        try:
            f_id = int(faction_sum['fid'])
        except:
            return None

        pids = []
        self.c.execute("""select player_id from playerwatch where faction_id=?""", (f_id,))
        for row in self.c:
            pids.append(row[0])

        player_table = {}
        for q in pids:
            tmp = self.get_player_data(q)
            tmp['events'] = ['player OC record'] # XXX
            player_table[q] = tmp

        # sort by player level and id
        pids = sorted(pids, key=lambda one: player_table[one]['u'])
        pids = sorted(pids, key=lambda one: player_table[one]['level'], reverse=True)

        s_table = {} # sorted
        for q in pids:
            s_table[q] = player_table[q]
        return s_table

#=================================================================================

if __name__ == '__main__':
    print('running this file')
