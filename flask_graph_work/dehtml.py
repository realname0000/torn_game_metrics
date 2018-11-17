import re

class Dehtml:

    def __init__(self):
        pass

    def html_clean(self,t):
        while 1:
            got = re.search( r'(^.*)</[a-zA-Z0-9 ]*>(.*)$', t)
            if got:
                # want to edit string
                t=got.group(1)+got.group(2)
                continue
    
            got = re.search( r'(^.*)    *(.*)$', t)
            if got:
                # want to edit string
                t=got.group(1)+' '+got.group(2)
                continue
     
            got = re.search( r'(^.*)[\r\n](.*)$', t)
            if got:
                # want to edit string
                t=got.group(1)+' '+got.group(2)
                continue
     
            got = re.search( r'(^.*)<[a-zA-Z0-9" =.?]*>(.*)$', t)
            if got:
                # want to edit string
                t=got.group(1)+got.group(2)
                continue
            else:
                break
        return t
