import tempfile
import unittest
from pathlib import Path
from app import create_app, connect, init_db
from werkzeug.security import generate_password_hash

class HRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password='Test-password-12345'
        cls.password_hash=generate_password_hash(cls.password)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name)/'test.sqlite3');init_db(self.path)
        with connect(self.path) as db:
            db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)',('admin',self.password_hash))
        self.app=create_app({'TESTING':True,'DATABASE':self.path,'COOKIE_SECURE':False})
        self.client=self.app.test_client()
        self.headers={'X-HR-Request':'1'}

    def tearDown(self):
        self.temp.cleanup()

    def login(self):
        response=self.client.post('/api/login',json={'username':'admin','password':self.password},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.headers['X-CSRF-Token']=response.json['csrf']
        return response

    def shift(self, code='FF', overnight=False):
        return dict(code=code,name='Test shift',schedule=[dict(enabled=True,start='20:00' if overnight else '08:00',end='05:00' if overnight else '17:00',next_day=overnight) for _ in range(7)],min_full=480,min_half=240,lunch_minutes=30,arrival_before=120,arrival_after=60,active=1)

    def employee(self, shifts=None):
        return dict(code='TEST01',name='Example Employee',department='Workshop',designation='Operator',joined='2026-10-01',email='',phone='',pay_basis='Monthly',status='Active',shifts=shifts or [])

    def post(self,path,data):
        return self.client.post(path,json=data,headers=self.headers)

    def test_private_data_and_csrf(self):
        self.assertEqual(self.client.get('/api/data').status_code,401)
        self.assertEqual(self.client.get('/api/employees.csv').status_code,401)
        self.assertEqual(self.client.post('/api/login',json={}).status_code,403)
        self.login()
        self.assertEqual(self.client.post('/api/employees',json=self.employee(),headers={'X-HR-Request':'1'}).status_code,403)
        self.assertEqual(self.client.post('/api/employees',json=self.employee(),headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)

    def test_logout_revokes_server_session(self):
        response=self.login();cookie=self.client.get_cookie('hr_session').value
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
        self.assertEqual(self.post('/api/logout',{}).status_code,200)
        self.client.set_cookie('hr_session',cookie)
        self.assertEqual(self.client.get('/api/me').status_code,401)

    def test_login_throttle(self):
        for _ in range(10):
            self.assertEqual(self.post('/api/login',{'username':'admin','password':'bad'}).status_code,401)
        self.assertEqual(self.post('/api/login',{'username':'admin','password':self.password}).status_code,429)

    def test_employee_shift_persistence_and_conflicts(self):
        self.login()
        sid=self.post('/api/shifts',self.shift()).json['id']
        eid=self.post('/api/employees',self.employee([sid])).json['id']
        self.assertEqual(self.post('/api/employees',self.employee([sid])).status_code,409)
        data=self.client.get('/api/data').json
        employee=data['employees'][0];self.assertEqual(employee['shifts'],[sid])
        employee['name']='Updated Employee'
        self.assertEqual(self.client.put(f'/api/employees/{eid}',json=employee,headers=self.headers).status_code,200)
        self.assertEqual(self.client.put(f'/api/employees/{eid}',json=employee,headers=self.headers).status_code,409)
        with connect(self.path) as db:
            self.assertEqual(db.execute('SELECT name FROM employees').fetchone()[0],'Updated Employee')
            self.assertEqual(db.execute('SELECT count(*) FROM audit').fetchone()[0],3)
        second=create_app({'DATABASE':self.path,'TESTING':True,'COOKIE_SECURE':False}).test_client()
        second.set_cookie('hr_session',self.client.get_cookie('hr_session').value)
        self.assertEqual(second.get('/api/data').json['employees'][0]['name'],'Updated Employee')

    def test_overnight_and_invalid_threshold(self):
        self.login()
        self.assertEqual(self.post('/api/shifts',self.shift('NN',True)).status_code,200)
        bad=self.shift('BAD',True);bad['schedule'][0]['next_day']=False
        self.assertEqual(self.post('/api/shifts',bad).status_code,400)
        bad=self.shift('BAD');bad['min_full']=600
        self.assertEqual(self.post('/api/shifts',bad).status_code,400)
        bad=self.shift('BAD');bad['min_half']=500
        self.assertEqual(self.post('/api/shifts',bad).status_code,400)
        bad=self.shift('BAD');bad['schedule'][0]['start']='25:00'
        self.assertEqual(self.post('/api/shifts',bad).status_code,400)

    def test_allowed_shifts_validation(self):
        self.login()
        ids=[self.post('/api/shifts',self.shift('S'+str(i))).json['id'] for i in range(4)]
        self.assertEqual(self.post('/api/employees',self.employee(ids)).status_code,400)
        self.assertEqual(self.post('/api/employees',self.employee([999])).status_code,400)
        self.assertEqual(self.post('/api/employees',self.employee(ids[:3])).status_code,200)
        shift=self.client.get('/api/data').json['shifts'][0];shift['active']=0
        self.assertEqual(self.client.put('/api/shifts/'+str(shift['id']),json=shift,headers=self.headers).status_code,400)
        self.assertEqual(len(self.client.get('/api/data').json['employees'][0]['shifts']),3)

    def test_csv_injection_and_input_validation(self):
        self.login()
        e=self.employee();e['name']='=DANGEROUS()'
        self.assertEqual(self.post('/api/employees',e).status_code,200)
        csv=self.client.get('/api/employees.csv')
        self.assertIn("'=DANGEROUS()",csv.text)
        invalid=self.employee();invalid['code']='NEW';invalid['joined']='2026-02-30'
        self.assertEqual(self.post('/api/employees',invalid).status_code,400)
        self.assertEqual(self.post('/api/employees',[]).status_code,400)

    def test_health_and_security_headers(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])
        self.assertEqual(self.client.get('/healthz').json['status'],'ok')
        with self.client.get('/static/app.js') as asset:
            self.assertEqual(asset.status_code,200)

if __name__=='__main__':
    unittest.main()
