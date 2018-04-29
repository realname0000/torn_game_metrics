#!/usr/bin/python3

import dehtml

frog=dehtml.Dehtml()

texts = ['In hospital for 15 mins ', 'Attacked by <a href=profiles.php?XID=1043621>HenkiePuk</a>']
#
texts.append('Attacked by <a href="profiles.php?XID=1307523">Drieke')
texts.append('Attacked by <a href="profiles.php?XID=130895">ViSiOn')
texts.append('Attacked by <a href="profiles.php?XID=336112">Akagami')
texts.append('Hospitalized by <a href="profiles.php?XID=1514590">Nub')
texts.append('Hospitalized by <a href="profiles.php?XID=1953860">RGiskard')
texts.append('Hospitalized by <a href="profiles.php?XID=253384">IIIlusionist')
texts.append('Hospitalized by <a href="profiles.php?XID=705319">Scar')
texts.append('Lost to <a href="profiles.php?XID=139168">Tazzy')
texts.append('Lost to <a href="profiles.php?XID=271756">Buuwack')
texts.append('Mugged by <a href="profiles.php?XID=259880">raintrain')
texts.append('Mugged by <a href="profiles.php?XID=560161">DiamondAce')
texts.append('Mugged by <a href="profiles.php?XID=96875">Spurtung')


for t in texts:
    toad = frog.html_clean(t)
    print(toad)
