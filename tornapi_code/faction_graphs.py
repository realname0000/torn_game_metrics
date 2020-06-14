from  player_graphs import Draw_graph
import matplotlib.pyplot as plt
import datetime
import os
import hashlib

class Draw_faction_graph:

    def __init__(self, docroot, c, var_interval_no, faction_dname):
        self.docroot = docroot
        self.c = c
        self.faction_dname = faction_dname

    def faction(self, f_id):
        urls = []
        for subject in ('respect', 'neumune'):
            xx = []
            yy = []
            y2 = []
            y3 = []
            last_x = 0
            nonzero_data = 0
            if 'respect' == subject:
                self.c.execute("""select et,respect from factionrespect where f_id=? order by et""",(f_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'neumune' == subject:
                self.c.execute("""select et,neumune from factionstore where faction_id=? order by et""",(f_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            else:
                print("bad graph name", subject, p_id)
                continue
            if nonzero_data and (len(xx) > 2):
                faction_name = '[' + str(f_id) + ']'
                self.c.execute("""select f_name from factiondisplay where f_id=?""",(f_id,))
                for row in self.c:
                    faction_name = row[0] +  '[' + str(f_id) + ']'
                graphname = hashlib.sha1(bytes('faction_png_graph' + str(f_id) + self.faction_dname + subject, 'utf-8')).hexdigest()
                short_fname ="faction/" + self.faction_dname + "/" + graphname + ".png"
                long_fname = self.docroot + short_fname
                try:
                    mtime = os.stat(long_fname).st_mtime
                    if mtime > last_x:
                        urls.append('/' + short_fname)
                        continue # no need to redraw graph
                except:
                    pass
                new_graph = Draw_graph.one_graph(self, xx, yy, y2, short_fname, subject, faction_name)
                urls.append(new_graph)
            else:
                print("No graph to be plotted (" + subject + ") - insufficient data.", nonzero_data, len(xx))
        return urls
