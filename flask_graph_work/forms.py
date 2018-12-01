from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, RadioField, SelectField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('username', validators = [DataRequired()])
    password = PasswordField('password', validators = [DataRequired()])
    submit = SubmitField('Go')

class RegisterForm(FlaskForm):
    username = StringField('username', validators = [DataRequired()])
    password = PasswordField('password', validators = [DataRequired()])
    checkbox = BooleanField('click for yes')
    submit = SubmitField('Logi In')

class PaymentForm(FlaskForm):
    pass # this is all in the template

class PasswordForm(FlaskForm):
    old_password = PasswordField('old_password', validators = [DataRequired()])
    new_password = PasswordField('new_password', validators = [DataRequired()])
    submit = SubmitField('Change')

class OccalcForm(FlaskForm):
    number_oc = StringField('number_oc', validators = [DataRequired()])
    submit = SubmitField('Save')

class ApikeyForm(FlaskForm):
    apikey = PasswordField('apikey')
    use_for_faction = RadioField('Label', choices=[('yes','yes'),('no','no')])
    submit = SubmitField('Save')

class DeleteForm(FlaskForm):
    password = PasswordField('password')
    submit = SubmitField('Delete')

class OCpolicyForm(FlaskForm):
    cn = SelectField('cn', validators=[DataRequired()], id = 'select_oc', coerce=int)
    percent = StringField('percent', validators = [DataRequired()])
    submit = SubmitField('Change')

class LeaderForm(FlaskForm):
    player_demote = SelectField('player_demote',  id = 'player_demote', coerce=int, default=0)
    player_promote = SelectField('player_promote',id = 'player_promote', coerce=int, default=0)
