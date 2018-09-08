#!/usr/bin/python3

import hashlib
import hmac
import keep_files
import oc_cf_web
import oc_history_to_text
import os
import player_graphs
import sqlite3
import time


def seconds_text(s):
    if s < 180:
        return str(s) + 's'
    elif s < 7200:
        return str(int(s/60)) + 'm'
    else:
        return str(int(s/3600)) + 'h'


def prepare_player_stats(p_id, pid2name, page_time, show_debug, fnamepre, weekno, keeping_player, docroot, my_oc_cf, appleorange):
    blob = []
    old_player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + fnamepre + str(weekno-1), 'utf-8')).hexdigest()
    player_dname = hashlib.sha1(bytes('player-directory-for' + str(p_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    keeping_player.gotid(p_id)
    keeping_player.allow(old_player_dname)
    keeping_player.allow(player_dname)
    if show_debug:
        print("player data for ", p_id)
        print("use directory ", player_dname)

    # Get hmac details once (outside loops)
    hmac_key_f = open('/var/torn/hmac_key', 'r')
    hmac_key = bytes(hmac_key_f.read(),'utf-8')
    hmac_key_f.close()

    longdname = docroot + 'player/' + player_dname
    try:
        mtime = os.stat(longdname).st_mtime
    except:
        os.mkdir(longdname)

    # produce OC comparison for this player
    oc_cf_link = None
    if len(my_oc_cf):
        retlist = appleorange.web(c, my_oc_cf, pid2name, player_dname, p_id, weekno)
        if show_debug:
            print(retlist)
        got_page = retlist[0]
        if got_page:
            # time parameter to help see whether a page has changed since you last loaded it in the browser
            oc_cf_link = '<br/><a href="' + retlist[1] + '?t=' + str(retlist[2]) + '">OC comparison</a>'

    # produce OC list for this player
    linebreak = ''
    db_queue = []
    c.execute("""select factionoc.crime_name,factionoc.initiated,factionoc.success,factionoc.time_completed,factionoc.time_executed,factionoc.participants,factionoc.money_gain,factionoc.respect_gain,factionoc.et,factionoc.time_ready from factionoc,whodunnit where factionoc.oc_plan_id = whodunnit.oc_plan_id and  whodunnit.player_id = ? order by time_ready desc""", (p_id,))
    for row in c:
        db_queue.append(row)
    #
    if len(db_queue):
        # what should the name of the web page be?
        hist=oc_history_to_text.Crime_history(docroot)
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
    #
    if oc_cf_link:
        crimes_planned += oc_cf_link

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
    linebreak = ''
    for oc in sorted(crimes_done):
        r = oc + '=' + str(crimes_good[oc]) + '/' + str(crimes_done[oc])
        build_string = build_string + linebreak + r
        linebreak = '<br/>'
    col_ratio_answer = build_string

    # timeliness of stats data
    c.execute("""select et from namelevel where player_id = ?""", (p_id,))
    for row in c:
        level_time = page_time - row[0]
    c.execute("""select latest from playerwatch where player_id=?""", (p_id,))
    for row in c:
        crime_time = page_time - row[0]
    col6_answer = "level=" + seconds_text(level_time) + "<br/>crimes=" + seconds_text(crime_time)


#   PSTATS
    # XXX player stats may or may not be available - it needs that player's API key
    pstats ='jail ?<br/>bust ?<br/>failbust ?<br/>hosp ?<br/>OD ?'
    stat_num = None
    nerve_details = None
    drug_details = None
    # XXX This is inefficient - can't I just take the latest row?
    c.execute("""select et,xantaken from drugs where player_id=? order by et""", (p_id,))
    for row in c:
        drug_details = row
    # XXX This is inefficient - can't I just take the latest row?
    c.execute("""select et,cur_nerve,max_nerve from readiness where player_id=? order by et""", (p_id,))
    for row in c:
        nerve_details = row
    # XXX This is inefficient - can't I just take the latest row?
    c.execute("""select jailed,peoplebusted,failedbusts,hosp,od from pstats where player_id=? order by et""", (p_id,))
    for row in c:
        stat_num = row
    if stat_num:
        pstats = 'jail ' + str(stat_num[0]) + '<br/>bust ' + str(stat_num[1]) + '<br/>failbust ' + str(stat_num[2]) + '<br/>hosp ' + str(stat_num[3]) + '<br/>OD ' + str(stat_num[4])
    if nerve_details and nerve_details[2]:
        pstats = 'nerve ' + str(nerve_details[2]) + '<br/>' + pstats
    else:
        pstats = 'nerve ?<br/>' + pstats
    if drug_details and drug_details[1]:
        pstats = pstats + '<br/>xanax ' + str(drug_details[1])
    else:
        pstats = pstats + '<br/>xanax ?'

#   IDLE TIME
    c.execute("""select et,total from playercrimes where player_id=? order by et""", (p_id,))
    was, when, one_interval, longest_interval = 0, 0, 0, 0  # activity
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
    days_idle = int(longest_interval / 86400)
    if days_idle > 300:
        days_idle = 'many'
    else:
        days_idle = str(days_idle)

    # column of recenvy
    c.execute("""select et,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where  player_id = ? order by et""", (p_id,))
    crim_record = [-1 ,-1, -1, -1, -1, -1, -1, -1, -1]
    timestamp = [0, 0, 0, 0, 0, 0, 0, 0, 0]
    for row in c:
        new_crim_record=row[1:]
        for i in range (0,9):
            if (new_crim_record[i] > crim_record[i]) and (crim_record[i] > -1):
                timestamp[i] = row[0]
        crim_record=new_crim_record
    col4_answer = ''
    for rt in timestamp:
        if rt:
            col4_answer = col4_answer + "<div align='right'>" +  time.strftime("%Y-%m-%d", time.gmtime(rt)) + "</div><div align='right'>"
        else:
            col4_answer = col4_answer + "<div align='right'>?</div><div align='right'>"
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
    print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'></head><body>", file=pg_index)
    print("Player data for ", col1_answer[0], file=pg_index)
    #
    print("<table border='1'>", file=pg_index)
    print("<tr><th>Most days idle</br>(no crime)</th><th>OC success</th><th>event list</th></tr>", file=pg_index)
    print("<tr><td>", blob[4], "</td><td>", blob[1], "</td><td>", blob[0], "</td></tr>", file=pg_index)
    print("</table>", file=pg_index)

    # link to flash graph (parameters protected by HMAC)
    graph_selection = ( str(p_id) + 'crime' + str(int(time.time())) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, graph_selection, digestmod=hashlib.sha1).hexdigest()
    print('<br/><a href="/rhubarb/graph/' + str(graph_selection)[2:-1] + '-' +  hmac_hex + '">detailed crime graph</a>', file=pg_index)

    # picture file graphs
    graph_action=player_graphs.Draw_graph(docroot, c, weekno, player_dname)
    graph_urls = graph_action.player(pid2name, p_id)
    for gu in graph_urls:
        print('<br/><img src="' + gu + '" alt="timeseries graph">', file=pg_index)
    #
    print("</body></html>", file=pg_index)
    pg_index.close()
    player_index = hashlib.sha1(bytes('player-index' + str(p_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    os.rename("/torntmp/begin_graphs.html", docroot + "player/" + player_dname + "/" + player_index + ".html")
    col1_answer.append("/player/" + player_dname + "/" + player_index + ".html")

    blob.append(col1_answer)
    return blob

def prepare_faction_stats(f_id, fnamepre, weekno, keeping_faction, keeping_player, docroot):
    page_time = int(time.time())  # seconds
    print("faction data for ", f_id)

    all_oc_cf = []  # f_id, crime_id, oc_plan_a, oc_plan_b, player_a, player_b
    # Obtain the type of crime with a join as this is not in the compare table.
    c.execute("""select distinct compare.f_id,factionoc.crime_id,compare.oc_a,compare.oc_b,compare.player_a,compare.player_b from compare,factionoc where f_id=? and factionoc.oc_plan_id=compare.oc_a""", (f_id,))
    for row in c:
        if row[3] < row [2]:
            print("Crime order problem in compare ", row)
            continue
        all_oc_cf.append(row)

    pid2name = {}  # used while processing each player
    f_data = []
    c.execute("""select playerwatch.player_id,namelevel.name from playerwatch,namelevel where playerwatch.faction_id=? and playerwatch.player_id=namelevel.player_id""", (f_id,))
    player_todo = []
    for p in c:
        player_todo.append(p[0])
        pid2name[str(p[0])] = p[1]

    appleorange=oc_cf_web.Crime_compare(docroot)
    n_player=0
    for p in player_todo:
        show_debug = 0
        if n_player < 3:
            show_debug = 1
        my_oc_cf = []
        for pair in all_oc_cf:
            if int(pair[4]) == int(p):
                # coerce tuple into list
                notflipped = [pair[0], pair[1], pair[2], pair[3], pair[4], pair[5]]
                my_oc_cf.append(notflipped)
            elif pair[5] == p:
                flipped = [pair[0], pair[1], pair[3], pair[2], pair[5], pair[4]]
                my_oc_cf.append(flipped)
        f_data.append(prepare_player_stats(p, pid2name, page_time, show_debug, fnamepre, weekno, keeping_player, docroot, my_oc_cf, appleorange))
        n_player += 1
    print(n_player, "players processed")

    f_data = sorted(f_data, key=lambda one: one[-1][1])
    f_data = sorted(f_data, key=lambda one: one[-1][2], reverse=True)

    faction_name, faction_web = '?', None
    c.execute("""select f_name,f_web from factiondisplay where f_id=?""", (f_id,))
    for fdetails in c:
        faction_name,faction_web = fdetails

    c.execute("""select latest_oc from factionwatch where faction_id=?""", (f_id,))
    for tt in c:
        oc_time = page_time - tt[0]

    old_faction_dname = hashlib.sha1(bytes('faction_variable_dir' + str(f_id) + fnamepre + str(weekno-1), 'utf-8')).hexdigest()
    faction_dname = hashlib.sha1(bytes('faction_variable_dir' + str(f_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    keeping_faction.allow(old_faction_dname)
    keeping_faction.allow(faction_dname)

    web=open("/torntmp/player_table.html", "w")
    print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'></head><body><h2>Faction Player Table:", file=web)
    print(faction_name, f_id, file=web)
    print("</h2>", file=web)
    print("<br/>Page created at ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(page_time)), file=web)
    print("<br/>Faction organised crime data " + seconds_text(oc_time) + " old", file=web)
    print("<p>The first and last colums contain clickable links.<p/>", file=web)
    print("<p/>", file=web)

    print("<table border='1'>", file=web)
    print("<tr><th>Player</th><th>Crime</th><th>Number</th><th>Recency</th> <th>Most days idle</br>(no crime)</th><th>Stats<br/>(needs API key)</th><th>Age of data</th><th>OC success</th><th>event list</th></tr>", file=web)

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
    print("</body></html>", file=web)
    web.close()

    longdname= docroot + 'faction/' + faction_dname
    try:
        mtime = os.stat(longdname).st_mtime
    except:
        os.mkdir(longdname)
    faction_ptname = hashlib.sha1(bytes('faction_player_table' + str(f_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    os.rename("/torntmp/player_table.html", docroot + "faction/" + faction_dname + '/' + faction_ptname +  ".html")

    #  Organised crime counts
    poc = {} # player OC
    c.execute("""select playeroc.player_id,playeroc.oc_calc from playeroc,playerwatch where playerwatch.faction_id=? and  playerwatch.player_id=playeroc.player_id""", (f_id,))
    for whatocs in c:
        poc[str(whatocs[0])] = whatocs[1]
    oc_ordered = sorted(poc.keys(), key=lambda p: poc[p])
    #
    oc_tmp_page=open("/torntmp/oc_count.html", "w")
    print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'></head><body><h2>OC Count (award at 100)</h2>", file=oc_tmp_page)
    print("<ul>", file=oc_tmp_page)
    for p_id in oc_ordered:
        if p_id not in pid2name:
            continue
        print("<li>", poc[p_id], pid2name[p_id], "</li>", file=oc_tmp_page)
    print("</ul></body></html>", file=oc_tmp_page)
    oc_tmp_page.close()
    oc_counts = hashlib.sha1(bytes('oc_counts' + str(f_id) + fnamepre + str(weekno), 'utf-8')).hexdigest()
    os.rename("/torntmp/oc_count.html", docroot + "faction/" + faction_dname + '/' + oc_counts + ".html")

    crime_schedule=[]
    c.execute("""select distinct crime_id from factionoc where faction_id=? order by crime_id desc""", (f_id,))
    for row in c:
        crime_schedule.append(row[0])
    # Intro file
    if not docroot:
        print("HELP - docroot is not defined")
    if not faction_web:
        print("HELP - faction_web is not defined")
    introdir = docroot + 'intro/' + faction_web
    try:
        mtime = os.stat(introdir).st_mtime
    except:
        os.mkdir(introdir)
    intro=open("/torntmp/index.html", "w")
    print("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><link rel='stylesheet' type='text/css' href='/style.css' /></head><body><h2>Faction Intro Page: ", file=intro)
    print(faction_name, f_id, file=intro)
    print("</h2>", file=intro)
    print("<br/>Page created at ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(page_time)), file=intro)
    print('<p/><a href="/faction/' + faction_dname + '/' + faction_ptname + '.html' + '">Player Table</a>', file=intro)
    print('<p/><hr>', file=intro)
    print('<p/><a href="/faction/' +   faction_dname + '/'  + oc_counts +  '.html' + '">Organised Crime Counts</a>', file=intro)
    print('<p/><hr>', file=intro)

    print('<ul>', file=intro)
    for crime_type in  crime_schedule:
        db_queue = []
        c.execute("""select distinct factionoc.crime_name,factionoc.initiated,factionoc.success,factionoc.time_completed,factionoc.time_executed,factionoc.participants,factionoc.money_gain,factionoc.respect_gain,factionoc.et,factionoc.time_ready from factionoc where factionoc.crime_id =? and factionoc.faction_id=? and factionoc.initiated=? order by time_ready desc""",(crime_type,f_id,1,))
        for row in c:
            db_queue.append(row)
        #
        if len(db_queue):
            hist=oc_history_to_text.Crime_history(docroot)
            retlist = hist.crime2html(c, db_queue, pid2name, 0, 'faction', faction_dname, crime_type, weekno)
            got_page = retlist[0]
            if got_page:
                # time parameter to help see whether a page has changed since you last loaded it in the browser
                print('<div id="oc-type-' + str(crime_type) + '"><li>', crime_type, '<a href="' + retlist[1] +  '?t=' + str(retlist[2]) + '">' +  db_queue[0][0] + '</a></li></div>', file=intro)
    print('</ul>', file=intro)
    print('<p/><hr>', file=intro)


    store_for_analytics = {}
    c.execute("""select distinct oc_plan_id,crime_name,success,time_executed,participants,money_gain,respect_gain from factionoc where faction_id=? and initiated=?""",(f_id,1,))
    for row in c:
        store_for_analytics[row[0]] = row


    print('<p/><a href="/docs/">Site documentation</a>', file=intro)
    print('<p/><hr>', file=intro)
    print("</body></html>", file=intro)
    intro.close()
    os.rename("/torntmp/index.html", docroot + "intro/" + faction_web +  "/index.html")


###################################################################################################

#START

weekno = int(time.time()/604800)
conn = sqlite3.connect('file:/var/torn/torn_db?mode=ro', uri=True)
c = conn.cursor()
conn.commit()

fnamepre = None
c.execute("""select fnamepre from admin""")
for row in c:
    fnamepre = row[0]

# display does not use the factionwatch.ignore column
f_todo = {}
c.execute("""select  faction_id,latest_basic,latest_oc,ignore,player_id  from factionwatch""")
for row in c:
        if not row[0] in f_todo:
            f_todo[row[0]] = []
        f_todo[row[0]].append(row[4])

docroot = '/srv/www/htdocs/'
keep_this_faction_htdoc = keep_files.Keep(docroot + 'faction')
keep_this_player_htdoc = keep_files.Keep(docroot + 'player')
n_faction = 0
for f in f_todo:
    prepare_faction_stats(f, fnamepre, weekno, keep_this_faction_htdoc, keep_this_player_htdoc, docroot)
    n_faction += 1
print(n_faction, "factions processed")

watch = {}
c.execute("""select player_id,ignore,latest from playerwatch""")
for row in c:
    pid, ign, latest = row[0], row[1], row[2]
    if not ign:
        watch[pid] = latest

keep_this_faction_htdoc.exterminate()
keep_this_player_htdoc.exterminate()

p_already = keep_this_player_htdoc.showid()

conn.commit()
c.close()

# Do we need to delete old entries from playerwatch?
plan_deletion = False
for pid in watch.keys():
    if pid in p_already:
        continue
    plan_deletion = True
    break

if not plan_deletion:
    exit(0)

# will need read-write access

conn2 = sqlite3.connect('/var/torn/torn_db')
c2 = conn2.cursor()
conn2.commit()
for pid in watch.keys():
    if pid in p_already:
        continue
    c2.execute("""delete from playerwatch where player_id = ?""", (pid,))
conn2.commit()
c2.close()
