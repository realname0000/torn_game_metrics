import sqlite3
import time
import hashlib
import hmac
import os
import dehtml

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

        # Get hmac key once (and store in self)
        self.c.execute("""select hmac_key from admin""")
        for row in self.c:
            hmac_string = row[0]
        hmac_string += '\n'
        self.hmac_key = bytes(hmac_string,'utf-8')

        self.fnamepre = None
        self.c.execute("""select fnamepre from admin""")
        for row in self.c:
            self.fnamepre = row[0]

        self.file_lifetime = 86400 # default but read from db
        self.c.execute("""select file_lifetime from admin""")
        for row in self.c:
            self.file_lifetime = row[0]

        self.docroot = '/srv/www/vhosts/tornutopia.com/'

#=================================================================================
    def getkey(self):
        return self.hmac_key
#=================================================================================
    def get_faction_for_player(self, u):

        faction_sum = {'fid':'0', 'name':'?', 'leader':0, 'coleader':0, 'leadername':'?', 'coleadername':'?'}
        f_id = 0
        right_now = int(time.time())
        yesterday = right_now - 86400

        # fid from pid
        self.c.execute("""select faction_id from playerwatch where player_id=?""", (u,))
        for row in self.c:
            faction_sum['fid'] = row[0]
            f_id = row[0]

        if f_id:
            # name from fid
            self.c.execute("""select f_name from factiondisplay where f_id=?""", (f_id,))
            for row in self.c:
                faction_sum['name'] = row[0]
            # leader and coleader from fid
            self.c.execute("""select leader_id,coleader_id from factiondisplay where f_id=?""", (f_id,))
            for row in self.c:
                faction_sum['leader'] = row[0]
                faction_sum['coleader'] = row[1]

        self.c.execute("""select name from namelevel where player_id=?""", (faction_sum['leader'],))
        for row in self.c:
            faction_sum['leadername'] = row[0]

        self.c.execute("""select name from namelevel where player_id=?""", (faction_sum['coleader'],))
        for row in self.c:
            faction_sum['coleadername'] = row[0]

        # what API id has been used recently?
        what_used = {}
        self.c.execute("""select et,api_id from factionoc where faction_id=? order by et desc limit 1""", (f_id,))
        for row in self.c:
            what_used[row[1]] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(row[0]))
        self.c.execute("""select et,api_id from factionrespect where f_id=? and et > ?""", (f_id,yesterday,))
        for row in self.c:
            what_used[row[1]] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(row[0]))
        faction_sum['api_ids_used_by_faction'] = what_used

        # directory for faction_dname may exist ... or not
        var_interval_no = int (right_now/self.file_lifetime)
        faction_dname = hashlib.sha1(bytes('faction_variable_dir' + str(f_id) + self.fnamepre + str(var_interval_no), 'utf-8')).hexdigest()
        try:
            mtime = os.stat(self.docroot + 'faction/' + faction_dname).st_mtime
        except:
            # in that case an older one should exist
            faction_dname = hashlib.sha1(bytes('faction_variable_dir' + str(f_id) + self.fnamepre + str(var_interval_no-1), 'utf-8')).hexdigest()
        # respect graph
        graphname = hashlib.sha1(bytes('faction_png_graph' + str(f_id) + faction_dname + 'respect', 'utf-8')).hexdigest()
        short_fname = 'faction/' +  faction_dname + '/' + graphname + '.png'
        long_fname = self.docroot + short_fname
        try:
            mtime = os.stat(long_fname).st_mtime
            faction_sum['respect_graph_url'] = short_fname
        except:
            # graph not ready
            faction_sum['respect_graph_url'] = None

        # API ids, multiple values expected
        id_used = {}
        ##### self.c.execute("""select playercrimes.et,playercrimes.api_id from playercrimes join playerwatch on playercrimes.player_id = playerwatch.player_id  and playerwatch.faction_id = ? and playercrimes.et > ?""",
        # trying this alternative
        self.c.execute("""select pstats.et,pstats.api_id from pstats join playerwatch on pstats.player_id = playerwatch.player_id  and playerwatch.faction_id = ? and pstats.et > ?""",
            (faction_sum['fid'],yesterday,))
        for row in self.c:
            et = row[0]
            api_id = row[1]
            if api_id in id_used:
                if et > id_used[api_id]:
                    id_used[api_id] = et
            else:
                id_used[api_id] = et
        good_id = {}
        for api_id in id_used:
            name = '?'
            self.c.execute("""select name from namelevel where player_id=?""", (api_id,))
            for row in self.c:
                name = row[0]
            good_id[ name + '[' + str(api_id) + ']' ] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(id_used[api_id]))
        faction_sum['api_id_list'] = good_id

        # OC results
        faction_sum['oc_table'] = {}
        crime_schedule = []
        oc_name = {}
        oc_et = {}
        oc_timestring = {}
        # which OC types do we actually have?
        self.c.execute("""select distinct crime_id from factionoc where faction_id=? order by crime_id desc""", (f_id,))
        for row in self.c:
            crime_schedule.append(row[0])
        for crime_type in crime_schedule:
            db_queue = []
            self.c.execute("""select distinct crime_name,et from factionoc where """ +
                           """crime_id =? and faction_id=? and initiated=? order by et desc limit 1""",(crime_type,f_id,1,))
            for row in self.c:
                oc_name[crime_type] = row[0]
                oc_et[crime_type] = row[1]
                oc_timestring[crime_type] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(row[1]))
        #
        for crime_type in crime_schedule:
            flask_parm = ( str(f_id) + '-' + str(crime_type) + '-' +  str(right_now) +  '-history' ).encode("utf-8")
            hmac_hex_hist = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
            flask_parm = ( str(f_id) + '-' + str(crime_type) + '-' +  str(right_now) ).encode("utf-8")
            hmac_hex_short = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
            faction_sum['oc_table'][crime_type] =  [ oc_name[crime_type],
                         '/rhubarb/faction_oc_history/' + str(f_id) + '-' + str(crime_type) + '-' + str(right_now) +  '-history-' + hmac_hex_hist,
                         '/rhubarb/faction_oc_history/' + str(f_id) + '-' + str(crime_type) + '-' + str(right_now) +  '-' +  str(oc_et[crime_type]) + '-' + hmac_hex_short,
                         oc_timestring[crime_type] ]
        return faction_sum

#=================================================================================

    def get_oc(self, t_id, cn, longsearch):
        """return an octable structure of past OC and possibly an item of future OC"""

        octable = []
        crimes_to_show = []
        #  if cn is 0 it means t_id is a p_id, else t_id is a f_id
        if int(cn):
            # for faction
            time_limit = int(time.time() - 604800) # recent past
            if longsearch:
                time_limit = 0 # use whole time range
            self.c.execute("""select distinct factionoc.crime_name,factionoc.success,factionoc.time_completed,factionoc.time_executed,factionoc.participants,factionoc.money_gain,factionoc.respect_gain,factionoc.time_ready from factionoc where     factionoc.crime_id=? and factionoc.faction_id=? and factionoc.initiated=? and factionoc.time_completed>? order by time_ready desc""",(cn,t_id,1,time_limit,))
            for row in self.c:
                outcome = {}
                if row[1]:
                    outcome['money'] = row[5]
                    outcome['respect'] = row[6]
                else:
                    outcome['result'] = 'FAIL'
                outcome['delay'] = str(int((row[2] - row[7])/60)) + " mins" # time_completed - time_ready, converted to minutes
                this_crime = [ time.strftime("%Y-%m-%d", time.gmtime(row[7])), cn, row[0], row[4], outcome ]
                crimes_to_show.append(this_crime)
            for this_crime in crimes_to_show:
                participants = this_crime[3]
                new_participants = {}
                for pid in participants.split(','):
                    self.c.execute("""select name from namelevel where player_id=?""", (pid,))
                    for row in self.c:
                        new_participants[pid] = row[0]
                this_crime[3]  = new_participants
                octable.append(this_crime)
            return octable, None

        # for player
        time_intervals = [] # matches octable entries to complete them with player status data after db cursor finishes looping over factionoc
        self.c.execute("""select factionoc.crime_id,factionoc.crime_name,factionoc.success,factionoc.time_completed,factionoc.time_ready,factionoc.money_gain,factionoc.respect_gain from factionoc,whodunnit where  factionoc.initiated=? and factionoc.oc_plan_id=whodunnit.oc_plan_id and  whodunnit.player_id=? order by time_ready desc""", (1,t_id,))
        for row in self.c:
            outcome = {}
            if row[3]:
                outcome['money'] = row[5]
                outcome['respect'] = row[6]
            else:
                outcome['result'] = 'FAIL'
            outcome['delay'] = str(int((row[3] - row[4])/60)) + " mins" # time_completed - time_ready, converted to minutes
            this_crime = [ time.strftime("%Y-%m-%d", time.gmtime(row[4])), row[0], row[1], 'placeholder fixed below', outcome ]
            crimes_to_show.append(this_crime)
            time_intervals.insert(0, [row[3], row[4]]) # completed and ready
        for this_crime in crimes_to_show: # most recent at top of the list
            # work on readiness placeholder
            octable.append(this_crime)
            want_readiness = time_intervals.pop()
            time_completed,time_ready = want_readiness
            self.c.execute("""select max(et) from readiness where player_id=? and et<? and et>?""", (t_id, time_ready, time_ready-43200,))  # last observation before readiness
            time_first = time_ready
            for row in self.c:
                time_first = row[0]
            self.c.execute("""select et,cur_nerve,max_nerve,status_0,status_1  from readiness where player_id=? and et>=? and et<?""", (t_id, time_first, time_completed,))
            readiness_record = []
            for row in self.c:
                delta_t = row[0] - time_ready  # could be +ve or -ve
                time_description = time.strftime("%H:%M", time.gmtime(row[0])) + ' T '
                if delta_t < 0:
                    time_description += 'minus '
                    delta_t *= -1
                else:
                    time_description += 'plus '
                time_description += str(int(delta_t/60)) + 'm'
                player_status_then = {time_description:row[3] + ' ' +row[4]}
                if row[2]:
                    player_status_then['nerve'] = str(row[1]) + '/' + str(row[2]) # may or may not exist
                readiness_record.append(player_status_then)
            octable[-1][3] = readiness_record

        return octable, None

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

        # PSTATS
        # player stats may or may not be available - it needs that player's API key
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

        # IDLE TIME
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

        # OC success
        oc_calc = 0
        self.c.execute("""select oc_calc from playeroc where player_id = ?""", (p_id,))
        for row in self.c:
            oc_calc = row[0]

        # Calc OC ratios from the last year
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

        # OC data for display to the individual
        flask_parm = (str(u) + '-0-' +  str(page_time) + '-history' ).encode("utf-8")
        hmac_hex_hist = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
        events = '/rhubarb/faction_oc_history/' + str(u) + '-0-' + str(page_time) +  '-history-' + hmac_hex_hist

        # attacknews
        attacklinks = {}
        flask_parm = ( str(p_id) + 'attack' + str(page_time) ).encode("utf-8")
        hmac_hex = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
        attacklinks[str(flask_parm)[2:-1] + '-' +  hmac_hex]  = 'attack'
        #
        flask_parm = ( str(p_id) + 'defend' + str(page_time) ).encode("utf-8")
        hmac_hex = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
        attacklinks[str(flask_parm)[2:-1] + '-' +  hmac_hex]  = 'defend'

        js_graphs = []
        # link to flask js graphs (parameters protected by HMAC)
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
        # directory for player_dname may exist ... or not
        player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + self.fnamepre + str(var_interval_no), 'utf-8')).hexdigest()
        try:
            mtime = os.stat(self.docroot + 'player/' + player_dname).st_mtime
        except:
            # in that case an older one should exist
            player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + self.fnamepre + str(var_interval_no-1), 'utf-8')).hexdigest()
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
                 'got_drug_bool':got_drug_bool, 'oc_calc':oc_calc}

        return player
#=================================================================================
    def get_player_table(self, faction_sum):
        try:
            f_id = int(faction_sum['fid'])
        except:
            return None

        page_time = int(time.time())
        pids = []
        self.c.execute("""select player_id from playerwatch where faction_id=?""", (f_id,))
        for row in self.c:
            pids.append(row[0])

        player_table = {}
        for q in pids:
            one_player_structure = self.get_player_data(q)
            #
            # OC data for display to the individual
            flask_parm = (str(q) + '-0-' +  str(page_time) + '-history' ).encode("utf-8")
            hmac_hex_hist = hmac.new(self.hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
            one_player_structure['events'] = ['/rhubarb/faction_oc_history/' + str(q) + '-0-' + str(page_time) +  '-history-' + hmac_hex_hist]
            #
            player_table[q] = one_player_structure

        # sort by player level and id
        pids = sorted(pids, key=lambda one: player_table[one]['u'])
        pids = sorted(pids, key=lambda one: player_table[one]['level'], reverse=True)

        s_table = {} # remake in order
        for q in pids:
            s_table[q] = player_table[q]
        return s_table

#=================================================================================

if __name__ == '__main__':
    print('running this file')
