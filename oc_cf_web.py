import time
import os
import hashlib


class Crime_compare:

    def __init__(self, docroot):
        self.docroot = docroot
        self.dbcache = {}

    def one_oc(self, c, f_id, plan):
            if plan in self.dbcache:
                return self.dbcache[plan]
            c.execute("""select time_completed,time_executed,crime_name,participants,money_gain,respect_gain from factionoc where faction_id=? and oc_plan_id=?""", (f_id, plan,))
            for row in c:
                self.dbcache[plan] = row
                return self.dbcache[plan]

    def load(self, c, my_oc_cf, pid2name, p_id, cf, chosen_crime_type):
        self.queue = []
        seen_left = {}  # debugging info to catch duplicates
        for oc_pair in my_oc_cf:
            f_id = oc_pair[0]
            crime_name = oc_pair[1]
            oc_a = oc_pair[2]
            oc_b = oc_pair[3]
            if oc_a in seen_left:
                if oc_b in seen_left[oc_a]:
                    print("Suspect duplication for player ", p_id, my_oc_cf)
                    continue
                seen_left[oc_a].append(oc_b)
            else:
                seen_left[oc_a] = [oc_b]
            player_1 = oc_pair[4]
            player_2 = oc_pair[5]
            if int(p_id) != int(player_1):
                print("error with missing player", p_id, player_1)
                continue
            if int(cf) != int(player_2):
                continue  # ok to miss this
            line = []
            for oc_plan in [oc_a, oc_b]:
                gang = ''
                details = self.one_oc(c, f_id, oc_plan)
                time_executed = time.strftime("%Y-%m-%d %H:%M", time.gmtime(details[0]))
                if details[1]:
                    time_executed = time.strftime("%Y-%m-%d %H:%M", time.gmtime(details[1]))  # a better result provided we have it
                crime_name = details[2]
                participants = details[3]
                money_gain = details[4]
                respect_gain = details[5]
                for p in participants.split(','):
                    if p in pid2name:
                        gang += pid2name[p] + '[' + p + '] '
                    else:
                        gang += '?[' + p + '] '
                if crime_name == chosen_crime_type:
                    stuff = str(oc_plan) + ' at time ' + str(time_executed) + '<br/>' + str(crime_name) + ' by ' + gang + '<br/> money=' + str(money_gain) + ' respect=' + str(respect_gain)
                    line.append(stuff)
            if len(line):
                self.queue.append(line)

    def iterate(self):
        try:
            return self.queue.pop()
        except:
            return None

    def table_left_right(self, c, my_oc_cf, pid2name, dname, p_id, cf, weekno, chosen_crime_type):
        rfname = hashlib.sha1(bytes('oc_two_player' + dname + str(p_id) + ':' + str(cf) + chosen_crime_type, 'utf-8')).hexdigest()
        shortname = '/player/' + dname + '/' + rfname + '.html'
        longname = self.docroot + shortname

        webpage = open("/torntmp/tmpfile_player_oc_cf_table_of_two", "w")
        print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'></head><body>", file=webpage)
        print('<table border="1">', file=webpage)

        print('<tr>', file=webpage)
        for i in [p_id, cf]:
            if str(i) in pid2name:
                player_name = str(pid2name[str(i)])
            else:
                player_name = "?"
            print('<th>' + player_name + '[' + str(i) + ']</th>', file=webpage)
        print('</tr>', file=webpage)

        self.load(c, my_oc_cf, pid2name, p_id, cf, chosen_crime_type)
        while 1:
            something_to_print = self.iterate()
            if not something_to_print:
                break
            print('<tr>', file=webpage)
            for i in something_to_print:
                print('<td>' + str(i) + '</td>', file=webpage)
            print('</tr>', file=webpage)

        print("</table>", file=webpage)
        print("</body></html>", file=webpage)
        webpage.close()

        os.rename("/torntmp/tmpfile_player_oc_cf_table_of_two", longname)
        mtime = os.stat(longname).st_mtime
        return [1, shortname, int(mtime)]

    def web(self, c, my_oc_cf, pid2name, dname, p_id, weekno):
        # return value is [ success/failure, the HREF of the web page, mtime of web page ]

        # what time is our data?
        how_recent = 0
        c.execute("""select et from player_compare_t where player_id=?""", (p_id,))
        for row in c:
            how_recent = row[0]

        longdname = self.docroot + 'player/' + dname
        try:
            mtime = os.stat(longdname).st_mtime
        except:
            return [0]  # Directory should already exist
        rfname = hashlib.sha1(bytes('oc_comparison' + dname, 'utf-8')).hexdigest()
        shortname = '/player/' + dname + '/' + rfname + '.html'
        longname = self.docroot + shortname
        try:
            mtime = os.stat(longname).st_mtime
            if int(mtime) > int(how_recent):  # time-of-data
                # page exists, use it unchanged
                return [1, shortname, int(mtime)]
        except:
            pass  # need to write file

        webpage = open("/torntmp/tmpfile_player_oc_cf", "w")
        print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'></head><body>", file=webpage)
        if str(p_id) in pid2name:
            player_name = str(pid2name[str(p_id)])
        else:
            player_name = "?"
        print("<h2>Comparing " + player_name + "[" + str(p_id) + "] to others:</h2>", file=webpage)

        type_person = {}
        for row in my_oc_cf:
            oc_type = row[1]
            if oc_type not in type_person:
                type_person[oc_type] = {}
            #
            if str(row[4]) == str(p_id):
                type_person[oc_type][row[5]] = row[2]
            elif str(row[5]) == str(p_id):
                type_person[oc_type][row[4]] = row[2]

        # New bit
        for ty in sorted(type_person.keys()):
            print("<hr />", file=webpage)
            for per in sorted(type_person[ty].keys()):
                if str(per) in pid2name:
                    player_name = str(pid2name[str(per)])
                else:
                    player_name = "?"
                t_details = self.table_left_right(c, my_oc_cf, pid2name, dname, p_id, per, weekno, ty)
                if t_details[0]:
                    print('<br/><a href="' + t_details[1] + '">' + player_name + '[' + str(per) + ']</a>', file=webpage)
                else:
                    print("<br/>" + player_name + "[" + str(per) + "] ... web page not found", file=webpage)
        print("<hr />", file=webpage)

        print("</body></html>", file=webpage)

        webpage.close()
        os.rename("/torntmp/tmpfile_player_oc_cf", longname)
        mtime = os.stat(longname).st_mtime
        return [1, shortname, int(mtime)]
