import base64
import sqlite3
import tempfile
import unittest
from pathlib import Path
from app import SCHEMA, connect, create_app, init_db
from company import FIELDS, MAX_FILE
from werkzeug.security import generate_password_hash

class CompanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password='test-password-123'
        cls.password_hash=generate_password_hash(cls.password)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.temp.name)/'hr.sqlite3')
        # Start with the exact 0.2.0 schema and an existing administrator/employee.
        with connect(self.path) as db:
            db.executescript(SCHEMA)
            db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)',('admin',self.password_hash))
            db.execute("INSERT INTO employees(code,name,joined,pay_basis,status) VALUES('KEEP','Existing employee','2026-01-01','Monthly','Active')")
        init_db(self.path)
        self.app=create_app({'DATABASE':self.path,'COOKIE_SECURE':False,'TESTING':True})
        self.client=self.app.test_client()
        self.headers={'X-HR-Request':'1'}
        response=self.client.post('/api/login',json={'username':'admin','password':self.password},headers=self.headers)
        self.headers['X-CSRF-Token']=response.json['csrf']

    def tearDown(self):
        self.temp.cleanup()

    def post(self,url,data):
        return self.client.post(url,json=data,headers=self.headers)

    def company(self,**updates):
        data=dict(company_no='V01',short_name='TEST',name='Example Company',branch='Factory',city='Ahmedabad',active='Active')
        data.update(updates)
        return data

    def create(self,**updates):
        response=self.post('/api/companies',self.company(**updates))
        self.assertEqual(response.status_code,200,response.json)
        return response.json['company']

    def document(self,**updates):
        data=dict(kind='Document',document_type='Registration',filename='registration.pdf',content=base64.b64encode(b'%PDF-1.4\nTest fixture').decode(),document_date='2026-01-01',expiry_date='2027-01-01',popup_date='2026-12-01',remark='Line one\nLine two')
        data.update(updates)
        return data

    def test_additive_migration_idempotent_and_existing_login(self):
        self.create()
        init_db(self.path)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT name FROM employees').fetchone()[0],'Existing employee')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM companies').fetchone()[0],1)
        self.assertEqual(self.client.get('/api/me').status_code,200)

    def test_all_fields_roundtrip_and_company_isolation(self):
        data=self.company()
        for f in FIELDS:
            if f['key'] in data: continue
            kind=f['type']
            data[f['key']]=True if kind=='checkbox' else '1.25' if kind in ('decimal','percent') else '12' if kind=='integer' else '2026-10-04' if kind=='date' else 'a@example.com' if kind=='email' else f['options'][-1] if kind=='select' else 'Example'
        data.update(bank_ifsc='TEST0123456',pan='ABCDE1234F',tan='ABCD12345E',smtp_secret_env='HR_SMTP_PASSWORD')
        response=self.post('/api/companies',data)
        self.assertEqual(response.status_code,200,response.json)
        saved=response.json['company']
        for k,v in data.items(): self.assertEqual(saved[k],v,k)
        other=self.create(company_no='V02',name='Another company')
        saved['name']='Edited company'
        response=self.client.put('/api/companies/'+str(saved['id']),json=saved,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.put('/api/companies/'+str(saved['id']),json=saved,headers=self.headers).status_code,409)
        rows=self.client.get('/api/companies').json['companies']
        self.assertEqual(rows[1]['name'],other['name'])
        self.assertEqual(self.post('/api/companies',self.company(company_no='v01')).status_code,409)

    def test_validation(self):
        for update in [dict(name=''),dict(pf_limit='NaN'),dict(esi_employee='101'),dict(pf_start='2026-02-30'),dict(bank_ifsc='BAD'),dict(pan='BAD'),dict(email='bad'),dict(pt_enabled='yes'),dict(smtp_secret_env='a password!'),dict(active='Invalid')]:
            with self.subTest(update=update):
                self.assertEqual(self.post('/api/companies',self.company(**update)).status_code,400)
        self.assertEqual(self.post('/api/companies',[]).status_code,400)

    def test_auth_csrf_and_private_documents(self):
        c=self.create();url=f"/api/companies/{c['id']}/documents"
        doc=self.post(url,self.document()).json['id']
        anonymous=self.app.test_client()
        for path in ['/api/companies','/api/company-schema',url,f'/api/company-documents/{doc}/file']:
            self.assertEqual(anonymous.get(path).status_code,401)
        self.assertEqual(self.client.post(url,json=self.document(),headers={'X-HR-Request':'1'}).status_code,403)
        self.assertEqual(self.client.post(url,json=self.document(),headers={**self.headers,'Origin':'https://other.example'}).status_code,403)

    def test_documents_edit_archive_and_backup(self):
        c=self.create();url=f"/api/companies/{c['id']}/documents"
        response=self.post(url,self.document());self.assertEqual(response.status_code,200,response.json)
        doc=response.json['id'];file_url=f'/api/company-documents/{doc}/file'
        downloaded=self.client.get(file_url)
        self.assertTrue(downloaded.data.startswith(b'%PDF-'))
        self.assertIn('attachment',downloaded.headers['Content-Disposition'])
        record=self.client.get(url).json['documents'][0];record['remark']='Updated'
        self.assertEqual(self.client.put(url+'/'+str(doc),json=record,headers=self.headers).status_code,200)
        self.assertEqual(self.client.put(url+'/'+str(doc),json=record,headers=self.headers).status_code,409)
        backup=str(Path(self.temp.name)/'backup.sqlite3')
        with connect(self.path) as src,sqlite3.connect(backup) as dst: src.backup(dst)
        with connect(backup) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertTrue(db.execute('SELECT content FROM company_documents').fetchone()[0].startswith(b'%PDF-'))
        self.assertEqual(self.post(url+'/'+str(doc)+'/archive',{'version':2}).status_code,200)
        self.assertEqual(self.client.get(file_url).status_code,404)
        self.assertEqual(self.client.get(url).json['documents'],[])

    def test_document_validation_and_company_boundary(self):
        a=self.create();b=self.create(company_no='V02');url=f"/api/companies/{a['id']}/documents"
        for update in [dict(filename='attack.html'),dict(content='!!!'),dict(content=base64.b64encode(b'not a PDF').decode()),dict(expiry_date='2025-01-01'),dict(kind='Logo'),dict(popup_date='2028-01-01'),dict(content='A'*(((MAX_FILE+2)//3)*4+1))]:
            with self.subTest(update=list(update)):
                self.assertEqual(self.post(url,self.document(**update)).status_code,400)
        doc=self.post(url,self.document()).json['id']
        record=self.client.get(url).json['documents'][0]
        self.assertEqual(self.client.put(f"/api/companies/{b['id']}/documents/{doc}",json=record,headers=self.headers).status_code,409)
        self.assertEqual(self.post(f"/api/companies/{b['id']}/documents/{doc}/archive",{'version':1}).status_code,409)
        self.assertEqual(self.post('/api/companies/999/documents',self.document()).status_code,404)

    def test_logo_replacement_and_pdf_conversion_rejected(self):
        c=self.create();url=f"/api/companies/{c['id']}/documents"
        png=base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
        first=self.post(url,self.document(kind='Logo',filename='logo.png',content=png)).json['id']
        second=self.post(url,self.document(kind='Logo',filename='logo.png',content=png)).json['id']
        self.assertEqual(self.client.get(f'/api/company-documents/{first}/file').status_code,404)
        self.assertEqual(self.client.get('/api/companies').json['companies'][0]['logo_id'],second)
        doc=self.post(url,self.document()).json['id']
        record=next(r for r in self.client.get(url).json['documents'] if r['id']==doc);record['kind']='Logo'
        self.assertEqual(self.client.put(url+'/'+str(doc),json=record,headers=self.headers).status_code,400)
        self.assertEqual(self.client.get('/api/companies').json['companies'][0]['logo_id'],second)

if __name__=='__main__': unittest.main()
