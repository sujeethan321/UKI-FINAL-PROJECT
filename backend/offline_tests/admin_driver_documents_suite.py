"""Step 387 offline current-document authorization/review/approval integration."""
from uuid import uuid4
from unittest import main
from unittest.mock import patch
import driver_registration_suite as registration
from app.routers import admin
from app.core.auth_dependencies import get_current_user
from app.models import User, DriverProfile, DriverVerificationDocument, DriverDocumentAudit, AdminAudit, DeliveryRequest, DeliveryAssignment, Order
from app.services.driver_document_service import append_version
from app.services import admin_driver_documents as docs, admin_service
from sqlalchemy import select, func


class AdminDocumentsTests(registration.RegistrationFixture):
    def setUp(self):
        super().setUp()
        self.app.include_router(admin.router,prefix='/api/v1')
        raw=self.db.connection().connection.driver_connection
        raw.create_collation('utf8mb4_bin',lambda a,b:(a>b)-(a<b))
        raw.create_function('CHAR_LENGTH',1,lambda value:len(value) if value is not None else None)
        registration.foundation.base.Base.metadata.create_all(self.engine,tables=[AdminAudit.__table__,Order.__table__,DeliveryRequest.__table__,DeliveryAssignment.__table__])
        self.actor=1
        self.app.dependency_overrides[get_current_user]=lambda:self.db.get(User,self.actor)
        self.profile=self.db.get(DriverProfile,5)
        self.profile.vehicle_type='Bike';self.profile.registration_reference='FICTIONAL'
        self.db.commit()

    def create(self,kind='DRIVING_LICENCE'):
        row=append_version(self.db,5,kind,self.candidate(),self.store);self.db.commit();return row

    def endpoint(self,row,action='review',driver=5):
        return f'/api/v1/admin/drivers/{driver}/documents/{row.document_id}/{action}'

    def review(self,row,decision='approve'):
        return self.client.patch(self.endpoint(row),json={'decision':decision,'rejection_code':'OTHER' if decision=='reject' else None})

    def decide(self):
        with patch.object(admin_service,'notify_event'):
            return self.client.patch('/api/v1/admin/drivers/5/decision',json={'decision':'approve'})

    def test_admin_details_review_and_final_approval(self):
        first=self.create();second=self.create('VEHICLE_OWNERSHIP_PROOF')
        data=self.client.get('/api/v1/admin/drivers/5').json()
        self.assertFalse(data['verification']['approval_ready'])
        self.assertNotIn('storage_key',str(data));self.assertNotIn(self.temp.name,str(data))
        self.assertEqual(self.decide().status_code,409)
        self.assertEqual(self.review(first).status_code,200)
        self.assertEqual(self.decide().status_code,409)
        self.assertEqual(self.review(second).status_code,200)
        self.assertEqual(self.decide().status_code,200)
        self.assertEqual(self.profile.approval_status,'approved')
        self.assertEqual(first.reviewed_by,1);self.assertIsNotNone(first.reviewed_at)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverDocumentAudit).where(DriverDocumentAudit.action=='REVIEWED')),2)

    def test_non_admin_cross_driver_guessed_and_replaced_denial(self):
        row=self.create()
        for actor in (2,4,5):
            self.actor=actor
            self.assertEqual(self.client.get(self.endpoint(row,'preview')).status_code,403)
            self.assertEqual(self.review(row).status_code,403)
        self.actor=1
        self.assertEqual(self.client.get(self.endpoint(row,'download',driver=4)).status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/admin/drivers/5/documents/{uuid4()}/preview').status_code,404)
        replacement=append_version(self.db,5,'DRIVING_LICENCE',self.candidate(),self.store);self.db.commit()
        self.assertEqual(self.review(row).status_code,404)
        self.assertEqual(self.client.get(self.endpoint(row,'preview')).status_code,404)
        self.assertEqual(replacement.review_status,'PENDING')

    def test_headers_access_audit_and_integrity_failure(self):
        row=self.create()
        for mode in ('preview','download'):
            response=self.client.get(self.endpoint(row,mode))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(response.headers['x-content-type-options'],'nosniff')
            self.assertIn('sandbox',response.headers['content-security-policy'])
            self.assertEqual(response.content,(self.store.root/row.storage_key).read_bytes())
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DriverDocumentAudit).where(DriverDocumentAudit.action.in_(('PREVIEWED','DOWNLOADED')))),2)
        (self.store.root/row.storage_key).write_bytes(b'corrupt')
        self.assertEqual(self.client.get(self.endpoint(row,'download')).status_code,409)
        self.assertEqual(self.review(row).status_code,409)
        data=self.client.get('/api/v1/admin/drivers/5').json()['verification']
        self.assertFalse(data['documents'][0]['integrity_valid'])

    def test_conflicting_reviews_idempotency_and_replacement_invalidate_approval(self):
        row=self.create();self.create('VEHICLE_OWNERSHIP_PROOF')
        self.assertEqual(self.review(row).status_code,200)
        self.assertEqual(self.review(row).status_code,200)
        self.assertEqual(self.review(row,'reject').status_code,409)
        replacement=append_version(self.db,5,'DRIVING_LICENCE',self.candidate(),self.store);self.db.commit()
        self.assertEqual(replacement.review_status,'PENDING')
        self.assertFalse(self.client.get('/api/v1/admin/drivers/5').json()['verification']['approval_ready'])
        self.assertEqual(self.decide().status_code,409)

    def test_legacy_is_not_fabricated_document_approval(self):
        self.profile.approval_status='approved';self.profile.legacy_document_exempt=True
        self.profile.reviewed_by=1;self.profile.reviewed_at=registration.foundation.datetime(2026,1,1);self.db.commit()
        data=self.client.get('/api/v1/admin/drivers/5').json()['verification']
        self.assertTrue(data['legacy_exempt']);self.assertFalse(data['approval_ready'])
        self.assertTrue(all(d['review_status']=='MISSING' for d in data['documents']))
        self.assertEqual(self.profile.approval_status,'approved')

    def test_approval_gate_checks_integrity_after_both_reviews(self):
        first=self.create();second=self.create('VEHICLE_OWNERSHIP_PROOF')
        self.review(first);self.review(second)
        (self.store.root/second.storage_key).write_bytes(b'changed after review')
        self.assertEqual(self.decide().status_code,409)
        self.assertEqual(self.profile.approval_status,'pending')

    def test_rejected_document_and_pending_legacy_flag_cannot_bypass_gate(self):
        first=self.create();second=self.create('VEHICLE_OWNERSHIP_PROOF')
        self.assertEqual(self.review(first,'reject').status_code,200)
        self.assertEqual(self.review(second).status_code,200)
        self.profile.legacy_document_exempt=True;self.db.commit()
        self.assertEqual(self.decide().status_code,409)
        self.actor=2
        self.assertEqual(self.client.get('/api/v1/admin/drivers/5').status_code,403)
        self.actor=1
        self.db.get(User,1).account_status='suspended';self.db.commit()
        self.assertEqual(self.client.get(self.endpoint(first,'preview')).status_code,403)

    def test_pdf_delivery_and_mysql_lock_contract(self):
        from sqlalchemy.dialects import mysql
        from io import BytesIO
        with patch.object(registration.foundation.storage,'private_acl'):
            candidate=self.store.stage(BytesIO(registration.foundation.pdf()),'fictional.pdf','application/pdf',registration.foundation.storage.UploadBudget())
        row=append_version(self.db,5,'DRIVING_LICENCE',candidate,self.store);self.db.commit()
        response=self.client.get(self.endpoint(row,'preview'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        compiled=[];scalar=self.db.scalar;scalars=self.db.scalars
        def capture(statement,method):
            compiled.append(str(statement.compile(dialect=mysql.dialect())))
            return method(statement)
        with patch.object(self.db,'scalar',side_effect=lambda s:capture(s,scalar)),patch.object(self.db,'scalars',side_effect=lambda s:capture(s,scalars)):
            docs.get_current(self.db,self.db.get(User,1),5,row.document_id)
        for table in ('users','driver_profiles','driver_verification_documents'):
            self.assertTrue(any('FROM '+table in sql and 'FOR UPDATE' in sql for sql in compiled),table)


if __name__=='__main__':main(verbosity=2)
