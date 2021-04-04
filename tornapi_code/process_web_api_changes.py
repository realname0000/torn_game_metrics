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
        return "FAIL"
    if 'player_id' in data:
        p_id = data['player_id']
        c2.execute("""delete from apikeys where player_id = ?""", (p_id,))
        c2.execute("""insert into apikeys(et,player_id,short_err,long_err,key) values(?,?,?,?,?)""", (int(time.time()), p_id, 0, 0, apikey,))
        c2.execute("""update playerwatch set latest=latest/2  where player_id=?""", (p_id,))
        conn2.commit()
        return "OK"

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
        print("\n unfinished ", filename, "\n")
        return # unfinished file

    do_remove = False

    if len(text) < 5:
        if text[0] == 'APIKEY':
            if text[3] == 'END':
                apikey = text[1]
                faction = text[2]
                print("\n calling check_and_store() ", filename, "\n")
                cs_status = check_and_store(apikey, faction)
                if "OK" == cs_status:
                    do_remove = True
            else:
                print("\nwrong content:", filename, text, "\n")
                return 
        elif text[0] == 'DELETE APIKEY':
            if text[2] == 'END':
                p_id = text[1]
                print("\n deleting ...\n")
                delete_api_key(p_id)
            else:
                print("\nwrong content:", filename, text, "\n")
                return 
        else:
            print('unexpected', text)
            return 

    if do_remove:
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
                print("finished work on", entry.name)
            else:
                print("removing non-numeric filename", entry.name)
                os.remove(entry.name)

    c2.close()
