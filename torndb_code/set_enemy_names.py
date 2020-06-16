#!/usr/bin/python3

import psycopg2
import sqlite3
import time



# ===================
# # open sqlite and read all namelevel names and player_ids

conn2 = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
c2 = conn2.cursor()
conn2.commit()

now = int(time.time())

enemy_names = {}
c2.execute("""select player_id,name from namelevel""")
for row in c2:
    enemy_names[str(row[0])] = row[1]


# ===================

conn2.commit()
c2.close()



# update postresql

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


# ===================
for i in enemy_names.keys():
    c_pg.execute("""update enemy set username=%s where tornid=%s""", (enemy_names[i],i,))


# ===================

conn.commit()
c_pg.close()
