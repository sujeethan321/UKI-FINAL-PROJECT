"""Synthetic SQLite only. Harness blocks networking and real configuration."""
from unittest import TestCase,main
from unittest.mock import patch
from decimal import Decimal
from pathlib import Path
import ast
import subscription_suite as base
from sqlalchemy import create_engine,event,select,update
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import CustomerAddress,UserPreference,User
from app.schemas.customer_address import AddressCreate,AddressUpdate,AddressVersion,DefaultAddress
from app.services import customer_address_service as service,customer_address_rollout as rollout
from app.services.driver_fee_pricing import commitment

@compiles(DATETIME,'sqlite')
def datetime_sqlite(type_,compiler,**kw):return 'DATETIME'

class AddressTests(TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',poolclass=base.StaticPool,connect_args={'check_same_thread':False})
        @event.listens_for(self.engine,'connect')
        def functions(connection,record):
            connection.create_collation('utf8mb4_bin',lambda a,b:(a>b)-(a<b))
            connection.create_function('CHAR_LENGTH',1,len)
        base.create_tables(self.engine)
        # MySQL timestamp defaults are compiled to SQLite equivalents, locally.
        from sqlalchemy.schema import CreateTable,CreateIndex
        for table in (CustomerAddress.__table__,UserPreference.__table__):
            sql=str(CreateTable(table).compile(self.engine)).replace('CURRENT_TIMESTAMP(6)','CURRENT_TIMESTAMP')
            with self.engine.begin() as conn:
                conn.exec_driver_sql(sql)
                for index in table.indexes:conn.exec_driver_sql(str(CreateIndex(index).compile(self.engine)))
        self.db=Session(self.engine,expire_on_commit=False);base.seed(self.db)
        self.user=self.db.get(User,4)
        self.ready=patch.object(rollout,'require_ready');self.ready.start();self.addCleanup(self.ready.stop)
    def tearDown(self):self.db.close();self.engine.dispose()
    def payload(self,version=1,key='synthetic-address-001',**changes):
        return AddressCreate(**(dict(label='Home',recipient_name='Fictional Customer',address_line='Fictional lane\nFloor 2',version=version,request_key=key)|changes))
    def create(self,**changes):
        data=service.mutate(self.db,self.user,self.payload(**changes),'create');self.db.commit();return data
    def test_create_list_edit_archive_default_and_preference_preservation(self):
        first=self.create();ident=first['address']['address_id']
        pref=self.db.get(UserPreference,4);pref.theme='dark';self.db.commit()
        result=service.mutate(self.db,self.user,DefaultAddress(version=2,address_id=ident),'default')
        self.assertEqual(result['version'],3);self.assertEqual(pref.preferred_address_id,ident)
        edit=AddressUpdate(label='Office',recipient_name='Customer',address_line='New fictional road',version=3)
        service.mutate(self.db,self.user,edit,'edit',ident)
        service.mutate(self.db,self.user,AddressVersion(version=4),'archive',ident);self.db.commit()
        self.assertIsNone(pref.preferred_address_id);self.assertEqual(pref.theme,'dark')
        self.assertEqual(service.listing(self.db,self.user)['total'],0)
        self.assertEqual(service.listing(self.db,self.user,archived=True)['total'],1)
    def test_idempotency_conflicts_and_archived_replay(self):
        first=self.create();self.assertTrue(service.mutate(self.db,self.user,self.payload(),'create')['replayed'])
        with self.assertRaises(HTTPException):service.mutate(self.db,self.user,self.payload(label='Different'),'create')
        service.mutate(self.db,self.user,AddressVersion(version=2),'archive',first['address']['address_id']);self.db.commit()
        self.assertTrue(service.mutate(self.db,self.user,self.payload(),'create')['address']['archived'])
    def test_stale_versions_and_active_limit(self):
        for i in range(10):self.create(version=i+1,key='synthetic-address-'+str(i).zfill(3))
        with self.assertRaises(HTTPException) as error:self.create(version=11,key='synthetic-address-999')
        self.assertEqual(error.exception.detail['code'],'ADDRESS_LIMIT')
        with self.assertRaises(HTTPException):service.mutate(self.db,self.user,DefaultAddress(version=1,address_id=1),'default')
    def test_roles_ownership_archived_defaults_and_unknown_fields(self):
        first=self.create();ident=first['address']['address_id']
        for role in (1,2,5):
            with self.assertRaises(HTTPException):service.listing(self.db,self.db.get(User,role))
        other=User(user_id=6,full_name='Other Customer',email='other@invalid.example',password_hash='unused',platform_role='customer',account_status='active')
        self.db.add(other);self.db.commit()
        with self.assertRaises(HTTPException) as error:service.owned(self.db,other,ident)
        self.assertEqual(error.exception.status_code,404)
        service.mutate(self.db,self.user,AddressVersion(version=2),'archive',ident);self.db.commit()
        with self.assertRaises(HTTPException):service.mutate(self.db,self.user,DefaultAddress(version=3,address_id=ident),'default')
        with self.assertRaises(ValueError):self.payload(user_id=6)
    def test_unicode_controls_and_limits(self):
        self.assertIn('\n',self.payload().address_line)
        for field,value in [('label','a'*51),('address_line','\u202eInjected'),('recipient_name','\x00Name'),('city','a'*101),('phone','1'*21)]:
            with self.assertRaises(ValueError):self.payload(**{field:value})
    def test_signed_destination_binding_and_fee_preserved(self):
        lines=[dict(product_id=1,quantity=1,unit_price=Decimal('5000.00'))]
        binding=[1,2,'a'*64]
        values,token=commitment(4,10,lines,Decimal('5000.00'),'delivery',destination=binding)
        self.assertEqual(values['delivery_fee'],'150.00')
        self.assertEqual(commitment(4,10,lines,Decimal('5000.00'),'delivery',token,destination=binding)[0],values)
        for other in ([2,2,'a'*64],[1,3,'a'*64],[1,2,'b'*64]):
            with self.assertRaises(HTTPException):commitment(4,10,lines,Decimal('5000.00'),'delivery',token,destination=other)
        self.assertEqual(commitment(4,10,lines,Decimal('5000.00'),'pickup')[0]['delivery_fee'],'0.00')
    def test_disabled_gate_performs_no_queries(self):
        with patch.multiple(base.config.settings,ADDRESS_BOOK_ENABLED=False,ADDRESS_CHECKOUT_ENABLED=False,create=True):
            self.ready.stop()
            try:
                with self.assertRaises(HTTPException):rollout.require_ready(None)
            finally:self.ready.start()
    def test_migration_static_chain_and_immutability(self):
        path=Path(__file__).parents[1]/'alembic/versions/d15a8c902e64_customer_addresses.py'
        source=path.read_text();ast.parse(source)
        self.assertIn("down_revision='c04d9e7a6201'",source)
        self.assertIn('CREATE TRIGGER',source);self.assertIn("('UPDATE','DELETE')",source)
        self.assertNotIn('UPDATE users',source);self.assertNotIn('DELETE FROM',source)
        from sqlalchemy.schema import CreateTable
        from sqlalchemy.dialects.mysql import dialect
        from app.models.order_address import OrderDeliveryAddress
        frozen=[ast.literal_eval(n.args[0]) for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and n.args[0].value.startswith('CREATE TABLE')]
        self.assertEqual(frozen,[str(CreateTable(OrderDeliveryAddress.__table__).compile(dialect=dialect())).strip()])
        for index in OrderDeliveryAddress.__table__.indexes:self.assertIn(index.name,source)

    def test_http_role_authorization_validation_and_no_store(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.customer_addresses import router
        from app.core.auth_dependencies import get_current_user
        app=FastAPI();app.include_router(router,prefix='/api/v1')
        app.dependency_overrides[base.get_db]=lambda:self.db
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v1/customer/addresses').status_code,401)
            for ident in (1,2,5):
                app.dependency_overrides[get_current_user]=lambda ident=ident:self.db.get(User,ident)
                self.assertEqual(client.get('/api/v1/customer/addresses').status_code,403)
            app.dependency_overrides[get_current_user]=lambda:self.user
            response=client.post('/api/v1/customer/addresses',json=self.payload().model_dump())
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertEqual(client.post('/api/v1/customer/addresses',json={**self.payload().model_dump(),'user_id':6}).status_code,422)
            self.assertEqual(client.get('/api/v1/customer/addresses?page_size=51').status_code,422)

    def test_mysql_lock_syntax_and_stale_independent_session(self):
        from sqlalchemy.dialects.mysql import dialect
        sql=str(service.locked(self.db,select(UserPreference).where(UserPreference.user_id==4)).compile(dialect=dialect()))
        self.assertIn('FOR UPDATE',sql)
        first=self.create()
        with Session(self.engine,expire_on_commit=False) as other:
            customer=other.get(User,4)
            stale=service.listing(other,customer)['version']
            service.mutate(self.db,self.user,DefaultAddress(version=2,address_id=first['address']['address_id']),'default');self.db.commit()
            with self.assertRaises(HTTPException):service.mutate(other,customer,DefaultAddress(version=stale,address_id=None),'default')

    def test_exact_revision_gate_and_missing_schema_fail_closed(self):
        from sqlalchemy import text
        self.db.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)'))
        self.db.execute(text("INSERT INTO alembic_version VALUES ('d15a8c902e64')"));self.db.commit()
        self.ready.stop()
        try:
            with patch.multiple(base.config.settings,ADDRESS_BOOK_ENABLED=True,ADDRESS_CHECKOUT_ENABLED=False,ADDRESS_DBA_ATTESTED_REVISION='d15a8c902e64',create=True):
                rollout.require_ready(self.db)
                with self.assertRaises(HTTPException):rollout.require_ready(self.db,True)
                with patch.object(base.config.settings,'ADDRESS_DBA_ATTESTED_REVISION','c04d9e7a6201'):
                    with self.assertRaises(HTTPException):rollout.require_ready(self.db)
        finally:self.ready.start()

if __name__=='__main__':main()
