#!/usr/bin/python3


import sqlite3
import oc_analytics


conn = sqlite3.connect('/var/torn/torn_db')
c = conn.cursor()
conn.commit()

f_id=11581
analytics = oc_analytics.Compare(c, f_id)


# 1506367060|1338804|11581|5138979|3|Bomb threat|1073400,1975558,2061118|1505445100|1505704300|1|0|0|0|1506367062

# crimeplan = 5138979
# oc = {}
# oc[crimeplan] = {}
# oc[crimeplan]['crime_id'] = 3
# players=['1073400', '1975558', '2061118']
# analytics.ingest(f_id, crimeplan, oc[crimeplan]['crime_id'], players)

analytics.all_the_things(f_id)

analytics.examine()
conn.commit()
