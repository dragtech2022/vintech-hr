"""Local administration: credentials never go in command arguments."""
import argparse
import getpass
import os
import re
import sqlite3
from pathlib import Path
from app import connect, init_db
from werkzeug.security import generate_password_hash

parser=argparse.ArgumentParser()
parser.add_argument('command',choices=['init','admin','backup'])
parser.add_argument('--output')
args=parser.parse_args()
path=os.getenv('HR_DATABASE','/data/hr.sqlite3')
if args.command=='init':
    init_db(path)
    print('Database ready. No employee or shift data seeded.')
elif args.command=='admin':
    init_db(path)
    username=input('Admin username: ').strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,80}',username):
        raise SystemExit('Use 3–80 letters, numbers, dots, underscores or hyphens.')
    password=getpass.getpass('New password (at least 12 characters): ')
    if len(password)<12 or len(password)>256 or password!=password.strip() or any(ord(c)<32 for c in password):
        raise SystemExit('Use 12–256 characters without leading/trailing spaces.')
    if password!=getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords did not match.')
    with connect(path) as db:
        row=db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()
        if row:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(password),row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
        else:
            db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)',(username,generate_password_hash(password)))
    print('Admin saved. Previous sessions for this account were revoked.')
else:
    if not args.output:
        raise SystemExit('Specify --output /backups/hr-YYYYMMDD.sqlite3')
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    # Refuse overwriting existing backups.
    with output.open('xb'):
        pass
    try:
        with connect(path) as src, sqlite3.connect(output) as dst:
            src.backup(dst)
            result=dst.execute('PRAGMA integrity_check').fetchone()[0]
            if result!='ok':
                raise RuntimeError(result)
        os.chmod(output,0o600)
        print(f'Backup verified: {output}')
    except Exception:
        output.unlink(missing_ok=True)
        raise
