#!/usr/bin/python3

import hashlib
import bcrypt
import base64

def future():
    return 2

def pwhash(ver, pw):
    if 0 == ver:
        ver = future()
    if 1 == ver:
        # unsalted sha1
        return ver, hashlib.sha1(bytes(pw, 'utf-8')).hexdigest()
    elif 2 == ver:
        # The bcrypt algorithm only handles passwords up to 72
        # characters, any characters beyond that are ignored. To
        # work around this, a common approach is to hash a password
        # with a cryptographic hash (such as sha256) and then base64
        # encode it to prevent NULL byte problems before hashing
        # the result with bcrypt:
        password = base64.b64encode(hashlib.sha256(pw.encode('utf-8')).digest())
        salt = bcrypt.gensalt(rounds=12, prefix=b'2b')
        h = bcrypt.hashpw(password, salt)
        h64 = base64.b64encode(h).decode('utf-8')
        return ver, h64
    else:
        return None

def checkpw(ver, pw, pwhash):
    if 1 == ver:
        # unsalted sha1
        given = hashlib.sha1(bytes(pw, 'utf-8')).hexdigest()
        return True if (given == pwhash) else False
    elif 2 == ver:
        # bcrypt
        password = base64.b64encode(hashlib.sha256(pw.encode('utf-8')).digest())
        pwhash = base64.b64decode(pwhash)
        return bcrypt.checkpw(password, pwhash)
    else:
        return None


if __name__ == "__main__":
    for foo in ['a','ab','abc','longerpasswordhere','baigighouholihoiyh80yfgjaklj;lwjpiwyyudfhjgwgiwgyigfi', 'Bhtwhwnq8yhbq']:
        v,h64 = pwhash(0,foo)
        test = checkpw(v,foo, h64)
        print(test, foo, h64)
