#!/usr/bin/python3

import sqlite3
import time
import random
import oc_analytics

how_many_points = { # points per player crime
        0: 2,
        1: 4,
        2: 8,
        3: 9,
        4: 10,
        5: 12,
        6: 12,
        7: 12
    }

def get_word():
    w = ''
    vowel = 'aeiou'
    conso = 'bcdfghjklmnpqrstvwxyz'
    if (random.random() > 0.5):
        r =  int(random.random() * len(conso))
        w += conso[r]
        r =  int(random.random() * len(vowel))
        w += vowel[r]
        r =  int(random.random() * len(conso))
        w += conso[r]
        r =  int(random.random() * len(vowel))
        w += vowel[r]
        r =  int(random.random() * len(conso))
        w += conso[r]
    else:
        r =  int(random.random() * len(conso))
        w += conso[r]
        r =  int(random.random() * len(conso))
        w += conso[r]
        r =  int(random.random() * len(conso))
        w += conso[r]
        r =  int(random.random() * 10)
        w += str(r)
    return w
   
def populate_faction(c, f_id):
    if f_id >= 0:
        return  # This is for making fictitious demo data.
    oet = int(time.time()) - (86400 * 359)
    all_player_ids = {}
    all_player_names = {}
    c.execute("""select player_id from playerwatch""",)
    for row in c:
        all_player_ids[row[0]] = row[0]
    for p_id in all_player_ids:
        c.execute("""select name from namelevel where player_id=?""",(p_id,))
        for row in c:
            all_player_names[row[0]] = row[0]

    for new_player in range(26,76):
        word = get_word()
        if word in all_player_names:
            continue
        p_id = (f_id * 100) - new_player
        if p_id in all_player_ids:
            continue
        c.execute("""insert into playerwatch values(?,?,?,?,?)""", (oet, oet, 1, f_id, p_id,))
        c.execute("""insert into namelevel values(?,?,?,?)""", (oet, word, new_player, p_id,))
        # empty crime hstory
        c.execute("""insert into playercrimes values(?,?,?,?, ?,?,?,?, ?,?,?,?)""", (oet, 0, p_id,  0, 0, 0, 0, 0, 0, 0, 0, 0,))
        c.execute("""insert into pstats values(?,?,?,?, ?,?,?,?)""", (oet, 0, p_id, 0, 0, 0, 0, 0,))
        conn.commit()


def playercrime(c, players):
    for p_id in players:
        c.execute("""select et,api_id,player_id,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where player_id=? and et=(select max(et) from playercrimes where player_id=?)""", (p_id, p_id,))
        crimedata = []
        for row in c:
            for i in row:
                crimedata.append(i)
        if len(crimedata) != 12:
            print( len(crimedata), " wrong length")
            continue
        crimedata[0] += 86400
        et = crimedata[0]
        #
        r= int(random.random() * 8)    
        increase = int( 288/how_many_points[r] )
        crimedata[r + 3] += increase
        crimedata[11] += increase
        #
        c.execute("""insert into playercrimes values(?,?,?,?, ?,?,?,?,  ?,?,?,?)""", (crimedata))
        c.execute("""update playerwatch set et=? where player_id=?""", (crimedata[0], p_id,))
        c.execute("""update playerwatch set latest=? where player_id=?""", (crimedata[0], p_id,))
    conn.commit()
    return et

def reap_oc(c, f_id):
    analytics = oc_analytics.Compare(c, f_id)
    c.execute("""select distinct oc_plan_id,crime_id,crime_name,participants from factionoc where faction_id=? and initiated=?""",(f_id,0,))
    plans = []
    oc_plan_already = {}
    for row in c:
        print("Uncompleted OC: ", row)
        plans.append(row[0])
        oc_plan_already[row[0]]=row
    for crimeplan in plans:
        c.execute("""update factionoc set initiated=? where faction_id=? and oc_plan_id=?""", (1, f_id, crimeplan,))
        c.execute("""update factionoc set et=? where faction_id=? and oc_plan_id=?""", (et, f_id, crimeplan,))
        c.execute("""update factionoc set time_executed=? where faction_id=? and oc_plan_id=?""", (et, f_id, crimeplan,))
        if (random.random()) > 0.1:
            crime_id = crimeplan
            if crime_id == 8: # PA
                money = 100000 + int (random.random() * 200000)
                respect = 50 + int (random.random() * 250)
            elif crime_id  == 4: # PR
                money = 50000 + int (random.random() * 150000)
                respect = 10 + int (random.random() * 70)
            elif crime_id  < 4:
                money = 100 + int (random.random() * 5000)
                respect = 5 + int (random.random() * 50)
            else:
                money = 50000 + int (random.random() * 100000)
                respect = 20 + int (random.random() * 150)
            c.execute("""update factionoc set success=? where faction_id=? and oc_plan_id=?""", (1, f_id, crimeplan,))
            c.execute("""update factionoc set money_gain=? where faction_id=? and oc_plan_id=?""", (money, f_id, crimeplan,))
            c.execute("""update factionoc set respect_gain=? where faction_id=? and oc_plan_id=?""", (respect, f_id, crimeplan,))
        participants = oc_plan_already[crimeplan][3]
        players = participants.split(',')
        analytics.ingest(f_id, crimeplan, oc_plan_already[crimeplan][1], players)
        print("Recording outcome of OC ", crimeplan)
    analytics.examine()
    conn.commit()

def sow_oc(c, f_id, players):
    c.execute ("""select max(oc_plan_id) from factionoc where faction_id=?""",(f_id,))
    for row in c:
        max_plan_already= row[0]
    if not max_plan_already:
        max_plan_already = 400000
    free = players[:]
    booked = []
    # discover booked
    c.execute ("""select whodunnit.oc_plan_id,factionoc.participants from whodunnit,factionoc where whodunnit.faction_id=? and factionoc.initiated=? and  whodunnit.oc_plan_id=factionoc.oc_plan_id""",(f_id,0,))
    for row in c:
       print("Booked: ", row)
       parts = row[1].split(',')
       for i in parts:
           ii = int(i)
           if ii in free:
               free.remove(ii)
    print("Free: ", free)
    while 1:
        if (len(free) < 2):
            return # no new OC possible
        elif (len(free) == 2):
            crime_id = 2
            need = 2
            crime_name = 'Kidnapping'
        elif (len(free) == 3):
            crime_id = 3
            need = 3
            crime_name = 'Bomb threat'
        elif (len(free) >= 5):
            crime_id = 4
            need = 5
            crime_name = 'Planned robbery'
        else:
            crime_id = 1
            need = 2
            crime_name = 'Blackmailing'
        max_plan_already += 1
        # choose OC to use free, INSERT into factionoc and whodunnit
        participants = ''
        comma = ''
        for use in range(0,need):
            # some randomisation
            if  (len(free) > 2)  and (random.random() < 0.25):
                fofi = free.pop()
                loli = free.pop()
                free.append(fofi)
                free.append(loli)
            p = free.pop()
            participants = participants + comma + str(p)
            comma = ','
            c.execute("""insert into whodunnit values(?,?,?,?)""", (et, p, f_id, max_plan_already,))
        print("For OC ", max_plan_already, " of type ",  crime_id, " using ", participants, "at time ",  time.strftime("%Y-%m-%d", time.gmtime(et)))
        c.execute("""insert into factionoc values(?,?,?,?,?, ?,?,?,?,?, ?,?,?,?)""",
                     (et, 4, f_id, max_plan_already, crime_id, crime_name, participants, et, et+80000, 0,0,0,0,0,))



conn = sqlite3.connect('/var/torn/torn_db')
c = conn.cursor()
conn.commit()

et = int(time.time()) - (86400 * 200)

for f_id in [-99]:
    players = []
    c.execute("""select player_id from playerwatch where faction_id=?""", (f_id,))
    for row in c:
        players.append(int(row[0]))
    if not len(players):
        print("No players in faction ", f_id)
        populate_faction(c, f_id)
        continue
    et = playercrime(c, players)
    reap_oc(c, f_id)
    sow_oc(c, f_id, players)

conn.commit()
c.close()
