import os
import subprocess


class Keep:

    def __init__(self, start_pathname):
        self.start_pathname = start_pathname
        self.keep_these = {}
        self.iddict = {}

    def gotid(self, pid):
        self.iddict[pid] = 1

    def showid(self):
        return self.iddict.keys()

    def allow(self, subdirectory):
        self.keep_these[subdirectory] = 1

    def exterminate(self):
        os.chdir(self.start_pathname)
        allfiles = os.listdir('.')
        for fn in allfiles:
            if fn not in self.keep_these:
                subprocess.call(['rm', '-rf', fn], shell=False)
