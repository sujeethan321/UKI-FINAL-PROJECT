"""PM-02: synthetic SQLite only; imported harness blocks all network access."""
from datetime import datetime,timezone,timedelta
from unittest import TestCase,main
from unittest.mock import patch
import jwt
import subscription_suite as base
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,event
from sqlalchemy.orm import Session
from app.schemas.profile import ProfileUpdate
from app.services import profile_service as service
from app.routers import profile,auth
from app.core.profile_body_limit import ProfileBodyLimit
from app.core.http_security import configure_http_security

class ProfileTests(TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',poolclass=base.StaticPool,connect_args={'check_same_thread':False})
        base.create_tables(self.engine);self.db=Session(self.engine,expire_on_commit=False);base.seed(self.db)
        self.admin=self.db.get(base.User,1);self.admin.email='synthetic-admin@example.com';self.db.commit()
        self.options=patch.multiple(base.config.settings,create=True,APP_ENV='testing',LOG_LEVEL='WARNING',RATE_LIMIT_MODE='external',RATE_LIMIT_MUTATION=60,
            CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5176']);self.options.start();self.addCleanup(self.options.stop)
    def tearDown(self):self.db.close();self.engine.dispose()
    def client(self):
        app=FastAPI();app.include_router(profile.router,prefix='/api/v1');app.include_router(auth.router,prefix='/api/v1')
        app.dependency_overrides[base.get_db]=lambda:self.db
        configure_http_security(app,base.config.settings);app.add_middleware(ProfileBodyLimit)
        return TestClient(app)
    def headers(self,ident=1,revision=None):
        now=datetime.now(timezone.utc)
        data={'Authorization':'Bearer '+jwt.encode(dict(sub=str(ident),type='access',iat=now,exp=now+timedelta(minutes=10)),base.config.settings.JWT_SECRET_KEY,algorithm='HS256')}
        if revision:data['If-Match']=revision
        return data

    def test_four_roles_update_only_owned_display_preferences(self):
        for ident in (1,2,4,5):
            user=self.db.get(base.User,ident);before=service.read(self.db,user)
            result=service.update(self.db,user,ProfileUpdate(full_name='Display '+str(ident),preferred_language='ta'),before.revision);self.db.commit()
            self.assertEqual(result.user_id,ident);self.assertEqual(result.full_name,'Display '+str(ident));self.assertEqual(result.preferred_language,'ta')
            self.assertEqual(result.email,before.email);self.assertEqual(result.platform_role,before.platform_role)

    def test_phone_readonly_and_no_secret_fields(self):
        self.admin.phone='0771234567';self.db.commit()
        result=service.read(self.db,self.admin).model_dump()
        self.assertEqual(result['phone'],'0771234567')
        for key in ('password_hash','token','legacy_document_exempt','approval_status'):self.assertNotIn(key,result)
        self.assertNotIn(base.config.settings.JWT_SECRET_KEY,str(result))

    def test_mass_assignment_and_cross_user_targets_rejected(self):
        for key,value in {'user_id':4,'platform_role':'admin','account_status':'active','email':'other@example.invalid','phone':'0770000000','password':'secret','password_hash':'bad','approval_status':'approved','vehicle_type':'Bike','legacy_document_exempt':True,'business_id':10,'membership_status':'active','documents':[]}.items():
            with self.assertRaises(ValueError):ProfileUpdate(**{key:value})
        with self.client() as client:
            before=service.read(self.db,self.db.get(base.User,4))
            response=client.patch('/api/v1/account/profile',headers=self.headers(4,before.revision),json={'user_id':1,'full_name':'Attack'})
            self.assertEqual(response.status_code,422)
            self.assertEqual(self.db.get(base.User,1).full_name,'Synthetic 1')

    def test_unicode_normalization_limits_and_invalid_fields(self):
        for name in ('தமிழ் பெயர்','සිංහල නම','Zoë O’Connor','A\u200dB'):
            payload=ProfileUpdate(full_name=name);self.assertTrue(payload.full_name)
        self.assertEqual(ProfileUpdate(full_name='  Test   Name  ').full_name,'Test Name')
        for name in ('',' ','a','a'*151,'Name\nInjected','A\u202eB','\u200c\u200d',None,123):
            with self.assertRaises(ValueError):ProfileUpdate(full_name=name)
        for value in ('fr','EN',None):
            with self.assertRaises(ValueError):ProfileUpdate(preferred_language=value)
        with self.assertRaises(ValueError):ProfileUpdate()

    def test_stale_edits_and_safe_replays_do_not_overwrite_other_changes(self):
        original=service.read(self.db,self.admin)
        saved=service.update(self.db,self.admin,ProfileUpdate(full_name='First edit'),original.revision);self.db.commit()
        repeated=service.update(self.db,self.admin,ProfileUpdate(full_name='First edit'),original.revision);self.db.commit()
        self.assertEqual(saved.revision,repeated.revision)
        with self.assertRaises(HTTPException) as error:service.update(self.db,self.admin,ProfileUpdate(full_name='Stale edit'),original.revision)
        self.assertEqual(error.exception.detail['code'],'PROFILE_STALE')
        changed=service.update(self.db,self.admin,ProfileUpdate(preferred_language='si'),saved.revision);self.db.commit()
        replay=service.update(self.db,self.admin,ProfileUpdate(full_name='First edit'),original.revision);self.db.commit()
        self.assertEqual(replay.preferred_language,'si');self.assertEqual(replay.revision,changed.revision)

    def test_independent_sessions_reject_stale_version_after_first_commit(self):
        first=service.read(self.db,self.admin)
        with Session(self.engine,expire_on_commit=False) as other:
            user=other.get(base.User,1);stale=service.read(other,user)
            service.update(self.db,self.admin,ProfileUpdate(full_name='First transaction'),first.revision);self.db.commit()
            with self.assertRaises(HTTPException):service.update(other,user,ProfileUpdate(full_name='Other transaction'),stale.revision)

    def test_user_only_schema_and_business_records_unchanged(self):
        before=list(self.db.execute(select(base.Business.__table__))),list(self.db.execute(select(base.BusinessMember.__table__)))
        statements=[];event.listen(self.engine,'before_cursor_execute',lambda conn,cursor,sql,params,context,many:statements.append(sql.lower()))
        current=service.read(self.db,self.admin);service.update(self.db,self.admin,ProfileUpdate(full_name='Display only'),current.revision);self.db.commit()
        for sql in statements:
            for forbidden in ('driver_profiles','driver_verification','ledger_entries','support_cases','driver_earnings','user_preferences','customer_addresses'):self.assertNotIn(forbidden,sql)
        self.assertEqual(before,(list(self.db.execute(select(base.Business.__table__))),list(self.db.execute(select(base.BusinessMember.__table__)))))

    def test_http_authentication_headers_cors_and_sensitive_input_redaction(self):
        with self.client() as client:
            self.assertEqual(client.get('/api/v1/account/profile').status_code,401)
            response=client.get('/api/v1/account/profile',headers=self.headers());self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store');self.assertEqual(response.headers['etag'],'"'+response.json()['revision']+'"')
            preflight=client.options('/api/v1/account/profile',headers={'Origin':'http://127.0.0.1:5176','Access-Control-Request-Method':'PATCH','Access-Control-Request-Headers':'authorization,content-type,if-match'})
            self.assertEqual(preflight.status_code,200)
            bad=client.patch('/api/v1/account/profile',headers=self.headers(1,response.json()['revision']),json={'password':'PRIVATE-SHOULD-NOT-ECHO'})
            self.assertEqual(bad.status_code,422);self.assertNotIn('PRIVATE-SHOULD-NOT-ECHO',bad.text)
            self.assertEqual(client.patch('/api/v1/account/profile',headers=self.headers(),json={'full_name':'Valid Name'}).status_code,422)
            self.admin.account_status='suspended';self.db.commit();self.assertEqual(client.get('/api/v1/account/profile',headers=self.headers()).status_code,403)

    def test_body_limit_and_identity_response_phone_language(self):
        self.admin.phone='0771111111';self.admin.preferred_language='si';self.db.commit()
        with self.client() as client:
            response=client.get('/api/v1/auth/me',headers=self.headers());self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['phone'],'0771111111');self.assertEqual(response.json()['preferred_language'],'si')
            self.assertEqual(client.patch('/api/v1/account/profile',content=b'x'*4097,headers=self.headers()).status_code,413)

if __name__=='__main__':main(verbosity=2)
