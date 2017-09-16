import requests
import time
import signal

class Tornapi:

    #             user/faction   selection   property
    def torn(self, what, which, how):
        if 'player' == what:
            what = 'user'
        elif 'user' == what:
            dummy = 1
        elif 'faction' == what:
            dummy = 1
        else:
            return ["EPARM what"]
    
        if 'basic' == how:
            # do on usr or faction
            dummy = 1
        elif 'crimes' == how:
            # do on usr or faction
            dummy = 1
        elif 'profile' == how:
            if 'user' != what:
                return ["EPARM what/how"]
        elif 'bars' == how:
            if 'user' != what:
                return ["EPARM what/how"]
        else:
            return ["EPARM how"]
    
        print("about to query ", what, repr(which) , " for ", how)
        ak="7CKwQOsq" # XXX XXX XXX XXX XXX XXX
    
        apiurl="https://api.torn.com/" + what + "/" + str(which) + "?selections=" + how + "&key=" + ak
        time.sleep(1)
        try:
            signal.alarm(20)
            r = requests.get(apiurl, timeout=10)
            signal.alarm(0)
            if not r:
                return ["FAIL API REQUEST r is None"]
        except:
            return ["FAIL API REQUEST"]
        data = r.json()
    
        if 'error' in data:
            # handle Torn API error
            # e.g.  {'error': {'code': 5, 'error': 'Too many requests'}}
            #       {"error":{"code":7,"error":"Incorrect ID-entity relation"}}
            #
            #  log this XXX
            return ["API ERROR", data['error']['code']]
    
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
    
        return ["OK", data]
