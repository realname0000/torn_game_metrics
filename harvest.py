#!/usr/bin/python3

import sqlite3
import time
import web_api
import dehtml
import oc_analytics
import re
import sys

t_start_finegrain = time.time()

player_crime_timestep = 43200
faction_basic_timestep = 43200
level_timestep = 86400

re_named = re.compile('^<a href = "http://www.torn.com/profiles.php.XID=(\d+)">([()\w-]+)</a> (\w+) <a href = "http://www.torn.com/profiles.php.XID=(\d+)">([()\w-]+)<.a>([\w, +().-]*)$')
re_someone = re.compile('^Someone (\w+) <a href = "http://www.torn.com/profiles.php.XID=(\d+)">([\w-]+)<.a>([\w, +().-]*)$')


def get_player(web, p_id):
    t = int(time.time())
    c.execute("""select latest,ignore from playerwatch where player_id=?""", (p_id,))
    for row in c:
        if row[0]+player_crime_timestep > t:
            return "TOO RECENT"
        if row[1]:
            return "IGNORE THIS PLAYER"
    result = web.torn('user', p_id, 'crimes')
    conn.commit()
    if 'OK' == result[0]:
        cx = result[1]['criminalrecord']
        player_id_api = result[2]
        c.execute("""insert into playercrimes values (?,?,?,?, ?,?,?,?, ?,?,?,?)""",
            (t, player_id_api, p_id, cx['selling_illegal_products'], cx['theft'], cx['auto_theft'], cx['drug_deals'], cx['computer_crimes'], cx['murder'], cx['fraud_crimes'], cx['other'], cx['total'],))
        c.execute("""update playerwatch set latest=? where player_id=?""", (t, p_id,))
        conn.commit()
    else:
        return "FAIL to get crimes"
    result = web.torn('user', p_id, 'personalstats')
    conn.commit()
    if 'OK' == result[0]:
        ps = result[1]['personalstats']
        player_id_api = result[2]
        c.execute("""insert into pstats values (?,?,?, ?,?,?, ?,?,?)""", (t, player_id_api, p_id,  ps['jailed'], ps['peoplebusted'], ps['failedbusts'], ps['hospital'], ps['overdosed'], ps['organisedcrimes'],))
        conn.commit()
        # and drugs XXX some of these may be missing
        if 'cantaken' not in ps:
            ps['cantaken'] = 0
        if 'exttaken' not in ps:
            ps['exttaken'] = 0
        if 'lsdtaken' not in ps:
            ps['lsdtaken'] = 0
        if 'opitaken' not in ps:
            ps['opitaken'] = 0
        if 'shrtaken' not in ps:
            ps['shrtaken'] = 0
        if 'pcptaken' not in ps:
            ps['pcptaken'] = 0
        if 'xantaken' not in ps:
            ps['xantaken'] = 0
        if 'victaken' not in ps:
            ps['victaken'] = 0
        if 'spetaken' not in ps:
            ps['spetaken'] = 0
        if 'kettaken' not in ps:
            ps['kettaken'] = 0
        c.execute("""insert into drugs values (?,?,?, ?,?,?, ?,?,?, ?,?,?)""", (t, p_id,  ps['cantaken'], ps['exttaken'], ps['lsdtaken'], ps['opitaken'], ps['shrtaken'], ps['pcptaken'], ps['xantaken'], ps['victaken'], ps['spetaken'], ps['kettaken'],))
        c.execute("""update playerwatch set latest=? where player_id=?""", (t, p_id,))
        conn.commit()
    else:
        return "FAIL to get personalstats"
    get_readiness(web, p_id, 86400)
    return "OK"


def get_faction(web, f_id, oc_interval):
    t = int(time.time())
    c.execute("""select latest_basic,latest_oc,ignore from factionwatch where faction_id=?""",(f_id,))
    for row in c:
        latest_basic=row[0]
        latest_oc=row[1]
        ignore=row[2]
    if ignore:
        return "IGNORE THIS FACTION"
    if latest_basic+faction_basic_timestep < t:
        print("plan to query faction ", repr(f_id), "for BASIC")
        result = web.torn('faction', f_id, 'basic')
        conn.commit()
        if 'OK' == result[0]:
            respect=result[1]['respect']
            api_id_used = result[2]
            c.execute("""insert into factionrespect values(?,?,?,?)""", (t, api_id_used, f_id,respect,))
            lead=result[1]['leader']
            if lead:
                c.execute("""update factiondisplay set leader_id=? where f_id=?""", (lead,f_id,))
            colead=result[1]['co-leader']
            if colead:
                c.execute("""update factiondisplay set coleader_id=? where f_id=?""", (colead,f_id,))
            #
            members=result[1]['members']
            # Because I have not figured out "insert if not exists", "on conflict" kind of thing
            player_faction_already = {}
            c.execute("""SELECT player_id,faction_id FROM playerwatch""")
            for row in c:
                player_faction_already[str(row[0])] = row[1]  # needs string key to compare player_faction_already to members
            for m in members:
                if m in player_faction_already:
                    if player_faction_already[m] != f_id:
                        c.execute("""update playerwatch set faction_id=? where player_id=?""", (f_id, m,))
                else:
                    print("Inserting player", m, "into faction", f_id)
                    c.execute("""insert into playerwatch values (?, ?,?, ?, ?)""", (t, 0, 0, f_id, m,))
            conn.commit()
            # exclude non-members
            for m in members:
                if m in player_faction_already:
                    del player_faction_already[m]
            for other_players in player_faction_already:
                if player_faction_already[other_players] == f_id:
                    c.execute("""update playerwatch set faction_id=? where player_id=?""", (-1, other_players,))
            c.execute("""update factionwatch set latest_basic=? where faction_id=?""", (t, f_id,))
            conn.commit()
            # and check faction name
            table_has=None
            faction_name=result[1]['name']
            c.execute("""SELECT f_name FROM factiondisplay where f_id=?""",(f_id,))
            for row in c:
                table_has=row[0]
            if not table_has:
                c.execute("""insert into factiondisplay values(?,?, ?,?)""", (t, f_id, faction_name, None))
            if table_has != faction_name:
                c.execute("""update factiondisplay set f_name=? where f_id=?""", (faction_name, f_id,))
                c.execute("""update factiondisplay set et=? where f_id=?""", (t, f_id,))
            conn.commit()
        else:
            print("Problem discovering faction basic? ", result)

    if latest_oc+oc_interval < t:
        print("plan to query faction ", repr(f_id), "for CRIMES")
        # Now do faction crimes - OC
        result = web.torn('faction', f_id, 'crimes')
        conn.commit()
        if 'OK' == result[0]:
            #
            oc=result[1]['crimes']
            for oc_api_id in oc:
                print("OC from api is", oc_api_id, oc[oc_api_id]['crime_name'], oc[oc_api_id]['initiated'])
            #
            player_id_api = result[2]
            c.execute("""SELECT oc_plan_id,time_started,initiated,participants FROM factionoc where faction_id=?""", (f_id,))
            oc_plan_already = {}
            for row in c:
                oc_plan_already[str(row[0])] = row  # needs string key
            analytics = oc_analytics.Compare(c, f_id)
            for crimeplan in oc:
                if crimeplan in oc_plan_already:
                    if  oc[crimeplan]['time_started'] != oc_plan_already[crimeplan][1]:
                        print("CONFUSION OVER OC DETAILS")
                    if  oc[crimeplan]['initiated'] != oc_plan_already[crimeplan][2]:
                        c.execute("""update factionoc set initiated=? where faction_id=? and oc_plan_id=?""", (oc[crimeplan]['initiated'], f_id, crimeplan,))
                        c.execute("""update factionoc set success=? where faction_id=? and oc_plan_id=?""", (oc[crimeplan]['success'], f_id, crimeplan,))
                        c.execute("""update factionoc set money_gain=? where faction_id=? and oc_plan_id=?""", (oc[crimeplan]['money_gain'], f_id, crimeplan,))
                        c.execute("""update factionoc set respect_gain=? where faction_id=? and oc_plan_id=?""", (oc[crimeplan]['respect_gain'], f_id, crimeplan,))
                        c.execute("""update factionoc set time_executed=? where faction_id=? and oc_plan_id=?""", (int(time.time()), f_id, crimeplan,))
                        c.execute("""update factionoc set time_completed=? where faction_id=? and oc_plan_id=?""", (int(oc[crimeplan]['time_completed']), f_id, crimeplan,))
                        c.execute("""update factionoc set et=? where faction_id=? and oc_plan_id=?""", (t, f_id, crimeplan,))
                        participants = oc_plan_already[crimeplan][3]
                        players = participants.split(',')
                        analytics.ingest(f_id, crimeplan, oc[crimeplan]['crime_id'], players)
                        # counting OC success by each player
                        if oc[crimeplan]['success']:
                            for pu in players:
                                c.execute("""update playeroc set oc_calc=oc_calc+1 where player_id=?""", (pu,))
                        print("Recording outcome of OC ", crimeplan, " success is", oc[crimeplan]['success'])
                else:
                    cx = oc[crimeplan]
                    # change from a structure into a string
                    part = ','.join(cx["participants"].keys())
                    c.execute("""insert into factionoc values (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?,?)""",
                    (t, player_id_api, f_id, crimeplan,
                     cx["crime_id"], cx["crime_name"], part, cx["time_started"], cx["time_completed"],
                     cx["initiated"], cx["success"], cx["money_gain"], cx["respect_gain"], 0, cx["time_ready"],0,0,))
                    print("Storing new OC ", crimeplan)
            #
            c.execute("""update factionwatch set latest_oc=? where faction_id=?""", (t, f_id,))
            analytics.examine()
            conn.commit()
        else:
            print("Problem discovering faction crimes?  ", result)

    # no time requirement for attacknews - read it every time
    attack_already_logged = {}
    c.execute("""select evid from combat_events where fid=?""", (f_id,))
    for row in c:
        attack_already_logged[str(row[0])] = 1
    #
    total_att_counted = 0
    for qtype in ('attacknews', 'attacknewsfull'):
        print("plan to query faction ", repr(f_id), "for attacks", qtype)
        result = web.torn('faction', f_id, qtype)
        conn.commit()
        if 'OK' != result[0]:
            print("API call for", qtype, "returned", result[0])
            continue
        events = result[1]['attacknews']
        att_counted = 0
        for ev in events:
            if ev in attack_already_logged:
                continue # skip an event we already have
            news = events[ev]['news']
            parts_n = re_named.match(news)
            parts_s = re_someone.match(news)
            if parts_n:
                att_id   = parts_n.group(1)
                att_name = parts_n.group(2)
                verb     = parts_n.group(3)
                def_id   = parts_n.group(4)
                def_name = parts_n.group(5)
                outcome  = parts_n.group(6)
                frog=dehtml.Dehtml()
                clean_outcome = frog.html_clean(outcome)
                c.execute("""insert into combat_events values (?,?,?, ?,?,?, ?,?,?)""", (f_id, ev, events[ev]['timestamp'], att_name, att_id, verb, def_name, def_id, clean_outcome,))
                att_counted += 1
                attack_already_logged[ev] = 1
            elif parts_s:
                verb     = parts_s.group(1)
                def_id   = parts_s.group(2)
                def_name = parts_s.group(3)
                outcome  = parts_s.group(4)
                frog=dehtml.Dehtml()
                clean_outcome = frog.html_clean(outcome)
                c.execute("""insert into combat_events values (?,?,?, ?,?,?, ?,?,?)""", (f_id, ev, events[ev]['timestamp'], 'Someone', 0, verb, def_name, def_id, clean_outcome,))
                att_counted += 1
                attack_already_logged[ev] = 1
            else:
                print("NOT UNDERSTOOD:", news, file=sys.stderr)
        conn.commit()
        total_att_counted += att_counted
        if att_counted < 99:
            break # do not continue from attacknews to attacknewsfull

    print("Number of attacks inserted is", total_att_counted)
    return "OK"  # XXX TBC

    #
    #XXX TODO
    print("plan to query faction for STATS")
    return "OK"
    # write to db
    conn.commit()


def expire_old_data():
    now = int(time.time())
    day_ago = now - 86400
    c.execute("""select last_expire from admin""",)
    for when in c:
        if when[0] > day_ago:
            return
    weeks_ago = now - (86400 * 28)
    c.execute("""delete from combat_events where et<?""", (weeks_ago,))
    year_ago = now - (86400 * 365)
    c.execute("""delete from playercrimes where et<?""", (year_ago,))
    c.execute("""delete from readiness where et<?""", (year_ago,))
    c.execute("""delete from pstats where et<?""", (year_ago,))
    c.execute("""delete from drugs where et<?""", (year_ago,))
    c.execute("""delete from factionrespect where et<?""", (year_ago,))
    # These next ones are more complicated because of foreign keys.
    c.execute("""select oc_plan_id from factionoc where et<?""", (year_ago,))
    oc_to_del = []
    for row in c:
        print("Deleting oc ", row[0])
        oc_to_del.append(row[0])
    for oc in oc_to_del:
        c.execute("""delete from whodunnit where oc_plan_id=?""", (oc,))
        c.execute("""delete from compare where oc_a=?""", (oc,))
        c.execute("""delete from compare where oc_b=?""", (oc,))
        c.execute("""delete from factionoc where oc_plan_id=?""", (oc,))
    c.execute("""update admin set last_expire = ?""", (now,))
    conn.commit()
    # old entries from payment_percent
    factions = []
    c.execute("""select distinct faction_id from payment_percent""")
    for row in c:
        factions.append(row[0])
    #
    for fid in factions:
        cn_todo = {}
        c.execute("""select count(1),crime_id from payment_percent where faction_id=? group by crime_id""",(fid,))
        for row in c:
            if row[0] > 1:
                cn_todo[row[1]] =1
        for cn in cn_todo.keys():
            c.execute("""select et,faction_id,crime_id from payment_percent where faction_id=? and crime_id=? order by et limit 1""",(fid,cn,))
            ee,ff,cc = None,None,None
            for row in c:
                ee,ff,cc = row
            c.execute("""delete from payment_percent where et=? and faction_id=? and crime_id=?""",(ee,ff,cc,))
    conn.commit()
    # continue using that factions list
    # zero entries from payment_percent
    for fid in factions:
        cn_percent = {}
        cn_count = {}
        c.execute("""select percent,crime_id from payment_percent where faction_id=?""",(fid,))
        for row in c:
            pc, cn = row
            if cn in cn_count:
                cn_count[cn] += 1
            else:
                cn_count[cn] = 1
            cn_percent[cn] = pc
        for cn in cn_percent.keys():
            if (0 == cn_percent[cn]) and (1 == cn_count[cn]):
                c.execute("""delete from payment_percent where faction_id=? and crime_id=?""",(fid,cn,))
    conn.commit()
    c.execute("""vacuum""")

def clean_data():
    now = int(time.time())
    day_ago = now - 86400
    c.execute("""select last_clean from admin""",)
    for when in c:
        if when[0] > day_ago:
            return

    #  remove duplication if present in factionwatch
    for ignore in [0, 1]:
        faction = {}
        need_to_clean = 0
        c.execute("""select faction_id,player_id from factionwatch WHERE ignore=?""", (ignore,))
        for row in c:
            faction_id, player_id = row
            if faction_id in faction:
                # seeing a faction again
                if player_id in faction[faction_id]:
                    faction[faction_id][player_id].append(row)
                    need_to_clean = 1
                else:
                    faction[faction_id][player_id] = [row]
            else:
                # store data on a faction the first time we see it
                faction[faction_id] = {player_id:[row]}
        c.execute("""update admin set last_clean = ?""", (now,))
        for f in faction:
            for p in faction[f]:
                list_length = len(faction[f][p])
                if list_length > 1:
                    # replace multiple rows with one chosen row
                    et=1234
                    latest_basic = 99
                    latest_oc = 99
                    for x in faction[f][p]:
                        if x[0] > et:
                            et = x[0]
                            latest_basic = x[1]
                            latest_oc = x[2]
                    c.execute("""delete from factionwatch WHERE ignore=? and faction_id=? and player_id=?""", (ignore, f, p,))
                    c.execute("""insert into factionwatch values (?, ?,?,?, ?, ?)""", (et, latest_basic, latest_oc, ignore, f, p,))
                    conn.commit()

def refresh_namelevel(web):
    # Get player names and levels
    et = int(time.time())
    player_level_already = {}
    player_level_todo = {}
    player_watched = {}
    c.execute("""SELECT et,player_id FROM namelevel""")
    for row in c:
        player_level_already[str(row[1])] = row[0]
    #
    c.execute("""SELECT player_id FROM playerwatch where ignore=?""",(0,))
    for row in c:
        player_watched[str(row[0])] = 1
    #
    for m in player_watched:
        if m in player_level_already:
            if (player_level_already[m] + level_timestep) < et:
                player_level_todo[m] = 1
        else:
            player_level_todo[m] = 1
    #
    for m in player_level_todo:
        result = web.torn('user', m, 'basic')
        conn.commit()
        if 'OK' == result[0]:
            level = result[1]['level']
            name = result[1]['name']
        else:
            return "Fail"
        if m in player_level_already:
            c.execute("""update namelevel set name=? where player_id=?""", (name, m,))
            c.execute("""update namelevel set level=? where player_id=?""", (level, m,))
            c.execute("""update namelevel set et=? where player_id=?""", (et, m,))
        else:
            c.execute("""insert or ignore into namelevel values (?, ?, ?, ?)""", (et, name, level, m,))
        conn.commit()


def get_readiness(web, p_id, interval):
    # readiiness for OC
    #
    # test for how recent a result we already have
    et = int (time.time())
    t_already = 0
    c.execute("""select max(et) from readiness  where player_id=?""", (p_id,))
    for row in c:
        if row[0]:
            t_already = row[0]
    if interval < 300:
        interval = 300
    if (t_already + interval > et):
        return "TOO RECENT"
    #
    cur_nerve, max_nerve, status_0, status_1=0, 0, '?', '?'
    result = web.torn('user', p_id, 'profile')
    conn.commit()
    if 'OK' == result[0]:
        q1_data = result[1]
        if type(q1_data) == type('a_string'):
            printf("Readiness: unexpected string value", q1_data)
            return "Fail"
        frog=dehtml.Dehtml()
        q1_data['status'][0] = frog.html_clean(q1_data['status'][0])
        q1_data['status'][1] = frog.html_clean(q1_data['status'][1])
    else:
        return "Fail"
    # and find nerve if possible
    result = web.torn('user', p_id, 'bars')
    conn.commit()
    if 'OK' == result[0]:
        cur_nerve = result[1]['nerve']['current']
        max_nerve = result[1]['nerve']['maximum']
    #
    c.execute("""insert into readiness values (?, ?, ?, ?, ?, ?)""", (et, p_id, cur_nerve, max_nerve, q1_data['status'][0], q1_data['status'][1],))
    conn.commit()


def oc_count_per_player():
    week_ago = time.time() - 604800
    pstat_oc = {}
    c.execute("""select player_id,oc_read from pstats where et > ? order by et""", (week_ago,))
    for row in c:
        pstat_oc[str(row[0])] = row[1]
    #
    calc_oc = {}
    c.execute("""select player_id,oc_calc from playeroc""")
    for row in c:
        calc_oc[str(row[0])] = row[1]
    #
    for p in pstat_oc.keys():
        if p in calc_oc:
            c.execute("""update playeroc set oc_calc=? where player_id=?""", (pstat_oc[p],p,))
        else:
            c.execute("""insert into playeroc values(?,?)""", (p, pstat_oc[p],))
            calc_oc[str(p)] = pstat_oc[p]
    #
    # all other players in playerwatch need to get inserted too
    need2insert = {}
    c.execute("""select player_id from playerwatch""",)
    for row in c:
        if not str(row[0]) in calc_oc:
            need2insert[row[0]] = 1
    for p in need2insert.keys():
        numcrimes = 1
        c.execute("""select count(factionoc.crime_name) from factionoc,whodunnit where factionoc.oc_plan_id = whodunnit.oc_plan_id and  whodunnit.player_id = ? and factionoc.initiated = 1 and factionoc.success = 1""", (p,))
        for row in c:
            numcrimes = row[0]
        c.execute("""insert into playeroc values(?,?)""", (p, numcrimes,))


###################################################################################################

# START

conn = sqlite3.connect('/var/torn/torn_db')
c = conn.cursor()
conn.commit()

f_todo = {}
f_ignore = {}
c.execute("""select faction_id,ignore,player_id from factionwatch""")
for row in c:
    faction_id, ignore,player_id = row
    if ignore:
        f_ignore[faction_id] = 1
        continue
    if faction_id not in f_todo:
        f_todo[faction_id] = []
    f_todo[faction_id].append(player_id)

for f in f_ignore:
    if f in f_todo:
        del f_todo[f]

web=web_api.Tornapi(c) # use this one object throughout

# detect OC that are ready or nearly ready
near = 3600 + int(time.time())
for f in f_todo:
    all_gang = {}
    oc_soon = []
    c.execute("""select oc_plan_id from factionoc where initiated=0 and faction_id=? and time_ready<?""", (f, near,))
    for row in c:
        oc_soon.append(row[0])
    if len(oc_soon):
        # OC due - look more closely at the OC data
        for plan in oc_soon:
            this_gang = {}
            c.execute("""select player_id from whodunnit where oc_plan_id==? and faction_id=?""", (plan, f,))
            for row in c:
                all_gang[row[0]]=1
                this_gang[row[0]]=1
            c.execute("""select crime_name from factionoc where oc_plan_id==? and faction_id=?""", (plan, f,))
            for row in c:
                crime_name = row[0]
            print("Interest in OC for", f, "a plan is", plan, crime_name, "by", sorted(this_gang.keys()))
        rc=get_faction(web, f, 900)  # get from API the faction data (except where recent data is already known or ignored flag is set)
    else:
        rc=get_faction(web, f, 7200)  # get from API the faction data (except where recent data is already known or ignored flag is set)
    for player in all_gang:
        get_readiness(web, player, 300)
    if 'OK' != rc:
        print("return from get_faction(", web, f, ") is ", rc)
    # if rc was OK should remove from f_todo and avoid possible duplication

# Put crimes in whodunnit if not there already
now = int(time.time())
for f in f_todo:
    maybe_double_booked = []
    crimes = {}
    whodunnit = {}
    c.execute("""select oc_plan_id,participants from factionoc where faction_id=?""", (f,))
    for row in c:
        crimes[row[0]] = row[1]
    c.execute("""select distinct oc_plan_id from whodunnit where faction_id=?""", (f,))
    for row in c:
        plan_id = row[0]
        if plan_id in crimes:
            del crimes[plan_id]
    for plan_id in crimes:
        players = crimes[plan_id].split(',')
        for who in players:
            # Will check player is not in an earlier OC (now invalid).
            maybe_double_booked.append(who)
        #
        for who in players:
            c.execute("""insert into whodunnit values (?,?,?,?)""", (now, who, f, plan_id,))
    conn.commit()
    # crime cancellation considered
    for who in maybe_double_booked:
        c.execute("""select whodunnit.oc_plan_id,factionoc.time_ready from whodunnit,factionoc where whodunnit.faction_id=? and whodunnit.player_id=? and factionoc.initiated=? and  whodunnit.oc_plan_id=factionoc.oc_plan_id order by factionoc.time_started desc""",
            (f, who, 0,))
        crime_bookings = []  # for one player
        crime_due_at = {}
        for row in c:
            crime_bookings.append(row[0])
            crime_due_at[row[0]] = row[1]
        if len(crime_bookings) > 1:
            crime_bookings = crime_bookings[1:]
            for oc_multi in crime_bookings:
                if crime_due_at[oc_multi] > int(t_start_finegrain):
                    print("Future crime ", oc_multi, " cancelled - deleting from factionoc")
                    c.execute("""delete from factionoc where oc_plan_id=?""", (oc_multi,))
                else:
                    print("Crime ", oc_multi, " set as initiated/failed in factionoc (although it might have been deleted)")
                    c.execute("""update factionoc set initiated=1 where oc_plan_id=?""", (oc_multi,))
    conn.commit()


p_todo = {}
c.execute("""select player_id from playerwatch""")
for row in c:
    p_todo[row[0]] = 1

for p in p_todo:
    rc = get_player(web, p)
    if rc == "TOO RECENT":
        continue
    print("return from get_player(" + str(p) + ") is ", rc)
    time.sleep(2)

oc_count_per_player()
refresh_namelevel(web)
clean_data()
expire_old_data()

conn.commit()
c.close()
web.apistats()
t_end_finegrain = time.time()
print("Time taken is ", t_end_finegrain - t_start_finegrain)
print("Finished OK")
