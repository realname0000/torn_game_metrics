#!/usr/bin/python3

import psycopg2
import sqlite3

# readonly postresql

try:
    connect_str = "dbname='torndb_dev' user='UUUUUU' host='localhost' " + \
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
c_pg.execute("""select id,faction_id,oc_plan_id,timestamp,paid_by from payment_cache""")
#  10 |      11581 |    5731534 | 1541846617 | 1455847
payment_rows = c_pg.fetchall()
print(len(payment_rows), "payment data items read from postgres")
# ===================

c_pg.execute("""select id,pid,number_oc,timestamp from report_number_oc order by timestamp""")
occalc_rows = c_pg.fetchall()
print(len(occalc_rows), "OCcalc data items read from postgres")
oc_calc = {}
for r in occalc_rows:
    oc_calc[r[1]] = r[2]

c_pg.close()
if  not len(payment_rows) and not len(occalc_rows):
    exit(1)

# ===================
# # open sqlite and update it with data gathered above # # 

conn2 = sqlite3.connect('/var/torn/torn_db')
c2 = conn2.cursor()
conn2.commit()

need_todo = []
for r in payment_rows:
    f_id = r[1]
    oc_plan_id = r[2]
    c2.execute("""select faction_id,oc_plan_id from factionoc where faction_id=? and oc_plan_id=? and initiated=? and paid_by=?""", (f_id,oc_plan_id,1,0,))
    for oc in c2:
        print("OC {} has been paid but not recorded in sqlite".format(oc_plan_id))
        need_todo.append(r)

for r in need_todo:
    f_id = r[1]
    oc_plan_id = r[2]
    paid_at = r[3]
    paid_by = r[4]
    print("changing ", f_id, oc_plan_id)
    c2.execute("""update factionoc set paid_by=? where faction_id=? and oc_plan_id=?""", (paid_by,f_id,oc_plan_id,))
    c2.execute("""update factionoc set paid_at=? where faction_id=? and oc_plan_id=?""", (paid_at,f_id,oc_plan_id,))

# ===================
for pid in oc_calc.keys():
    c2.execute("""update playeroc set oc_calc=? where player_id=?""", (oc_calc[pid], pid,))
# ===================

conn2.commit()
c2.close()
