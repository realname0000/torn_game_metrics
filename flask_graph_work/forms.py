from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
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
    submit = SubmitField('Save')

class DeleteForm(FlaskForm):
    pass
