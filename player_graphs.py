import matplotlib.pyplot as plt
import datetime
import os
import hashlib


class Draw_graph:

    def __init__(self, docroot, c, weekno, player_dname):
        self.docroot = docroot
        self.c = c
        self.player_dname = player_dname

    def one_graph(self, xx, y, y2, fname, subject, title):
        plt.clf()
        plt.plot(xx, y)
        if len(y2) > 2:
            plt.plot(xx, y2)
        plt.title(str(title) +  " " +  subject)
        plt.xticks( [xx[0],xx[-1]],  [xx[0], xx[-1]])
        plt.savefig('/torntmp/peabrain_foo.png')
        os.rename("/torntmp/peabrain_foo.png",  self.docroot + fname)
        return  '/' + fname


    def player(self, pid2name, p_id):
        urls = []
        for subject in ('nerve', 'jail', 'total_crime'):
            xx = []
            yy = []
            y2 = []
            nonzero_data = 0
            if 'nerve' == subject:
                self.c.execute("""select et,cur_nerve,max_nerve from readiness where player_id=? order by et""",(p_id,))
                for row in self.c:
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    y2.append(int(row[2]))
                    if row[1] or row[2]:
                        nonzero_data = 1
            elif 'jail' == subject:
                self.c.execute("""select et,jailed from pstats where player_id=? order by et""",(p_id,))
                for row in self.c:
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'total_crime' == subject:
                self.c.execute("""select et,total from playercrimes where player_id=? order by et""",(p_id,))
                for row in self.c:
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            else:
                continue
            if nonzero_data and (len(xx) > 2):
                player_name = '?'
                if str(p_id) in pid2name:
                    player_name = pid2name[str(p_id)]
                player_name = player_name + '[' + str(p_id) + ']'
                graphname = hashlib.sha1(bytes('player-graph-for' + str(p_id) + self.player_dname + subject, 'utf-8')).hexdigest()
                short_fname="player/" + self.player_dname +  "/" +  graphname + ".png"
                urls.append(self.one_graph(xx, yy, y2, short_fname, subject, player_name))
        return urls
