from flask import Flask, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from forms import LoginForm
import base64
import datetime
import hashlib
import hmac
import json
import pandas as pd
import re
import sqlite3
import time
import read_sqlite

re.numeric = re.compile('^[0-9]+$')
token = re.compile('^([-\d]+)([a-z]+)(\d+)-([0-9a-f]+)$')

now = int(time.time())
hmac_key_f = open('/var/torn/hmac_key', 'r')
hmac_key = bytes(hmac_key_f.read(),'utf-8')
hmac_key_f.close()

app = Flask(__name__)

app.config.from_pyfile('config.py')


db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True)   # torn numeric id
    login_allowed = db.Column(db.Integer)              # int used as bool
    must_change_pw = db.Column(db.Integer)             # int used as bool
    pwhash = db.Column(db.String(40))                  # sha1 for now - later a good hash
    pwsalt = db.Column(db.String(10))                  # random string
    registered = db.Column(db.Integer)                 # et account created
    confirmed = db.Column(db.Integer)                  # et confirmed, or 0 if not confirmed
    last_login = db.Column(db.Integer)                 # et
    failed_logins = db.Column(db.Integer)              # reset to 0 on success
    #
    # see  is_authenticated()   is_anonymous()   get_id()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns whole object

# this logs someone out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')
    
#=================================================================================
@app.route('/', methods = ['GET','POST'])
@app.route('/rhubarb/login', methods = ['GET','POST'])
@app.route('/login', methods = ['GET','POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        try:
            u = request.form['username']
            p = request.form['password']
            reject = True # assume rejection
            allowed_login = False
        except:
            print('something failed about reading U and P')
            return render_template('login.html', title='Sign In', form=form)


        # compute each step for constant time operation
        pwhash_given = hashlib.sha1(bytes(p, 'utf-8')).hexdigest()
        wantuser = User.query.filter_by(username = u).first()
        if not wantuser:
            # unknown username
            if not re.numeric.match(u):
                u = 'bad username (must be all numeric)'
            return render_template('bad_login.html', title='bad login attempt', u=u)

        try:
            lastt =  wantuser.last_login
            nfail =  wantuser.failed_logins
            # XXX use constant-time compare
            if wantuser.login_allowed and (pwhash_given == wantuser.pwhash):
                reject = False
        except:
            return render_template('login.html', title='Sign In', form=form)

        if not reject:
            wantuser.last_login  = int(time.time())
            wantuser.failed_logins = 0
            login_user(wantuser)
            db.session.commit()
            if lastt:
                lastt = datetime.datetime.fromtimestamp(lastt)
            else:
                lastt = 'never'
            return render_template('good_login.html', title='successful login', u=u, nfail=nfail, lastt=lastt)

        wantuser.failed_logins += 1
        db.session.commit()
        return render_template('bad_login.html', title='bad login attempt', u=u)

    # form submission failed - show login page again
    return render_template('login.html', title='Sign In', form=form)

#=================================================================================
@app.route('/rhubarb/register', methods = ['GET','POST'])
@app.route('/register', methods = ['GET','POST'])
def register():
    form = LoginForm()

    if form.validate_on_submit():
        try:
            u = request.form['username']
            p = request.form['password']
            reject = True # assume rejection
            allowed_login = False
        except:
            print('something failed about reading U and P')
            return render_template('register', title='Register new account', form=form)

        # is username numeric?
        if not re.numeric.match(u):
            return render_template('accounts_explained.html', title='Accounts Explained')
        # does user already exist?
        wantuser = User.query.filter_by(username = u).first()
        if wantuser:
            return "That username is already in use."
        # is pw acceptable?
        #  newu = User (id=1, username=str(u), login_allowed=0, must_change_pw=0, pwsalt='abc',pwhash='qwert', registered=et, confirmed=0, last_login=0, failed_logins=0)
        #  db.session.add(newu)
        #  db.session.commit()
        # set challenge

        return render_template('accounts_explained.html', title='Accounts Explained')

#=================================================================================

@app.route("/rhubarb/unknown_pw_reset/<username>", methods=['GET','POST'])
@app.route("/unknown_pw_reset/<username>", methods=['GET','POST'])
def unknown_pw_reset(username):
    return "password reset TBC"

@app.route("/rhubarb/settings", methods=['GET','POST'])
@app.route("/settings", methods=['GET','POST'])
@login_required
def settings():
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']
    return render_template('settings.html', title='Tornutopia Settings', u=u, name=name)

#=================================================================================

@app.route('/rhubarb/faction_ov')
@app.route('/faction_ov')
@login_required
def faction_ov():
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = True if ((int(current_user.username) == faction_sum['leader']) or (int(current_user.username) == faction_sum['coleader'] ) ) else False
    return render_template('faction_ov.html', title='Faction Overview', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader)

#=================================================================================

@app.route('/rhubarb/faction_player_table')
@app.route('/faction_player_table')
@login_required
def faction_player_table():
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = True if ((int(current_user.username) == faction_sum['leader']) or (int(current_user.username) == faction_sum['coleader'] ) ) else False
    pt = rodb.get_player_table(faction_sum) # take advantage of having looked this up already
    return render_template('faction_player_table.html', title='Faction Player Table', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader, pt=pt)

#=================================================================================

@app.route('/rhubarb/home')
@app.route('/home')
@login_required
def home():
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = True if ((int(current_user.username) == faction_sum['leader']) or (int(current_user.username) == faction_sum['coleader'] ) ) else False
    return render_template('home.html', title='home', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader)


@app.route("/rhubarb/graph/<what_graph>", methods=['GET'])
@app.route("/graph/<what_graph>", methods=['GET'])
def jsgraph(what_graph):
    p_id = None
    graph_type = None
    timestamp = None
    given_hmac = None
    df = None

    # what graph is this meant to produce?
    re_object = token.match(what_graph)
    if re_object:
        p_id = re_object.group(1)
        graph_type = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        print("RE did not match URL")
        return render_template("bad_graph_request.html")

    # calc correct hmac
    if 'crime' == graph_type:
        graph_selection = ( str(p_id) + 'crime' + str(timestamp) ).encode("utf-8")
    elif 'drug' == graph_type:
        graph_selection = ( str(p_id) + 'drug' + str(timestamp) ).encode("utf-8")
    else:
        return render_template("bad_graph_request.html")
    hmac_hex = hmac.new(hmac_key, graph_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        print("HMAC disagreement")
        return render_template("bad_graph_request.html")
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < now):
        print("timestamp is old:", timestamp)
        return render_template("bad_graph_request.html")

    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    if 'crime' == graph_type:
        parm = (int(p_id),)
        df = pd.read_sql_query("select et,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where player_id=? order by et", conn, params=parm)
    elif 'drug' == graph_type:
        parm = (int(p_id),)
        df = pd.read_sql_query("select et,cantaken,exttaken,lsdtaken,opitaken,shrtaken,pcptaken,xantaken,victaken,spetaken,kettaken from drugs where player_id=? order by et", conn, params=parm)
    else:
        conn.close()
        return render_template("bad_graph_request.html")
    conn.close()

    # Does df contain reasonable data? TODO
    print("LEN DF", len(df))

    # convert et to date-as-string so it can be parsed in JS
    df['et'] = pd.to_datetime(df['et'],unit='s').astype(str)

    chart_data = df.to_dict(orient='records')
    data = {'chart_data': chart_data}

    if 'crime' == graph_type:
        return render_template("playercrimes.html", data=data)
    elif 'drug' == graph_type:
        return render_template("drug.html", data=data)
    else:
        return render_template("bad_graph_request.html")


@app.route("/rhubarb/attack/<player_role_t>", methods=['GET'])
@app.route("/attack/<player_role_t>", methods=['GET'])
def combat_events(player_role_t):
    p_id = None
    role = None
    timestamp = None
    given_hmac = None
    df = None

    # what page is this meant to produce, attack or defend?
    re_object = token.match(player_role_t)
    if re_object:
        p_id = re_object.group(1)
        role = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        print("RE did not match URL")
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = ( str(p_id) + role + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        print("HMAC disagreement")
        return render_template("bad_graph_request.html")
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < now):
        print("timestamp is old:", timestamp)
        return render_template("bad_graph_request.html")

    tbefore = int(time.time()) - 3600 # an hour ago
    parm = (int(p_id), tbefore,)
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    if 'attack' == role:
        c.execute("select et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where att_id=? and et<? order by et desc", parm)
    elif 'defend' == role:
        c.execute("select et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where def_id=? and et<? order by et desc", parm)
    else:
        c.close()
        conn.close()
        return render_template("bad_graph_request.html")

    att_count = 0
    items = []
    old_et = 0
    old_att_id = 0
    old_def_id = 0
    for i in c:
        et = i[0]
        if (old_et == et) and (old_att_id == i[2]) and (old_def_id == i[5]):
            continue
        iso_time = datetime.datetime.utcfromtimestamp(et).isoformat()
        items.append( { 'et': iso_time,  'att_name': i[1],  'att_id': i[2], 'verb': i[3], 'def_name': i[4], 'def_id': i[5],  'outcome': i[6]} )
        att_count += 1
        old_et = et
        old_att_id = i[2]
        old_def_id = i[5]
        if 'attack' == role:
            player_name = i[1]
        else:
            player_name = i[4]
    c.close()
    conn.close()
    
    if att_count:
        return render_template("combat_events.html", data=items, role=role, player_name=player_name)
    return render_template("combat_none.html", role=role, player_id=p_id)


if __name__ == "__main__":
    app.run(debug = True)

