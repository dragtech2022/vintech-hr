"""Company Master metadata, validation and authenticated persistence (MIT)."""
import base64
import binascii
import io
import json
import re
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

SCHEMA = '''
CREATE TABLE IF NOT EXISTS companies (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 company_no TEXT NOT NULL UNIQUE COLLATE NOCASE,
 short_name TEXT NOT NULL, name TEXT NOT NULL, branch TEXT NOT NULL DEFAULT '',
 city TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
 details TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS company_documents (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 company_id INTEGER NOT NULL REFERENCES companies(id),
 kind TEXT NOT NULL, document_type TEXT NOT NULL, document_date TEXT NOT NULL DEFAULT '',
 authority_group TEXT NOT NULL DEFAULT '', expiry_date TEXT NOT NULL DEFAULT '',
 popup_date TEXT NOT NULL DEFAULT '', remark TEXT NOT NULL DEFAULT '',
 filename TEXT NOT NULL, mime TEXT NOT NULL, content BLOB NOT NULL,
 archived INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_company_documents ON company_documents(company_id,archived);
'''

def f(key, label, kind='text', **kwargs):
    return dict(key=key, label=label, type=kind, **kwargs)

def section(title, fields):
    return dict(title=title, fields=fields)

TABS = [dict(id='details', label='Company details', sections=[
    section('Company identity', [f('company_no','Company number / code',required=True,max=30), f('short_name','Short name',required=True,max=60), f('name','Company name',required=True,max=160), f('branch','Branch / location'), f('establishment_type','Establishment type'), f('email','Email','email'), f('phone','Phone',max=40), f('active','Status','select',options=['Active','Inactive'])]),
    section('Address', [f('address','Address','textarea'),f('state','State'),f('district','District'),f('city','City'),f('pincode','PIN code',max=12)]),
    section('Contractor / unit / point / site', [f('unit_type','Establishment type'),f('unit_name','Unit / contractor name'),f('unit_address','Address','textarea')]),
    section('Bank details', [f('bank_name','Bank name'),f('bank_account','Account number',max=40),f('bank_ifsc','IFSC code',max=11),f('bank_address','Bank address','textarea')]),
    section('Salary slip email settings', [f('smtp_email','Sender email','email'),f('smtp_server','SMTP server'),f('smtp_port','SMTP port','integer',max_value=65535),f('smtp_security','Encryption','select',options=['','STARTTLS','TLS']),f('smtp_username','SMTP username'),f('smtp_secret_env','Password environment variable name',max=100)])]),
 dict(id='statutory',label='PF / ESI / PT / IT',sections=[
    section('PF details',[f('pf_no','PF number'),f('pf_limit','PF limit','decimal'),f('pf_extension','Extension code'),f('pf_group','PF group'),f('pf_start','PF start date','date'),f('pf_office','PF office'),f('pf_company_group','PF company group'),f('pf_basis','PF calculation on','select',options=['','Basic','All']),f('pf_diff_epf','Difference EPF (%)','percent'),f('pf_pension','Pension A/C 10 (%)','percent'),f('pf_ac2','A/C 2 (%)','percent'),f('pf_ac2_min','A/C 2 minimum amount','decimal'),f('pf_ac21','A/C 21 (%)','percent'),f('pf_ac21_min','A/C 21 minimum amount','decimal'),f('pf_ac22','A/C 22 (%)','percent'),f('pf_ac22_min','A/C 22 minimum amount','decimal')]),
    section('ESI details',[f('esi_no','ESI number'),f('esi_local_office','Local area office'),f('esi_start','ESI start date','date'),f('esi_company_group','ESI company group'),f('esi_basis','ESI calculation on','select',options=['','Gross','All']),f('esi_limit','ESI limit','decimal'),f('esi_employee','Employee (%)','percent'),f('esi_employer','Employer (%)','percent'),f('esi_on_ot','ESI on overtime','checkbox')]),
    section('Professional tax',[f('pt_no','PT number'),f('pt_enabled','Professional tax enabled','checkbox')]),
    section('Income tax',[f('pan','PAN number',max=10),f('tan','TAN number',max=10),f('it_auto_deduct','Auto deduct income tax','checkbox'),f('minimum_wage_limit','Minimum wage limit','decimal')]),
    section('Overtime',[f('ot_ratio','OT ratio','decimal'),f('ot_type','OT type'),f('ot_count_on','OT calculated on'),f('ot_show_in','OT shown in'),f('ot_scale','OT scale / day basis')]),
    section('Bonus',[f('bonus_basis','Bonus on','select',options=['','Gross','Basic']),f('bonus_percent','Bonus (%)','percent'),f('bonus_limit','Bonus limit','decimal')])]),
 dict(id='heads',label='Allowance details',sections=[
    section('Allowance heads',sum(([f(f'allowance_{i}_short',f'Head {i} · short ID',max=30),f(f'allowance_{i}_name',f'Head {i} · full name'),f(f'allowance_{i}_import',f'Head {i} · import enabled','checkbox')] for i in range(1,11)),[])),
    section('Deduction heads',[f(f'deduction_{i}',f'Deduction head {i}') for i in range(1,7)]),
    section('CTC heads (employer)',[f(f'ctc_{i}',f'CTC head {i}') for i in range(1,7)]),
    section('Reimbursement heads',[f(f'reimbursement_{i}',f'Reimbursement head {i}') for i in range(1,13)]),
    *[section(f'Owner details {i}',[f(f'owner_{i}_name','Owner name'),f(f'owner_{i}_designation','Designation'),f(f'owner_{i}_phone','Phone',max=40),f(f'owner_{i}_address','Address','textarea')]) for i in (1,2)]]),
 dict(id='other',label='Other details',sections=[
    section('Application settings',[f('selfie_admin','Selfie admin name'),f('mispunch_day_limit','Mispunch application day limit','integer',max_value=366)]),
    section('Company manager',[f('manager_name','Manager name'),f('manager_designation','Manager designation'),f('manager_id','Manager ID'),f('manager_email','Manager email','email'),f('backend_name','Backend contact name'),f('backend_id','Backend contact ID'),f('backend_email','Backend contact email','email')])])]
FIELDS = [field for tab in TABS for group in tab['sections'] for field in group['fields']]
CORE = {'company_no','short_name','name','branch','city','active'}
MAX_FILE = 4 * 1024 * 1024
DOC_COLS = 'id,company_id,kind,document_type,document_date,authority_group,expiry_date,popup_date,remark,filename,mime,version'

def clean(data, spec):
    key, kind = spec['key'], spec['type']
    value = data.get(key, False if kind=='checkbox' else '')
    if kind=='checkbox':
        if type(value) is not bool:
            raise ValueError(spec['label']+': choose yes or no.')
        return value
    if not isinstance(value,str):
        raise ValueError(spec['label']+': enter text.')
    value=value.strip()
    if len(value)>spec.get('max',2000 if kind=='textarea' else 160) or any(ord(c)<32 and not (kind=='textarea' and c in '\n\r\t') for c in value):
        raise ValueError(spec['label']+': text is too long or contains invalid characters.')
    if not value:
        if spec.get('required'):
            raise ValueError(spec['label']+' is required.')
        return ''
    if kind=='date':
        if date.fromisoformat(value).isoformat()!=value:
            raise ValueError(spec['label']+': use YYYY-MM-DD.')
    if kind in ('decimal','percent','integer'):
        try:
            n=Decimal(value)
            if not n.is_finite() or n<0 or n>spec.get('max_value',100 if kind=='percent' else 999999999999) or (kind=='integer' and n!=n.to_integral_value()) or n.as_tuple().exponent < -4:
                raise ValueError()
        except (InvalidOperation,ValueError):
            raise ValueError(spec['label']+': enter a valid non-negative value (maximum four decimal places).')
    if kind=='select' and value not in spec['options']:
        raise ValueError(spec['label']+': choose a listed option.')
    if kind=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
        raise ValueError(spec['label']+': enter a valid email.')
    return value

def register_company(app, db, body, error, audit, number):
    def company_row(row):
        data=json.loads(row['details'])
        data.update({k:row[k] for k in ('id','company_no','short_name','name','branch','city','version')})
        data['active']='Active' if row['active'] else 'Inactive'
        logo=db().execute("SELECT id FROM company_documents WHERE company_id=? AND kind='Logo' AND archived=0 ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
        data['logo_id']=logo['id'] if logo else None
        return data

    @app.get('/api/company-schema')
    def company_schema():
        return jsonify(tabs=TABS,max_file=MAX_FILE)

    @app.get('/api/companies')
    def companies():
        return jsonify(companies=[company_row(r) for r in db().execute('SELECT * FROM companies ORDER BY id')])

    @app.post('/api/companies')
    @app.put('/api/companies/<int:company_id>')
    def save_company(company_id=None):
        try:
            data=body()
            values={s['key']:clean(data,s) for s in FIELDS}
            if not re.fullmatch(r'[A-Za-z0-9_-]+',values['company_no']):
                raise ValueError('Company number: use letters, numbers, underscores or hyphens.')
            values['company_no']=values['company_no'].upper()
            values['active']=values['active'] or 'Active'
            for key, pattern in [('bank_ifsc',r'[A-Z]{4}0[A-Z0-9]{6}'),('pan',r'[A-Z]{5}[0-9]{4}[A-Z]'),('tan',r'[A-Z]{4}[0-9]{5}[A-Z]'),('smtp_secret_env',r'[A-Z_][A-Z0-9_]*')]:
                values[key]=values[key].upper()
                if values[key] and not re.fullmatch(pattern,values[key]):
                    raise ValueError(key+': invalid format.')
            core={k:values[k] for k in ('company_no','short_name','name','branch','city')}
            core['active']=int(values['active']=='Active')
            core['details']=json.dumps({k:v for k,v in values.items() if k not in CORE})
            version=number(data,'version',1,2147483647) if company_id else None
            with db():
                db().execute('BEGIN IMMEDIATE')
                if company_id:
                    result=db().execute('UPDATE companies SET '+','.join(k+'=?' for k in core)+',version=version+1 WHERE id=? AND version=?',(*core.values(),company_id,version))
                    if not result.rowcount:
                        return error('Company changed in another session. Close and reopen it before saving.',409)
                else:
                    company_id=db().execute('INSERT INTO companies('+','.join(core)+') VALUES('+','.join('?' for _ in core)+')',tuple(core.values())).lastrowid
                audit('update' if version else 'create','company',company_id)
            return jsonify(company=company_row(db().execute('SELECT * FROM companies WHERE id=?',(company_id,)).fetchone()))
        except sqlite3.IntegrityError:
            return error('That company number already exists.',409)
        except (ValueError,TypeError) as e:
            return error(str(e))

    @app.get('/api/companies/<int:company_id>/documents')
    def documents(company_id):
        return jsonify(documents=[dict(r) for r in db().execute(f'SELECT {DOC_COLS} FROM company_documents WHERE company_id=? AND archived=0 ORDER BY id DESC',(company_id,))])

    @app.post('/api/companies/<int:company_id>/documents')
    @app.put('/api/companies/<int:company_id>/documents/<int:document_id>')
    def save_document(company_id,document_id=None):
        try:
            data=body()
            if not db().execute('SELECT id FROM companies WHERE id=?',(company_id,)).fetchone():
                return error('Company not found.',404)
            fields=[f('kind','File category','select',required=True,options=['Document','Logo','HR policy']),f('document_type','Document type',required=True),f('document_date','Document date','date'),f('authority_group','Authority group'),f('expiry_date','Expiry date','date'),f('popup_date','Reminder date','date'),f('remark','Remark','textarea')]
            values={s['key']:clean(data,s) for s in fields}
            if values['document_date'] and values['expiry_date'] and values['expiry_date']<values['document_date']:
                raise ValueError('Expiry date cannot precede document date.')
            if values['popup_date'] and values['expiry_date'] and values['popup_date']>values['expiry_date']:
                raise ValueError('Reminder date cannot follow expiry date.')
            if not document_id or data.get('content'):
                encoded=data.get('content','')
                if not isinstance(encoded,str) or len(encoded)>((MAX_FILE+2)//3)*4:
                    raise ValueError('Choose a file up to 4 MiB.')
                content=base64.b64decode(encoded,validate=True)
                if not content or len(content)>MAX_FILE:
                    raise ValueError('Choose a non-empty file up to 4 MiB.')
                filename=secure_filename(clean(data,f('filename','Filename',required=True,max=200)))
                if content.startswith(b'\x89PNG\r\n\x1a\n') and filename.lower().endswith('.png'):
                    mime='image/png'
                elif content.startswith(b'\xff\xd8\xff') and filename.lower().endswith(('.jpg','.jpeg')):
                    mime='image/jpeg'
                elif content.startswith(b'%PDF-') and filename.lower().endswith('.pdf'):
                    mime='application/pdf'
                else:
                    raise ValueError('Only PDF, PNG and JPEG files with matching content are accepted.')
                values.update(filename=filename,mime=mime,content=content)
            version=number(data,'version',1,2147483647) if document_id else None
            with db():
                db().execute('BEGIN IMMEDIATE')
                old=db().execute('SELECT * FROM company_documents WHERE id=? AND company_id=? AND archived=0',(document_id,company_id)).fetchone() if document_id else None
                if document_id and (not old or old['version']!=version):
                    return error('Document changed. Reload before editing.',409)
                if values['kind']=='Logo' and values.get('mime',old['mime'] if old else '') not in ('image/png','image/jpeg'):
                    raise ValueError('A logo must be a PNG or JPEG image.')
                if values['kind'] in ('Logo','HR policy'):
                    db().execute('UPDATE company_documents SET archived=1,version=version+1 WHERE company_id=? AND kind=? AND archived=0 AND id!=?',(company_id,values['kind'],document_id or 0))
                if document_id:
                    db().execute('UPDATE company_documents SET '+','.join(k+'=?' for k in values)+',version=version+1 WHERE id=?',(*values.values(),document_id))
                else:
                    values['company_id']=company_id
                    document_id=db().execute('INSERT INTO company_documents('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values())).lastrowid
                audit('update' if version else 'create','company document',document_id)
            return jsonify(id=document_id)
        except (ValueError,TypeError,binascii.Error) as e:
            return error(str(e))

    @app.post('/api/companies/<int:company_id>/documents/<int:document_id>/archive')
    def archive_document(company_id,document_id):
        try:
            version=number(body(),'version',1,2147483647)
            with db():
                result=db().execute('UPDATE company_documents SET archived=1,version=version+1 WHERE company_id=? AND id=? AND version=? AND archived=0',(company_id,document_id,version))
                if not result.rowcount:
                    return error('Document changed. Reload before archiving.',409)
                audit('archive','company document',document_id)
            return jsonify(ok=True)
        except ValueError as e:
            return error(str(e))

    @app.get('/api/company-documents/<int:document_id>/file')
    def download_document(document_id):
        row=db().execute('SELECT * FROM company_documents WHERE id=? AND archived=0',(document_id,)).fetchone()
        if not row:
            return error('Document not found.',404)
        return send_file(io.BytesIO(row['content']),mimetype=row['mime'],download_name=row['filename'],as_attachment=row['kind']!='Logo',max_age=0)
