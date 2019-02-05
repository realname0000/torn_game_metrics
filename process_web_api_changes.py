#!/usr/bin/python3

import os
import subprocess
import sqlite3
import re
import requests
import json
import sys
import time

re_numeric = re.compile('^\d+$')


def check_and_store(apikey, faction):
    apiurl = "https://api.torn.com/user/?selections=basic&key=" + apikey
    r = requests.get(apiurl, timeout=10)
    try:
        data = r.json()
    except:
        return
    if 'player_id' in data:
        p_id = data['player_id']
        c2.execute("""delete from apikeys where player_id = ?""", (p_id,))
        c2.execute("""insert into apikeys(et,player_id,short_err,long_err,key) values(?,?,?,?,?)""", (int(time.time()), p_id, 0, 0, apikey,))
        conn2.commit()

def delete_api_key(p_id):
    c2.execute("""delete from apikeys where player_id = ?""", (p_id,))
    conn2.commit()

def read_and_update(filename):
    text = []
    with open(filename) as in_file:
        print("\n", filename, "\n")
        n = 0
        while True:
            line = in_file.readline()
            if not line:
                break
            line = line.rstrip()
            text.append(line)
            n += 1
            if n > 10:
                break

    if len(text) < 3:
        return # unfinished file

    if len(text) < 5:
        if text[0] == 'APIKEY':
            if text[3] == 'END':
                apikey = text[1]
                faction = text[2]
                check_and_store(apikey, faction)
            else:
                return 
        elif text[0] == 'DELETE APIKEY':
            if text[2] == 'END':
                p_id = text[1]
                delete_api_key(p_id)
            else:
                return 
        else:
            print('unexpected', text)
            return 

    os.remove(filename)


if __name__ == "__main__":
    os.chdir('/var/torn/spool/collect')

    conn2 = sqlite3.connect('/var/torn/torn_db')
    c2 = conn2.cursor()
    conn2.commit()
    
    with os.scandir('/var/torn/spool/collect') as it:
      for entry in it:
        if entry.is_file():
            is_numeric = re_numeric.match(entry.name)
            if is_numeric:
                print("planning to work on", entry.name)
                read_and_update(entry.name)
            else:
                os.remove(entry.name)

    c2.close()
