"""Consistent SQLite backup to stdout; never copy the live WAL database file."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as temp:
    out=Path(temp)/'hr.sqlite3'
    source=sqlite3.connect('file:'+os.environ.get('HR_DATABASE','/data/hr.sqlite3')+'?mode=ro',uri=True)
    target=sqlite3.connect(out)
    try:
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise RuntimeError('Backup integrity check failed')
    finally:
        target.close();source.close()
    sys.stdout.buffer.write(out.read_bytes())
