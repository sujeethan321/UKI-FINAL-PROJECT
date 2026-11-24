"""Multipart integration on synthetic SQLite and private temporary fixtures."""
from io import BytesIO
from unittest import main
from unittest.mock import patch
import driver_documents_suite as foundation
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import auth, driver
from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.core.rate_limit import registration_limit, login_limit
from app.core.request_limits import RequestBodyLimitMiddleware
from app.models import User, DriverProfile, DriverVerificationDocument
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.services import driver_registration_service as service


class RegistrationFixture(foundation.MetadataTests):
    def setUp(self):
        super().setUp()
        self.options=patch.object(service.settings,'DRIVER_DOCUMENT_PRIVATE_ROOT',self.temp.name,create=True);self.options.start()
        self.acl=patch.object(foundation.storage,'private_acl');self.acl.start()
        self.app=FastAPI();self.app.include_router(auth.router,prefix='/api/v1');self.app.include_router(driver.router,prefix='/api/v1')
        self.app.add_middleware(RequestBodyLimitMiddleware)
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.app.dependency_overrides[registration_limit]=lambda:None
        self.app.dependency_overrides[login_limit]=lambda:None
        self.app.dependency_overrides[get_current_user]=lambda:self.db.get(User,5)
        self.client=TestClient(self.app,raise_server_exceptions=False)

    def tearDown(self):
        self.client.close();self.acl.stop();self.options.stop();super().tearDown()

    def fields(self):
        return dict(full_name='New Fictional Driver',email='new-driver@example.com',password='fictional-passphrase-123',phone='',preferred_language='en')

    def submit(self, first=None, second=None, fields=None):
        return self.client.post('/api/v1/driver/vehicle',data=fields or dict(vehicle_type='Motorbike',registration_reference='FICTIONAL-123'),files={
            'driving_licence':first or ('licence.png',foundation.image(),'image/png'),
            'vehicle_ownership_proof':second or ('ownership.jpg',foundation.image('JPEG'),'image/jpeg')})


class RegistrationTests(RegistrationFixture):
    def test_basic_account_registration_login_and_vehicle_missing(self):
        response=self.client.post('/api/v1/auth/register/driver',json=self.fields())
        self.assertEqual(response.status_code,201,response.text)
        uid=response.json()['user_id']
        self.assertIsNone(self.db.get(DriverProfile,uid))
        self.assertEqual(self.db.get(User,uid).account_status,'active')
        self.app.dependency_overrides[get_current_user]=lambda:self.db.get(User,uid)
        profile=self.client.get('/api/v1/driver/profile').json()
        self.assertEqual(profile['vehicle_registration_status'],'not_registered')
        self.assertFalse(profile['eligible_for_jobs'])
        login=self.client.post('/api/v1/auth/login',data={'username':self.fields()['email'],'password':self.fields()['password']})
        self.assertEqual(login.status_code,200,login.text)
        self.assertEqual(self.client.post('/api/v1/auth/register/driver',json=self.fields()).status_code,409)
        self.assertEqual(self.submit().status_code,201)
        self.assertEqual(self.db.get(DriverProfile,uid).approval_status,'pending')

    def test_images_pdfs_and_mixed_pending_and_duplicate_denial(self):
        for first,second in [('png','jpg'),('pdf','pdf'),('png','pdf')]:
            def fixture(kind): return ('fixture.'+kind,foundation.pdf() if kind=='pdf' else foundation.image('JPEG' if kind=='jpg' else 'PNG'),'application/pdf' if kind=='pdf' else 'image/jpeg' if kind=='jpg' else 'image/png')
            response=self.submit(fixture(first),fixture(second))
            self.assertEqual(response.status_code,201,response.text)
            self.assertFalse(response.json()['eligible_for_jobs'])
            self.assertEqual(self.submit().status_code,409)
            profile=self.db.get(DriverProfile,5);profile.approval_status='rejected';profile.reviewed_by=1;profile.reviewed_at=foundation.datetime(2026,1,1);self.db.commit()
        self.assertEqual(len(list(self.db.scalars(select(DriverVerificationDocument).where(DriverVerificationDocument.current_slot==1)))),2)

    def test_missing_disguised_oversized_and_invalid_fields(self):
        response=self.client.post('/api/v1/driver/vehicle',data={'vehicle_type':'Bike','registration_reference':'X'},files={'driving_licence':('x.png',foundation.image(),'image/png')})
        self.assertEqual(response.status_code,422)
        for file in [('x.exe',b'bad','application/octet-stream'),('x.png',b'bad','image/png'),('x.png',b'x'*(5*1024*1024+1),'image/png')]:
            self.assertEqual(self.submit(first=file).status_code,422)
        self.assertEqual(self.submit(fields={'vehicle_type':'','registration_reference':'X'}).status_code,422)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverVerificationDocument)),0)
        self.assertEqual(self.client.post('/api/v1/driver/profile',json={'vehicle_type':'Bike','registration_reference':'X'}).status_code,409)
        self.assertEqual(self.client.post('/api/v1/driver/vehicle',json={}).status_code,415)

    def test_rejected_document_allows_replacement_and_invalidates_reviews(self):
        self.assertEqual(self.submit().status_code,201)
        docs=list(self.db.scalars(select(DriverVerificationDocument)))
        docs[0].review_status='REJECTED';docs[0].reviewed_by=1;docs[0].reviewed_at=foundation.datetime(2026,1,1);docs[0].rejection_code='UNREADABLE';self.db.commit()
        self.assertEqual(self.client.get('/api/v1/driver/profile').json()['vehicle_registration_status'],'rejected')
        self.assertEqual(self.submit().status_code,201)
        current=list(self.db.scalars(select(DriverVerificationDocument).where(DriverVerificationDocument.current_slot==1)))
        self.assertTrue(all(d.version==2 and d.review_status=='PENDING' for d in current))

    def test_approved_legacy_and_non_driver_cannot_submit(self):
        profile=self.db.get(DriverProfile,5);profile.approval_status='approved';profile.legacy_document_exempt=True;profile.reviewed_by=1;profile.reviewed_at=foundation.datetime(2026,1,1)
        profile.vehicle_type='Bike';profile.registration_reference='LEGACY';self.db.commit()
        self.assertEqual(self.submit().status_code,409)
        self.assertTrue(self.client.get('/api/v1/driver/profile').json()['eligible_for_jobs'])
        self.app.dependency_overrides[get_current_user]=lambda:self.db.get(User,1)
        self.assertEqual(self.submit().status_code,403)
        self.app.dependency_overrides[get_current_user]=lambda:None

    def test_storage_failure_and_uncertain_commit_preserve(self):
        from app.services import driver_vehicle_service as vehicle_service
        with patch.object(vehicle_service,'PrivateDocumentStore',side_effect=foundation.storage.DocumentError('PRIVATE_STORAGE_UNAVAILABLE')):
            self.assertEqual(self.submit().status_code,503)
        with patch.object(self.db,'commit',side_effect=RuntimeError('sensitive')):
            response=self.submit();self.assertEqual(response.status_code,503);self.assertNotIn('sensitive',response.text)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverVerificationDocument)),0)
        self.assertEqual(len(list(self.store.root.iterdir())),2)

    def test_request_limits_only_for_authenticated_vehicle_path(self):
        self.assertEqual(self.client.post('/api/v1/auth/register/driver',content=b'x'*(300*1024)).status_code,413)
        self.assertEqual(self.client.post('/api/v1/driver/vehicle',content=b'x'*(11*1024*1024+1)).status_code,413)

    def test_pending_and_unverified_approved_profiles_cannot_take_deliveries(self):
        from fastapi import HTTPException
        from app.services.driver_service import eligible_driver
        with self.assertRaises(HTTPException): eligible_driver(self.db,5)
        profile=self.db.get(DriverProfile,5)
        profile.approval_status='approved';profile.vehicle_type='Bike';profile.registration_reference='X'
        profile.reviewed_by=1;profile.reviewed_at=foundation.datetime(2026,1,1);self.db.commit()
        with self.assertRaises(HTTPException): eligible_driver(self.db,5)
        profile.legacy_document_exempt=True;self.db.commit()
        eligible_driver(self.db,5)


if __name__=='__main__': main(verbosity=2)
