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
# ===================


#   id | faction | timestamp  | percent | username | octype
#  ----+---------+------------+---------+----------+--------
#    1 |   11581 | 1542756367 |   20.00 | 1338804  |      8

c_pg.execute("""select faction,octype,percent,username,timestamp from ocpolicy order by timestamp""")
ocpolicy_rows = c_pg.fetchall()
print(len(ocpolicy_rows), "OCpolicy data items read from postgres")
oc_policy_by_faction = {}
for r in ocpolicy_rows:
    f_id = r[0]
    cn = r[1]
    percent = r[2]
    p_id = r[3]
    et = r[4]
    if not f_id in oc_policy_by_faction:
        oc_policy_by_faction[f_id] = {}
    oc_policy_by_faction[f_id][cn] = [percent, p_id, et]


# ===================
c_pg.close()
if not len(payment_rows) and not len(occalc_rows) and not len(ocpolicy_rows):
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
for f_id in oc_policy_by_faction.keys():
    d = oc_policy_by_faction[f_id]
    for cn in d.keys():
        # compare to sqlite
        c2.execute("""select percent from payment_percent where faction_id=? and crime_id=? order by et desc limit 1""", (f_id, cn,))
        pc = 0
        for row in c2:
            pc = row[0]
        if float(pc) != float(d[cn][0]):
            c2.execute("""insert into payment_percent(et,faction_id,crime_id,percent,set_by) values(?,?,?,?,?)""", (d[cn][2], f_id, cn, float(d[cn][0]), d[cn][1],))
            print("Writing change for", f_id, cn)

# ===================

conn2.commit()
c2.close()
