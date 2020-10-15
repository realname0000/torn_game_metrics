#!/usr/bin/python3

import web_api

web=web_api.Tornapi()

result = web.torn('faction', 11581, 'basic')
if 'OK' == result[0]:
    print(result[1]['name'],  len(result[1]['members']))
else:
    print(result)
    exit(1)

result = web.torn('faction', 11581, 'crimes')
if 'OK' == result[0]:
    crimes=result[1]['crimes']
    for oc in crimes:
        print(oc, crimes[oc])
        break # just show one
else:
    print(result)
    exit(1)



result = web.torn('user', 1338804, 'basic')
if 'OK' == result[0]:
    print(result[1])
else:
    print(result)
    exit(1)

result = web.torn('user', 1338804, 'crimes')
if 'OK' == result[0]:
    print(result[1])
else:
    print(result)
    exit(1)


result = web.torn('user', 1338804, 'profile')
if 'OK' == result[0]:
    print(result[1]['status'])
else:
    print(result)
    exit(1)

result = web.torn('user', 1338804, 'bars')
if 'OK' == result[0]:
    print(result[1]['nerve'])
else:
    print(result)
    exit(1)
