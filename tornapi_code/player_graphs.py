import matplotlib.pyplot as plt
import datetime
import os
import hashlib


class Draw_graph:

    def __init__(self, docroot, c, var_interval_no, player_dname, old_player_dname):
        self.docroot = docroot
        self.c = c
        self.player_dname = player_dname
        self.old_player_dname = old_player_dname

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

# suposed interactive code
##  fig = plt.figure()
##  plot = fig.add_subplot(111)
##  # create some curves
##  for i in range(4):
##      plot.plot(
##          [i*1,i*2,i*3,i*4],
##          gid=i)
##  
##  def on_plot_hover(event):
##      for curve in plot.get_lines():
##          if curve.contains(event)[0]:
##              print "over %s" % curve.get_gid()
##  
##  fig.canvas.mpl_connect('motion_notify_event', on_plot_hover)           
##  plt.show()


    def player(self, pid2name, p_id):
        urls = []
        for subject in ('nerve', 'drugs', 'total_crime', 'peoplebusted', 'jail', 'organisedcrimes', 'hospital', 'overdose'):
            xx = []
            yy = []
            y2 = []
            y3 = []
            last_x = 0
            nonzero_data = 0
            if 'nerve' == subject:
                self.c.execute("""select et,cur_nerve,max_nerve from readiness where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    y2.append(int(row[2]))
                    if row[1] or row[2]:
                        nonzero_data = 1
            elif 'drugs' == subject:
                self.c.execute("""select et,xantaken,victaken,exttaken from drugs where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    y2.append(int(row[2]))
                    y3.append(int(row[3]))
                    if row[1] or row[2] or row[3]:
                        nonzero_data = 1
            elif 'peoplebusted' == subject:
                self.c.execute("""select et,peoplebusted from pstats where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'jail' == subject:
                self.c.execute("""select et,jailed from pstats where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'total_crime' == subject:
                self.c.execute("""select et,total from playercrimes where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'organisedcrimes' == subject:
                self.c.execute("""select et,oc_read from pstats where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'hospital' == subject:
                self.c.execute("""select et,hosp from pstats where player_id=? order by et""",(p_id,))
                for row in self.c:
                    last_x = int(row[0])
                    xx.append(datetime.date.fromtimestamp(int(row[0])))
                    yy.append(int(row[1]))
                    if row[1]:
                        nonzero_data = 1
            elif 'overdose' == subject:
                self.c.execute("""select et,od from pstats where player_id=? order by et""",(p_id,))
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
                player_name = '?'
                if str(p_id) in pid2name:
                    player_name = pid2name[str(p_id)]
                player_name = player_name + '[' + str(p_id) + ']'
                graphname = hashlib.sha1(bytes('player-graph-for' + str(p_id) + self.player_dname + subject, 'utf-8')).hexdigest()
                short_fname ="player/" + self.player_dname + "/" + graphname + ".png"
                long_fname = self.docroot + short_fname

                # logic around when to write a new graph (supposed to involve less work at new day)
                mtime = 0
                try:
                    mtime = os.stat(long_fname).st_mtime
                except:
                    try:
                        # new file does not exist, test for the old one
                        old_graphname = hashlib.sha1(bytes('player-graph-for' + str(p_id) + self.old_player_dname + subject, 'utf-8')).hexdigest()
                        old_short_fname ="player/" + self.old_player_dname + "/" + old_graphname + ".png"
                        old_long_fname = self.docroot + old_short_fname
                        mtime = os.stat(old_long_fname).st_mtime
                        # older graph exists
                        os.link(old_long_fname, long_fname) # reuse the old file
                    except:
                        # old and new files both missing
                        pass
                if mtime <= last_x:
                    urls.append('/' + short_fname)
                    try:
                        new_graph = self.one_graph(xx, yy, y2, short_fname, subject, player_name)
                    except:
                        print('failed to write player graph for', str(p_id), subject)
                urls.append('/' + short_fname)
        return urls
