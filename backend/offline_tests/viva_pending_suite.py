"""Source-only VIVA safety checks; all network forbidden."""
import importlib.util
from pathlib import Path
import sys
import socket
import ssl
import unittest
from unittest.mock import patch,Mock

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
spec=importlib.util.spec_from_file_location('viva_pending',ROOT/'backend/scripts/viva_pending_migrations.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from app.core import viva_tls as tls

class SafetyTests(unittest.TestCase):
    def setUp(self):
        guard=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'))
        guard.start();self.addCleanup(guard.stop)
    def test_graph_and_exact_stage_sets(self):
        self.assertEqual(len(m.graph()),22)
        contract=m.recovery_contract()
        self.assertEqual([(len(contract.tables_at(r)),len(contract.trigger_contract(r))) for r in m.CHAIN],list(m.COUNTS))
    def test_wrong_targets_and_accounts(self):
        for database,account in (('lankapex_db',m.MIGRATOR),(m.SOURCE,m.SCRATCH_ACCOUNT),(m.SCRATCH,m.MIGRATOR)):
            with self.assertRaises(RuntimeError):m.target_guard(database,account)
    def test_exact_stages_only(self):
        for pair in ((m.CHAIN[0],m.CHAIN[-1]),(m.CHAIN[1],m.CHAIN[0]),(m.CHAIN[0],'head')):
            with self.assertRaises(RuntimeError):m.stage_guard(*pair)
    def observation(self):
        return dict(host='127.0.0.1',port=3306,server_uuid=m.UUID,database=m.SCRATCH,account=m.SCRATCH_ACCOUNT,
            revision=m.CHAIN[0],version='8.0.46',tls_verified=True,roles='NONE',mandatory_roles='',grants=list(m.RIGHTS),
            grant_scope=m.SCRATCH,grant_option=False,writer_freeze=True,ddl_freeze=True,observed_at=100,expires_at=200,
            log_bin=True,log_bin_trust_function_creators=1,tables=list(m.recovery_contract().tables_at(m.CHAIN[0])),triggers={})
    def test_identity_privileges_freeze_and_binary_logging_stop(self):
        value=self.observation();kwargs=dict(database=m.SCRATCH,account=m.SCRATCH_ACCOUNT,revision=m.CHAIN[0],now=150)
        m.observed_guard(value,**kwargs)
        for key,bad in (('server_uuid','wrong'),('account',m.MIGRATOR),('grants',['SUPER']),('grant_scope',m.SOURCE),('roles','admin'),('expires_at',140),('log_bin',False),('log_bin_trust_function_creators',0),('tables',[]),('tls_verified',False)):
            with self.subTest(key=key),self.assertRaises(RuntimeError):m.observed_guard(dict(value,**{key:bad}),**kwargs)
    def test_original_projections_preserved(self):
        before={name:dict(columns=['id','amount'],row_count=2,content_sha256='A'*64) for name in m.recovery_contract().tables_at(m.CHAIN[0]) if name!='alembic_version'}
        m.preservation(before,before)
        for alteration in (dict(columns=['id'],row_count=2,content_sha256='A'*64),dict(columns=['id','amount'],row_count=2,content_sha256='B'*64)):
            after=dict(before);after['orders']=alteration
            with self.assertRaises(RuntimeError):m.preservation(before,after)
        with self.assertRaises(RuntimeError):m.preservation({}, {})
    def test_strict_ca_and_missing_ca_fail_closed(self):
        with patch.object(ssl.SSLContext,'load_verify_locations') as load:
            ctx=tls.context();load.assert_called_once_with(cafile=str(tls.CA_PATH))
            self.assertTrue(ctx.check_hostname);self.assertEqual(ctx.verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(ctx.verify_flags&ssl.VERIFY_X509_STRICT)
        with self.assertRaises(ValueError):tls.context('other.pem')
        with patch.object(ssl.SSLContext,'load_verify_locations',side_effect=OSError('MISSING_CA')):
            with self.assertRaises(OSError):tls.context()
    def test_peer_fingerprint_and_plain_socket_rejected(self):
        with self.assertRaises(ValueError):tls.verify_socket(object())
        sock=Mock(spec=ssl.SSLSocket);sock.version.return_value='TLSv1.3'
        with patch.object(ssl.SSLContext,'load_verify_locations'):sock.context=tls.context()
        sock.getpeercert.return_value=b'FICTIONAL_DER'
        with self.assertRaisesRegex(ValueError,'CERTIFICATE_MISMATCH'):tls.verify_socket(sock)
    def test_execution_disabled(self):
        with self.assertRaisesRegex(RuntimeError,'NOT_APPROVED'):m.execute_stage()

if __name__=='__main__':unittest.main()
