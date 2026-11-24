"""Step 13.52: supplied manual inventory and mocked runner sessions only."""
import ast
import copy
from decimal import Decimal
import importlib.util
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('viva_dba_gate_review',ROOT/'backend/scripts/viva_migration_execute.py')
v=importlib.util.module_from_spec(spec);sys.modules[spec.name]=v;spec.loader.exec_module(v)

# Exact supplied fields, mapped to query aliases. CONNECTION_TYPE was NOT supplied.
MANUAL=[dict(thread_id=44,thread_name='thread/sql/event_scheduler',id=5,user='event_scheduler',host='localhost',database=None,command='Daemon',state='Waiting on empty queue'),
        dict(thread_id=47,thread_name='thread/sql/compress_gtid_table',id=7,user=None,host=None,database=None,command='Daemon',state='Suspending'),
        dict(thread_id=69,thread_name='thread/sql/one_connection',id=28,user='root',host='localhost',database=None,command='Query',state='executing')]

def client(cid,user=None,database=None,command='Sleep'):
    return dict(id=cid,user=user or v.g.MIGRATOR.split('@')[0],database=database or v.SOURCE,command=command,host='localhost',thread_name='thread/sql/one_connection',connection_type='SSL/TLS')

def conditional_manual():
    # Conditional offline cases, not additional claims about the manual snapshot.
    return [dict(row,connection_type=None if row['command']=='Daemon' else 'SSL/TLS') for row in MANUAL]

class GateTests(unittest.TestCase):
    def setUp(self):
        self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('NO_REAL_MYSQL'));self.net.start();self.addCleanup(self.net.stop)
    def check(self,rows=None,ids=None,own=28):
        if rows is None:rows=conditional_manual()+[client(27)]
        return v.check_client_inventory(rows,[27] if ids is None else ids,own,'root')
    def test_exact_manual_fields_do_not_prove_required_null_connection_type(self):
        self.assertFalse(v.internal_mysql_daemon(MANUAL[0]));self.assertFalse(v.internal_mysql_daemon(MANUAL[1]))
        with self.assertRaisesRegex(v.VivaStop,'DBA_THREAD_METADATA_INCOMPLETE'):self.check(MANUAL)
    def test_both_known_daemons_match_if_unreported_connection_types_are_null(self):
        rows=conditional_manual()
        self.assertTrue(v.internal_mysql_daemon(rows[0]));self.assertTrue(v.internal_mysql_daemon(rows[1]));self.assertFalse(v.internal_mysql_daemon(rows[2]))
        report=self.check(rows+[client(27)])
        self.assertEqual(report,dict(expected_client_count=2,foreground_count=4,internal_daemon_count=2,observed_client_count=2,unexpected_client_count=0,missing_expected_count=0,self_visible=True,expected_connection_ids=[27,28],unexpected_connection_ids=[],missing_connection_ids=[],id_list_truncated=False))
    def test_manual_snapshot_without_running_migrator_correctly_stops(self):
        with self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CONNECTION_NOT_VISIBLE') as caught:self.check(conditional_manual())
        details=v.failure_details(caught.exception);self.assertEqual(details['dba_missing_expected_count'],1);self.assertEqual(details['dba_unexpected_client_count'],0)
    def test_thread_id_is_not_used_as_processlist_connection_id(self):
        self.check()
        with self.assertRaisesRegex(v.VivaStop,'DBA_SELF_CONNECTION_NOT_VISIBLE'):self.check(own=69)
    def test_bad_known_daemon_attributes_get_specific_diagnostics(self):
        for index,change,reason in [(0,dict(connection_type='SSL/TLS'),'CONNECTION_TYPE_PRESENT'),(1,dict(connection_type='NULL'),'CONNECTION_TYPE_PRESENT'),(0,dict(command='Sleep'),'COMMAND_MISMATCH'),(1,dict(user='root'),'USER_MISMATCH'),(0,dict(host='remote'),'HOST_MISMATCH'),(1,dict(database=v.SOURCE),'DATABASE_PRESENT')]:
            rows=conditional_manual()+[client(27)];rows[index].update(change)
            with self.subTest(reason=reason),self.assertRaisesRegex(v.VivaStop,'DBA_INTERNAL_DAEMON_CLASSIFICATION_FAILED') as caught:self.check(rows)
            self.assertEqual(v.failure_details(caught.exception)['dba_daemon_reason'],reason)
    def test_unknown_null_users_and_daemons_are_never_whitelisted(self):
        for row in [dict(id=99,user=None,thread_name='thread/sql/unknown_daemon',command='Daemon',host=None,database=None,connection_type=None),dict(id=99,user='event_scheduler',thread_name='thread/sql/event_worker',command='Query',host='localhost',database=None,connection_type=None)]:
            with self.assertRaisesRegex(v.VivaStop,'DBA_UNEXPECTED_CLIENTS_STOP'):self.check(conditional_manual()+[client(27),row])
    def test_second_root_client_is_rejected_even_when_idle(self):
        row=client(99,'root',command='Sleep');row['database']=None
        with self.assertRaisesRegex(v.VivaStop,'DBA_UNEXPECTED_CLIENTS_STOP'):self.check(conditional_manual()+[client(27),row])
    def test_missing_self_and_other_session_visibility_are_distinct(self):
        with self.assertRaisesRegex(v.VivaStop,'DBA_SELF_CONNECTION_NOT_VISIBLE'):self.check([client(27)])
        with self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CONNECTION_NOT_VISIBLE'):self.check(conditional_manual())
        with self.assertRaisesRegex(v.VivaStop,'DBA_UNEXPECTED_AND_MISSING_CLIENTS_STOP'):self.check(conditional_manual()+[client(99)])
    def test_duplicate_and_malformed_rows_fail_before_set_comparison(self):
        rows=conditional_manual()+[client(27)]
        with self.assertRaisesRegex(v.VivaStop,'DBA_DUPLICATE_PROCESSLIST_ID'):self.check(rows+[copy.deepcopy(rows[-1])])
        for bad in (None,True,'27',Decimal('27'),0,-1,2**64):
            changed=copy.deepcopy(rows);changed[-1]['id']=bad
            with self.subTest(kind=type(bad).__name__),self.assertRaisesRegex(v.VivaStop,'DBA_THREAD_METADATA_INVALID'):self.check(changed)
    def test_missing_columns_are_not_equivalent_to_sql_null(self):
        for field in v.THREAD_FIELDS:
            rows=conditional_manual()+[client(27)];rows[0].pop(field)
            with self.subTest(field=field),self.assertRaisesRegex(v.VivaStop,'DBA_THREAD_METADATA_INCOMPLETE'):self.check(rows)
    def test_expected_ids_must_be_unique_positive_integers_distinct_from_dba(self):
        for ids in ([],[27,27],[28],[True],['27'],[Decimal('27')],[None],[0],[-1],[27,29,30]):
            with self.subTest(kind='bad_expected_ids'),self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CONNECTION_IDS_INVALID'):self.check(ids=ids)
    def test_visible_ids_do_not_override_authenticated_roles_or_tls(self):
        for changes in (dict(user='root'),dict(database='lankapex_db'),dict(connection_type='TCP/IP'),dict(thread_name='thread/sql/event_worker'),dict(command='Query')):
            rows=conditional_manual()+[dict(client(27),**changes)]
            with self.subTest(kind='identity_mismatch'),self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH'):self.check(rows)
    def test_source_and_scratch_roles_are_exact_and_cannot_be_duplicated(self):
        rows=conditional_manual()+[client(27),client(29,v.SCRATCH_USER,v.SCRATCH)]
        self.assertEqual(self.check(rows,ids=[27,29])['expected_client_count'],3)
        rows[-1]=client(29)
        with self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CLIENT_IDENTITY_MISMATCH'):self.check(rows,ids=[27,29])
    def test_real_pymysql_handshake_id_agrees_with_sql_without_connecting(self):
        import pymysql
        raw=pymysql.connect(user='fictional',defer_connect=True);raw.server_thread_id=(27,)
        with patch.object(v,'scalar',return_value=27):self.assertEqual(v.verified_connection_id(raw),27)
        self.assertIsNone(raw._sock)
    def test_handshake_mismatch_types_and_connection_replacement_are_blocked(self):
        raw=Mock();raw.thread_id.return_value=27
        with patch.object(v,'scalar',return_value=29),self.assertRaisesRegex(v.VivaStop,'DBA_CONNECTION_ID_MISMATCH'):v.verified_connection_id(raw)
        for value in (True,'27',Decimal('27'),None):
            with patch.object(v,'scalar',return_value=value),self.assertRaisesRegex(v.VivaStop,'DBA_CONNECTION_ID_INVALID'):v.verified_connection_id(raw)
        with patch.object(v,'scalar',return_value=27):v.verified_connection_id(raw)
        raw.thread_id.return_value=29
        with patch.object(v,'scalar',return_value=29),self.assertRaisesRegex(v.VivaStop,'DBA_CONNECTION_ID_CHANGED'):v.verified_connection_id(raw)
    def gate(self,*,rows=None,extra_query=None,close_error=None,grants=None,query_error=None):
        raw=Mock();raw.thread_id.return_value=28
        if close_error:raw.close.side_effect=close_error
        rows=conditional_manual()+[client(27)] if rows is None else rows
        def scalar(raw,sql,parameters=()):return v.g.UUID if 'server_uuid' in sql else 'root@localhost' if 'CURRENT_USER' in sql else 28
        def query(raw,sql,parameters=()):
            if sql.startswith('SHOW GRANTS'):return [{'grant':grants or "GRANT SELECT, PROCESS, EVENT ON *.* TO 'root'@'localhost'"}]
            if 'performance_schema.threads' in sql:
                if query_error:raise query_error
                self.assertNotIn('PROCESSLIST_ID IS NOT NULL',sql)
                return rows
            if extra_query and extra_query in sql:return [{'fictional':'not private'}]
            return []
        with patch('pymysql.connect',return_value=raw),patch.object(v.tls,'context'),patch.object(v.tls,'verify_socket'),patch.object(v,'scalar',side_effect=scalar),patch.object(v,'query',side_effect=query):
            try:return v.dba_gate('root','FICTIONAL_SECRET',[27])
            finally:raw.close.assert_called_once()
    def test_actual_dba_gate_accepts_complete_conditional_inventory(self):
        self.assertEqual(self.gate()['client_inventory']['internal_daemon_count'],2)
    def test_unknown_foreground_null_id_is_observed_and_rejected(self):
        row=client(None,'unverified')
        with self.assertRaisesRegex(v.VivaStop,'DBA_THREAD_METADATA_INVALID'):self.gate(rows=conditional_manual()+[client(27),row])
    def test_visibility_sql_errors_keep_original_class_and_safe_numeric_code(self):
        import pymysql
        for code,category in [(1142,'DBA_VISIBILITY_PERMISSION_DENIED'),(1146,'DBA_VISIBILITY_UNAVAILABLE'),(2013,'DBA_QUERY_FAILED')]:
            original=pymysql.err.OperationalError(code,'FICTIONAL_PRIVATE_SQL_AND_CREDENTIAL')
            with self.subTest(code=code),self.assertRaises(pymysql.err.OperationalError) as caught:self.gate(query_error=original)
            self.assertIs(caught.exception,original);self.assertEqual(v.diagnostic(original),category)
            self.assertEqual(v.failure_details(original)['dba_mysql_code'],code);self.assertNotIn('FICTIONAL_PRIVATE_SQL_AND_CREDENTIAL',str(v.failure_details(original)))
    def test_events_transactions_replication_and_locks_still_block(self):
        for query,code in [('information_schema.innodb_trx','UNEXPLAINED_TRANSACTION'),("STATUS='ENABLED'",'EVENT_WRITER_ENABLED'),('information_schema.ROUTINES','UNEXPECTED_ROUTINE'),('EVENT_SCHEMA IN','UNEXPECTED_EVENT'),('replication_applier_status','REPLICATION_WRITER_ENABLED'),('metadata_locks','PENDING_METADATA_LOCK')]:
            with self.subTest(code=code),self.assertRaisesRegex(v.VivaStop,code):self.gate(extra_query=query)
    def test_missing_dba_visibility_privileges_are_not_treated_as_empty_inventory(self):
        with self.assertRaisesRegex(v.VivaStop,'DBA_PROCESS_VISIBILITY_REQUIRED'):self.gate(grants="GRANT SELECT, EVENT ON *.* TO 'root'@'localhost'")
        with self.assertRaisesRegex(v.VivaStop,'DBA_METADATA_VISIBILITY_REQUIRED'):self.gate(grants="GRANT PROCESS, EVENT ON *.* TO 'root'@'localhost'")
    def test_dba_close_failure_cannot_hide_original_inventory_failure(self):
        with self.assertRaisesRegex(v.VivaStop,'DBA_EXPECTED_CONNECTION_NOT_VISIBLE') as caught:self.gate(rows=conditional_manual(),close_error=RuntimeError('FICTIONAL_PRIVATE_MESSAGE'))
        details=v.failure_details(caught.exception);self.assertEqual(details['dba_cleanup'],'INCOMPLETE');self.assertNotIn('FICTIONAL_PRIVATE_MESSAGE',str(details))
    def test_close_only_failure_cannot_report_gate_success(self):
        with self.assertRaisesRegex(v.VivaStop,'DBA_CONNECTION_CLOSE_FAILED'):self.gate(close_error=RuntimeError('FICTIONAL_SECRET'))
    def test_gate_for_revalidates_owned_sockets_on_every_call(self):
        source=Mock();source.thread_id.return_value=27;scratch=Mock();scratch.thread_id.return_value=29
        with patch.object(v,'scalar',side_effect=lambda raw,sql:27 if raw is source else 29),patch.object(v,'dba_gate',return_value={}) as gate:
            v.gate_for('root','FICTIONAL_SECRET',source);v.gate_for('root','FICTIONAL_SECRET',source,scratch);v.gate_for('root','FICTIONAL_SECRET',source)
        self.assertEqual([call.args[2] for call in gate.call_args_list],[[27],[27,29],[27]])
        self.assertEqual(source.thread_id.call_count,3);self.assertEqual(scratch.thread_id.call_count,1)
    def test_all_execution_modes_and_readonly_path_use_shared_fresh_gate(self):
        tree=ast.parse((ROOT/'backend/scripts/viva_migration_execute.py').read_text(encoding='utf-8'))
        calls=[]
        for function in [node for node in tree.body if isinstance(node,ast.FunctionDef)]:
            for node in ast.walk(function):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dba_gate':calls.append(function.name)
        self.assertEqual(calls,['gate_for'])
    def test_failure_diagnostics_do_not_persist_session_users_hosts_databases_or_sql(self):
        row=client(99,'FICTIONAL_PRIVATE_CUSTOMER',database='FICTIONAL_PRIVATE_DATABASE');row['host']='FICTIONAL_PRIVATE_HOST'
        with self.assertRaises(v.VivaStop) as caught:self.check(conditional_manual()+[client(27),row])
        output=str(v.failure_details(caught.exception));self.assertEqual(v.diagnostic(caught.exception),'DBA_UNEXPECTED_CLIENTS_STOP')
        for value in ('FICTIONAL_PRIVATE_CUSTOMER','FICTIONAL_PRIVATE_DATABASE','FICTIONAL_PRIVATE_HOST'):self.assertNotIn(value,output)
        self.assertEqual(v.failure_details(caught.exception)['dba_unexpected_client_count'],1)
        self.assertEqual(v.failure_details(caught.exception)['dba_unexpected_connection_ids'],'99')

if __name__=='__main__':unittest.main()
