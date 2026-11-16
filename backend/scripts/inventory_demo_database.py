"""Exact-target inventory; default is offline, execution never writes files or DB rows."""
import argparse
import ast
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend/scripts'))
from check_demo_backend import validate_schema

TARGET = 'lankapex_demo_db'
ACCOUNT = 'lankapex_demo_app@localhost'
HEAD = '7b9e4d2c8a15'
TABLES = frozenset('users businesses business_members customer_profiles credit_accounts ledger_entries business_approval_audits payment_reminders notifications communication_consents communication_attempts driver_profiles delivery_requests delivery_assignments delivery_status_events product_categories products orders order_items admin_audits customer_addresses user_preferences business_settings vehicles vehicle_documents customer_link_invitations business_join_links customer_join_requests'.split())
# Deliberately excludes password hashes, tokens, QR public codes, notes and personal data.
PROJECTIONS = {
    'credit_accounts': 'credit_account_id creditor_business_id customer_id debtor_business_id credit_limit payment_term_days account_status',
    'ledger_entries': 'entry_id credit_account_id order_id created_by reverses_entry_id entry_type amount payment_method due_at recorded_at',
    'customer_profiles': 'customer_id business_id user_id',
    'business_members': 'membership_id business_id user_id business_role membership_status',
    'orders': 'order_id business_id customer_user_id credit_account_id credit_sale_id delivery_request_id payment_method payment_status status subtotal total',
    'order_items': 'order_item_id order_id product_id quantity unit_price line_total',
    'delivery_requests': 'delivery_request_id business_id status',
    'delivery_assignments': 'assignment_id delivery_request_id driver_user_id',
    'delivery_status_events': 'event_id delivery_request_id actor_user_id status occurred_at',
    'payment_reminders': 'reminder_id business_id customer_id credit_account_id outstanding_amount currency status',
}
# Metadata-only queries are explicitly restricted to the connected schema.
META = {
    'tables': 'SELECT TABLE_NAME, ENGINE, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME',
    'columns': 'SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLLATION_NAME, ORDINAL_POSITION FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, ORDINAL_POSITION',
    'keys': 'SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION',
    'constraints': 'SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME',
    'indexes': 'SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX, NON_UNIQUE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX',
    'rules': 'SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME',
    'checks': 'SELECT CONSTRAINT_NAME, CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() ORDER BY CONSTRAINT_NAME',
}
DUPLICATES = 'SELECT COUNT(*) FROM (SELECT business_id, user_id FROM customer_profiles WHERE user_id IS NOT NULL GROUP BY business_id, user_id HAVING COUNT(*) > 1) duplicate_pairs'
LEDGER_TOTALS = 'SELECT entry_type, COUNT(*), COALESCE(SUM(amount),0) FROM ledger_entries GROUP BY entry_type ORDER BY entry_type'
BALANCES = """SELECT a.credit_account_id, COALESCE(SUM(CASE WHEN e.entry_type='credit_sale' THEN e.amount WHEN e.entry_type='repayment' THEN -e.amount ELSE 0 END),0) AS signed_balance FROM credit_accounts a LEFT JOIN ledger_entries e ON e.credit_account_id=a.credit_account_id AND e.entry_type IN ('credit_sale','repayment') AND NOT EXISTS (SELECT 1 FROM ledger_entries r WHERE r.credit_account_id=e.credit_account_id AND r.entry_type='reversal' AND r.reverses_entry_id=e.entry_id) GROUP BY a.credit_account_id ORDER BY a.credit_account_id"""
SETUP = {'SET SESSION TRANSACTION READ ONLY', 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ', 'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY'}
IDENTITY = {'SELECT DATABASE()', 'SELECT CURRENT_USER()', 'SELECT CURRENT_ROLE()', 'SELECT @@GLOBAL.partial_revokes', 'SELECT @@port', 'SHOW GRANTS FOR CURRENT_USER()', 'SELECT version_num FROM alembic_version', 'SELECT UTC_TIMESTAMP(6)'}


class Stop(Exception):
    """Only allowlisted category labels may be printed by the CLI."""


def require(condition, category):
    if not condition:
        raise Stop(category)


def target(environ):
    expected = {'APP_ENV':'development', 'MYSQL_HOST':'localhost', 'MYSQL_PORT':'3306',
                'MYSQL_DATABASE':TARGET, 'MYSQL_USER':'lankapex_demo_app'}
    require(all(environ.get(k) == v for k,v in expected.items()), 'configured_identity')
    require(bool(environ.get('MYSQL_PASSWORD')), 'credential_missing')


def grants(rows, partial_revokes, role):
    require(role == 'NONE', 'grants')
    rights = set()
    for row in rows:
        if re.fullmatch(r"GRANT USAGE ON \*\.\* TO .+", row):
            require('WITH ' not in row, 'grants')
            continue
        m = re.fullmatch(r'GRANT ([A-Z, ]+) ON `([^`]+)`\.\* TO [^ ]+', row)
        require(m is not None, 'grants')
        scope=m[2]
        require(scope.replace('\\_', '_') == TARGET and
                (partial_revokes or not re.search(r'(?<!\\)[_%]', scope)), 'grants')
        rights.update(m[1].split(', '))
    require(rights == {'SELECT','INSERT','UPDATE','DELETE'}, 'grants')
    return sorted(rights)


def fingerprint(rows):
    h=hashlib.sha256(); count=0
    for row in rows:
        h.update(json.dumps(list(row), default=str, ensure_ascii=True, separators=(',', ':')).encode())
        h.update(b'\n'); count+=1
    return {'rows':count, 'sha256':h.hexdigest()}


def ident(value):
    require(bool(re.fullmatch('[a-z][a-z0-9_]*', value)), 'metadata_identifier')
    return '`'+value+'`'


class Metadata:
    def __init__(self, data):
        self.data=data
        self.columns=defaultdict(list); self.keys=defaultdict(lambda:defaultdict(list))
        for row in data['columns']:
            self.columns[row[0]].append({'name':row[1], 'type':row[2], 'nullable':row[3], 'collation':row[4]})
        for row in data['keys']:
            self.keys[row[0]][row[1]].append(row)
    def get_table_names(self): return [r[0] for r in self.data['tables']]
    def get_columns(self,t): return self.columns[t]
    def get_pk_constraint(self,t): return {'constrained_columns':[r[2] for r in self.keys[t].get('PRIMARY',[])]}
    def get_unique_constraints(self,t):
        return [{'name':r[1], 'column_names':[k[2] for k in self.keys[t][r[1]]]} for r in self.data['constraints'] if r[0]==t and r[2]=='UNIQUE']
    def get_foreign_keys(self,t):
        rules={(r[0],r[1]):r[2] for r in self.data['rules']}
        return [{'name':name,'constrained_columns':[r[2] for r in rows], 'referred_schema':rows[0][4], 'referred_table':rows[0][5], 'referred_columns':[r[6] for r in rows], 'options':{'ondelete':rules.get((t,name))}} for name,rows in self.keys[t].items() if rows[0][5] is not None]
    def get_indexes(self,t):
        groups=defaultdict(list)
        for r in self.data['indexes']:
            if r[0]==t: groups[r[1]].append(r[2])
        return [{'name':n,'column_names':c} for n,c in groups.items()]
    def get_check_constraints(self,t):
        names={r[1] for r in self.data['constraints'] if r[0]==t and r[2]=='CHECK'}
        return [{'name':r[0], 'sqltext':r[1]} for r in self.data['checks'] if r[0] in names]


class Reader:
    """Only exact internally registered statements reach the connection."""
    def __init__(self,conn): self.conn=conn; self.allowed=set(META.values())|IDENTITY|SETUP|{DUPLICATES,BALANCES,LEDGER_TOTALS}
    def execute(self,sql):
        require(sql in self.allowed,'sql_refused')
        return self.conn.exec_driver_sql(sql)
    def generated(self,sql):
        # Three exact query grammars; metadata never becomes executable SQL.
        table = r'`[a-z][a-z0-9_]*`'
        cols = table + r'(?:,' + table + r')*'
        projection = r'SELECT '+cols+r' FROM '+table+r' ORDER BY '+cols
        count = r'SELECT COUNT\(\*\) FROM '+table
        orphan = (r'SELECT COUNT\(\*\) FROM '+table+r' c LEFT JOIN '+table+
                  r' p ON c\.'+table+r'=p\.'+table+r'(?: AND c\.'+table+r'=p\.'+table+r')*'+
                  r' WHERE c\.'+table+r' IS NOT NULL(?: AND c\.'+table+r' IS NOT NULL)* AND p\.'+table+r' IS NULL')
        require(any(re.fullmatch(pattern,sql) for pattern in (projection,count,orphan)),'sql_refused')
        require(all(t in TABLES for t in re.findall(r'(?:FROM|JOIN) `([^`]+)`',sql)),'sql_refused')
        self.allowed.add(sql)
        return self.execute(sql)
    def scalar(self,sql): return self.execute(sql).scalar_one()


def revision_chain():
    chain={}
    for p in (ROOT/'backend/alembic/versions').glob('*.py'):
        values={}
        for n in ast.parse(p.read_text(encoding='utf-8')).body:
            if isinstance(n,ast.Assign):
                for t in n.targets:
                    if isinstance(t,ast.Name) and t.id in ('revision','down_revision'): values[t.id]=ast.literal_eval(n.value)
            elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id in ('revision','down_revision'):
                values[n.target.id]=ast.literal_eval(n.value)
        chain[values['revision']]=values['down_revision']
    require(len(chain)==16 and set(chain)-set(chain.values())=={HEAD},'source_chain')
    visited=set(); node=HEAD
    while node is not None:
        require(node in chain and node not in visited,'source_chain'); visited.add(node); node=chain[node]
    require(visited==set(chain),'source_chain')
    return chain


def collect(reader):
    require(reader.scalar('SELECT DATABASE()')==TARGET and reader.scalar('SELECT CURRENT_USER()')==ACCOUNT and reader.scalar('SELECT @@port')==3306,'actual_identity')
    permissions=grants([r[0] for r in reader.execute('SHOW GRANTS FOR CURRENT_USER()')], reader.scalar('SELECT @@GLOBAL.partial_revokes'),reader.scalar('SELECT CURRENT_ROLE()'))
    data={name:list(reader.execute(sql)) for name,sql in META.items()}
    m=Metadata(data); names=set(m.get_table_names())
    require(names <= TABLES|{'alembic_version'} and 'alembic_version' in names,'unexpected_inventory')
    require(all(r[1]=='InnoDB' and r[2]=='BASE TABLE' for r in data['tables']),'unsupported_table_engine_or_view')
    revisions=[r[0] for r in reader.execute('SELECT version_num FROM alembic_version')]
    require(len(revisions)==1 and revisions[0] in revision_chain(),'revision')
    findings=[]
    try: validate_schema(m,revisions,TABLES)
    except RuntimeError: findings.append('current_schema_validation_failed')
    # Return every QR structural aspect separately, not only the first gate failure.
    qr={}
    expected_columns={
        'business_join_links':{'business_id','public_code','created_at'},
        'customer_join_requests':{'request_id','business_id','customer_user_id','status','created_at','decided_at','decided_by'},
    }
    for t in ('business_join_links','customer_join_requests','customer_profiles'):
        if t not in names:
            qr[t]={'present':False}; continue
        columns={c['name'] for c in m.get_columns(t)}
        expected=expected_columns.get(t,{'business_id','user_id','customer_id'})
        expected_unique={
            'business_join_links':('uq_business_join_public_code',['public_code']),
            'customer_join_requests':('uq_customer_join_business_user',['business_id','customer_user_id']),
            'customer_profiles':('uq_customer_profile_business_user',['business_id','user_id']),
        }[t]
        qr[t]={'present':True,'required_columns_present':expected<=columns,
               'unexpected_column_count':len(columns-expected) if t in expected_columns else None,
               'primary_key_expected':m.get_pk_constraint(t)['constrained_columns']==[{'business_join_links':'business_id','customer_join_requests':'request_id','customer_profiles':'customer_id'}[t]],
               'required_unique_constraint_present':any(c['name']==expected_unique[0] and c['column_names']==expected_unique[1] for c in m.get_unique_constraints(t)),
               'foreign_key_count':len(m.get_foreign_keys(t)),
               'index_count':len(m.get_indexes(t)),
               'check_count':len(m.get_check_constraints(t)),
               'unexpected_constraint_count':sum(1 for r in data['constraints'] if r[0]==t and r[1] not in {
                   'PRIMARY',expected_unique[0], 'fk_business_join_business', 'fk_customer_join_business',
                   'fk_customer_join_user','fk_customer_join_decider','ck_customer_join_status'}) if t in expected_columns else None,
               'structure_sha256':fingerprint([r for key in ('columns','keys','constraints','indexes','rules') for r in data[key] if r[0]==t])['sha256']}
        if t in expected_columns:
            nullable={'decided_at','decided_by'}
            column_details={c['name']:c for c in m.get_columns(t)}
            types={c:('varchar(32)' if c=='public_code' else 'varchar(20)' if c=='status' else 'datetime' if c.endswith('_at') else 'bigint') for c in expected}
            qr[t]['column_requirements']={c:{'present':c in columns,
                'type_matches':bool(c in column_details and column_details[c]['type']==types[c]),
                'nullability_matches':bool(c in column_details and column_details[c]['nullable']==('YES' if c in nullable else 'NO'))} for c in sorted(expected)}
            expected_fks={
                'business_join_links':{('business_id','businesses','business_id')},
                'customer_join_requests':{('business_id','businesses','business_id'),('customer_user_id','users','user_id'),('decided_by','users','user_id')},
            }[t]
            actual_fks=m.get_foreign_keys(t)
            qr[t]['foreign_keys_match_expected']=(len(actual_fks)==len(expected_fks) and
                {(f['constrained_columns'][0],f['referred_table'],f['referred_columns'][0]) for f in actual_fks if len(f['constrained_columns'])==len(f['referred_columns'])==1}==expected_fks and
                all(f['referred_schema'] in (None,TARGET) and (f['options'].get('ondelete') or 'RESTRICT') in ('RESTRICT','NO ACTION') for f in actual_fks))
        if t=='customer_join_requests':
            qr[t]['required_index_present']=any(i['name']=='ix_customer_join_business_status_created' and i['column_names']==['business_id','status','created_at'] for i in m.get_indexes(t))
        if t=='business_join_links':
            public=next((c for c in m.get_columns(t) if c['name']=='public_code'),None)
            qr[t]['public_code_type_collation_valid']=bool(public and public['type']=='varchar(32)' and public['collation']=='utf8mb4_bin' and public['nullable']=='NO')
    # Use the shared validator at HEAD as well as the observed revision to assess QR shape.
    try: validate_schema(m,[HEAD],TABLES); qr_structure=True
    except RuntimeError: qr_structure=False
    if qr_structure:
        qr_structure=all(qr[t]['unexpected_constraint_count']==0 and qr[t]['unexpected_column_count']==0
            and all(v['type_matches'] and v['nullability_matches'] for v in qr[t]['column_requirements'].values())
            and qr[t]['foreign_keys_match_expected'] for t in expected_columns) and qr['business_join_links']['public_code_type_collation_valid']
    counts={}; hashes={}; unavailable=[]
    for t in sorted(names-{'alembic_version'}):
        counts[t]=reader.generated('SELECT COUNT(*) FROM '+ident(t)).scalar_one()
    for t, requested in PROJECTIONS.items():
        if t not in names: unavailable.append(t); continue
        available={c['name'] for c in m.get_columns(t)}
        columns=requested.split(); keys=m.get_pk_constraint(t)['constrained_columns']
        if not set(columns)<=available or not keys or not set(keys)<=set(columns):
            unavailable.append(t); continue
        sql='SELECT '+','.join(map(ident,columns))+' FROM '+ident(t)+' ORDER BY '+','.join(map(ident,keys))
        hashes[t]=fingerprint(reader.generated(sql))
    duplicates=None; balance=None; ledger_totals=None
    if {'business_id','user_id'} <= {c['name'] for c in m.get_columns('customer_profiles')}:
        duplicates=reader.scalar(DUPLICATES)
    if all(set(PROJECTIONS[t].split()) <= {c['name'] for c in m.get_columns(t)} for t in ('credit_accounts','ledger_entries')):
        balance=fingerprint(reader.execute(BALANCES))
        ledger_totals=fingerprint(reader.execute(LEDGER_TOTALS))
    orphans={}
    for t in sorted(names):
        for fk in m.get_foreign_keys(t):
            parent=fk['referred_table']; a=fk['constrained_columns']; b=fk['referred_columns']
            require(fk['referred_schema'] in (None,TARGET) and parent in names and a and len(a)==len(b),'foreign_key_scope')
            require(set(a)<={c['name'] for c in m.get_columns(t)} and set(b)<={c['name'] for c in m.get_columns(parent)},'foreign_key_columns')
            join=' AND '.join('c.'+ident(x)+'=p.'+ident(y) for x,y in zip(a,b))
            present=' AND '.join('c.'+ident(x)+' IS NOT NULL' for x in a)
            sql='SELECT COUNT(*) FROM '+ident(t)+' c LEFT JOIN '+ident(parent)+' p ON '+join+' WHERE '+present+' AND p.'+ident(b[0])+' IS NULL'
            # Hash metadata constraint names rather than printing arbitrary database text.
            key=t+':'+hashlib.sha256(fk['name'].encode()).hexdigest()
            orphans[key]=reader.generated(sql).scalar_one()
    require(all(list(reader.execute(sql))==data[name] for name,sql in META.items()),'metadata_changed')
    require([r[0] for r in reader.execute('SELECT version_num FROM alembic_version')]==revisions,'metadata_changed')
    return {'database':TARGET,'host':'localhost','port':3306,'account':ACCOUNT,
        'privileges':permissions,'global_usage_only':True,'active_roles':'NONE',
        'revision':revisions[0],'application_tables':len(names)-1,'total_tables':len(names),
        'tables':sorted(names),'missing_current_tables':sorted((TABLES|{'alembic_version'})-names),
        'current_schema_compatible':not findings and qr_structure,'qr_structure_complete':qr_structure,'qr_metadata':qr,
        'qr_schema_state':('complete' if qr_structure else 'absent' if not names & {'business_join_links','customer_join_requests'} and not qr.get('customer_profiles',{}).get('required_unique_constraint_present') else 'partial_or_mismatched'),
        'schema_metadata_sha256':fingerprint([[key,*row] for key in sorted(data) for row in data[key]])['sha256'],
        'duplicate_profile_pair_count':duplicates,'row_counts':counts,'preservation_fingerprints':hashes,
        'fingerprint_unavailable':unavailable,'signed_account_balance_fingerprint':balance,'ledger_type_totals_fingerprint':ledger_totals,
        'foreign_key_orphan_counts':orphans,'captured_utc':str(reader.scalar('SELECT UTC_TIMESTAMP(6)')),
        'limitations':['Fingerprints cover explicit numeric/relationship projections, not private user or credential fields.',
                      'Consistent InnoDB data snapshot; concurrent DDL is not locked out.',
                      'No comparison with historical private evidence is performed.'],
        'database_changed':False,'evidence_file_created':False}


def run(environ):
    target(environ)
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    engine=create_engine(URL.create('mysql+pymysql',username='lankapex_demo_app',password=environ['MYSQL_PASSWORD'],host='localhost',port=3306,database=TARGET),hide_parameters=True,echo=False,connect_args={'connect_timeout':5,'read_timeout':30},pool_pre_ping=False)
    try:
        with engine.connect() as conn:
            reader=Reader(conn)
            # Roll back SQLAlchemy's implicit bookkeeping transaction; never commit.
            reader.execute('SET SESSION TRANSACTION READ ONLY'); conn.rollback()
            reader.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            reader.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            try: return collect(reader)
            finally: conn.rollback()
    finally: engine.dispose()


def main(argv=None,environ=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true'); p.add_argument('--confirm-target')
    args=p.parse_args(argv)
    if not args.execute:
        print('PASS: offline inventory preparation only; no credentials loaded or database connected'); return 0
    if args.confirm_target != TARGET:
        print('STOP: demo inventory category=confirmation'); return 1
    try:
        report=run(os.environ if environ is None else environ)
        print(json.dumps(report,sort_keys=True,indent=2))
        print('PASS: read-only demo inventory complete; compatibility is reported separately; no files or database records changed')
        return 0
    except Exception as exc:
        safe={'configured_identity','credential_missing','grants','actual_identity','sql_refused','source_chain','revision','unexpected_inventory','unsupported_table_engine_or_view','foreign_key_scope','foreign_key_columns','metadata_identifier','metadata_changed'}
        category=str(exc) if isinstance(exc,Stop) and str(exc) in safe else 'read_or_metadata_unavailable'
        print('STOP: demo inventory category='+category); return 1


if __name__=='__main__': sys.exit(main())
