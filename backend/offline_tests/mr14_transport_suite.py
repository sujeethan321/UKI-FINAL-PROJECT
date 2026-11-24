"""Offline MR-14 policy tests: no certificates/approvals issued, no MySQL."""
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import socket
import ssl
import unittest
from unittest.mock import patch,MagicMock

spec=importlib.util.spec_from_file_location('mr14_test',Path(__file__).resolve().parents[1]/'scripts/mr14_readonly_transport.py')
import sys
t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN'));self.network.start();self.addCleanup(self.network.stop)
        self.ca=b'FICTIONAL INVALID CERTIFICATE'
        self.binding=t.SourceBinding('127.0.0.1',3306,'12345678-1234-1234-1234-123456789abc',t.d.m.SOURCE,t.d.a.SOURCE_ACCOUNT,hashlib.sha256(self.ca).hexdigest().upper())
    def test_exact_binding(self):t.validate_binding(self.binding,self.binding)
    def test_no_approval(self):
        with self.assertRaisesRegex(t.Rejected,'APPROVAL_REQUIRED'):t.validate_binding(self.binding,None)
    def test_substitution(self):
        for field,value in [('host','other.example'),('port',3307),('server_uuid','00000000-1234-1234-1234-123456789abc'),('schema',t.d.m.TARGET),('account','root@localhost'),('ca_sha256','A'*64)]:
            with self.subTest(field=field),self.assertRaises(t.Rejected):t.validate_binding(replace(self.binding,**{field:value}),self.binding)
    def test_self_matching_wrong_account_is_still_rejected(self):
        config=replace(self.binding,account='root@localhost')
        with self.assertRaisesRegex(t.Rejected,'SOURCE_READER_ONLY'):t.validate_binding(config,config)
    def test_invalid_endpoint_and_uuid(self):
        for config in [replace(self.binding,host='localhost;drop'),replace(self.binding,port=True),replace(self.binding,server_uuid='mock')]:
            with self.assertRaises(t.Rejected):t.validate_binding(config,config)
    def test_invalid_certificate(self):
        with self.assertRaisesRegex(t.Rejected,'CA_INVALID'):t.certificate_context(self.binding,self.binding,self.ca)
    def test_changed_certificate(self):
        with self.assertRaisesRegex(t.Rejected,'CA_IDENTITY_MISMATCH'):t.certificate_context(self.binding,self.binding,b'CHANGED')
    def test_tls_context_policy_with_mock_parser(self):
        context=MagicMock()
        with patch.object(t.ssl,'SSLContext',return_value=context) as factory:
            self.assertIs(t.certificate_context(self.binding,self.binding,self.ca),context)
        factory.assert_called_once_with(ssl.PROTOCOL_TLS_CLIENT)
        self.assertTrue(context.check_hostname);self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertEqual(context.minimum_version,ssl.TLSVersion.TLSv1_2)
        context.load_verify_locations.assert_called_once_with(cadata=self.ca.decode())
    def test_all_metadata_query_plans(self):
        for key in t.d.SQL:
            table='orders' if key in ('columns','keys','foreign_keys','checks','indexes') else None
            t.inspect_plan(t.d.plan(key,t.d.m.SOURCE,table),table)
    def test_financial_and_orphan_queries(self):
        t.inspect_plan(t.d.plan('rows',t.d.m.SOURCE,'orders',['order_id','total']),'orders')
        tables=t.d.c.build()['stages'][t.d.m.CHAIN[0]]['tables']
        for name,table in tables.items():
            for fk in table['foreign_keys']:t.inspect_plan(t.d.orphan_plan(t.d.m.SOURCE,name,fk),name)
    def test_sql_bypass_attempts(self):
        for sql in ('DELETE FROM orders','SELECT 1; DROP TABLE orders','SELECT * FROM lankapex_db.orders','SELECT * FROM orders INTO OUTFILE /tmp/a'):
            with self.assertRaises(t.Rejected):t.inspect_plan(t.d.ReadPlan('rows',sql,()),'orders')
        with self.assertRaises(t.Rejected):t.inspect_plan('SELECT 1')
        with self.assertRaises(t.Rejected):t.inspect_plan(t.d.plan('tables',t.d.m.TARGET))
    def test_bad_column_and_table(self):
        with self.assertRaises(t.Rejected):t.inspect_plan(t.d.plan('rows',t.d.m.SOURCE,'orders',['secret']),'orders')
        with self.assertRaises(t.Rejected):t.inspect_plan(t.d.plan('count',t.d.m.SOURCE,'driver_earnings'),'driver_earnings')
    def test_observed_identity(self):
        row=dict(server_uuid=self.binding.server_uuid,database_name=self.binding.schema,account=self.binding.account)
        t.verify_observed_identity(self.binding,self.binding,row)
        for field in row:
            with self.assertRaises(t.Rejected):t.verify_observed_identity(self.binding,self.binding,dict(row,**{field:'wrong'}))
    def test_no_activation_or_mock_trust_bypass(self):
        transport=t.SourceInspectionTransport()
        for method in ('connect','fetch','execute','verify_trusted_authorization'):
            with self.assertRaises(t.Rejected):getattr(transport,method)(execute=True,approved=True,evidence={'mock':True})
        for method in ('connect','fetch','upgrade'):
            with self.assertRaises(t.d.m.GuardFailure):getattr(t.d.DisabledRealTransport(),method)()

if __name__=='__main__':unittest.main()
