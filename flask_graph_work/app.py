import logging
import logging.handlers
from flask import Flask, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from forms import LoginForm, PaymentForm, PasswordForm, OccalcForm, ApikeyForm, DeleteForm, RegisterForm, OCpolicyForm, LeaderForm
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

re.numeric = re.compile('^[0-9]+$')
token = re.compile('^([-\d]+)([a-z]+)(\d+)-([0-9a-f]+)$')
# f_id, crimetype, timestamp, (either number or 'history'),  hmac
oc_history_picker = re.compile('^([-\d]+)-([0-9])-([0-9]+)-([0-9a-z]+)-([0-9a-f]+)$')

now = int(time.time())

# Now there is just one way to read this.
rodb = read_sqlite.Rodb()
hmac_key = rodb.getkey()
rodb = None

app = Flask(__name__)

app.config.from_pyfile('config.py')

loghandler = logging.handlers.RotatingFileHandler('/home/peabrain/logs/tu0008.log', maxBytes=1024 * 1024, backupCount=10)
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

    # form submission failed - show login page again
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
        print("type of pwhash is ", type(pwhash), pwhash)
        #  newu = LUser (id=1, username=str(u), login_allowed=0, must_change_pw=0, pw_ver==pw_ver, pwhash='qwert', registered=et, confirmed=0, last_login=0, failed_logins=0)
        #  db.session.add(newu)
        #  db.session.commit()
        # set challenge to be done before confirmed gets a value
        return render_template('message.html', title='Message', message='Your registration attempt has U={} P={} C={}'.format(u,p,c), logged_in=False)

    return render_template('register.html', title='Register', form=form, retrry=False)

#=================================================================================

# This is not the same as "settings" change when pw is known.
@app.route("/rhubarb/unknown_pw_reset/<username>", methods=['GET','POST'])
@app.route("/unknown_pw_reset/<username>", methods=['GET','POST'])
def unknown_pw_reset(username):
    # prompt for new pw and test quality
    # and store hash as provisional
    # set challlenge
    # later either scrap or use the provisional hash
    return render_template('message.html', message='reset mechanism for unknown password ... TBC', logged_in=False)

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
    not_obsolete = 1
    wantevent = Apikey_history.query.filter_by(username = u).first()
    if wantevent:
        if wantevent.et_web_update > ak_stats[1]:
            not_obsolete = 0
        if wantevent.deleted:
            got_key[0] = 0

    # massage for human readability
    if ak_stats[3] < ak_stats[0]:
        ak_stats[3] = 0
    else:
        got_key[1] = 1
    if ak_stats[2] < ak_stats[0]:
        ak_stats[2] = 0
    else:
        got_key[1] = 1
    #
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

      # XXX is old pw correct?
      wantuser = LUser.query.filter_by(username = u).first()
      if not wantuser:
          # should never happen - has this user been deleted while logged in?
          return redirect('/rhubarb/logout') 
      if not password.checkpw(wantuser.pw_ver, old_pw, wantuser.pwhash):
          return render_template('message.html', message='old password incorrect', logged_in=True)
      # XXX is new pw acceptable?
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
          print(form.errors)
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
            for x in request.form.keys():
                print('DeleteForm K=', x,  'V=', request.form[x])

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
    player = rodb.get_player_data(current_user.username)
    is_leader = bool_leader(int(current_user.username), faction_sum['fid'])

    friendly_fires = rodb.get_friendly_fire(faction_sum['fid'])

    # extra leaders from ORM
    extra = obtain_leaders_for_faction(current_user.username, faction_sum['fid'])

    return render_template('faction_ov.html', title='Faction Overview', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader, friendly_fires=friendly_fires, extra=extra)
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
        for x in request.form.keys():
            print('LeaderForm K=', x,  'V=', request.form[x])
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
    # XXX check the orm for a cached alteration to the figures from sqlite
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

    # what do we know about this plater being a leader?
    maybe_leader = Extra_leaders.query.filter_by(faction_id = int(faction_sum['fid'])).filter_by(player_id = int(current_user.username)).all()
    print("Maybe leader?", maybe_leader)
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
    leader_record  = [any_data, leader_entry, time.strftime("%Y-%m-%d %H:%M",time.gmtime(et)), rodb.pid2n[str(set_by)]]

    return render_template('home.html', title='home', u=current_user.username, player=player, faction_sum=faction_sum, is_leader=is_leader, leader_record=leader_record)

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

@app.route("/rhubarb/attack/<player_role_t>", methods=['GET'])
@app.route("/attack/<player_role_t>", methods=['GET'])
def combat_events(player_role_t):
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
    re_object = token.match(player_role_t)
    if re_object:
        p_id = re_object.group(1)
        role = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
    else:
        app.logger.info('in combat_events RE did not match URL')
        return render_template("bad_graph_request.html")

    # calc correct hmac
    display_selection = ( str(p_id) + role + str(timestamp) ).encode("utf-8")
    hmac_hex = hmac.new(hmac_key, display_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        return render_template('message.html', message='link has been altered; cannot use it', logged_in=logged_in)
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < right_now):
        return render_template('message.html', message='too old; link has expired', logged_in=logged_in)

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

