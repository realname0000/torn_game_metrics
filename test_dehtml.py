#!/usr/bin/python3

import dehtml

frog=dehtml.Dehtml()

texts = ['In hospital for 15 mins ', 'Attacked by <a href=profiles.php?XID=1043621>HenkiePuk</a>']

for t in texts:
    toad = frog.html_clean(t)
    print(toad)
