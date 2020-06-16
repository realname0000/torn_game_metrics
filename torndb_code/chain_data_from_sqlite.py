#!/usr/bin/python3

# Read chain data from sqlite and crunch it into
# pg tables useful do display in the app.

import psycopg2
import sqlite3
import time
import re

now = int(time.time())
re.numeric_respect = re.compile('^ *\(\+([0-9,]+\.?[0-9]*)\) *$')

# ===================
# # open sqlite and read all chains from recent time

conn2 = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
c2 = conn2.cursor()
conn2.commit()

chains_from_sqlite = []
c2.execute("""select f_id,et,current,tstart,tend,cid,respect,cooldown from chain where et > ?""", (now-86400000,))
for row in c2:
    chains_from_sqlite.append(row)

print("CH from sqlite (early)", chains_from_sqlite)

# e.g.
# (11581, 1589236500, 13, 1589236455, 1589237170, 11010288)
# (11581, 1589276062, 10002, 1588243813, 1588390375, 10795189)
# (11581, 1589276062, 10000, 1587967218, 1588143795, 10734216)

# ===================
# update postresql

try:
    connect_str = "dbname='torndb_dev' user='devusr' host='localhost' " + \
                  "password='PPPPPP'"
    # use our connection values to establish a connection
    conn = psycopg2.connect(connect_str)
    # create a psycopg2 cursor that can execute queries
    c_pg = conn.cursor()
except Exception as e:
    print("Uh oh, can't connect. Invalid dbname, user or password?")
    print(e)
    exit(1)

# ===================

for rep in [1]:
    chains_from_pg_by_fid = {}
    c_pg.execute("""select f_id,tstart,pg_chain_id,et,chain_len,tend,torn_chain_id,respect from chains""")
    rows = c_pg.fetchall()
    for r in rows:
        f_id = r[0]
        tstart = r[1]
        if not f_id in chains_from_pg_by_fid:
            chains_from_pg_by_fid[f_id] = {}
        chains_from_pg_by_fid[f_id][tstart] = r[:]
    print("chains_from_pg_by_fid", chains_from_pg_by_fid)
    
    # process each chain
    for ch in chains_from_sqlite:
        print("CH from sqlite", ch)
        f_id, et, chain_len, tstart, sq_tend = ch[:5]
        if sq_tend and (et > sq_tend):
            et = sq_tend; # avoid calculating past the end of the chain
        # is this already in pg?
        if (f_id in chains_from_pg_by_fid) and (tstart in chains_from_pg_by_fid[f_id]):
            # is this up to date in pg?   (et and tend and cid all match)
            c_pg.execute("""select pg_chain_id,torn_chain_id,et,tend from chains where f_id=%s and tstart=%s""", (f_id, tstart,))
            rows = c_pg.fetchall()
            pg_chain_id, torn_chain_id, pg_et, tend = -1,-1,-1,-1
            for r in rows:
                pg_chain_id, torn_chain_id, pg_et, tend = r
                print("existing ID is", pg_chain_id, f_id, tstart)
                print("Compare chain id", torn_chain_id, ch[5])
                print("Compare time", et, pg_et)
                print("Compare time end", tend, ch[4])
            #
            # XXX bug in this stage - updates data after there is no need
            if (pg_chain_id) and (torn_chain_id==ch[5]) and (et) and (pg_et) and (tend==ch[4]) and (tend):
                print("Treating as finished - no work here", pg_chain_id)
            elif (pg_et >= et):
                print("Treating as up to date - no work here", pg_chain_id)
            else:
                print("PLAN TO update", pg_chain_id)
                print("updating row", pg_chain_id)
                c_pg.execute("""update chains set et=%s where pg_chain_id=%s""", (ch[1], pg_chain_id,))
                c_pg.execute("""update chains set chain_len=%s where pg_chain_id=%s""", (ch[2], pg_chain_id,))
                c_pg.execute("""update chains set tend=%s where pg_chain_id=%s""", (ch[4], pg_chain_id,))
                c_pg.execute("""update chains set torn_chain_id=%s where pg_chain_id=%s""", (ch[5], pg_chain_id,))
                c_pg.execute("""update chains set respect=%s where pg_chain_id=%s""", (ch[6], pg_chain_id,))
                #  fetch combat_events
                t_comb_1 = pg_et
                t_comb_2 = tend if tend else et
                c2.execute("""select fid,evid,et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where et >= ? and et <= ? and fid = ?""", (t_comb_1, t_comb_2, f_id,))
                for row in c2:
                    # strip leading/trailing whitespace from outcome text
                    edit_row = list(row)
                    edit_row[8] = edit_row[8].rstrip(' ')
                    edit_row[8] = edit_row[8].lstrip(' ')
                    # insert or ignore = UPSERT
                    c_pg.execute("""insert into combat_events values(%s,%s,%s, %s,%s,%s, %s,%s,%s) ON CONFLICT DO NOTHING""", tuple(edit_row))
                    re_respect = re.numeric_respect.match(row[8])
                    if re_respect:
                        number_string = re_respect.group(1)
                        number_string = number_string.replace(',', '')
                        resp = float(number_string)
                        if resp > 100:
                            bonus_detected = edit_row[2:9]
                            bonus_detected.append(pg_chain_id)
                            bonus_detected.append(resp)
                            c_pg.execute("""insert into bonus_events(et,att_name,att_id,verb,def_name,def_id,outcome,pg_chain_id,num_respect) values(%s,%s,%s, %s,%s,%s, %s,%s,%s)""", tuple(bonus_detected))
                    else:
                        resp = 0.0
                    c_pg.execute("""insert into combat_respect(evid,respect) values(%s,%s) ON CONFLICT DO NOTHING""", (row[1],resp,))
                #
                # make/remake the summary: start with empty dictionary to hold results
                sum_player= {}
                t_comb_1 = tstart # whole chain, not just the new part as above
                empty = { 'actions':0, 'attacked':0, 'hospitalized':0, 'mugged':0,   'respect':0,   'att_stale':0, 'lost':0, 'att_escape':0,   'def_stale':0, 'defend':0, 'def_escape':0 }
                c_pg.execute("""select player_id,player_name from chain_members where pg_chain_id = %s""", (pg_chain_id,))
                rows = c_pg.fetchall()
                for row in rows:
                    sum_player[row[0]] = empty.copy()
                #
                c_pg.execute("""select att_id,verb,count(att_id) from combat_events where f_id=%s and outcome like %s and et>=%s and et<=%s group by att_id,verb""", (f_id, '%(+%', t_comb_1, t_comb_2,) )
                rows = c_pg.fetchall()
                for row in rows:
                    our_att_id = row[0]
                    verb = row[1]
                    count = row[2]
                    if our_att_id in sum_player.keys():
                        sum_player[our_att_id][verb] = count
                # discover defends
                c_pg.execute("""select def_id,count(def_id) from combat_events where f_id=%s and outcome like %s and et>=%s and et<=%s group by def_id""", (f_id, '%but lost', t_comb_1, t_comb_2,) )
                rows = c_pg.fetchall()
                for row in rows:
                    our_def_id = row[0]
                    count = row[1]
                    if our_def_id in sum_player.keys():
                        sum_player[our_def_id]['defend'] = count
                # and escaped
                c_pg.execute("""select att_id,count(att_id) from combat_events where f_id=%s and outcome like %s and et>=%s and et<=%s group by att_id""", (f_id, '%and escaped', t_comb_1, t_comb_2,) )
                rows = c_pg.fetchall()
                for row in rows:
                    our_att_id = row[0]
                    count = row[1]
                    if our_att_id in sum_player.keys():
                        sum_player[our_att_id]['att_escape'] = count
                # but lost
                c_pg.execute("""select att_id,count(att_id) from combat_events where f_id=%s and outcome like %s and et>=%s and et<=%s group by att_id""", (f_id, '%but lost', t_comb_1, t_comb_2,) )
                rows = c_pg.fetchall()
                for row in rows:
                    our_att_id = row[0]
                    count = row[1]
                    if our_att_id in sum_player.keys():
                        sum_player[our_att_id]['lost'] = count
                #
                c_pg.execute("""select att_id,count(att_id) from combat_events where f_id=%s and outcome like %s and et>=%s and et<=%s group by att_id""", (f_id, '%and stalemated', t_comb_1, t_comb_2,) )
                rows = c_pg.fetchall()
                for row in rows:
                    our_att_id = row[0]
                    count = row[1]
                    if our_att_id in sum_player.keys():
                        sum_player[our_att_id]['att_stale'] = count
                # note:   ignoring any of   'but timed out'

                incomplete_respect_per_chain = 0
                for p_id in sum_player:
                    # sum of respect per player for this chain
                    c_pg.execute("""select sum(combat_respect.respect) from combat_events,combat_respect where f_id=%s and att_id=%s and et>=%s and et<=%s and combat_events.evid=combat_respect.evid""", (f_id, p_id, t_comb_1, t_comb_2,) )
                    rows = c_pg.fetchall()
                    for row in rows:
                        if row[0]:
                            sum_player[p_id]['respect'] = row[0]
                    incomplete_respect_per_chain += sum_player[p_id]['respect']
                    sum_player[p_id]['actions'] = sum_player[p_id]['attacked'] + sum_player[p_id]['hospitalized'] + sum_player[p_id]['mugged'] + sum_player[p_id]['lost'] + sum_player[p_id]['att_stale'] + sum_player[p_id]['att_escape']
                    #
                    print("Player Summary", p_id, sum_player[p_id])
                    # Needs to insert first time and update at later times or delete and insert to get that effect.
                    player_already_present = False
                    c_pg.execute("""select player_id from chain_player_sum where pg_chain_id=%s and player_id=%s""", (pg_chain_id, p_id,) )
                    rows = c_pg.fetchall()
                    for row in rows:
                        player_already_present = True
                    #
                    if player_already_present:
                        # Update
                        print("updating chain_player_sum for player", p_id, pg_chain_id)
                        c_pg.execute("""update chain_player_sum set actions=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['actions'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set attacked=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['attacked'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set hospitalized=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['hospitalized'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set mugged=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['mugged'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set respect=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['respect'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set att_stale=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['att_stale'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set lost=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['lost'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set att_escape=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['att_escape'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set def_stale=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['def_stale'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set defend=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['defend'], pg_chain_id,  p_id,) )
                        c_pg.execute("""update chain_player_sum set def_escape=%s where pg_chain_id=%s and player_id=%s""", (sum_player[p_id]['def_escape'], pg_chain_id,  p_id,) )
                    else:
                        # Insert
                        print("inserting chain_player_sum player", p_id)
                        c_pg.execute("""insert into chain_player_sum(pg_chain_id,player_id,actions,attacked,hospitalized,mugged,respect,att_stale,lost,att_escape,def_stale,defend,def_escape)"""
                                 """ values(%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s)""",
                                 (pg_chain_id,  p_id,
                                  sum_player[p_id]['actions'],
                                  sum_player[p_id]['attacked'],
                                  sum_player[p_id]['hospitalized'],
                                  sum_player[p_id]['mugged'],
                                  sum_player[p_id]['respect'],
                                  sum_player[p_id]['att_stale'],
                                  sum_player[p_id]['lost'],
                                  sum_player[p_id]['att_escape'],
                                  sum_player[p_id]['def_stale'],
                                  sum_player[p_id]['defend'],
                                  sum_player[p_id]['def_escape'],) ) 
                #
                c_pg.execute("""update chains set respect=%s where pg_chain_id=%s""", (incomplete_respect_per_chain, pg_chain_id,))
                c_pg.execute("""insert into chain_respect_history(pg_chain_id,seconds_rel,respect_rel) values(%s,%s,%s)""", (pg_chain_id, t_comb_2-tstart,incomplete_respect_per_chain,))
                conn2.commit()
        else:
            chain_len,et = 0,tstart # fake an empty chain to begin with and update it later
            c_pg.execute("""insert into chains(f_id,et,chain_len,tstart) values(%s,%s,%s,%s)""", (f_id,et,chain_len,tstart,))
            # What is the PK sequence number ?
            c_pg.execute("""select pg_chain_id from chains where f_id=%s and tstart=%s""", (f_id, tstart,))
            rows = c_pg.fetchall()
            for r in rows:
                pg_chain_id = r[0]
                print("new ID is", pg_chain_id)
            # get member snapshot from sqlite and store in pg
            c2.execute("""select playerwatch.player_id,namelevel.name from playerwatch,namelevel"""
                       """ where playerwatch.faction_id = ?  and playerwatch.player_id=namelevel.player_id""", (f_id,))
            for row in c2:
                print("Member of", f_id, row)
                c_pg.execute("""insert into chain_members(pg_chain_id,player_id,player_name) values(%s,%s,%s)""", (pg_chain_id, row[0], row[1],))
            conn2.commit()

# ===================
# remove sufficiently old entries
fourweeks = now - (4 * 7 * 86400)
# combat_events
c_pg.execute("""select evid from combat_events where et < %s""", (fourweeks,))
rows = c_pg.fetchall()
for unwanted_evid in rows:
    c_pg.execute("""delete from combat_events where evid = %s""", (unwanted_evid,))
    c_pg.execute("""delete from combat_respect where evid = %s""", (unwanted_evid,))
# bonus_events
c_pg.execute("""delete from bonus_events where et < %s""", (fourweeks,))
# chains
c_pg.execute("""select pg_chain_id from chains where tstart < %s""", (fourweeks,))
rows = c_pg.fetchall()
for pg_id in rows:
    c_pg.execute("""delete from chains where pg_chain_id = %s""", (pg_id,))
#
# GC: keep thing that support existing chains
allowed_chain_ids = []
c_pg.execute("""select pg_chain_id from chains""")
id_tuples = c_pg.fetchall()
for t in id_tuples:
    allowed_chain_ids.append(t[0])
print("ALLOWED", allowed_chain_ids)
#
mem_chain_ids = []
c_pg.execute("""select distinct pg_chain_id from chain_members""")
mem_tuples = c_pg.fetchall()
for mt in mem_tuples:
    mem_chain_ids.append(mt[0])
print("MEM", mem_chain_ids)
for pg_id in mem_chain_ids:
    if not pg_id in allowed_chain_ids:
        c_pg.execute("""delete from chain_members where pg_chain_id = %s""", (pg_id,))

# also summary table and chain_respect_history
cps_chain_ids = []
c_pg.execute("""select distinct pg_chain_id from chain_player_sum""")
cps_tuples = c_pg.fetchall()
for cps in cps_tuples:
    cps_chain_ids.append(cps[0])
print("CPS", cps_chain_ids)
for pg_id in cps_chain_ids:
    if not pg_id in allowed_chain_ids:
        c_pg.execute("""delete from chain_player_sum where pg_chain_id = %s""", (pg_id,))
        c_pg.execute("""delete from chain_respect_history where pg_chain_id = %s""", (pg_id,))


conn2.commit()
c2.close()

conn.commit()
c_pg.close()
