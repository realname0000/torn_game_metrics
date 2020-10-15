#!/usr/bin/python3

import psycopg2
import sqlite3
import time
import sys
import requests
import re

re_subject = re.compile('^[A-Z]+: [A-Z]+ [A-Z]+ [A-Z]+ [A-Z]+ [A-Z]+ [A-Z]+\s*$')

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


# open sqlite for api key
try:
    conn2 = sqlite3.connect('/var/torn/torn_db')
    c2 = conn2.cursor()
except:
    print("failed to use sqlite")
    sys.exit(1)

# USER
player = 1338804
# APIKEY
c2.execute("""select key from apikeys where player_id = ?""", (player,))
for row in c2:
    apikey = row[0]

c2.close()


# get api data
apiurl = "https://api.torn.com/user/?selections=messages&key=" + apikey
r = requests.get(apiurl, timeout=10)
try:
    data = r.json()
except:
    print("tornapi_challenge_responses.py request for messages failed")
    c_pg.close()
    conn.close()
    sys.exit(1)

if 'messages' in data:
    mess = data['messages']
else:
    c_pg.close()
    conn.close()
    sys.exit(1)

already_in_table = {}
c_pg.execute("""select provided from response""")
rows = c_pg.fetchall()
for r in rows:
    already_in_table[r[0]] = 1

now = int(time.time())
for m in mess.keys():
    if mess[m]['timestamp'] < (now - 800):
        continue
    #print("MAIL:", mess[m])
    subj = re_subject.match(mess[m]['title'])
    if subj:
        print("MAIL OKRE:", mess[m]['title'])
        mess[m]['title'] = mess[m]['title'].rstrip()
        print("MAIL:", mess[m])
        if not mess[m]['title'] in already_in_table:
            print("MAIL INSERT:", mess[m]['title'])
            c_pg.execute("""insert into response(et,used,username,chal_type,provided) values(%s,%s,%s,%s,%s)""", (now,0,str(mess[m]['ID']),'message',mess[m]['title'],))
            conn.commit()
    else:
        pass
        #print("This title does not match RE:", mess[m]['title'])

c_pg.close()
conn.close()
