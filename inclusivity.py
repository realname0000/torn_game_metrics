#!/usr/bin/python3

import psycopg2
import sqlite3
import time
import sys


#  postresql with ability to write to response table
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


need_these = {} # player ids to ensure are being harvested

c_pg.execute("""select username from l_user where login_allowed = %s""", (1,))
rows = c_pg.fetchall()
for r in rows:
    need_these[str(r[0])] = 1
c_pg.close()
conn.close()

# open sqlite
try:
    conn2 = sqlite3.connect('/var/torn/torn_db')
    c2 = conn2.cursor()
except:
    sys.exit(1)

# discover who is already in playerwatch
c2.execute("""select player_id from playerwatch""")
for row in c2:
    if str(row[0]) in need_these:
        del need_these[str(row[0])]

now = int(time.time())

for pid in need_these.keys():
   print("need pid", pid)
   c2.execute("""insert into playerwatch (et,latest,ignore,faction_id,player_id) values(?,?,?,?,?)""", (now,0,0,0,int(pid),))
   conn2.commit()

c2.close()
