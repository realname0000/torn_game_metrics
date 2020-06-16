#!/usr/bin/python3

import psycopg2
import time

now = int(time.time())
# postresql

try:
    connect_str = "dbname='torndb_dev' user='pyflask' host='localhost' " + \
                  "password='PPPPPP'"
    # use our connection values to establish a connection
    conn = psycopg2.connect(connect_str)
    # create a psycopg2 cursor that can execute queries
    c_pg = conn.cursor()
except Exception as e:
    print("Uh oh, can't connect. Invalid dbname, user or password?")
    print(e)
    exit(1)

# delete old entries from data that should have been copied by now into sqlite

c_pg.execute("""delete from payment_cache where timestamp < %s""", ((now-7200),) )

c_pg.execute("""delete from report_number_oc where timestamp < %s""", ((now-7200),) )

c_pg.execute("""delete from ocpolicy where timestamp < %s""", ((now-7200),) )

c_pg.execute("""delete from apikey_history where et_web_update < %s""", ((now-7200),) )

c_pg.execute("""delete from timerange where tstart < %s""", ((now-(28*86400)),) )


# faction leaders where the definition is superseded
todo_leaders_fid = []
c_pg.execute("""select count(1),faction_id from extra_leaders group by faction_id""")
rows = c_pg.fetchall()
for r in rows:
    if r[0] > 1:
        todo_leaders_fid.append(r[1])

for fid in todo_leaders_fid:
    todo_players_pid = []
    c_pg.execute("""select count(1),player_id from extra_leaders where faction_id = %s group by player_id""", (fid,))
    rows = c_pg.fetchall()
    for r in rows:
        if r[0] > 1:
            print("In faction {} seen player {} {} times".format(fid, r[1], r[0]))
            todo_players_pid.append(r[1])

    for pid in todo_players_pid:
        c_pg.execute("""select et from extra_leaders where faction_id = %s and player_id = %s order by et limit 1""", (fid,pid,))
        rows = c_pg.fetchall()
        for r in rows:
            print("In faction {} seen player {} at times {}".format(fid, pid, r[0]))
            c_pg.execute("""delete from extra_leaders where faction_id = %s and player_id = %s and et = %s""", (fid,pid,r[0],))


# copy entries from chains into timerange
c_pg.execute("""select f_id,tstart,tend from chains where tend != %s and tend > %s""", (0,(now-86400),))
rows = c_pg.fetchall()
for r in rows:
    print(r)
    c_pg.execute("""select f_id,tstart,tend from timerange where f_id=%s and tstart = %s and  tend = %s""", r)
    matches = c_pg.fetchall()
    if not matches:
        c_pg.execute("""insert into timerange(f_id,tstart,tend) values(%s,%s,%s) ON CONFLICT DO NOTHING""", r)

conn.commit()
c_pg.close()
conn.close()
