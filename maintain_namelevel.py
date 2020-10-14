#!/usr/bin/python3

import psycopg2
import sqlite3
import time
import web_api
import sys

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
enemy_stuff = c_pg.fetchall()
enemy_tornid = []
for i in enemy_stuff:
    enemy_tornid.append(i[0])
# ===================

c_pg.close()


# ===================
# # open sqlite and update it with data gathered above # # 

conn2 = sqlite3.connect('/var/torn/torn_db')
c2 = conn2.cursor()
conn2.commit()

now = int(time.time())

# query from API, replace in sqlite
web=web_api.Tornapi(c2) # use this one object throughout

for m in enemy_tornid:
    result = web.torn('user', m, 'basic')
    print(result)
    if len(result) > 1:
        if ((type(result[1]) == type(9)) or (type(result[1]) == type('api disabled already'))):
            print(result, file=sys.stderr)
        else:
            c2.execute("""replace into namelevel(et,name,level,player_id) values(?,?,?,?)""", (now, result[1]['name'], result[1]['level'], m,))

# ===================

conn2.commit()
c2.close()
