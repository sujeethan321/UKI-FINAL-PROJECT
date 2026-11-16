"""Missing schema is diagnosed safely; only isolated synthetic MySQL fixtures."""
import pytest
from pymysql.err import ProgrammingError as MySQLProgrammingError
from pymysql.err import OperationalError as MySQLOperationalError
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import event
from test_admin_foundation import admin, api, db, shop, call
from test_catalogue import request


@pytest.mark.parametrize('path,service',[('/overview','overview'),('/audit-events','audit_events')])
def test_admin_missing_table_returns_safe_schema_code(admin,monkeypatch,path,service):
    def missing(*args,**kwargs):
        raise ProgrammingError('SELECT PRIVATE SQL',{'secret':'PRIVATE'},
            MySQLProgrammingError(1146,"Table 'PRIVATE_SCHEMA.PRIVATE_TABLE' doesn't exist"))
    monkeypatch.setattr('app.services.admin_service.'+service,missing)
    response=call(admin,path)
    assert response.status_code==503 and response.headers['cache-control']=='no-store'
    assert response.json()=={'detail':{'code':'ADMIN_SCHEMA_UNAVAILABLE',
        'message':'Required Administrator database structures are unavailable. Contact the platform operator.'}}
    assert 'PRIVATE' not in response.text


def test_database_connectivity_error_is_not_misclassified_as_schema(admin,monkeypatch):
    def unavailable(*args):raise OperationalError('PRIVATE',{},MySQLOperationalError(2003,'PRIVATE credentials'))
    monkeypatch.setattr('app.services.admin_service.overview',unavailable)
    response=call(admin,'/overview')
    assert response.status_code==503
    assert response.json()=={'detail':'Administrator operation could not be confirmed; refresh before retrying'}
    assert 'PRIVATE' not in response.text and 'ADMIN_SCHEMA_UNAVAILABLE' not in response.text


def test_schema_diagnostics_remain_admin_only(admin,monkeypatch):
    called=[]
    def missing(*args):called.append(True);raise AssertionError('Must authorize before service')
    monkeypatch.setattr('app.services.admin_service.overview',missing)
    assert admin['client'].get('/api/v1/admin/overview').status_code==401
    for role in ['customer','shop_owner','driver']:
        response=request(admin,'/admin/overview',actor=admin['make_user'](role))
        assert response.status_code==403 and 'ADMIN_SCHEMA_UNAVAILABLE' not in response.text
    assert called==[]


def test_current_test_schema_serves_overview_activity_without_catalogue_or_ledger_queries(admin):
    statements=[];connection=admin['db'].connection()
    def observe(conn,cursor,statement,parameters,context,many):statements.append(statement.lower())
    event.listen(connection,'before_cursor_execute',observe)
    try:
        overview=call(admin,'/overview');activity=call(admin,'/audit-events',limit=5,offset=0)
        assert overview.status_code==activity.status_code==200
        assert overview.json()['total_orders']==0 and activity.json()['events']==[]
    finally:event.remove(connection,'before_cursor_execute',observe)
    sql=' '.join(statements)
    for table in ['product_categories','products','ledger_entries','credit_accounts']:
        assert table not in sql
    assert all(not s.lstrip().startswith(('insert ','update ','delete ')) for s in statements)
    for secret in ['password_hash','credit_limit','outstanding_balance','repayment']:
        assert secret not in overview.text and secret not in activity.text
