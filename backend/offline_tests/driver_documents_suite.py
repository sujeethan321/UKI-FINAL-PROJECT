"""Synthetic fixtures only. SQLite + isolated parser workers; no DB/network access."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
from unittest import TestCase, main
from unittest.mock import patch
import subscription_suite as base
from PIL import Image
import pymupdf
from app.models import DriverProfile, DriverVerificationDocument, DriverDocumentAudit
from app.services import driver_document_storage as storage
from app.services.driver_document_service import append_version, application_documents_ready
from app.core.driver_document_body_limit import DriverDocumentBodyLimit
from app.services.driver_document_limits import attach_limits


def image(kind='PNG'):
    data=BytesIO(); im=Image.new('RGB',(30,40),'white')
    exif=Image.Exif();exif[270]='FICTIONAL FIXTURE'
    im.save(data,format=kind,exif=exif); return data.getvalue()


def pdf(pages=1, encrypted=False, unsafe=False):
    with pymupdf.open() as doc:
        for _ in range(pages): doc.new_page().insert_text((40,40),'FICTIONAL DOCUMENT')
        if unsafe:
            root=doc.pdf_catalog(); doc.xref_set_key(root,'OpenAction',r'<< /S /JavaScript /JS (app.alert\(1\)) >>')
        if encrypted: return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='fictional-owner',user_pw='fictional-user')
        return doc.tobytes()


class StorageTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        # Test fixture ACL only; production construction still verifies ACLs.
        self.acl=patch.object(storage,'private_acl'); self.acl.start()
        self.store=storage.PrivateDocumentStore(self.root)

    def tearDown(self): self.acl.stop(); self.temp.cleanup()

    def stage(self,data,name='fixture.png',media='image/png'):
        return self.store.stage(BytesIO(data),name,media,storage.UploadBudget())

    def test_valid_images_metadata_stripped_and_pdf_flattened(self):
        for kind,name,mime in [('JPEG','fixture.jpeg','image/jpeg'),('PNG','fixture.png','image/png')]:
            result=self.stage(image(kind),name,mime)
            with Image.open(self.root/result.storage_key) as normalized:
                self.assertFalse(normalized.getexif()); self.assertNotIn('icc_profile',normalized.info)
            self.assertEqual(len(result.storage_key),64)
            self.assertNotIn(result.storage_key,repr(result))
        result=self.stage(pdf(),'fixture.pdf','application/pdf')
        with pymupdf.open(self.root/result.storage_key) as normalized:
            self.assertEqual(len(normalized),1); self.assertFalse(normalized[0].get_text())
        self.assertEqual(len(list(self.root.iterdir())),3)

    def test_extensions_mime_signatures_and_malformed(self):
        for data,name,mime in [(image(),'x.exe','image/png'),(image(),'x.jpg','image/jpeg'),
                (image(),'x.png','application/pdf'),(b'\x89PNG\r\n\x1a\nBAD','x.png','image/png'),
                (b'%PDF-1.7\nBAD','x.pdf','application/pdf'),(b'','x.png','image/png')]:
            with self.assertRaises(storage.DocumentError): self.stage(data,name,mime)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_limits_paths_and_budget(self):
        for name in ('../x.png','x:y.png','dir\\x.png','/x.png'):
            with self.assertRaises(storage.DocumentError): self.stage(image(),name)
        for key in ('../secret','A'*64,'a'*63):
            with self.assertRaises(storage.DocumentError): self.store._path(key)
        with self.assertRaises(storage.DocumentError): self.stage(b'\x89PNG\r\n\x1a\n'+b'x'*storage.MAX_FILE)
        budget=storage.UploadBudget(); budget.consume(storage.MAX_REQUEST)
        with self.assertRaises(storage.DocumentError): budget.consume(1)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_pdf_rejection_and_image_bomb(self):
        for content in (pdf(11),pdf(encrypted=True),pdf(unsafe=True)):
            with self.assertRaises(storage.DocumentError): self.stage(content,'x.pdf','application/pdf')
        data=BytesIO(); Image.new('1',(5000,5000)).save(data,format='PNG')
        with self.assertRaises(storage.DocumentError): self.stage(data.getvalue())
        self.assertEqual(list(self.root.iterdir()),[])

    def test_protection_unavailable_timeout_and_unrelated_file_preserved(self):
        unrelated=self.root/'operator-owned'; unrelated.write_text('fictional')
        for failure in (RuntimeError('private detail'),storage.subprocess.TimeoutExpired('worker',15)):
            with patch.object(storage,'attach_limits',side_effect=failure):
                with self.assertRaises(storage.DocumentError) as caught: self.stage(image())
                self.assertNotIn('private detail',str(caught.exception))
        self.assertEqual(list(self.root.iterdir()),[unrelated])
        with patch.object(Path,'open',side_effect=OSError('sensitive path')):
            with self.assertRaises(storage.DocumentError) as caught: self.stage(image())
            self.assertNotIn('sensitive',str(caught.exception))

    def test_concurrent_uploads_have_unique_private_versions(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.stage(image()),range(2)))
        self.assertNotEqual(results[0].storage_key,results[1].storage_key)
        self.assertEqual(len(list(self.root.iterdir())),2)

    def test_untrusted_roots_and_permission_failure(self):
        with self.assertRaises(storage.DocumentError): storage.PrivateDocumentStore(storage.REPOSITORY)
        with patch.object(storage,'private_acl',side_effect=RuntimeError()):
            with self.assertRaises(storage.DocumentError): storage.PrivateDocumentStore(self.root)
        with self.assertRaises(storage.DocumentError): storage.PrivateDocumentStore('relative')


class MetadataTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with patch.object(storage,'private_acl'): self.store=storage.PrivateDocumentStore(self.temp.name)
        self.engine=base.create_engine('sqlite://',poolclass=base.StaticPool,connect_args={'check_same_thread':False})
        tables=base.TABLES+[DriverProfile.__table__,DriverVerificationDocument.__table__,DriverDocumentAudit.__table__]
        @base.event.listens_for(self.engine,'connect')
        def fk(conn,record): conn.execute('PRAGMA foreign_keys=ON')
        base.Base.metadata.create_all(self.engine,tables=tables)
        self.db=base.Session(self.engine,expire_on_commit=False);base.seed(self.db)
        self.db.add(DriverProfile(user_id=5,approval_status='pending',created_at=datetime(2026,1,1)));self.db.commit()

    def tearDown(self): self.db.close();self.engine.dispose();self.temp.cleanup()

    def candidate(self):
        with patch.object(storage,'private_acl'):
            return self.store.stage(BytesIO(image()),'fixture.png','image/png',storage.UploadBudget())

    def test_version_replacement_constraints_and_uncertain_commit_preservation(self):
        first=append_version(self.db,5,'DRIVING_LICENCE',self.candidate(),self.store);self.db.commit()
        candidate=self.candidate()
        second=append_version(self.db,5,'DRIVING_LICENCE',candidate,self.store);self.db.commit()
        self.assertEqual((first.current_slot,second.version,second.supersedes_id),(None,2,first.document_id))
        self.assertFalse(application_documents_ready(self.db,5))
        self.assertEqual(self.db.scalar(base.select(base.func.count()).select_from(DriverDocumentAudit)),2)
        second.content_sha256='0'*64
        with self.assertRaises(ValueError): self.db.flush()
        self.db.rollback()
        self.assertTrue((self.store.root/candidate.storage_key).exists())
        with self.assertRaises(ValueError): self.db.delete(first);self.db.flush()
        self.db.rollback()

    def test_role_legacy_and_current_uniqueness(self):
        candidate=self.candidate()
        with self.assertRaises(storage.DocumentError): append_version(self.db,2,'DRIVING_LICENCE',candidate,self.store)
        profile=self.db.get(DriverProfile,5)
        profile.approval_status='approved';profile.reviewed_by=1;profile.reviewed_at=datetime(2026,1,1);profile.legacy_document_exempt=True
        self.db.commit()
        with self.assertRaises(storage.DocumentError): append_version(self.db,5,'DRIVING_LICENCE',candidate,self.store)
        self.assertTrue(profile.legacy_document_exempt)
        self.assertEqual(profile.approval_status,'approved')

    def test_database_rejects_competing_current_document(self):
        candidate=self.candidate()
        first=append_version(self.db,5,'DRIVING_LICENCE',candidate,self.store);self.db.commit()
        duplicate=DriverVerificationDocument(document_id='competing',driver_user_id=5,document_type='DRIVING_LICENCE',
            version=2,current_slot=1,storage_key='b'*64,content_sha256='a'*64,media_type='image/png',size_bytes=10,
            created_at=datetime(2026,1,1),validated_at=datetime(2026,1,1),review_status='PENDING')
        self.db.add(duplicate)
        with self.assertRaises(base.IntegrityError): self.db.flush()
        self.db.rollback()
        self.assertEqual(self.db.get(DriverVerificationDocument,first.document_id).current_slot,1)


class InfrastructureTests(TestCase):
    def test_real_windows_memory_limit_rejects_resource_exhaustion(self):
        if storage.os.name!='nt': self.skipTest('Windows Job Object assertion')
        # No parser/file input. Worker waits until the real Job is installed.
        code="import sys; sys.stdin.buffer.readline(); bytearray(768*1024*1024)"
        proc=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),'-I','-c',code],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        close=None
        try:
            close=attach_limits(proc)
            proc.communicate(b'GO\n',timeout=15)
            self.assertNotEqual(proc.returncode,0)
        finally:
            if proc.poll() is None: proc.kill();proc.wait()
            if proc.stdin: proc.stdin.close()
            if close: close()

    def test_multipart_gate_bounds_actual_bytes_before_parser(self):
        async def run(size):
            received=[];sent=[]
            async def app(scope,receive,send): received.append(await receive())
            async def receive(): return dict(type='http.request',body=b'x'*size,more_body=False)
            async def send(message): sent.append(message)
            await DriverDocumentBodyLimit(app,{'/future-upload'})({'type':'http','path':'/future-upload'},receive,send)
            return received,sent
        self.assertEqual(len(asyncio.run(run(100))[0]),1)
        received,sent=asyncio.run(run(11*1024*1024+1))
        self.assertFalse(received);self.assertEqual(sent[0]['status'],413)

    def test_migration_structure_without_execution(self):
        path=Path(__file__).resolve().parents[1]/'alembic/versions/ae2b7c5f1d48_driver_verification_documents.py'
        spec=importlib.util.spec_from_file_location('migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.down_revision,'9d1a6f4e0c37')
        calls=[]
        with patch.object(module,'op') as op:
            module.upgrade()
            self.assertEqual([c.args[0] for c in op.create_table.call_args_list],['driver_verification_documents','driver_document_audits'])
            self.assertEqual(op.add_column.call_args.args[0],'driver_profiles')
            self.assertEqual(str(op.execute.call_args.args[0]),"UPDATE driver_profiles SET legacy_document_exempt=1 WHERE approval_status='approved'")
            self.assertFalse(op.drop_table.called)
        with self.assertRaises(RuntimeError): module.downgrade()


if __name__=='__main__': main(verbosity=2)
