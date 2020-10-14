import logging
import logging.handlers
from flask import Flask, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from forms import LoginForm, PaymentForm, PasswordForm, OccalcForm, ApikeyForm, DeleteForm, RegisterForm, OCpolicyForm, LeaderForm, EnemyForm, TimeForm, DeleteEnemyForm, AddEnemyForm
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
import dehtml
import random
import password
import challenge

re.numeric = re.compile('^[0-9]+$')
token = re.compile('^([-\d]+)([a-z]+)(\d+)-([0-9a-f]+)$') # used for graphs
combat_token = re.compile('^([-\d]+)-([-\d]+)([a-z]+)(\d+)-([0-9a-f]+)$') # used for combat events
bonus_token = re.compile('^([-\d]+)-([-\d]+)bonus(\d+)-([0-9a-f]+)$') # used for chain bonus record
armory_token = re.compile('^([-\d]+)-(\d+)-([0-9a-f]+)$')
enemy_token = re.compile('^([-\d]+)-(\d+)-(\d+)-([0-9a-f]+)$')
target_token = re.compile('^([-\d]+)-(\d+)-(\d+)-(\d+)-([0-9a-f]+)$')
time_interval = re.compile('^(\d+)-(\d+)$')
# f_id, crimetype, timestamp, (either number or 'history'),  hmac
oc_history_picker = re.compile('^([-\d]+)-([0-9])-([0-9]+)-([0-9a-z]+)-([0-9a-f]+)$')
chain_token = re.compile('^(\d+)-chain-(\d+)-(\d+)-([0-9a-f]+)$')
chain_token_o = re.compile('^(\d+)-scoreboard-(\d+)-(\d+)-([0-9a-f]+)-([a-z]+)$')  # with ordering parameter

now = int(time.time())

# Now there is just one way to read this.
rodb = read_sqlite.Rodb()
hmac_key = rodb.getkey()
rodb = None

app = Flask(__name__)

app.config.from_pyfile('config.py')

loghandler = logging.handlers.RotatingFileHandler('/home/peabrain/logs/tu0036.log', maxBytes=1024 * 1024, backupCount=10)
loghandler.setLevel(logging.INFO)
app.logger.setLevel(logging.INFO)
app.logger.addHandler(loghandler)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

class LUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True)   # torn numeric id
    login_allowed = db.Column(db.Integer)              # int used as bool
    must_change_pw = db.Column(db.Integer)             # int used as bool
    pwhash = db.Column(db.String(255))                 # a hash
    registered = db.Column(db.Integer)                 # et account created
    confirmed = db.Column(db.Integer)                  # et confirmed, or 0 if not confirmed
    last_login = db.Column(db.Integer)                 # et
    failed_logins = db.Column(db.Integer)              # reset to 0 on success
    pw_ver = db.Column(db.Integer)                     # 1=sha1, 2=bcrypt
    #
    # see  is_authenticated()   is_anonymous()   get_id()

class Payment_cache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faction_id = db.Column(db.Integer)
    oc_plan_id = db.Column(db.Integer)
    timestamp = db.Column(db.Integer)
    paid_by = db.Column(db.Integer)

class Report_number_oc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Integer)
    pid = db.Column(db.Integer)
    number_oc = db.Column(db.Integer)

class Banned_pw(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sha = db.Column(db.String(40))    # sha1 of a prohibited pw

class Apikey_history(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    et_web_update = db.Column(db.Integer)
    deleted = db.Column(db.Integer)

class Ocpolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faction = db.Column(db.Integer)
    timestamp = db.Column(db.Integer)
    percent = db.Column(db.Numeric(6,2))
    username = db.Column(db.String(30))
    octype = db.Column(db.Integer)

class Extra_leaders(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    et = db.Column(db.Integer)
    faction_id = db.Column(db.Integer)
    player_id = db.Column(db.Integer)
    is_leader = db.Column(db.Integer)
    set_by = db.Column(db.Integer)


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    et = db.Column(db.Integer)
    expires = db.Column(db.Integer)
    used = db.Column(db.Integer)
    username = db.Column(db.String(30), unique=True)   # torn numeric id
    action = db.Column(db.String(20))
    data = db.Column(db.String(60))
    pw_ver = db.Column(db.Integer)
    pw_ver = db.Column(db.Integer)
    chal_type = db.Column(db.String(10))
    expect = db.Column(db.String(40))


class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    et = db.Column(db.Integer)
    used = db.Column(db.Integer)
    username = db.Column(db.String(30), unique=True)   # torn numeric id
    chal_type = db.Column(db.String(10))
    provided = db.Column(db.String(40))

class Enemy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tornid = db.Column(db.String(30))   # torn numeric id
    username = db.Column(db.String(30))
    f_id = db.Column(db.Integer)

class Timerange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tstart = db.Column(db.Integer)
    tend = db.Column(db.Integer)
    f_id = db.Column(db.Integer)

class Chains(db.Model):
    pg_chain_id = db.Column(db.Integer, primary_key=True)
    f_id = db.Column(db.Integer)
    et = db.Column(db.Integer)
    chain_len = db.Column(db.Integer)
    tstart = db.Column(db.Integer)
    tend = db.Column(db.Integer)
    torn_chain_id = db.Column(db.Integer)
    respect = db.Column(db.String(16))

class Chain_player_sum(db.Model):
    pk = db.Column(db.Integer, primary_key=True)
    pg_chain_id    = db.Column(db.Integer)
    player_id      = db.Column(db.Integer)
    actions        = db.Column(db.Integer)
    attacked       = db.Column(db.Integer)
    hospitalized   = db.Column(db.Integer)
    mugged         = db.Column(db.Integer)
    respect        = db.Column(db.Integer)
    att_stale      = db.Column(db.Integer)
    lost           = db.Column(db.Integer)
    att_escape     = db.Column(db.Integer)
    def_stale      = db.Column(db.Integer)
    defend         = db.Column(db.Integer)
    def_escape     = db.Column(db.Integer)

class Chain_members(db.Model):
    mempk        = db.Column(db.Integer, primary_key=True)
    pg_chain_id  = db.Column(db.Integer)
    player_id    = db.Column(db.Integer)
    player_name  = db.Column(db.String(16))

class Bonus_events(db.Model):
    bonus_pk_id    = db.Column(db.Integer, primary_key=True)
    pg_chain_id    = db.Column(db.Integer)
    et             = db.Column(db.Integer)
    att_name       = db.Column(db.String(16))
    att_id         = db.Column(db.Integer)
    verb           = db.Column(db.String(16))
    def_name       = db.Column(db.String(16))
    def_id         = db.Column(db.Integer)
    outcome        = db.Column(db.String(20))
    num_respect    = db.Column(db.Numeric(12,4))


@login_manager.user_loader
def load_user(user_id):
    return LUser.query.get(int(user_id)) # returns whole object

# this logs someone out
@app.route('/logout')
def logout():
    logout_user()
    return redirect('/')
    
#=================================================================================
def obtain_leaders_for_faction(pid, fid):
    # extra leaders from ORM
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(pid)

    extra = {faction_sum['leader']: [1, 1, faction_sum['leadername'], 'Torn', 'mists of time'],   faction_sum['coleader']: [1, 1, faction_sum['coleadername'], 'Torn', 'mists of time']}

    leader_orm = {}
    extras = Extra_leaders.query.filter_by(faction_id = fid).all()
    for leader in extras:
        pid = leader.player_id
        if (not pid in leader_orm) or (leader.et > leader_orm[pid][1]):
            leader_orm[leader.player_id] = [leader.is_leader, leader.et, rodb.pid2n[str(pid)], rodb.pid2n[str(leader.set_by)], time.strftime("%Y-%m-%d %H:%M",time.gmtime(leader.et))]
    # only the players with a 1 for is_leader from their latest record in ORM and the two recignised by Torn
    for kl in leader_orm.keys():
        if leader_orm[kl][0]: extra[kl] = leader_orm[kl]

    return extra
#=================================================================================
def bool_leader(pid, fid):
    leaders = obtain_leaders_for_faction(pid, fid)
    return  pid in leaders
#=================================================================================
@app.route('/', methods = ['GET','POST'])
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
            app.logger.info('error reading from login form')
            return render_template('login.html', title='Sign In', form=form)

        wantuser = LUser.query.filter_by(username = u).first()
        if not wantuser:
            # unknown username
            if not re.numeric.match(u):
                u = 'bad username (must be all numeric)'
            return render_template('bad_login.html', title='bad login attempt', u=u)

        try:
            lastt = wantuser.last_login
            nfail = wantuser.failed_logins
            hash_version = wantuser.pw_ver
        except:
            return "failed somehow"
            return render_template('login.html', title='Sign In', form=form)

        if wantuser.login_allowed and password.checkpw(hash_version, p, wantuser.pwhash):
            reject = False

        if not reject:
            wantuser.last_login  = int(time.time())
            wantuser.failed_logins = 0
            login_user(wantuser)
            db.session.commit()
            if lastt:
                lastt = datetime.datetime.fromtimestamp(lastt)
            else:
                lastt = 'never'
            app.logger.info('%s logged in successfully', u)
            for rh in request.headers:
                app.logger.info('%s had request header %s', u, rh)
            return render_template('good_login.html', title='successful login', u=u, nfail=nfail, lastt=lastt, must_change_pw=wantuser.must_change_pw)

        wantuser.failed_logins += 1
        db.session.commit()
        return render_template('bad_login.html', title='bad login attempt', u=u)

    # show form before submission
    return render_template('login.html', title='Sign In', form=form)

#=================================================================================
# This is for testing flask without the web server.
@app.route("/rhubarb/<anything_here>", methods=['GET'])
def no_rhubarb(anything_here):
    return redirect('/' + anything_here)
#=================================================================================
@app.route('/register', methods = ['GET','POST'])
def register():
    form = RegisterForm()
    u = 'default-u'
    p = 'default-p'
    c = 'default-c'

    if form.validate_on_submit():
        try:
            u = request.form['username']
            p = request.form['password']
            c = request.form['checkbox']
        except:
            return render_template('register.html', title='Register', form=form, retry=True)

        # is username numeric?
        if not re.numeric.match(u):
            return render_template('accounts_explained.html', title='Accounts Explained')
        # does user already exist?
        wantuser = LUser.query.filter_by(username = u).first()
        if wantuser:
            return render_template('message.html', message='That username is already in use.  If already registered and confirmed use login.  Or wait for a past registration attempt to expire and retry.', logged_in=False)
        # is pw acceptable?
        if not test_strength(p):
            return render_template('message.html', message='That password is not allowed - too obvious.', logged_in=False)
        # is cookie consent on?
        if c != 'yes':
            return render_template('message.html', title='Message', message='Consent to a cookie (for a logged-in session) is required.', logged_in=False)
        pw_ver, pwhash = password.pwhash(0, p)
        et = int(time.time())
        newu = LUser (username=str(u), login_allowed=0, must_change_pw=0, pw_ver=pw_ver, pwhash=pwhash, registered=et, confirmed=0, last_login=0, failed_logins=0)
        db.session.add(newu)
        db.session.commit()
        # set challenge to be done before confirmed is set
        new_random_challenge = challenge.Challenge()
        expected = 'NEWUSER:' + new_random_challenge.get_rfc1760_challenge()
        newc = Challenge(et=et, expires=et+900, used=0, username=u, action='newuser', data='', chal_type='message', expect=expected, pw_ver=pw_ver)
        db.session.add(newc)
        db.session.commit()
        return render_template('challenge.html', title='In-game challenge', challenge=expected)

    return render_template('register.html', title='Register', form=form, retrry=False)

#=================================================================================

# This is not the same as "settings" change when pw is known.
@app.route("/rhubarb/unknown_pw_reset", methods=['GET','POST'])
@app.route("/unknown_pw_reset", methods=['GET','POST'])
def unknown_pw_reset():
    form = LoginForm() # requests username and password

    # - - - - - - -  POST section
    if request.method == 'POST':
        u = None
        p = None
        if form.validate_on_submit():
            try:
                u = request.form['username']
                p = request.form['password']
                # another job either uses or discards the data provided here
            except:
                app.logger.info('error reading from login form for pw reset')
                return redirect('/rhubarb/unknown_pw_reset')
        else:
            app.logger.info('change_pw form fails validation')
            return redirect('/rhubarb/unknown_pw_reset')

        if not test_strength(p):
            return render_template('message.html', message='That password is not allowed - too obvious.', logged_in=False)

        ban_digest = hashlib.sha1(bytes(p, 'utf-8')).hexdigest()
        ban = Banned_pw(sha = ban_digest)
        db.session.add(ban)
        db.session.commit()

        # rate limit - not too many of these allowed at once
        rate_discovery = Challenge.query.filter_by(username = u).all()
        if len(rate_discovery) > 10:
            return render_template('message.html', message='Too many reset attempts - need to wait.', logged_in=False)

        # set challenge to be done before applied to l_user table
        new_random_challenge = challenge.Challenge()
        expected = 'PWRESET:' + new_random_challenge.get_rfc1760_challenge()
        et = int(time.time())
        pw_ver, pwhash = password.pwhash(0, p)
        newc = Challenge(et=et, expires=et+900, used=0, username=u, action='pwreset', data=pwhash, pw_ver=pw_ver, chal_type='message', expect=expected)
        db.session.add(newc)
        db.session.commit()
        return render_template('challenge.html', title='In-game challenge', challenge=expected)
    # - - - - - - -  POST section

    return render_template('pw_reset.html', form=form)

#=================================================================================

@app.route("/settings", methods=['GET'])
@login_required
def settings():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']

    # check whether API key has worked recently for player
    # XXX and faction
    #  et_pstats, et_set, short_err, long_err
    got_key = [0,0]
    ak_stats = list(rodb.has_api_key(u)) # simple numeric values
    if ak_stats[0]:
        got_key[0] = 1

    # compare to ORM
    not_obsolete = 1 # assume sqlite is current then check whether there is a more recent psql
    wantevent = Apikey_history.query.filter_by(username = u).first()
    if wantevent:
        if wantevent.et_web_update > ak_stats[1]:
            not_obsolete = 0 # psql more recent
        if wantevent.deleted:
            got_key[0] = 0

    # massage for human readability
    if ak_stats[0] and ak_stats[3]:
        if ak_stats[3] < ak_stats[0]:
            # error has been fixed
            ak_stats[3] = 0
        else:
            # problem been seen
            got_key[1] = 1
        if ak_stats[2] < ak_stats[0]:
            # error has been fixed
            ak_stats[2] = 0
        else:
            # problem been seen
            got_key[1] = 1

    ak_stats[0] = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ak_stats[0]))
    ak_stats[1] = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ak_stats[1]))

    oc_calc_sr = 0
    want_oc = Report_number_oc.query.filter_by(pid = u).all()
    for i in want_oc:
        if player['oc_calc'] != i.number_oc:
            oc_calc_sr = i.number_oc # self-reported number

    return render_template('settings.html', title='Tornutopia Settings', u=u, name=name, player=player, oc_calc_sr=oc_calc_sr, got_key=got_key, ak_stats=ak_stats, not_obsolete=not_obsolete)
#=================================================================================

@app.route("/change_pw", methods=['GET','POST'])
@login_required
def change_pw():
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']
    form = PasswordForm()

    # - - - - - - -  POST section
    if request.method == 'POST':
      old_pw = None
      new_pw = None
      if form.validate_on_submit():
          try:
              old_pw = request.form['old_password']
              new_pw = request.form['new_password']
          except:
              app.logger.info('error reading from change_pw form')
              return redirect('/rhubarb/change_pw')
      else:
          app.logger.info('change_pw form fails validation')
          return redirect('/rhubarb/change_pw')

      # is old pw correct?
      wantuser = LUser.query.filter_by(username = u).first()
      if not wantuser:
          # should never happen - has this user been deleted while logged in?
          return redirect('/rhubarb/logout') 
      if not password.checkpw(wantuser.pw_ver, old_pw, wantuser.pwhash):
          return render_template('message.html', message='old password incorrect', logged_in=True)
      # is new pw acceptable?
      if not test_strength(new_pw):
          return render_template('message.html', message='That password is not allowed - too obvious.', logged_in=True)
      # set new pwhash for u and show success
      v,h = password.pwhash(0, new_pw)
      if not v or not h:
          return render_template('message.html', message='failure to handle new password', logged_in=True)
      # set new password and add to banned list
      wantuser.pw_ver = v
      wantuser.pwhash = h
      wantuser.must_change_pw = 0
      db.session.commit()
      ban_digest = hashlib.sha1(bytes(new_pw, 'utf-8')).hexdigest()
      ban = Banned_pw(sha = ban_digest)
      db.session.add(ban)
      db.session.commit()
      return render_template('message.html', message='password changed', logged_in=True)
    # - - - - - - -  POST section

    return render_template('set_pw.html', title='Tornutopia Settings', u=u, name=name, player=player, form=form)

#=================================================================================

@app.route("/set_oc_calc", methods=['GET','POST'])
@login_required
def set_oc_calc():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']
    number_oc = 0
    form = OccalcForm()

    if request.method == 'POST':
      if form.validate_on_submit():
          try:
              number_oc = request.form['number_oc']
          except:
              return render_template('message.html', message='Something failed about reading from occalcform.', logged_in=True)
      else:
          app.logger.info('set_oc_calc form fails validation')
          return render_template('message.html', message='Form fails validation.', logged_in=True)
      if int(number_oc) > 0:
          new_id=int(random.random() * 1000000000)
          report_number_oc = Report_number_oc(id=new_id, timestamp=int(time.time()), pid=int(u), number_oc=number_oc)
          db.session.add(report_number_oc)
          db.session.commit()
      return redirect('/rhubarb/settings')

    return render_template('set_oc_calc.html', title='Tornutopia Settings', u=u, name=name, player=player, form=form)

#=================================================================================

@app.route("/delete_api_key", methods=['GET','POST'])
@login_required
def delete_api_key():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')

    new_fname = '/var/torn/spool/collect/' + str(int(random.random() * 1000000000))
    with open(new_fname, 'w') as api_out:
        print("DELETE APIKEY\n" + str(current_user.username) + "\nEND", file=api_out)

    event = Apikey_history(username=str(current_user.username), et_web_update=int(time.time()), deleted=1)
    db.session.add(event)
    db.session.commit()

    return render_template('message.html', message='accepted command to delete API key', logged_in=True)

#=================================================================================
@app.route("/set_api_key", methods=['GET','POST'])
@login_required
def set_api_key():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']
    form = ApikeyForm()

    # - - - - - - -  POST section
    if request.method == 'POST':
      if form.validate_on_submit():
        try:
             apikey = request.form['apikey']
             use_for_faction = request.form['use_for_faction']
        except:
             return render_template('message.html', message='something failed about reading', logged_in=True)
      else:
          app.logger.info('error reading from ApikeyForm')
          return render_template('message.html', message='ApikeyForm fails validation.', logged_in=True)
      new_fname = '/var/torn/spool/collect/' + str(int(random.random() * 1000000000))
      with open(new_fname, 'w') as api_out:
          print("APIKEY\n" + apikey + '\n' + str(use_for_faction) + "\nEND", file=api_out)

      event = Apikey_history(username=str(current_user.username), et_web_update=int(time.time()), deleted=0)
      db.session.add(event)
      db.session.commit()
      return redirect('/rhubarb/settings') 
    # - - - - - - -  POST section

    return render_template('set_api_key.html', title='Tornutopia Settings', u=u, name=name, player=player, form=form)
#=================================================================================
@app.route("/delete_account", methods=['GET','POST'])
@login_required
def delete_account():
    u =  current_user.username
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    name = player['name']
    form = DeleteForm()

    # - - - - - - -  POST section
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                pw = request.form['password']
            except:
                return render_template('message.html', title='Delete Failed', message='something failed about reading from deleteform', logged_in=False)
        else:
            app.logger.info('delete_account form fails validation')
            return redirect('/rhubarb/settings')

        wantuser = LUser.query.filter_by(username = u).first()
        if not wantuser:
            return render_template('message.html', title='Delete Failed', message='user to be deleted cannot be found', logged_in=False)
        # check password
        if not password.checkpw(wantuser.pw_ver, pw, wantuser.pwhash):
            return render_template('message.html', title='Delete Failed', message='wrong password', logged_in=True)
        db.session.delete(wantuser)
        db.session.commit()
        return redirect('/rhubarb/logout') 
    # - - - - - - -  POST section

    return render_template('delete_account.html', title='Tornutopia Settings', u=u, name=name, player=player, form=form)

#=================================================================================

@app.route('/faction_ov')
@login_required
def faction_ov():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    big_losses = rodb.recent_big_losses(faction_sum['fid'])
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    friendly_fires = rodb.get_friendly_fire(faction_sum['fid'])

    # extra leaders from ORM
    extra = obtain_leaders_for_faction(current_user.username, faction_sum['fid'])

    return render_template('faction_ov.html', title='Faction Overview', u=current_user.username, player=player, faction_sum=faction_sum,
                           is_leader=is_leader, friendly_fires=friendly_fires, extra=extra, nrbl=len(big_losses), big_losses=big_losses)
#=================================================================================
@app.route('/leaders', methods=['GET','POST'])
@login_required
def leaders():
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    extra = obtain_leaders_for_faction(current_user.username, faction_sum['fid'])

    form = LeaderForm()
    #
    form.player_demote.choices = [(0, 'no selection')]
    for eleader in extra:
        form.player_demote.choices.append((eleader, extra[eleader][2]))
    #
    form.player_promote.choices = [(0, 'no selection')]
    for pid in sorted(faction_sum['members']):
        # members of this faction, and only if they are not leaders already
        if not bool_leader(int(pid), faction_sum['fid']):
            form.player_promote.choices.append((pid, rodb.pid2n[pid]))

    # - - - - - - -  POST section
    if request.method == 'POST':
        if not is_leader:
            return redirect('/rhubarb/logout') 
        player_demote = None
        player_promote = None
        #
        if form.is_submitted():
            try:
                player_demote = request.form['player_demote']
            except:
                pass
            try:
                player_promote = request.form['player_promote']
            except:
                pass
        else:
            return render_template('message.html', title='Change leaders', message='validation of LeaderForm failed', logged_in=True)

        # player_demote and player_promote are str and '0' is a valid value meaning no selection.
        if not player_demote or not player_promote:
            return render_template('message.html', title='Change leaders', message='valid input not detected', logged_in=True)

        now = int(time.time())
        if player_demote != '0':
            dl = Extra_leaders(et=now, faction_id=int(faction_sum['fid']), player_id=int(player_demote), is_leader=0, set_by=int(current_user.username))
            db.session.add(dl)
        if player_promote != '0':
            pl = Extra_leaders(et=now, faction_id=int(faction_sum['fid']), player_id=int(player_promote), is_leader=1, set_by=int(current_user.username))
            db.session.add(pl)
        db.session.commit()
        return redirect('/rhubarb/faction_ov')
    # - - - - - - -  POST section

    return render_template('leaders.html', title='Leader Appointment', faction_sum=faction_sum, is_leader=is_leader, form=form)
#=================================================================================
@app.route('/pay_policy', methods=['GET','POST'])
@login_required
def pay_policy():
    rodb = read_sqlite.Rodb()
    oc_num2title = rodb.get_oc_titles()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])
    form = OCpolicyForm()
    form.cn.choices = [(k, oc_num2title[k]) for k in sorted(oc_num2title.keys())]

    # - - - - - - -  POST section
    if request.method == 'POST':
        if not is_leader:
            return redirect('/rhubarb/logout') 
        if form.validate_on_submit():
            try:
                cn = request.form['cn']
                percent = request.form['percent']
            except:
                app.logger.info('error involving OCpolicyForm')
                return render_template('message.html', title='change to pay policy', message='OCpolicyForm exception reading input', logged_in=True)
        else:
            app.logger.info('OCpolicyForm fails validation')
            return render_template('message.html', title='change to pay policy', message='OCpolicyForm failed validation', logged_in=True)

        try:
            policy_update = Ocpolicy(faction=int(faction_sum['fid']), timestamp=int(time.time()), percent=percent, username=current_user.username, octype=cn)
            db.session.add(policy_update)
            db.session.commit()
        except:
            app.logger.info('error inserting ino Ocpolicy ORM')
            return render_template('message.html', title='change to pay policy', message='Change of pay policy failed to update DB.', logged_in=True)
        return redirect('/rhubarb/pay_policy') 
    # - - - - - - -  POST section

    # read policy from sqlite
    read_policy = rodb.get_oc_payment_policy(faction_sum['fid'])
    policy = {} # mutable to produce human-readable times
    for k in sorted(read_policy.keys()):
        et = read_policy[k][0]
        policy[k] = list(read_policy[k])
        policy[k][0] = time.strftime("%Y-%m-%d %H:%M",time.gmtime(et))
        if str(read_policy[k][3]) in rodb.pid2n:
            policy[k][3] = rodb.pid2n[ str(read_policy[k][3]) ]
    # check the orm for a cached alteration to the figures from sqlite
    pending = 0
    want_policy_change = Ocpolicy.query.filter_by(faction = faction_sum['fid']).all()
    for pol_item in want_policy_change:
        if pol_item.octype not in policy:
            pending=1
            break
        if float(pol_item.percent) != float(policy[pol_item.octype][2]):
            pending=1
            break

    return render_template('pay_policy.html', title='Pay Policy', u=current_user.username, is_leader=is_leader, policy=policy, oc_num2title=oc_num2title, pending=pending, form=form)
#=================================================================================

@app.route('/faction_player_table')
@login_required
def faction_player_table():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])
    if not is_leader:
        return render_template('message.html', title='Faction Player Table Denied', u=current_user.username, player=player, message='No access to player table!', logged_in=True)
    pt = rodb.get_player_table(faction_sum) # take advantage of having looked this up already
    return render_template('faction_player_table.html', title='Faction Player Table', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader, pt=pt)

#=================================================================================

@app.route('/home')
@login_required
def home():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])
    f_id = faction_sum['fid']
    p_id = int(current_user.username)

    # what do we know about this player being a leader?
    maybe_leader = Extra_leaders.query.filter_by(faction_id = int(faction_sum['fid'])).filter_by(player_id = int(current_user.username)).all()
    leader_entry = False
    et = 0
    set_by = None
    any_data = False
    for ml in maybe_leader:
        if ml.et > et:
            any_data = True
            et = ml.et
            set_by = ml.set_by
            leader_entry = True if ml.is_leader else False
    if any_data:
        leader_record  = [any_data, leader_entry, time.strftime("%Y-%m-%d %H:%M",time.gmtime(et)), rodb.pid2n[str(set_by)]]
    else:
        leader_record  = [any_data, False, 'never', '']

    payment_due = []
    if is_leader:
        payment_due = rodb.oc_payment_check(faction_sum['fid'])

    return render_template('home.html', title='home', u=current_user.username,
            player=player, faction_sum=faction_sum, is_leader=is_leader,
            leader_record=leader_record, payment_due=payment_due)

#=================================================================================

@app.route("/rhubarb/graph/<what_graph>", methods=['GET'])
@app.route("/graph/<what_graph>", methods=['GET'])
def jsgraph(what_graph):
    p_id = None
    graph_type = None
    timestamp = None
    given_hmac = None
    df = None
    right_now = int(time.time())

    # what graph is this meant to produce?
    re_object = token.match(what_graph)
    if re_object:
        p_id = re_object.group(1)
        graph_type = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        app.logger.info('in jsgraph RE did not match URL')
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
        app.logger.info('in jsgraph HMAC disagreement')
        return render_template("bad_graph_request.html")
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        app.logger.info('in jsgraph timestamp is old')
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

#=================================================================================

@app.route("/rhubarb/faction_oc_history/<tid_cn_t>", methods=['GET','POST'])
@app.route("/faction_oc_history/<tid_cn_t>", methods=['GET','POST'])
@login_required
def faction_oc_history(tid_cn_t):
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')
    # fid, cn, history-or-et
    percent_to_pay = 0
    cu =  current_user.username
    logged_in = True
    tid = None
    cn = None
    timestamp = None
    history_column = None
    hmac_given = None
    re_object = oc_history_picker.match(tid_cn_t)
    if re_object:
        tid = re_object.group(1)
        cn = re_object.group(2)
        timestamp = re_object.group(3)
        history_column = re_object.group(4)
        hmac_given = re_object.group(5)
    else:
        return render_template('message.html', message='failed to discover the history intended by this click', logged_in=logged_in)
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    # check time and hmac
    right_now = int(time.time())
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='link expired; cannot use it', logged_in=logged_in)
    # either show all the data (up to the last year) or just a recent extract
    long_search = False
    if history_column == 'history':
        long_search = True
        flask_parm = (str(tid) + '-' + str(cn) + '-' + str(timestamp) + '-history' ).encode("utf-8")
    else:
        flask_parm = (str(tid) + '-' + str(cn) + '-' + str(timestamp)).encode("utf-8")
        # read the payment policy of this faction (e.g. pay 20% of PA winnings to each player)
        oc_percentages = rodb.get_oc_payment_policy(tid)
        if int(cn) in oc_percentages:
            percent_to_pay = oc_percentages[int(cn)][2]
    hmac_hex_hist = hmac.new(hmac_key, flask_parm, digestmod=hashlib.sha1).hexdigest()
    if not hmac_hex_hist == hmac_given:
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=logged_in)

    form = PaymentForm()

    # - - - - - - -  POST section
    if request.method == 'POST':
        if not is_leader:
            return redirect('/rhubarb/logout') 
        if form.validate_on_submit():
            try:
                form_faction = request.form['faction_id']
                ocp = request.form['oc_plan_id']
            except:
                app.logger.info('error involving paymentform')
                return redirect('/rhubarb/faction_ov')
        else:
            app.logger.info('paymentform fails validation')
            return redirect('/rhubarb/faction_ov')
        # write to ORM payment for (form_faction,ocp) by current user at now
        new_pay_id=int(random.random() * 1000000000)
        pay = Payment_cache(id=new_pay_id, faction_id=int(tid), oc_plan_id=int(ocp), timestamp=int(time.time()), paid_by=int(cu))
        db.session.add(pay)
        db.session.commit()
        return redirect('/rhubarb/faction_oc_history/' + tid_cn_t) 
    # - - - - - - -  POST section

    player = {'name':'no name'}
    if int(cn):
        try:
            faction_sum = rodb.get_faction_for_player(current_user.username)
            if not faction_sum['fid'] == int(tid):
                # viewing from outside faction
                return render_template('message.html', message='organised crime data - need to be logged in and in the faction to see that', logged_in=logged_in)
        except:
            # viewing from outside faction
            return render_template('message.html', message='organised crime data - need to be logged in and in the faction to see that', logged_in=logged_in)
    else:
        # This is a player request and not a faction request - indicated by crime number 0.
        # no need to authenticate the user but we do want the name
        player = rodb.get_player_data(tid)


    # This is the file with Payment_cache defined.  Read ORM here and pass details to rodb.get_oc()
    payment_query = db.session.query(Payment_cache).filter(Payment_cache.faction_id == tid)
    want_payment = payment_query.all()
    cached_payments = {}
    for cached in want_payment:
        cached_payments[cached.oc_plan_id] = {'paid_at':cached.timestamp, 'paid_by':cached.paid_by}

    try:
        octable, future = rodb.get_oc(tid, cn, long_search, cached_payments) # "tid" might be fid or pid
    except:
        # example data
        octable = [[ 'Today', 8, 'failed to fetch octable', {'4':'Duke', '317178':'Flex'} , {'money':100, 'respect':5, 'delay':1800},  {'paid_by':0,  'paid_at':0}, 1234  ],
                [ 'Yesterday', 8, 'failed to fetch octable', {'1455847':'Para'} , {'result':'FAIL', 'delay':60}, {'paid_by':0,  'paid_at':0}, 2345 ]]

    return render_template("completed_oc.html", form=form, cn=int(cn), player_name=player['name'], cu=cu, octable=octable, make_links=True if int(tid) >0 else False, percent_to_pay=percent_to_pay)

#=================================================================================
@app.route("/armory_index", methods=['GET'])
@login_required
def armory_index():
    if current_user.must_change_pw:
        return redirect('/rhubarb/change_pw')

    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])
    if not is_leader:
        return render_template('message.html', title='Denied', u=current_user.username, player=player, message='No access to armorynews!', logged_in=True)

    f_id = faction_sum['fid']

    players = {}
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    c.execute("select player_id,neumune,empty_blood,morphine,full_blood,first_aid,small_first_aid,bottle_beer,xanax,energy_refill from factionconsumption where faction_id=?", (f_id,))
    for row in c:
        p = row[0]
        # Not as nice as Perl - am I missing a Python trick here?
        if not p in players:
            players[p] = {}
            players[p]['neumune'] = row[1] 
            players[p]['empty_blood'] = row[2] 
            players[p]['morphine'] = row[3] 
            players[p]['full_blood'] = row[4] 
            players[p]['first_aid'] = row[5] 
            players[p]['small_first_aid'] = row[6] 
            players[p]['bottle_beer'] = row[7] 
            players[p]['xanax'] = row[8] 
            players[p]['energy_refill'] = row[9] 
        else:
            players[p]['neumune'] += row[1] 
            players[p]['empty_blood'] += row[2] 
            players[p]['morphine'] += row[3] 
            players[p]['full_blood'] += row[4] 
            players[p]['first_aid'] += row[5] 
            players[p]['small_first_aid'] += row[6] 
            players[p]['bottle_beer'] += row[7] 
            players[p]['xanax'] += row[8] 
            players[p]['energy_refill'] += row[9] 
    c.close()
    conn.close()

    right_now = int(time.time())
    for p in players.keys():
        players[p]['name'] = rodb.pid2namepid(p)
        display_selection = (str(p) + '-' + str(right_now) ).encode("utf-8")
        players[p]['url'] = '/rhubarb/armorynews/' +  str(p) + '-' + str(right_now) + '-' + hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()
    
    return render_template("faction_stuff_used.html", players=players)
#=================================================================================
@app.route("/rhubarb/armorynews/<player_t>", methods=['GET'])
@app.route("/armorynews/<player_t>", methods=['GET'])
@login_required
def armorynews(player_t):
    p_id = None
    timestamp = None
    given_hmac = None
    right_now = int(time.time())

    re_object = armory_token.match(player_t)
    if re_object:
        p_id = re_object.group(1)
        timestamp = re_object.group(2)
        given_hmac =  re_object.group(3)
    else:
        app.logger.info('in armorynews RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = (str(p_id) + '-' + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=True)
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=True)

    # need to know faction of the player viewing this page
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = faction_sum['fid']
    player = rodb.get_player_data(p_id)

    stuff_used = []
    parm = (int(p_id), int(f_id),)
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    c.execute("select et,words from factionconsumption where player_id=? and faction_id=? order by et desc", parm)
    for row in c:
        printable_time = time.strftime("%Y-%m-%d %H:%M",time.gmtime(row[0]))
        stuff_used.append([printable_time, row[1]])
    c.close()
    conn.close()
    
    return render_template("stuff_used.html", player_name=player['name'], stuff_used=stuff_used)
#=================================================================================
@app.route("/chain_bonus/<faction_player_t>", methods=['GET'])
@app.route("/rhubarb/chain_bonus/<faction_player_t>", methods=['GET'])
def chain_bonus(faction_player_t):
    f_id = None
    p_id = None
    timestamp = None
    given_hmac = None
    right_now = int(time.time())

    logged_in = False
    try:
        u = current_user.username
        logged_in = True
    except:
        pass

    re_object = bonus_token.match(faction_player_t)
    if re_object:
        f_id = re_object.group(1)
        p_id = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac = re_object.group(4)
    else:
        app.logger.info('in chain_bonus RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = (str(f_id) + '-' +  str(p_id) + 'bonus' + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=logged_in)
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=logged_in)

    # Need to show details of the player we are enquring about, which might not be the current player viewing it.
    tbefore = int(time.time()) - 3600 # an hour ago
    parm = (int(f_id), int(p_id), tbefore,)
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    bonus_list = []
    c.execute("select et,att_name,att_id,verb,def_name,def_id,respect from long_term_bonus where fid=? and att_id=? and et<? order by et desc", parm)
    for row in c:
        record = list(row)
        record[0] = (time.strftime("%Y-%m-%d", time.gmtime(record[0])))
        bonus_list.append(record)
    c.execute("select name from namelevel where player_id=?", (int(p_id),))
    name = '?'
    for row in c:
        name = row[0]
    c.close()
    conn.close()

    rodb = read_sqlite.Rodb()
    faction_name = rodb.get_faction_name(f_id)
    return render_template("chain_bonus.html", faction_id=f_id, faction_name=faction_name, player={'name':name, 'pid':p_id, 'chain_bonus_list':bonus_list})

#=================================================================================
@app.route("/defend_summary/<faction_player_role_t>", methods=['GET'])
@app.route("/rhubarb/defend_summary/<faction_player_role_t>", methods=['GET'])
def defend_summary(faction_player_role_t):
    f_id = None
    p_id = None
    role = None
    timestamp = None
    given_hmac = None
    df = None
    right_now = int(time.time())

    logged_in = False
    try:
        u = current_user.username
        logged_in = True
    except:
        pass

    # what page is this meant to produce, attack or defend?
    re_object = combat_token.match(faction_player_role_t)
    if re_object:
        f_id = re_object.group(1)
        p_id = re_object.group(2)
        role = re_object.group(3)
        timestamp = re_object.group(4)
        given_hmac = re_object.group(5)
    else:
        app.logger.info('in defend_summary RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = (str(f_id) + '-' +  str(p_id) + role + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=logged_in)
    # test for acceptable timestamp
    if ((int(timestamp) + (86400 * 7)) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=logged_in)

    # no time limit on defends other than the 28 days of storage
    parm = (int(f_id), int(p_id),)
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    if 'defsum' == role: # only allowed role
        c.execute("select count(att_id) as num,att_name,att_id,def_name,def_id from combat_events where fid=? and def_id=? and outcome like '%lost' group by att_id order by att_id", parm)
    else:
        c.close()
        conn.close()
        return render_template("bad_graph_request.html")

    defend_lines = []
    safe_text = dehtml.Dehtml()
    for row in c:
        defend_lines.append(row)
    c.close()
    conn.close()
    
    return render_template("defend_summary.html", dl=defend_lines)
#=================================================================================
@app.route("/faction_attack/<faction_player_role_t>", methods=['GET'])
@app.route("/rhubarb/faction_attack/<faction_player_role_t>", methods=['GET'])
def combat_events(faction_player_role_t):
    f_id = None
    p_id = None
    role = None
    timestamp = None
    given_hmac = None
    df = None
    right_now = int(time.time())

    logged_in = False
    try:
        u = current_user.username
        logged_in = True
    except:
        pass

    # what page is this meant to produce, attack or defend?
    re_object = combat_token.match(faction_player_role_t)
    if re_object:
        f_id = re_object.group(1)
        p_id = re_object.group(2)
        role = re_object.group(3)
        timestamp = re_object.group(4)
        given_hmac = re_object.group(5)
    else:
        app.logger.info('in combat_events RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = (str(f_id) + '-' +  str(p_id) + role + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=logged_in)
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=logged_in)

    tbefore = int(time.time()) - 3600 # an hour ago
    parm = (int(f_id), int(p_id), tbefore,)
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    if 'attack' == role:
        c.execute("select et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where fid=? and att_id=? and et<? order by et desc", parm)
    elif 'defend' == role:
        c.execute("select et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where fid=? and  def_id=? and et<? order by et desc", parm)
    else:
        c.close()
        conn.close()
        return render_template("bad_graph_request.html")

    att_count = 0
    items = []
    old_et = 0
    old_att_id = 0
    old_def_id = 0
    safe_text = dehtml.Dehtml()
    for i in c:
        et = i[0]
        if (old_et == et) and (old_att_id == i[2]) and (old_def_id == i[5]):
            continue
        iso_time = datetime.datetime.utcfromtimestamp(et).isoformat()
        items.append( { 'et': iso_time,  'att_name': safe_text.html_clean(i[1]),  'att_id': i[2], 'verb': i[3], 'def_name': safe_text.html_clean(i[4]), 'def_id': i[5],  'outcome': safe_text.html_clean(i[6])} )
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
#=================================================================================

@app.route("/rhubarb/enemy_watch", methods=['GET','POST'])
@app.route("/enemy_watch", methods=['GET','POST'])
@login_required
def enemy_watch():

    form = EnemyForm()
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = int(faction_sum['fid'])

    # if form.validate_on_submit():
    if request.method == 'POST':
        try:
            enemy = request.form['enemy']
            time_id = request.form['timerange_id']
        except:
            app.logger.info('error reading from enemy form')
            return render_template('message.html', message='something wrong with enemy selection', logged_in=True)

        #  get enemy and time details from ORM
        wantenemy = Enemy.query.filter_by(id = enemy).first()
        if not wantenemy:
            # unknown enemy id in postgres
            return render_template('message.html', message='enemy selection not recognised', logged_in=True)
        if not wantenemy.f_id == f_id:
            return render_template('message.html', message='enemy selection looks invalid for this faction', logged_in=True)

        wanttime = Timerange.query.filter_by(id = time_id).first()
        if not wanttime:
            # unknown time id in postgres
            return render_template('message.html', message='timerange selection not recognised', logged_in=True)
        if not wanttime.f_id == f_id:
            return render_template('message.html', message='timerange selection looks invalid for this faction', logged_in=True)

        # link to next page (with HMAC)
        selector = str(wantenemy.tornid) + '-' + str(wanttime.id) + '-'  + str(int(time.time()))
        hmac_hex = hmac.new(hmac_key, selector.encode("utf-8"), digestmod=hashlib.sha1).hexdigest()
        return redirect('/rhubarb/enemy_log/' + selector + '-' + hmac_hex) 

    # show form before submission
    form.enemy.choices = [(e.id, e.username + '[' + e.tornid + ']') for e in Enemy.query.filter_by(f_id = f_id).all()]
    form.timerange_id.choices = [(t.id, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(t.tstart)) + ' to ' + time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(t.tend))) for t in Timerange.query.filter_by(f_id = f_id).all()]
    return render_template('enemy_watch.html', title='Enemy Watch', form=form, now=int(time.time()))

#=================================================================================
@app.route("/rhubarb/enemy_watch_faction", methods=['GET','POST'])
@app.route("/enemy_watch_faction", methods=['GET','POST'])
@login_required
def enemy_watch_faction():

    form = EnemyForm()
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = int(faction_sum['fid'])

    # if form.validate_on_submit():
    if request.method == 'POST':
        try:
            enemy = request.form['enemy']
            time_id = request.form['timerange_id']
        except:
            app.logger.info('error reading from enemy form')
            return render_template('message.html', message='something wrong with enemy selection', logged_in=True)

        wanttime = Timerange.query.filter_by(id = time_id).first()
        if not wanttime:
            # unknown time id in postgres
            return render_template('message.html', message='timerange selection not recognised', logged_in=True)
        if not wanttime.f_id == f_id:
            return render_template('message.html', message='timerange selection looks invalid for this faction', logged_in=True)

        #  get details of taget faction
        enemy_factions = {}  # count of attacks by us on other factions
        all_enemy_faction_attacks = rodb.get_targeted_chain(f_id, enemy, wanttime.tstart, wanttime.tend)  # specific faction, specific time
        player_items = []
        total = 0
        for apid in all_enemy_faction_attacks:
            # XXX not needed ? # link to next pages (with HMAC)
            # selector = str(apid) + '-' + str(enemy) + '-' + str(wanttime.id) + '-'  + str(int(time.time()))
            # hmac_hex = hmac.new(hmac_key, selector.encode("utf-8"), digestmod=hashlib.sha1).hexdigest()
            player_items.append( [all_enemy_faction_attacks[apid][2], all_enemy_faction_attacks[apid][1], all_enemy_faction_attacks[apid][0]] )
            total += all_enemy_faction_attacks[apid][2]

        return render_template('enemy_watch_faction2.html', player_items=player_items, enemy_faction_name=rodb.get_faction_name(enemy), total=total)

    # show form before submission
    enemy_factions = {}  # count of attacks by us on other factions
    all_enemy_faction_attacks = rodb.get_targeted_chain(f_id, None, 0, 2100000000)  # not specific to faction, all time
    for x in all_enemy_faction_attacks.keys():
        # only bother with worthwhile numbers
        if x:
            if all_enemy_faction_attacks[x] >= 50:
                enemy_factions[x] = all_enemy_faction_attacks[x]

    sorted_ef = sorted(enemy_factions.items(), key=lambda kv: kv[1], reverse=True)
    enemy_factions_counted = list(sorted_ef)

    form.enemy.choices = [(ek[0],  rodb.get_faction_name(ek[0]) + '[' + str(ek[0]) + ']') for ek in enemy_factions_counted]
    form.timerange_id.choices = [(t.id, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(t.tstart)) + ' to ' + time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(t.tend))) for t in Timerange.query.filter_by(f_id = f_id).all()]

    return render_template('enemy_watch_faction.html', title='Enemy Watch Faction', form=form, enemy_factions_counted=enemy_factions_counted, now=int(time.time()))
#=================================================================================
@app.route("/enemy_log/<player_t_t_hmac>", methods=['GET'])
@app.route("/rhubarb/enemy_log/<player_t_t_hmac>", methods=['GET'])
@login_required
def enemy_log(player_t_t_hmac):
# display summary for that enemy and time range
# with links to times and outcomes
    p_id = None
    time_id = None
    timestamp = None
    given_hmac = None
    right_now = int(time.time())

    re_object = enemy_token.match(player_t_t_hmac)
    if re_object:
        p_id = re_object.group(1)
        time_id = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        app.logger.info('in enemy_log RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = (str(p_id) + '-' + str(time_id) +  '-' + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=True)
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=True)

    # need to know faction of the player viewing this page
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = faction_sum['fid']

    enemy = Enemy.query.filter_by(tornid = p_id).first()
    if not enemy:
        return render_template('message.html', message='enemy not recognised in enemy_log', logged_in=True)

    wanttime = Timerange.query.filter_by(id = time_id).first()
    if not wanttime:
        # unknown time id in postgres
        return render_template('message.html', message='timerange not recognised in enemy_log', logged_in=True)
    if not wanttime.f_id == f_id:
        return render_template('message.html', message='timerange selection looks invalid for this faction in enemy_log', logged_in=True)
    tstart = wanttime.tstart
    tend = wanttime.tend
    if tend > right_now - 3600:
        tend = right_now - 3600 # do not display events within the last hour

    attacks = rodb.get_attacks_on_target(faction_sum['fid'], p_id, tstart, tend)
    deco_attacks = []
    for d in attacks:
        name = str(d[1]) + '[' + str(d[2]) + ']'
        display_selection = str(p_id) + '-' + str(d[2])+ '-' + str(tstart) +  '-' + str(tend)
        hmac_hex = hmac.new(hmac_key, display_selection.encode("utf-8"),  digestmod=hashlib.sha1).hexdigest()
        link = '/rhubarb/target_log/' + display_selection + '-' + hmac_hex
        deco_attacks.append([d[0], name, link])
    
    return render_template("enemy_log.html", faction_sum=faction_sum, attacks=deco_attacks, target=str(enemy.username) + '[' + str(p_id) + ']')

#=================================================================================
@app.route("/target_log/<defid_attid_tstart_tend_hmac>", methods=['GET'])
@app.route("/rhubarb/target_log/<defid_attid_tstart_tend_hmac>", methods=['GET'])
def target_log(defid_attid_tstart_tend_hmac):
    # defails of attacks on a specific target by a specific player
    defid = None
    attid = None
    tstart = None
    tend = None
    given_hmac = None
    right_now = int(time.time())

    re_object = target_token.match(defid_attid_tstart_tend_hmac)
    if re_object:
        defid = re_object.group(1)
        attid = re_object.group(2)
        tstart = re_object.group(3)
        tend = re_object.group(4)
        given_hmac =  re_object.group(5)
    else:
        app.logger.info('in target_log RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = str(defid) + '-' + str(attid)+ '-' + str(tstart) +  '-' + str(tend)
    hmac_hex = hmac.new(hmac_key, display_selection.encode("utf-8"),  digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=True)

    # from here it's similar to combat_events and uses the same template
    role='attack'
    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    c = conn.cursor()
    c.execute("select et,att_name,att_id,verb,def_name,def_id,outcome from combat_events where def_id = ? and att_id=? and et>? and et<? order by et desc", (defid,attid,tstart,tend,))
    items = []
    old_et = 0
    old_att_id = 0
    old_def_id = 0
    safe_text = dehtml.Dehtml()
    for i in c:
        et = i[0]
        if (old_et == et) and (old_att_id == i[2]) and (old_def_id == i[5]):
            continue
        iso_time = datetime.datetime.utcfromtimestamp(et).isoformat()
        items.append( { 'et': iso_time,  'att_name': safe_text.html_clean(i[1]),  'att_id': i[2], 'verb': i[3], 'def_name': safe_text.html_clean(i[4]), 'def_id': i[5],  'outcome': safe_text.html_clean(i[6])} )
        old_et = et
        old_att_id = i[2]
        old_def_id = i[5]
        player_name = i[1]
    c.close()
    conn.close()
    
    return render_template("combat_events.html", data=items, role=role, player_name=player_name)

#=================================================================================
@app.route("/delete_faction_enemies/", methods=['GET','POST'])
@app.route("/rhubarb/delete_faction_enemies/", methods=['GET','POST'])
@login_required
def delete_faction_enemies():
    form = DeleteEnemyForm()
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = int(faction_sum['fid'])
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    if not is_leader:
       return redirect('/rhubarb/home') 

    # read enemies from ORM - BEFORE the POST section otherwise form choices won't be ready
    baddies = {}
    want_enemy = Enemy.query.filter_by(f_id = faction_sum['fid']).all()
    for enemy in want_enemy:
        baddies[enemy.tornid] = enemy.username
    form.de_id.choices = [( int(k), baddies[k] + '[' + k + ']') for k in sorted(baddies.keys())]

    # - - - - - - -  POST section
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                de_id = request.form['de_id']
            except:
                app.logger.info('error involving DeleteEnemyForm')
                return render_template('message.html', title='delete enemy', message='DeleteEnemyForm exception reading input', logged_in=True)
        else:
            app.logger.info('DeleteEnemyForm fails validation')
            return render_template('message.html', title='delete enemy', message='DeleteEnemyForm failed validation: ' + str(request.form),  form=form , logged_in=True)

        if de_id:
            wantenemy = Enemy.query.filter_by(tornid = de_id).filter_by(f_id = faction_sum['fid']).first()
            if wantenemy:
                db.session.delete(wantenemy)
                db.session.commit()
            return redirect('/rhubarb/enemy_watch')
    # - - - - - - -  POST section

    faction_name = rodb.get_faction_name(f_id)
    return render_template('delete_faction_enemies.html', title='Enemies', form=form, f_id=f_id, faction_name=faction_name)
#=================================================================================
@app.route("/add_faction_enemies/", methods=['GET','POST'])
@app.route("/rhubarb/add_faction_enemies/", methods=['GET','POST'])
@login_required
def add_faction_enemies():
    form = AddEnemyForm()
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = int(faction_sum['fid'])
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    if not is_leader:
       return redirect('/rhubarb/home') 

    # - - - - - - -  POST section
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                add_id = request.form['add_id']
            except:
                app.logger.info('error involving AddEnemyForm')
                return render_template('message.html', title='add enemy', message='AddEnemyForm exception reading input', logged_in=True)
        else:
            app.logger.info('AddEnemyForm fails validation')
            return render_template('message.html', title='add enemy', message='AddEnemyForm failed validation: ' + str(request.form),  form=form , logged_in=True)

        # XXX form validation could do better
        try:
            actual_integer = int(add_id)
        except ValueError:
            return render_template('message.html', title='add enemy', message='AddEnemyForm accepts only an integer',  form=form , logged_in=True)

        if add_id:
            # XXX does not obtain username (fix up in another program) or check whether already in table
            new_enemy = Enemy (tornid = add_id,  f_id = faction_sum['fid'], username = '?')
            db.session.add(new_enemy)
            db.session.commit()
            return redirect('/rhubarb/enemy_watch')
    # - - - - - - -  POST section

    faction_name = rodb.get_faction_name(f_id)
    return render_template('add_faction_enemies.html', title='Enemies', form=form, f_id=f_id, faction_name=faction_name)
#=================================================================================
@app.route("/define_timerange/<t_to_t>", methods=['GET','POST'])
@app.route("/rhubarb/define_timerange/<t_to_t>", methods=['GET','POST'])
@login_required
def define_timerange(t_to_t):
    form = TimeForm()
    rodb = read_sqlite.Rodb()
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = int(faction_sum['fid'])

    # sane defaults
    tstart = int(time.time())
    tend = tstart + 86400

    # what is t_to_t telling us?
    re_object = time_interval.match(t_to_t)
    if re_object:
        tstart = int(re_object.group(1))
        tend = int(re_object.group(2))

    if tstart > tend:
        tstart, tend = tend, tstart

    # - - - - - - -  POST section
    if request.method == 'POST':
        new_tr = Timerange (tstart=tstart, tend=tend, f_id=f_id)
        db.session.add(new_tr)
        db.session.commit()
        #return render_template('message.html', title='TBC', message='plan to creat this timerange {} to {}'.format(tstart,tend), logged_in=True)
        return redirect('/rhubarb/enemy_watch')
    # - - - - - - -  POST section

    # variations: plus one day etc
    start_block = []
    start_block.append( [ 'planned time', tstart, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart)) ] )
    start_block.append( [ 'plus 1 day', tstart+86400, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart+86400)) ] )
    start_block.append( [ 'minus 1 day', tstart-86400, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart-86400)) ] )
    start_block.append( [ 'plus 1 hour', tstart+3600, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart+3600)) ] )
    start_block.append( [ 'minus 1 hour', tstart-3600, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart-3600)) ] )
    start_block.append( [ 'plus 1 minute', tstart+60, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart+60)) ] )
    start_block.append( [ 'minus 1 minute', tstart-60, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tstart-60)) ] )

    end_block = []
    end_block.append( [ 'planned time', tend, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend)) ] )
    end_block.append( [ 'plus 1 day', tend+86400, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend+86400)) ] )
    end_block.append( [ 'minus 1 day', tend-86400, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend-86400)) ] )
    end_block.append( [ 'plus 1 hour', tend+3600, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend+3600)) ] )
    end_block.append( [ 'minus 1 hour', tend-3600, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend-3600)) ] )
    end_block.append( [ 'plus 1 minute', tend+60, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend+60)) ] )
    end_block.append( [ 'minus 1 minute', tend-60, time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(tend-60)) ] )

    rodb = read_sqlite.Rodb()
    faction_name = rodb.get_faction_name(f_id)
    return render_template('define_timerange.html', title='Timerange', form=form, start_block=start_block, end_block=end_block, tstart=tstart, tend=tend, f_id=f_id, faction_name=faction_name)

#=================================================================================
@app.route("/chain_reports", methods=['GET'])
@app.route("/rhubarb/chain_reports", methods=['GET'])
@login_required
def chain_reports():
    rodb = read_sqlite.Rodb()
    player = rodb.get_player_data(current_user.username)
    faction_sum = rodb.get_faction_for_player(current_user.username)
    f_id = faction_sum['fid']

    chains_from_orm = Chains.query.filter_by(f_id = f_id).all()
    # finished and unfinished chains
    chains_fin = []
    chains_unf = []
    for chain in chains_from_orm:
        start_text = time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(chain.tstart))
        chain_len = chain.chain_len
        respect = chain.respect
        if chain.tend:
            end_text = time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(chain.tend))
        else:
            end_text = time.strftime("%A %Y-%m-%d %H:%M",time.gmtime(chain.et))
        # calc correct hmac
        right_now = int(time.time())
        chain_selection_pre =  str(f_id) + '-chain-' + str(chain.tstart) + '-' + str(right_now)
        chain_selection = chain_selection_pre.encode("utf-8")
        hmac_hex = hmac.new(hmac_key, chain_selection, digestmod=hashlib.sha1).hexdigest()
        stage =  [ chain_selection_pre + '-' + hmac_hex, start_text, end_text, chain_len, respect ]
        if chain.tend:
            chains_fin.append(stage)
        else:
            chains_unf.append(stage)

    faction_name = rodb.get_faction_name(f_id)
    return render_template('chain_reports.html', title='Chain reports', chains_fin=chains_fin, chains_unf=chains_unf, f_id=f_id, faction_name=faction_name)
#=================================================================================
@app.route("/chain_details/<fid_tstart_timestamp_hmac>", methods=['GET'])
@app.route("/rhubarb/chain_details/<fid_tstart_timestamp_hmac>", methods=['GET'])
def chain_details(fid_tstart_timestamp_hmac):

    # what chain is this meant to display?
    re_object = chain_token.match(fid_tstart_timestamp_hmac)
    if re_object:
        f_id = re_object.group(1)
        chain_tstart = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        app.logger.info('in chain_details RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    chain_selection = ( str(f_id) + '-chain-' + str(chain_tstart) + '-' + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, chain_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac etc
    right_now = int(time.time())
    if not hmac.compare_digest(hmac_hex, given_hmac):
        app.logger.info('in chain_details HMAC disagreement')
        return render_template("bad_graph_request.html")
    if ((int(timestamp) + 86400) < right_now):
        app.logger.info('in chain_details timestamp is old')
        return render_template("bad_graph_request.html")

    # read from ORM which chain has the right f_id and tstart
    ch = None
    chains_from_orm = Chains.query.filter_by(f_id = f_id).filter_by(tstart = chain_tstart).all()
    for chain in chains_from_orm:
        ch = chain
    if not ch:
        return render_template('message.html', message='The chain you are looking for is not found.', logged_in=False)

    # outline
    tstart_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.tstart))
    if ch.tend:
        et_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.tend))
        over = True
    else:
        et_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.et))
        over = False
    outline = [tstart_text, et_text, over, ch.chain_len, ch.respect ]

    # members for names
    who_inactive = {}
    our_players = Chain_members.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for p_mem in our_players:
        who_inactive[p_mem.player_id] = p_mem.player_name + '[' + str(p_mem.player_id) + ']'

    # bonus
    right_now = int(time.time())
    bonus_list = []
    bonus_table = Bonus_events.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for bonus in bonus_table:
        if (right_now - bonus.et) > 3600:
            # ok to show attacker name
            try:
                stage = [ who_inactive[bonus.att_id] ]
            except:
                stage = [ '?[' + str(bonus.att_id) + ']' ]
        else:
            # hide attacker name
            stage = [ 'CENSORED[000000]' ]
        stage.append(bonus.verb)
        stage.append( bonus.def_name + '[' + str(bonus.def_id) + ']')
        stage.append(bonus.outcome)
        stage.append(bonus.num_respect)
        bonus_list.append(stage)
    bonus_list = sorted(bonus_list, key=lambda one: one[-1])

    # player scoreboard (link to new route),
    right_now = int(time.time())
    scoreboard_chain_selection_pre =  str(f_id) + '-scoreboard-' + str(chain.tstart) + '-' + str(right_now)
    scoreboard_chain_selection = scoreboard_chain_selection_pre.encode("utf-8")
    hmac_hex = hmac.new(hmac_key, scoreboard_chain_selection, digestmod=hashlib.sha1).hexdigest()
    scoreboard_at = scoreboard_chain_selection_pre + '-' + hmac_hex + '-resd'

    # inactive players
    #
    player_scores = Chain_player_sum.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for p_score in player_scores:
        if p_score.player_id in who_inactive:
            if p_score.actions:
                del who_inactive[p_score.player_id]

    rodb = read_sqlite.Rodb()
    faction_name = rodb.get_faction_name(f_id)
    return render_template('chain_details.html', title='Chain details', f_id=f_id, outline=outline, scoreboard_at=scoreboard_at, inactive = who_inactive, bonus = bonus_list, faction_name=faction_name)
#=================================================================================
@app.route("/chain_scoreboard/<fid_tstart_timestamp_hmac>", methods=['GET'])
@app.route("/rhubarb/chain_scoreboard/<fid_tstart_timestamp_hmac>", methods=['GET'])
def chain_scoreboard(fid_tstart_timestamp_hmac):

    # what chain is this meant to display?
    re_object = chain_token_o.match(fid_tstart_timestamp_hmac)
    if re_object:
        f_id = re_object.group(1)
        chain_tstart = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
        orderparm =  re_object.group(5)
    else:
        app.logger.info('in chain_player_summary RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    chain_selection = ( str(f_id) + '-scoreboard-' + str(chain_tstart) + '-' + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, chain_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac etc
    right_now = int(time.time())
    if not hmac.compare_digest(hmac_hex, given_hmac):
        app.logger.info('in chain_player_summary HMAC disagreement')
        return render_template("bad_graph_request.html")
    if ((int(timestamp) + 86400) < right_now):
        app.logger.info('in chain_player_summary timestamp is old')
        return redirect('/rhubarb/chain_reports')

    # read from ORM which chain has the right f_id and tstart
    ch = None
    chains_from_orm = Chains.query.filter_by(f_id = f_id).filter_by(tstart = chain_tstart).all()
    for chain in chains_from_orm:
        ch = chain
    if not ch:
        return render_template('message.html', message='The chain you are looking for is not found.', logged_in=False)

    # hyperlinks for ordering table
    hyper_seed = [ '/rhubarb/chain_scoreboard/' + fid_tstart_timestamp_hmac.rstrip('abcdefghijklmnopqrstuvwxyz') , 'Sort']
    hyper = []
    for nh in range(12):
        hyper.append( hyper_seed[:] ) # copy makes these separate data items unlike  [...] * N
    table_column = {}
    nh = 0
    table_control = [['act','actions'], ['att','attacked'], ['hos','hospitalized'], ['mug','mugged'], ['res','respect'],
            ['ast','att_stale'], ['los','lost'], ['ate','att_escape'], ['dst','def_stale'], ['def','defend'], ['des','def_escape'], ['arh','perhit']]
    for cols in table_control:
        table_column[cols[0]] = cols[1]
        hyper[nh][0] += cols[0] + 'd'  # string addition to each column e.g. 'resd' to the end of the URL
        nh += 1

    # get from ORM data on this chain
    # outline
    tstart_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.tstart))
    if ch.tend:
        et_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.tend))
        over = True
    else:
        et_text = time.strftime("%Y-%m-%d %H:%M",time.gmtime(ch.et))
        over = False
    outline = [tstart_text, et_text, over]

    # members for names
    who = {}
    our_players = Chain_members.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for p_mem in our_players:
        who[p_mem.player_id] = p_mem.player_name + '[' + str(p_mem.player_id) + ']'


    # get from ORM the chain_player_summary for this chain
    bonus_list = []
    bonus_table = Bonus_events.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for bonus in bonus_table:
        bonus_list.append([bonus.att_id, bonus.num_respect])

    # get from ORM the chain_player_summary for this chain
    summary = []
    pid2av_respect = {}
    pid2exp = {}
    player_scores = Chain_player_sum.query.filter_by(pg_chain_id = ch.pg_chain_id).all()
    for p_score in player_scores:
        # average respect scores to be computed here
        total_respect = p_score.respect   # made by adding floats then coerced to int
        num_actions = p_score.actions
        # amend by subtracting bonuses
        for bonus in bonus_list:
            if bonus[0] == p_score.player_id:
                total_respect -= bonus[1]
                num_actions -= 1
        # respect per action (division)
        res_explanation = ''
        if num_actions >= 2:
            av_respect = total_respect / num_actions
            res_explanation = str(total_respect) + '/' + str(num_actions)
        elif num_actions == 1:
            av_respect = total_respect
        else:
            av_respect = 0.0
        summary.append(p_score)
        # 2 dicts passed along with the object data but not part of it
        pid2av_respect[p_score.player_id] = str(av_respect)
        pid2exp[p_score.player_id] = res_explanation

    # SORTING depends on a parameter passed to the route
    orderparm_s = orderparm[:3] # first 3 chars key the table_colum dict
    if (len(orderparm) == 4) and (orderparm[-1] == 'd'):
        reverse = True
        #  remove 'd' from one hyperlink
        nh = 0
        for cols in table_control:
            if cols[0] == orderparm_s:
                hyper[nh][0] = hyper[nh][0][:-1]
            nh += 1
    else:
        reverse = False
    # need to sort on the right property
    if orderparm_s == 'arh':
        # sorting by AverageRespectPer-Hit, which is outside the summary (array of objects)
        # copy dict into a list that's sorted
        sorted_av_respect_per_hit = sorted(pid2av_respect.items(), key=lambda kv: kv[1], reverse=reverse)
        # make a replacement summary list in the new order
        position = {}
        n = 0
        for x in summary:
            position[x.player_id] = n
            n += 1
        new_summary = []
        for x in sorted_av_respect_per_hit:
            new_summary.append( summary[position[x[0]]] )
        summary = new_summary
    else:
        # sorting by one of the properies in the object
        try:
            summary = sorted(summary, key=lambda one: getattr(one, table_column[orderparm_s]), reverse=reverse)
        except:
            app.logger.info('sort failed - maybe bad orderparm (%s) supplied', orderparm)

    # decorate the data with a rank (n) and readable name (who)
    deco = []
    n=1
    for x in summary:
        if not who[x.player_id]:
            who[x.player_id] = str(x.player_id)
        deco.append( [n, who[x.player_id] , x])
        n += 1

    rodb = read_sqlite.Rodb()
    faction_name = rodb.get_faction_name(f_id)
    return render_template('chain_scoreboard.html', title='Chain scoreboard', f_id=f_id, outline=outline, hyper=hyper, deco=deco, faction_name=faction_name, pid2av_respect=pid2av_respect, pid2exp=pid2exp)
#=================================================================================
def test_strength(pw):
    if len(pw) < 8:
        return False
    digest = hashlib.sha1(bytes(pw, 'utf-8')).hexdigest()
    wantsha = Banned_pw.query.filter_by(sha = digest).first()
    if wantsha:
        # found in table =>  weak
        return False
    return True
#=================================================================================

if __name__ == "__main__":
    app.run(debug = True)
