import requests
import time
import signal
import random

class Tornapi:

    def __init__(self, c):
        self.c = c # db cursor
        self.count = [0, 0, 0]
        self.good_user_key = {}
        self.good_faction_key = {}
        self.suggest_faction_key = {}
        self.pid2ak = {}
        self.default_apikey = None
        #
        c.execute ("""select default_apikey from admin""")
        for row in c:
            self.default_apikey = row[0]
        #
        c.execute ("""select player_id,short_err,long_err,key  from apikeys""")
        for row in c:
            if row[2]: # long-lasting error on this key
                continue
            if (3600 + row[1]) > int(time.time()):
                continue
            self.pid2ak[row[0]] = row[3]
        #
        c.execute ("""select ignore,faction_id,player_id from factionwatch""")
        for row in c:
            ignore,faction_id,player_id = row
            if ignore:
                continue
            if not faction_id in self.suggest_faction_key:
                self.suggest_faction_key[faction_id] = []
            if player_id in self.pid2ak:
                self.suggest_faction_key[faction_id].append(player_id)

    def apistats(self):
        print("API stats: good, fail, error =", self.count)
        self.pid2ak = []

    #             user/faction   selection   property
    def torn(self, what, which, how):
        key_id = None
        ak = None
        if ('player' == what) or ('user' == what):
            what = 'user'
            choose_from = self.good_user_key.keys()
            if len(choose_from):
                key_id = random.choice(list(self.good_user_key.keys()))
        elif 'faction' == what:
            print("Suggestions: ", self.suggest_faction_key)
            if which in self.suggest_faction_key:
                print("look for key in ", self.suggest_faction_key[which])
                try:
                    key_id = self.suggest_faction_key[which].pop()
                except:
                    return ["No key to query faction"]
        else:
            return ["EPARM what"]
    
        if not key_id:
            print("Taking key of last resort ...")
            key_id = self.default_apikey

        if key_id in self.pid2ak:
            ak = self.pid2ak[key_id]

        if 'basic' == how:
            # do on usr or faction
            pass
        elif 'crimes' == how:
            # do on usr or faction
            pass
        elif 'profile' == how:
            if 'user' != what:
                return ["EPARM what/how"]
        elif ('bars' == how) or ('personalstats' == how):
            if 'user' != what:
                return ["EPARM what/how"]
            if which in self.pid2ak:
                ak = self.pid2ak[which]
                key_id = which
            else:
                return ["EPARM need right apikey for bars or personalstats"]
        else:
            return ["EPARM how"]
    
        if not ak:
            return ["EPARM no key available"]
        print("about to query ", what, repr(which) , " for ", how)
    
        apiurl="https://api.torn.com/" + what + "/" + str(which) + "?selections=" + how + "&key=" + ak
        time.sleep(1)
        try:
            signal.alarm(20)
            r = requests.get(apiurl, timeout=10)
            signal.alarm(0)
            if not r:
                self.count[1] += 1
                return ["FAIL API REQUEST r is None what=" + str(what) + " which=" + str(which) + " how=" + str(how)]
        except:
            self.count[1] += 1
            return ["FAIL API REQUEST what=" + str(what) + " which=" + str(which) + " how=" + str(how)]
        try:
            data = r.json()
        except:
            self.count[1] += 1
            return ["FAIL API JSON"]

        if what=='faction' and how=='crimes':
            print("faction crime data recieved as",r)
    
        if 'error' in data:
            # handle Torn API error
            e = data['error']
            code = e['code']
            error_msg = e['error']
            et = int(time.time())
            self.c.execute("""insert into error values (?,?,?,?, ?,?,?)""",
                     (et,key_id,what,which,how,code,error_msg,))
            # short key ban for 5  (7 if faction) 
            # long key ban      1  2  10
            if (5 == code) or ((7 == code) and ('faction' == what)):
                self.c.execute("""update apikeys set short_err=? where player_id=?""", (et,key_id,))
            elif (1 == code) or (2 == code) or (10 == code):
                self.c.execute("""update apikeys set long_err=? where player_id=?""", (et,key_id,))

            if key_id in self.good_user_key:
                del self.good_user_key[key_id]
            self.count[2] += 1
            return ["API ERROR what=" + str(what) + " which=" + str(which) + " how=" + str(how), code]
    
        if 'user' == what:
            if 'basic' == how:
                if not 'level' in data:
                    print("level not found", data)
                    return ['Bad data']
            if 'profile' == how:
                if not 'level' in data:
                    print("level not found", data)
                    return ['Bad data']
            if 'bars' == how:
                if not 'nerve' in data:
                    print("nerve not found", data)
                    return ['Bad data']
            if 'personalstats' == how:
                if not 'personalstats' in data:
                    print("personalstats not found", data)
                    return ['Bad data']
            if 'crimes' == how:
                if not 'criminalrecord' in data:
                    print("criminalrecord not found", data)
                    return ['Bad data']
        elif 'faction' == what:
            if 'basic' == how:
                if not 'members' in data:
                    print("Faction members not found", data)
                    return ['Bad data']
            if 'crimes' == how:
                if not 'crimes' in data:
                    print("Faction crimes not found", data)
                    return ['Bad data']
    
        self.good_user_key[key_id] = 1
        if 'faction' == what:
            self.good_faction_key[which] = key_id
        self.count[0] += 1
        return ["OK", data, key_id]
