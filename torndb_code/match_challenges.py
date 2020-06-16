#!/usr/bin/python3

import psycopg2
import time

now = int(time.time())
lf = open('../logs/challenge_response', 'a')
print("start of run {}".format(now), file=lf)

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
    print(e, file=lf)
    exit(1)

# match responses to challenges, mark both as used, take action
todo_chal = {}
c_pg.execute("""select id,username,action,data,chal_type,expect,pw_ver from challenge where used = %s and expires > %s""", (0,now,))
rows = c_pg.fetchall()
for r in rows:
    todo_chal[ r[0] ] = list(r)
    print("Have challenge", r, file=lf)

c_pg.execute("""select id,username,chal_type,provided from response where used = %s""", (0,))
rows = c_pg.fetchall()
for r in rows:
    print('have response', r, file=lf)
    # check against all of todo_chal
    for ck in todo_chal.keys():
        print('comparing:', r, ck, file=lf)
        if (todo_chal[ck][1] ==  r[1]) and (todo_chal[ck][4] == r[2] ) and (todo_chal[ck][5] == r[3]):
            if todo_chal[ck][2] == 'newuser':
                c_pg.execute("""update l_user set login_allowed=%s where username=%s""", (1,r[1],))
            elif todo_chal[ck][2] == 'pwreset':
                c_pg.execute("""update l_user set login_allowed=%s where username=%s and confirmed=0""", (1,r[1],))
                # use pwhash and pw_ver from the challenge table
                c_pg.execute("""update l_user set pwhash=%s where username=%s""", (todo_chal[ck][3], r[1],))
                c_pg.execute("""update l_user set pw_ver=%s where username=%s""", (todo_chal[ck][6], r[1],))
                c_pg.execute("""update l_user set must_change_pw=%s where username=%s""", (0, r[1],))
            else:
                print("unexpected type of challenge {}".format(todo_chal[ck][2]), file=lf)
                continue
            c_pg.execute("""update l_user set confirmed=%s where username=%s""", (now,r[1],))
            c_pg.execute("""update challenge set used=%s where id=%s""", (1,ck,))
            c_pg.execute("""update response set used=%s where id=%s""", (1,r[0],))
        else:
            print("could not match this response to this challenge {} {}".format(r[0], todo_chal[ck][0]), file=lf)

# delete old entries from these tables
c_pg.execute("""delete from challenge where expires < %s""", ((now-7200),) )
c_pg.execute("""delete from response where et < %s""", ((now-7200),) )
c_pg.execute("""delete from l_user where registered < %s and confirmed = %s""", ((now-86400),0,) )

conn.commit()
c_pg.close()
conn.close()
print("end of run {}".format(now), file=lf)
