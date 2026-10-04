"""VINTECH HR Community: standalone employee and shift management (MIT)."""
import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import date
from pathlib import Path
from flask import Flask, g, jsonify, render_template, request, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException

VERSION = '0.3.0'
from company import SCHEMA as COMPANY_SCHEMA, register_company
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
SCHEMA = '''
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS attempts(bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, schedule TEXT NOT NULL, min_full INTEGER NOT NULL, min_half INTEGER NOT NULL, lunch_minutes INTEGER NOT NULL, arrival_before INTEGER NOT NULL, arrival_after INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, department TEXT NOT NULL DEFAULT '', designation TEXT NOT NULL DEFAULT '', joined TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', pay_basis TEXT NOT NULL CHECK(pay_basis IN ('Monthly','Daily')), status TEXT NOT NULL CHECK(status IN ('Active','Inactive')), version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS employee_shifts(employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE, shift_id INTEGER NOT NULL REFERENCES shifts(id), PRIMARY KEY(employee_id,shift_id));
CREATE INDEX IF NOT EXISTS idx_employee_shifts_shift ON employee_shifts(shift_id);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at INTEGER NOT NULL, username TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER);
'''

def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(SCHEMA)
        db.executescript(COMPANY_SCHEMA)
        if db.execute('SELECT version FROM schema_version').fetchone()[0] != 1:
            raise RuntimeError('Unsupported database version; restore matching application release.')

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(DATABASE=os.getenv('HR_DATABASE', '/data/hr.sqlite3'), COOKIE_SECURE=os.getenv('HR_COOKIE_SECURE', 'true').lower() == 'true', MAX_CONTENT_LENGTH=6*1024*1024)
    if config:
        app.config.update(config)

    def db():
        if 'db' not in g:
            g.db = connect(app.config['DATABASE'])
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        if 'db' in g:
            g.db.close()

    def error(message, status=400):
        return jsonify(error=message), status

    @app.before_request
    def authenticate():
        if not request.path.startswith('/api/'):
            return
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            # All writes require custom same-origin headers. No CORS is enabled.
            if request.headers.get('X-HR-Request') != '1' or not request.is_json:
                return error('Invalid request headers.', 403)
            if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
                # TLS may terminate at a proxy; compare the browser's authority with Host.
                from urllib.parse import urlsplit
                if urlsplit(request.headers['Origin']).netloc != request.host:
                    return error('Cross-origin request rejected.', 403)
        if request.path == '/api/login':
            return
        token = request.cookies.get('hr_session', '')
        row = db().execute('SELECT s.*, u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if not row:
            return error('Please sign in.', 401)
        g.user = row
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not secrets.compare_digest(row['csrf'], request.headers.get('X-CSRF-Token', '')):
            return error('Your session changed. Refresh and try again.', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(e):
        return error(e.description, e.code)

    @app.errorhandler(sqlite3.Error)
    def db_error(e):
        app.logger.exception('Database request failed')
        return error('Unable to save or load data. Please try again.', 503)

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object.')
        return value

    def text_field(data, key, maximum=120, required=True):
        value = data.get(key, '')
        if not isinstance(value, str):
            raise ValueError(f'{key}: enter text.')
        value = value.strip()
        if len(value) > maximum or (required and not value) or any(ord(c) < 32 for c in value):
            raise ValueError(f'{key}: enter {"1–" if required else "up to "}{maximum} characters.')
        return value

    def number(data, key, low, high):
        v = data.get(key)
        if type(v) is not int or not low <= v <= high:
            raise ValueError(f'{key}: enter a whole number from {low} to {high}.')
        return v

    def code(data):
        v = text_field(data, 'code', 30)
        if not re.fullmatch(r'[A-Za-z0-9_-]+', v):
            raise ValueError('Code may contain letters, numbers, hyphens and underscores.')
        return v.upper()

    def audit(action, entity, entity_id):
        db().execute('INSERT INTO audit(at,username,action,entity,entity_id) VALUES(?,?,?,?,?)', (int(time.time()), g.user['username'], action, entity, entity_id))

    @app.get('/')
    def home():
        return render_template('index.html', version=VERSION)

    @app.get('/healthz')
    def health():
        db().execute('SELECT version FROM schema_version').fetchone()
        return jsonify(status='ok', version=VERSION)

    @app.post('/api/login')
    def login():
        try:
            data = body()
            username = text_field(data, 'username', 80).lower()
            password = text_field(data, 'password', 256)
        except ValueError as e:
            return error(str(e))
        now = int(time.time())
        buckets = ['user:' + username, 'ip:' + (request.remote_addr or 'unknown')]
        # Serialize throttle updates across workers; database-backed, not per-process.
        with db():
            db().execute('BEGIN IMMEDIATE')
            db().execute('DELETE FROM attempts WHERE expires<=?', (now,))
            db().execute('DELETE FROM sessions WHERE expires<=?', (now,))
            for bucket in buckets:
                row = db().execute('SELECT count FROM attempts WHERE bucket=?', (bucket,)).fetchone()
                if row and row[0] >= (10 if bucket.startswith('user:') else 50):
                    return error('Too many sign-in attempts. Try again in 15 minutes.', 429)
            for bucket in buckets:
                db().execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1', (bucket, now+900))
        user = db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            return error('Incorrect username or password.', 401)
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        with db():
            db().execute('DELETE FROM attempts WHERE bucket=?', (buckets[0],))
            db().execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, now+28800))
        response = jsonify(username=username, csrf=csrf)
        response.set_cookie('hr_session', token, max_age=28800, httponly=True, secure=app.config['COOKIE_SECURE'], samesite='Strict', path='/')
        return response

    @app.get('/api/me')
    def me():
        return jsonify(username=g.user['username'], csrf=g.user['csrf'])

    @app.post('/api/logout')
    def logout():
        with db():
            db().execute('DELETE FROM sessions WHERE token_hash=?', (g.user['token_hash'],))
        response = jsonify(ok=True)
        response.delete_cookie('hr_session', path='/', secure=app.config['COOKIE_SECURE'], httponly=True, samesite='Strict')
        return response

    def shift_rows():
        rows = [dict(r) for r in db().execute('SELECT * FROM shifts ORDER BY code')]
        for row in rows:
            row['schedule'] = json.loads(row['schedule'])
        return rows

    def employee_rows():
        rows = [dict(r) for r in db().execute('SELECT * FROM employees ORDER BY name,code')]
        assigned = {}
        for row in db().execute('SELECT * FROM employee_shifts ORDER BY shift_id'):
            assigned.setdefault(row['employee_id'], []).append(row['shift_id'])
        for row in rows:
            row['shifts'] = assigned.get(row['id'], [])
        return rows

    @app.get('/api/data')
    def data():
        return jsonify(employees=employee_rows(), shifts=shift_rows(), version=VERSION)

    @app.route('/api/employees', methods=['POST'])
    @app.route('/api/employees/<int:entity_id>', methods=['PUT'])
    def save_employee(entity_id=None):
        try:
            data = body()
            values = dict(code=code(data), name=text_field(data, 'name'), department=text_field(data,'department',80,False), designation=text_field(data,'designation',80,False), joined=text_field(data,'joined',10), email=text_field(data,'email',160,False), phone=text_field(data,'phone',30,False), pay_basis=text_field(data,'pay_basis',10), status=text_field(data,'status',10))
            if date.fromisoformat(values['joined']).isoformat() != values['joined']:
                raise ValueError('Enter a valid joining date.')
            if values['pay_basis'] not in ('Daily','Monthly') or values['status'] not in ('Active','Inactive'):
                raise ValueError('Invalid status or pay basis.')
            if values['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['email']):
                raise ValueError('Enter a valid email address.')
            shifts = data.get('shifts', [])
            if not isinstance(shifts,list) or any(type(i) is not int or not 1 <= i <= 2147483647 for i in shifts) or len(shifts)>3 or len(set(shifts))!=len(shifts):
                raise ValueError('Select up to three different allowed shifts.')
            version = number(data,'version',1,2147483647) if entity_id else None
            with db():
                db().execute('BEGIN IMMEDIATE')
                for sid in shifts:
                    if not db().execute('SELECT id FROM shifts WHERE id=? AND active=1',(sid,)).fetchone():
                        raise ValueError('An assigned shift is no longer active. Reload and try again.')
                if entity_id:
                    result = db().execute('UPDATE employees SET '+','.join(k+'=?' for k in values)+',version=version+1 WHERE id=? AND version=?', (*values.values(),entity_id,version))
                    if not result.rowcount:
                        return error('This employee changed or no longer exists. Reload before editing.',409)
                    db().execute('DELETE FROM employee_shifts WHERE employee_id=?',(entity_id,))
                else:
                    entity_id = db().execute('INSERT INTO employees('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
                db().executemany('INSERT INTO employee_shifts VALUES(?,?)',[(entity_id,sid) for sid in shifts])
                audit('update' if version else 'create','employee',entity_id)
            return jsonify(id=entity_id)
        except sqlite3.IntegrityError:
            return error('An employee with this code already exists.',409)
        except (ValueError,TypeError) as e:
            return error(str(e))

    @app.route('/api/shifts', methods=['POST'])
    @app.route('/api/shifts/<int:entity_id>', methods=['PUT'])
    def save_shift(entity_id=None):
        try:
            data = body()
            values = dict(code=code(data), name=text_field(data,'name',80))
            schedule = data.get('schedule')
            if not isinstance(schedule,list) or len(schedule)!=7:
                raise ValueError('Supply all seven weekdays.')
            normalized=[]
            for item in schedule:
                if not isinstance(item,dict) or type(item.get('enabled')) is not bool or type(item.get('next_day')) is not bool:
                    raise ValueError('Invalid weekday settings.')
                for key in ('start','end'):
                    if not isinstance(item.get(key),str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',item[key]):
                        raise ValueError('Use valid 24-hour shift times.')
                def minutes(v):
                    h,m = map(int,v.split(':')); return h*60+m
                duration=minutes(item['end'])-minutes(item['start'])+(1440 if item['next_day'] else 0)
                if item['enabled'] and not 0<duration<=1440:
                    raise ValueError('End must follow start; select Next day for overnight shifts (maximum 24 hours).')
                normalized.append({k:item[k] for k in ('enabled','start','end','next_day')})
            if not any(i['enabled'] for i in normalized):
                raise ValueError('Enable at least one weekday.')
            values['schedule']=json.dumps(normalized)
            for key, high in [('min_full',1440),('min_half',1440),('lunch_minutes',240),('arrival_before',720),('arrival_after',720)]:
                values[key]=number(data,key,0,high)
            if values['min_half']>values['min_full']:
                raise ValueError('Half-day minimum cannot exceed full-day minimum.')
            for item in normalized:
                duration=minutes(item['end'])-minutes(item['start'])+(1440 if item['next_day'] else 0)
                if item['enabled'] and values['min_full']>duration-values['lunch_minutes']:
                    raise ValueError('Full-day minimum exceeds scheduled hours after the unpaid break.')
            values['active']=number(data,'active',0,1)
            version=number(data,'version',1,2147483647) if entity_id else None
            with db():
                db().execute('BEGIN IMMEDIATE')
                if entity_id and not values['active'] and db().execute('SELECT 1 FROM employee_shifts WHERE shift_id=? LIMIT 1',(entity_id,)).fetchone():
                    raise ValueError('Remove this shift from employees before making it inactive.')
                if entity_id:
                    result=db().execute('UPDATE shifts SET '+','.join(k+'=?' for k in values)+',version=version+1 WHERE id=? AND version=?',(*values.values(),entity_id,version))
                    if not result.rowcount:
                        return error('This shift changed or no longer exists. Reload before editing.',409)
                else:
                    entity_id=db().execute('INSERT INTO shifts('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
                audit('update' if version else 'create','shift',entity_id)
            return jsonify(id=entity_id)
        except sqlite3.IntegrityError:
            return error('A shift with this code already exists.',409)
        except (ValueError,TypeError) as e:
            return error(str(e))

    @app.get('/api/employees.csv')
    def export():
        output=io.StringIO(); writer=csv.writer(output)
        writer.writerow(['Code','Name','Department','Designation','Joining date','Pay basis','Status','Allowed shifts'])
        shifts={s['id']:s['code'] for s in shift_rows()}
        def safe(v):
            v=str(v)
            return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else v
        for e in employee_rows():
            writer.writerow([safe(e[k]) for k in ('code','name','department','designation','joined','pay_basis','status')]+[', '.join(shifts[s] for s in e['shifts'])])
        response=make_response('\ufeff'+output.getvalue())
        response.headers['Content-Type']='text/csv; charset=utf-8'
        response.headers['Content-Disposition']='attachment; filename="vintech-employees.csv"'
        return response

    @app.get('/api/audit')
    def history():
        return jsonify(rows=[dict(r) for r in db().execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')])

    register_company(app, db, body, error, audit, number)
    return app
