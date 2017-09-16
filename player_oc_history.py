import sqlite3
import time
import os

#   def show(self, who, finance):
#       print("rhubarb",  who)
#       for person in finance.keys():
#           fname = "page_" + person + "_figures.html"
#           try:
#               mtime = os.stat(fname).st_mtime
#               print( fname, " has timestamp ", mtime)
#           except:
#               webpage=open(fname, "w")
#               print(person, ' gets ', finance[person], file=webpage)
#               webpage.close()

  
class Crime_history:

    def init():
        pass

    #  db connection
    #   list of OC data  ... needs to include player_id ... specify it here
    #     ? show status or not?
    #     Do the web page in here
    #        player or faction or other source?
    #        filename precursor
    #     player_id as p_id needed for status history
    def crime2html(self, c, db_queue, pid2name, need_status, source_type, fname_pre, p_id):
        # return value is [ success/failure, the filename of the web page (to be made into a link by the caller), mtime of web page ]
        if ('player' == source_type) and  p_id:
            fname = 'tmp-player-' + str(p_id) + '.txt'
            try:
                mtime = os.stat(fname).st_mtime
                if mtime > 0: # time-of-data: XXX
                    # page exists, use it unchanged
                    return [1, fname, mtime]
            except:
                pass # need to write file
        else:
            fail =1/0
        #
        # If the web page already exists and is up to date return immediately
        # else open and write temp web page then rename it
        crimes_planned = ''
        linebreak=''
        for row in db_queue:
            crime_name=row[0]
            initiated=row[1]
            success=row[2]
            time_completed=row[3]
            time_executed=row[4]
            player_list=row[5]
            money=row[6]
            respect=row[7]
                
            players= player_list.split(',')
            comma = ''
            namelist = ''
            for oneplayer in players:
                if oneplayer in pid2name:
                    namelist = namelist + comma + pid2name[oneplayer]
                else:
                    namelist = namelist + comma + str(oneplayer)
                comma = ', '
            timestring =  time.strftime("%Y-%m-%d", time.gmtime(time_completed)) + ' '
            crimes_planned = crimes_planned + linebreak +  timestring + crime_name + ' players are ' + namelist
            #
            #
            if initiated:
                if need_status:
                    # Player readiness history goes here
                    t_first = None
                    c.execute("""select max(et) from readiness where player_id=? and et<? and et>?""",(p_id, time_completed, time_completed-3600,))
                    for player_history in c:
                        if player_history[0]:
                            t_first = player_history[0]
                    if t_first:
                        c.execute("""select et,cur_nerve,max_nerve,status_0,status_1  from readiness where player_id=? and et>=? and et<?""",(p_id, t_first, time_executed,))
                        for player_history in c:
                            t_alibi,cur_nerve,max_nerve,status_0,status_1 = player_history
                            delta_t = t_alibi - time_completed # could be +ve or -ve
                            # status_0 may need cleaning for HTML
                            # status_1 may need cleaning for HTML
                            crimes_planned = crimes_planned + '<br/>' + time.strftime("%H:%M", time.gmtime(t_alibi)) + ' T '
                            if delta_t < 0:
                                crimes_planned = crimes_planned + 'minus '
                                delta_t *= -1
                            else:
                                crimes_planned = crimes_planned + 'plus '
                            crimes_planned = crimes_planned + str(int(delta_t/60)) + 'm ' + status_0 + ' ' +  status_1
                            if max_nerve:
                                crimes_planned = crimes_planned + ' nerve=' + str(cur_nerve) +'/'+ str(max_nerve)
                #
                if success:
                    crimes_planned = crimes_planned + '<br/>' + 'money=' + str(money) + ' respect=' + str(respect) 
                else:
                    crimes_planned = crimes_planned + '<br/>' + 'Fail'
                if time_executed:
                    delaytime = (time_executed - time_completed)/60
                    delaytime =int(delaytime+1)
                    crimes_planned = crimes_planned +  ' delay=' + str(delaytime) + ' minutes (or less)'
            else:
                crimes_planned = crimes_planned + '<br/>still future'
            crimes_planned = crimes_planned + '<br/>'
            linebreak='\n'

            return [1, fname, 1505509095] # mtime XXX
