#!/usr/bin/python3

import sqlite3
import time
import os
import hashlib
import oc_history_to_text

def seconds_text(s):
    if s < 180:
        return str(s) +'s'
    elif s < 7200:
        return str(int(s/60)) +'m'
    else:
        return str(int(s/3600)) +'h'

def prepare_player_stats(p_id, pid2name, page_time, show_debug, fnamepre, weekno):
    blob = []
    player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    if show_debug:
        print("player data for ", p_id)
        print("use directory ", player_dname)

    longdname='/srv/www/htdocs/player/' + player_dname
    try:
        mtime = os.stat(longdname).st_mtime
    except:
        os.mkdir(longdname)

    # produce OC list
    linebreak=''
    db_queue = []
    c.execute("""select factionoc.crime_name,factionoc.initiated,factionoc.success,factionoc.time_completed,factionoc.time_executed,factionoc.participants,factionoc.money_gain,factionoc.respect_gain,factionoc.et from factionoc,whodunnit where factionoc.oc_plan_id = whodunnit.oc_plan_id and  whodunnit.player_id = ? order by time_completed desc""",(p_id,))
    for row in c:
        db_queue.append(row)
    #
    if len(db_queue):
        # what should the name of the web page be?
        hist=oc_history_to_text.Crime_history()
        retlist = hist.crime2html(c, db_queue, pid2name, 1, 'player', player_dname, p_id, weekno)
        if show_debug:
            print(retlist)
        got_page = retlist[0]
        if got_page:
            # time parameter to help see whether a page has changed since you last loaded it in the browser
            crimes_planned = '<a href="' + retlist[1] + '?t=' +  str(retlist[2]) + '">OC history</a>'
        else:
            crimes_planned = 'failed to get page'
    else:
        crimes_planned = 'no OC to show'


    # Calc OC rations
    crimes_done = {}
    crimes_good = {}
    c.execute("""select factionoc.crime_name,factionoc.success from factionoc,whodunnit where factionoc.oc_plan_id = whodunnit.oc_plan_id and  whodunnit.player_id = ? and factionoc.initiated = 1""",(p_id,))
    for row in c:
        # Past OC data for this player
        if not row[0] in crimes_done:
            crimes_done[row[0]] = 0
            crimes_good[row[0]] = 0
        crimes_done[row[0]] += 1
        if row[1]:
            crimes_good[row[0]] += 1
    build_string = ''
    linebreak=''
    for oc in sorted(crimes_done):
        r = oc + '=' + str(crimes_good[oc]) + '/' + str(crimes_done[oc])
        build_string = build_string + linebreak + r
        linebreak='<br/>'
    col_ratio_answer = build_string


    # timeliness of stats data
    c.execute("""select et from namelevel where player_id = ?""",(p_id,))
    for row in c:
        level_time= page_time - row[0]
    c.execute ("""select latest from playerwatch where player_id=?""",(p_id,))
    for row in c:
        crime_time = page_time - row[0]
    col6_answer="level=" + seconds_text(level_time) + "<br/>crimes=" + seconds_text(crime_time)


#   PSTATS
    pstats='jail ?<br/>bust ?<br/>failbust ?<br/>hosp ?<br/>OD ?'
    stat_num = None
    c.execute("""select  jailed,peoplebusted,failedbusts,hosp,od from pstats where player_id=? order by et""",(p_id,))
    for row in c:
        stat_num = row
    if stat_num:
        pstats='jail ' + str(stat_num[0]) +  '<br/>bust ' + str(stat_num[1]) + '<br/>failbust ' + str(stat_num[2]) + '<br/>hosp ' + str(stat_num[3]) + '<br/>OD ' + str(stat_num[4]) 

#   IDLE TIME
    c.execute("""select  et,total from playercrimes where player_id=? order by et""",(p_id,))
    was, when, one_interval, longest_interval = 0,0,0,0 # activity
    for row in c:
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
    days_idle = int (longest_interval / 86400)
    if days_idle > 300:
        days_idle='many'
    else:
        days_idle=str(days_idle)

    # column of recenvy
    c.execute("""select et,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where  player_id = ? order by et""", (p_id,))
    crim_record = [-1,-1,-1, -1,-1,-1, -1,-1,-1]
    timestamp = [0,0,0, 0,0,0, 0,0,0]
    for row in c:
        new_crim_record=row[1:]
        for i in range (0,9):
            if (new_crim_record[i] > crim_record[i]) and (crim_record[i] > -1):
                timestamp[i] = row[0]
        crim_record=new_crim_record
    col4_answer = ''
    for rt in timestamp:
        if rt:
            col4_answer = col4_answer +  "<div align='right'>" +  time.strftime("%Y-%m-%d", time.gmtime(rt)) + "</div><div align='right'>"
        else:
            col4_answer = col4_answer +  "<div align='right'>?</div><div align='right'>"
    #
    col3_answer = ['numbers ?']
    col2_answer = ['what crimes ?']
    c.execute("""select selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where  player_id = ? and  et= (select max(et) from playercrimes where player_id = ?)""", (p_id, p_id,))
    for row in c:
        col3_answer = "<div align='right'>" + str(row[0]) + "</div><div align='right'>" + str(row[1]) + "</div><div align='right'>" + str(row[2]) +  \
        "</div><div align='right'>" + str(row[3]) + "</div><div align='right'>" + str(row[4]) + "</div><div align='right'>" + str(row[5]) + "</div><div align='right'>" +  \
        str(row[6]) + "</div><div align='right'>" + str(row[7]) + "</div><div align='right'>" + str(row[8]) + "</div>"
        #
        col2_answer = "selling illegal product<br/>theft<br/>auto theft<br/>drug deals<br/>computer crimes<br/>murder<br/>fraud crimes<br/>other<br/>total"

    blob.append(crimes_planned)
    blob.append(col_ratio_answer)
    blob.append(col6_answer)
    blob.append(pstats)
    blob.append(days_idle)
    blob.append(col4_answer)
    blob.append(col3_answer)
    blob.append(col2_answer)
    #
    col1_answer = ['???' ,p_id, '???']
    c.execute("""select name,level from namelevel where player_id=?""", (p_id,))
    for row in c:
        col1_answer = [row[0], p_id, row[1]]

    pg_index=open("/torntmp/begin_graphs.html", "w")
    print("<html><head></head><body>", file=pg_index)
    print("Player data for ", col1_answer[0], file=pg_index)
    #
    print("<table border='1'>", file=pg_index)
    print("<tr><th>Most days idle</br>(no crime)</th><th>OC success</th><th>event list</th></tr>", file=pg_index)
    print("<tr><td>", blob[4], "</td><td>", blob[1], "</td><td>", blob[0], "</td></tr>", file=pg_index)
    print("</table>", file=pg_index)
    print("<p/>links to graphs coming soon", file=pg_index)
    #
    print("</body></html>", file=pg_index)
    pg_index.close()
    player_index = hashlib.sha1(bytes('player-index' + str(p_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    os.rename("/torntmp/begin_graphs.html",  "/srv/www/htdocs/player/" + player_dname +  "/" +  player_index + ".html")
    col1_answer.append("/player/" + player_dname +  "/" +  player_index + ".html")

    blob.append(col1_answer)
    return blob

def prepare_faction_stats(f_id, fnamepre, weekno):
    page_time = int(time.time()) # seconds
    print("faction data for ", f_id)
    pid2name = {} # used while processing each player
    f_data = []
    c.execute("""select playerwatch.player_id,namelevel.name from playerwatch,namelevel where playerwatch.faction_id=? and  playerwatch.player_id=namelevel.player_id""", (f_id,))
    player_todo = []
    for p in c:
        player_todo.append(p[0])
        pid2name[str(p[0])] = p[1]

    n_player=0
    for p in player_todo:
        show_debug = 0
        if n_player < 3:
            show_debug = 1
        f_data.append( prepare_player_stats(p, pid2name, page_time, show_debug, fnamepre, weekno) )
        n_player += 1
    print(n_player, "players processed")

    f_data = sorted(f_data, key=lambda one: one[-1][1]) 
    f_data = sorted(f_data, key=lambda one: one[-1][2], reverse=True) 


    faction_name,faction_web = '?',None
    c.execute("""select f_name,f_web from factiondisplay where f_id=?""", (f_id,))
    for fdetails in c:
        faction_name,faction_web = fdetails

    c.execute("""select latest_oc from factionwatch where faction_id=?""", (f_id,))
    for tt in c:
        oc_time = page_time - tt[0]

    faction_dname = hashlib.sha1(bytes('faction_variable_dir' + str(f_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()

    web=open("/torntmp/player_table.html", "w")
    print("<html><head></head><body><h2>Faction Player Table:", file=web)
    print(faction_name, f_id, file=web)
    print("</h2>", file=web)
    print("<br/>Page created at ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(page_time)), file=web)
    print("<br/>Faction organised crime data " + seconds_text(oc_time) + " old", file=web)
# XXX      print("<br/>Faction membership data " + seconds_text(member_time) + " old", file=web)
    print("<p/>", file=web)

    print("<table border='1'>", file=web)
    print("<tr><th>Player</th><th>Crime</th><th>Number</th><th>Recency</th> <th>Most days idle</br>(no crime)</th><th>Stats</th><th>Age of data</th><th>OC success</th><th>event list</th></tr>", file=web)

    for item in f_data:
        q = item.pop()
        print("<tr><td>", file=web)
        print('<a href="', q[3], '">',  q[0], '</a>', file=web)
        print('<br/>', q[1], '<br/>', q[2], file=web)
        print("</td><td>", file=web)

        q = item.pop()
        #   crimes theft
        print(q, file=web)
        print("</td><td>", file=web)

        q = item.pop()
        #   Number 10000
        print(q, file=web)
        print("</td><td>", file=web)

        q = item.pop()
        #   recency timestamp
        print(q, file=web)
        print("</td><td>", file=web)

        q = item.pop()
        print("<div align='right'>" + q + "</div>", file=web)
        print("</td><td>", file=web)

        # jail etc
        q = item.pop()
        print(q, file=web)
        print("</td><td>", file=web)

        q = item.pop()
        print(q, file=web)
        print("</td><td>", file=web)

         #  oc
         # <div title='date-player-outcome date-player-outcome date-player-outcome date-player-outcome date-playeroutcome'>PA 4/5</div>
        q = item.pop()
        print(q, file=web)
        print("</td><td>", file=web)

        q = item.pop()
        print(q, file=web)
        print("</td></tr>", file=web)

    print("</table>", file=web)
    print("<body><html>", file=web)
    web.close()

    longdname='/srv/www/htdocs/faction/' + faction_dname
    try:
        mtime = os.stat(longdname).st_mtime
    except:
        os.mkdir(longdname)
    faction_ptname = hashlib.sha1(bytes('faction_player_table' + str(f_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    os.unlink("/srv/www/htdocs/faction/demo.html")   # XXX
    os.link("/torntmp/player_table.html", "/srv/www/htdocs/faction/demo.html")   # XXX
    os.rename("/torntmp/player_table.html", "/srv/www/htdocs/faction/" +  faction_dname + '/'  + faction_ptname +  ".html")

    crime_schedule=[]
    c.execute("""select distinct crime_id from factionoc where faction_id=? order by crime_id desc""", (f_id,))
    for row in c:
        crime_schedule.append(row[0])
    # Intro file
    introdir='/srv/www/htdocs/intro/' + faction_web
    try:
        mtime = os.stat(introdir).st_mtime
    except:
        os.mkdir(introdir)
    intro=open("/torntmp/index.html", "w")
    print("<html><head></head><body><h2>Faction Intro Page: ", file=intro)
    print(faction_name, f_id, file=intro)
    print("</h2>", file=intro)
    print("<br/>Page created at ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(page_time)), file=intro)
    print('<p/><a href="/faction/' +   faction_dname + '/'  + faction_ptname +  '.html' + '">Player Table</a>', file=intro)
    print('<p/><hr>', file=intro)

    print('<ul>', file=intro)
    for crime_type in  crime_schedule:
        db_queue = []
        c.execute("""select distinct factionoc.crime_name,factionoc.initiated,factionoc.success,factionoc.time_completed,factionoc.time_executed,factionoc.participants,factionoc.money_gain,factionoc.respect_gain,factionoc.et from factionoc where factionoc.crime_id =? and factionoc.faction_id=? and factionoc.initiated=? order by time_completed desc""",(crime_type,f_id,1,))
        for row in c:
            db_queue.append(row)
        #
        if len(db_queue):
            # what should the name of the web page be?
            hist=oc_history_to_text.Crime_history()
            retlist = hist.crime2html(c, db_queue, pid2name, 0, 'faction', faction_dname, crime_type, weekno)
            got_page = retlist[0]
            if got_page:
                # time parameter to help see whether a page has changed since you last loaded it in the browser
                print('<li>', crime_type, '<a href="' + retlist[1] +  '?t=' + str(retlist[2]) + '">' +  db_queue[0][0] + '</a></li>', file=intro)
    print('</ul>', file=intro)
    

    print('<p/><hr>', file=intro)
    print("</body></html>", file=intro)
    intro.close()
    os.rename("/torntmp/index.html", "/srv/www/htdocs/intro/" + faction_web +  "/index.html") # XXX


###################################################################################################

#START

weekno=int(time.time()/604800)
conn = sqlite3.connect('/var/torn/torn_db')
c = conn.cursor()
conn.commit()

fnamepre=None
c.execute ("""select fnamepre from admin""")
for row in c:
    fnamepre=row[0]

f_todo = {}
f_ignore = {}
c.execute ("""select  faction_id,latest_basic,latest_oc,ignore,player_id  from factionwatch""")
for row in c:
        if (row[3]):
            f_ignore[row[0]] = 1
            continue
        if not row[0] in f_todo:
            f_todo[row[0]] = []
        f_todo[row[0]].append(row[4])

for f in f_ignore:
    if f in f_todo:
        del f_todo[f]

n_faction=0
for f in f_todo:
    prepare_faction_stats(f, fnamepre, weekno)
    n_faction += 1
print(n_faction, "factions processed")

conn.commit()
c.close()
