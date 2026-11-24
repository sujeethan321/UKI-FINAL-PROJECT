"""Fictional certificates and MemoryBIO TLS only: no sockets or database."""
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch,MagicMock

spec=importlib.util.spec_from_file_location('mr16_transport',Path(__file__).resolve().parents[1]/'scripts/mr14_readonly_transport.py')
t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)

class SANTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        openssl=Path('C:/Program Files/Git/usr/bin/openssl.exe')
        if not openssl.is_file():raise RuntimeError('OFFLINE_CERTIFICATE_TOOL_REQUIRED')
        for name,san in [('cn',None),('dns','DNS:reader.example.test'),('ip','IP:127.0.0.1')]:
            args=[str(openssl),'req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=reader.example.test','-keyout',str(cls.root/(name+'.key')),'-out',str(cls.root/(name+'.pem'))]
            if san:args+=['-addext','subjectAltName='+san]
            subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    def setUp(self):
        self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK'));self.network.start();self.addCleanup(self.network.stop)
    def context(self,name,host):
        ca=(self.root/(name+'.pem')).read_bytes()
        b=t.SourceBinding(host,3306,'12345678-1234-1234-1234-123456789abc',t.d.m.SOURCE,t.d.a.SOURCE_ACCOUNT,hashlib.sha256(ca).hexdigest().upper())
        return t.certificate_context(b,b,ca)
    def handshake(self,name,host):
        context=self.context(name,host);server=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.load_cert_chain(self.root/(name+'.pem'),self.root/(name+'.key'))
        ci,co,si,so=[ssl.MemoryBIO() for _ in range(4)]
        client=context.wrap_bio(ci,co,server_hostname=host);peer=server.wrap_bio(si,so,server_side=True)
        done=set()
        for _ in range(20):
            for label,obj in [('client',client),('server',peer)]:
                try:obj.do_handshake();done.add(label)
                except ssl.SSLWantReadError:pass
            if co.pending:si.write(co.read())
            if so.pending:ci.write(so.read())
            if len(done)==2:return
        self.fail('MEMORY_HANDSHAKE_INCOMPLETE')
    def test_valid_dns_san(self):self.handshake('dns','reader.example.test')
    def test_valid_ip_san(self):self.handshake('ip','127.0.0.1')
    def test_cn_only_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.handshake('cn','reader.example.test')
    def test_wrong_dns_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.handshake('dns','other.example.test')
    def test_wrong_ip_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.handshake('ip','127.0.0.2')
    def test_dns_san_does_not_authorize_ip(self):
        with self.assertRaises(ssl.SSLCertVerificationError):self.handshake('dns','127.0.0.1')
    def test_unsupported_runtime_rejected(self):
        with patch.object(t.ssl,'HAS_NEVER_CHECK_COMMON_NAME',False),self.assertRaisesRegex(t.Rejected,'SAN_ONLY_UNSUPPORTED'):self.context('dns','reader.example.test')
    def test_missing_runtime_capability_rejected(self):
        with patch.object(t.ssl,'HAS_NEVER_CHECK_COMMON_NAME',None),self.assertRaisesRegex(t.Rejected,'SAN_ONLY_UNSUPPORTED'):self.context('dns','reader.example.test')
    def test_ineffective_san_setting_rejected(self):
        class Unsupported:
            hostname_checks_common_name=property(lambda self:True,lambda self,value:None)
        with patch.object(t.ssl,'SSLContext',return_value=Unsupported()),self.assertRaisesRegex(t.Rejected,'SAN_ONLY_UNSUPPORTED'):self.context('dns','reader.example.test')
    def test_disabled_certificate_verification_rejected(self):
        class Insecure:
            verify_mode=property(lambda self:ssl.CERT_NONE,lambda self,value:None)
        with patch.object(t.ssl,'SSLContext',return_value=Insecure()),self.assertRaisesRegex(t.Rejected,'SAN_ONLY_UNSUPPORTED'):self.context('dns','reader.example.test')
    def test_policy_preserved(self):
        context=self.context('dns','reader.example.test')
        self.assertFalse(context.hostname_checks_common_name);self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED);self.assertEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
    def test_blockers_preserved(self):
        with self.assertRaises(t.Rejected):t.SourceInspectionTransport().connect()
        with self.assertRaises(t.d.m.GuardFailure):t.d.DisabledRealTransport().connect()

if __name__=='__main__':unittest.main()
