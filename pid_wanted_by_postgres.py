#!/usr/bin/python3

import psycopg2
import sqlite3
import time

# readonly postresql

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
c_pg.execute("""select distinct tornid from enemy""")
# id | tornid  |   username    | f_id
#  4 | 317178  | Flex          | 11581
enemies = c_pg.fetchall()
print(len(enemies), "p_id read from enemy")
# ===================

c_pg.execute("""select distinct username from l_user""")
user_ids = c_pg.fetchall()
print(len(user_ids), "tornutopia users")
# ===================

wanted_pid = {}
for p in enemies + user_ids:
    wanted_pid[int(p[0])] = 1

et = int(time.time())
etlessfive =  et - (5 * 86400)

# ===================
c_pg.close()
if not len(wanted_pid):
    exit(1)

# ===================
# # open sqlite and update it with data gathered above # # 

conn2 = sqlite3.connect('/var/torn/torn_db')
c2 = conn2.cursor()
conn2.commit()

for pk in wanted_pid.keys():
    c2.execute("""replace into pid_wanted values(?,?)""", (pk, et,))
conn2.commit()

playerwatch_only = {}
to_delete = []
c2.execute("""select distinct player_id from playerwatch""")
for row in c2:
    playerwatch_only[int(row[0])] = 1
c2.execute("""select player_id,wanted from pid_wanted""")
for row in c2:
    if row[0] in playerwatch_only:
        playerwatch_only.pop(row[0])
        # If the time is right this should be deleted from both tables
        if ((et - row[1] ) > 604840):
            to_delete.append(row[0])

print("plan to delete", to_delete)
for pid in to_delete:
    c2.execute("""delete from pid_wanted where player_id = ?""", (pid,))
    c2.execute("""delete from playerwatch where player_id = ?""", (pid,))
conn2.commit()

for pid in playerwatch_only.keys():
    print(pid, "only in playerwatch but not pid_wanted")
    c2.execute("""insert or ignore into pid_wanted values(?,?)""", (pid, etlessfive,))

conn2.commit()
c2.close()
