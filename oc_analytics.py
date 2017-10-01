import sqlite3
import time

class Compare:

    def __init__(self, c, f_id):
        self.c = c
        self.scrutiny = {}
        self.tablecopy = {}
        c.execute("""SELECT oc_plan_id,crime_id,participants FROM factionoc where faction_id=? and initiated=?""", (f_id, 1,))
        for row in c:
             oc_plan_id, crime_id, participants = row
             players = participants.split(',')
             players.insert(0, crime_id)
             self.tablecopy[oc_plan_id] = players

    def ingest(self, f_id, oc_plan_id, crime_id, players):
        self.scrutiny[oc_plan_id] = [f_id, crime_id, players]

    def all_the_things(self, f_id):
        for plan in self.tablecopy.keys():
            self.ingest(f_id,  plan, self.tablecopy[plan][0], self.tablecopy[plan][1:])
            
   
    def examine(self):
        # examine the scrutiny data and insert into compare as needed
        et = int(time.time())
        for plan in self.scrutiny.keys():
            f_id, crime_id, players = self.scrutiny[plan]
            for other in self.tablecopy.keys():
                if plan == other:
                    continue
                if crime_id != self.tablecopy[other][0]:
                    continue
                op = self.tablecopy[other][1:]
                #
                counting = {}
                for i in players:
                    if i in counting:
                        counting[i] += 1
                    else:
                        counting[i] = 1
                for j in op:
                    if j in counting:
                        counting[j] += 1
                    else:
                        counting[j] = 1
                #
                if len(counting.keys()) == (1 + len(players)):
                    two = []
                    for x in counting.keys():
                       if 1 == counting[x]:
                           two.append(x)
                    if (two[0] in players) and (two[1] in op):
                        print("Two players are  ", two, " from ", plan, other)
                        add_this = [plan, other, two[0], two[1]]
                    elif (two[1] in players) and (two[0] in op):
                        print("Two players are  ", two, " from ", other, plan)
                        add_this = [other, plan, two[0], two[1]]
                    else:
                        print("Error performing analytics")
                        continue
                    # Conversion to int in case these have become strings
                    if int(add_this[0]) < int(add_this[1]):
                        self.c.execute("""delete from compare where f_id=? and oc_a=? and oc_b=?""", (f_id, add_this[0], add_this[1],))
                        self.c.execute("""insert into compare values (?, ?,?, ?,?)""", (f_id, add_this[0], add_this[1], two[0], two[1]))
                    else:
                        self.c.execute("""delete from compare where f_id=? and oc_a=? and oc_b=?""", (f_id, add_this[1], add_this[0],))
                        self.c.execute("""insert into compare values (?, ?,?, ?,?)""", (f_id, add_this[1], add_this[0], two[1], two[0]))

                    self.c.execute("""delete from player_compare_t where player_id=?""", (two[0],))
                    self.c.execute("""delete from player_compare_t where player_id=?""", (two[1],))
                    self.c.execute("""insert into player_compare_t values (?, ?)""", (two[0], et,))
                    self.c.execute("""insert into player_compare_t values (?, ?)""", (two[1], et,))
