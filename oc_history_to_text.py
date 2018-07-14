import time
import os
import hashlib
import dehtml


class Crime_history:

    def __init__(self, docroot):
        self.docroot = docroot

    def player_readiness(self, c, p_id, player_name, time_ready, t_end, t_begin, t_executed):
        what_readiness = ''
        t_first = None
        c.execute("""select max(et) from readiness where player_id=? and et<? and et>?""", (p_id, t_end, t_begin,))
        for player_history in c:
            if player_history[0]:
                t_first = player_history[0]
        if t_first:
            if t_executed:
                t_end = t_executed
            c.execute("""select et,cur_nerve,max_nerve,status_0,status_1  from readiness where player_id=? and et>=? and et<?""", (p_id, t_first, t_end,))
            for player_history in c:
                t_alibi, cur_nerve, max_nerve, status_0, status_1 = player_history
                frog = dehtml.Dehtml()
                status_0 = frog.html_clean(status_0)
                status_1 = frog.html_clean(status_1)
                delta_t = t_alibi - time_ready  # could be +ve or -ve
                what_readiness = what_readiness + '\n' + player_name + ' ' + time.strftime("%H:%M", time.gmtime(t_alibi)) + ' T '
                if delta_t < 0:
                    what_readiness += 'minus '
                    delta_t *= -1
                else:
                    what_readiness += 'plus '
                what_readiness = what_readiness + str(int(delta_t/60)) + 'm ' + status_0 + ' ' + status_1
                if max_nerve:
                    what_readiness = what_readiness + ' nerve=' + str(cur_nerve) + '/' + str(max_nerve)
        return what_readiness

    #  db connection
    #   list of OC data  ... needs to include player_id ... specify it here
    #     ? show status or not?
    #     Do the web page in here
    #        player or faction or other source?
    #        filename precursor
    #     player_id as p_id needed for status history
    def crime2html(self, c, db_queue, pid2name, need_status, source_type, dname, p_id, weekno):
        now = time.time()
        # return value is [ success/failure, the HREF of the web page, mtime of web page ]
        how_recent = 0
        time_ready = 0
        time_executed = 0
        for row in db_queue:
            et = row[8]
            if et > how_recent:
                how_recent = et
                time_executed = row[4]
                time_ready = row[9]

        if ('player' == source_type) and p_id:
            longdname = self.docroot + 'player/' + dname
            try:
                mtime = os.stat(longdname).st_mtime
            except:
                return [0]  # Directory should already exist
            rfname = hashlib.sha1(bytes('oc_history' + dname, 'utf-8')).hexdigest()
            shortname = '/player/' + dname + '/' + rfname + '.txt'
            longname = self.docroot + shortname
            if time_executed or ((time_ready - now) > 7200):
                # might or might not write file
                try:
                    mtime = os.stat(longname).st_mtime
                    if int(mtime) > int(how_recent):  # time-of-data
                        # page exists and is recent; use it unchanged
                        return [1, shortname, int(mtime)]
                except:
                    pass  # need to write file
        elif ('faction' == source_type):
            longdname = self.docroot + 'faction/' + dname
            try:
                mtime = os.stat(longdname).st_mtime
            except:
                return [0]  # Directory should already exist
            # abuse p_id for crime_id
            rfname = hashlib.sha1(bytes('oc_history_list' + dname + str(p_id), 'utf-8')).hexdigest()
            shortname = '/faction/' + dname + '/' + rfname + '.txt'
            longname = self.docroot + shortname
            try:
                mtime = os.stat(longname).st_mtime
                if int(mtime) > int(how_recent):  # time-of-data
                    # page exists, use it unchanged
                    return [1, shortname, int(mtime)]
                # need to write file becaue it is too old
            except:
                pass  # need to write file becaue it does not exist
        else:
            return [0]
        #
        crimes_planned = ''
        linebreak = ''
        for row in db_queue:
            crime_name = row[0]
            initiated = row[1]
            success = row[2]
            time_completed = row[3]
            time_executed = row[4]
            player_list = row[5]
            money = row[6]
            respect = row[7]
            et = row[8]
            time_ready = row[9]

            players = player_list.split(',')
            comma = ''
            namelist = ''
            for oneplayer in players:
                if oneplayer in pid2name:
                    one_player_name = pid2name[oneplayer]
                else:
                    one_player_name = str(oneplayer)
                namelist = namelist + comma + one_player_name
                comma = ', '
            timestring = time.strftime("%Y-%m-%d", time.gmtime(time_ready)) + ' '
            crimes_planned = crimes_planned + linebreak + timestring + crime_name + ' players are ' + namelist
            #
            #
            if initiated:
                if need_status:
                    if str(p_id) in pid2name:
                        player_name = pid2name[str(p_id)]
                    else:
                        print("WHY MISSING? ", p_id, " not in ", pid2name)
                        player_name = str(p_id)
                    # Player readiness history
                    crimes_planned += self.player_readiness(c, p_id, player_name, time_ready, time_ready, time_ready-3600, time_executed)
                #
                if success:
                    crimes_planned = crimes_planned + '\n' + 'money=' + str(money) + ' respect=' + str(respect)
                else:
                    crimes_planned = crimes_planned + '\n' + 'Fail'
                if time_executed:
                    if time_ready > 8640000:
                        # should use this
                        delaytime = (time_completed - time_ready)/60
                    else:
                        # old style before time_ready existed
                        delaytime = (time_executed - time_completed)/60
                    delaytime = int(delaytime+0.5)
                    crimes_planned = crimes_planned + ' delay=' + str(delaytime) + ' minutes'
            else:
                t_remaining = int(time_ready - now)
                if t_remaining > 0:
                    crimes_planned = crimes_planned + '\nstill future ' + time.strftime("%Y-%m-%d %H:%M", time.gmtime(time_ready))
                else:
                    crimes_planned = crimes_planned + '\ndue but not yet initiated'
                # Player readiness history
                crimes_planned += self.player_readiness(c, p_id, 'Advance readiness notice:', time_ready, now, now-86400, 0)
            crimes_planned = crimes_planned + '\n'
            linebreak = '\n'

        webpage = open("/torntmp/tmpfile_player_oc", "w")
        print(crimes_planned, file=webpage)
        webpage.close()
        os.rename("/torntmp/tmpfile_player_oc", longname)
        mtime = os.stat(longname).st_mtime
        return [1, shortname, int(mtime)]
