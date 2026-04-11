import json
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, request

AUTH_FILE = os.path.join(os.path.dirname(__file__), 'auth.json')


def get_auth():
    if not os.path.exists(AUTH_FILE):
        return None
    with open(AUTH_FILE) as f:
        return json.load(f)


def save_auth(username, password, pin):
    data = {
        'username': username,
        'password_hash': generate_password_hash(password, method='pbkdf2:sha256'),
        'pin_hash': generate_password_hash(pin, method='pbkdf2:sha256'),
    }
    with open(AUTH_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def check_password(username, password):
    auth = get_auth()
    if not auth:
        return False
    return (auth.get('username') == username and
            check_password_hash(auth['password_hash'], password))


def check_pin(pin):
    auth = get_auth()
    if not auth or 'pin_hash' not in auth:
        return False
    return check_password_hash(auth['pin_hash'], pin)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated
