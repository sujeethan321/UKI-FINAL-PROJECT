"""Offline, source-derived canonical contracts; no application/DB imports.

This module parses declarations. It never imports a migration, executes SQL,
opens a connection or enables the MR-02/MR-03 execution paths.
"""
import ast
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mr07_ledger',ROOT/'backend/scripts/mr05_source_contracts.py')
ledger=importlib.util.module_from_spec(spec);spec.loader.exec_module(ledger)
spec=importlib.util.spec_from_file_location('mr07_checks',ROOT/'backend/app/services/schema_integrity.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
PINNED={'alembic':'1.20.1','sqlalchemy':'2.1.6'}
POLICY={'engine':'InnoDB','charset':'utf8mb4','collation':'utf8mb4_unicode_ci'}

def need(condition,message):
    if not condition:raise ValueError(message)

def name(node):return node.id if isinstance(node,ast.Name) else node.attr if isinstance(node,ast.Attribute) else ''
def lit(node):return ast.literal_eval(node)
def kw(call):return {k.arg:k.value for k in call.keywords}
def number(value):
    text=format(Decimal(value),'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text

def check_key(expression,*,representation='sql'):
    def convert(value):
        if isinstance(value,Decimal):return number(value)
        if isinstance(value,tuple):return [convert(v) for v in value]
        return value
    need(representation in ('sql','mysql8_information_schema'),'Unsupported CHECK representation')
    tree=checks.mysql_check_tree(expression) if representation=='mysql8_information_schema' else checks.check_tree(expression)
    return convert(tree)

def type_ast(node,annotation=''):
    if node is None:
        need('int' in annotation,'Unsupported inferred column type');return type_sql('INTEGER'),None,None
    args=[lit(n) for n in node.args] if isinstance(node,ast.Call) else []
    options={k.arg:lit(k.value) for k in node.keywords} if isinstance(node,ast.Call) else {}
    kind=name(node.func) if isinstance(node,ast.Call) else name(node)
    family={'BigInteger':'BIGINT','Integer':'INTEGER','SmallInteger':'SMALLINT','String':'VARCHAR','Text':'TEXT','Boolean':'BOOL','Numeric':'DECIMAL','DateTime':'DATETIME','Date':'DATE'}.get(kind,kind.upper())
    family={'INTEGER':'INT','NUMERIC':'DECIMAL','BOOLEAN':'BOOL'}.get(family,family)
    need(set(options)<={'length','precision','scale','fsp','unsigned','charset','collation','timezone','create_constraint','name'},'Unsupported type options')
    need(not options.get('timezone',False) and not options.get('create_constraint',False),'Unreviewed timezone/Boolean CHECK semantics')
    need(family in ('VARCHAR','CHAR') or 'length' not in options,'Unreviewed text length hint')
    need(kind!='DateTime' or 'fsp' not in options,'Use reviewed MySQL DATETIME precision')
    need(kind not in ('BigInteger','Integer','SmallInteger','Numeric') or 'unsigned' not in options,'Generic type does not declare MySQL unsigned')
    if family in ('VARCHAR','CHAR'):
        length=options.get('length',args[0] if args else None);need(type(length) is int and length>0,'Missing string length');text=f'{family}({length})'
    elif family=='DECIMAL':
        precision=options.get('precision',args[0] if args else None);scale=options.get('scale',args[1] if len(args)>1 else None)
        need(type(precision) is int and type(scale) is int and 0<precision<=65 and 0<=scale<=min(precision,30),'Missing/invalid decimal dimensions');text=f'DECIMAL({precision},{scale})'
    elif family=='DATETIME':
        precision=options.get('fsp',0);need(type(precision) is int and 0<=precision<=6,'Invalid datetime precision');text=f'DATETIME({precision})'
    else:need(not args,'Unreviewed type dimensions');text=family
    if options.get('unsigned'):text+=' UNSIGNED'
    result=type_sql(text)
    return result,options.get('charset'),options.get('collation')

def type_sql(text):
    match=re.fullmatch(r'(BIGINT|INTEGER|INT|SMALLINT|TINYINT|BOOL|BOOLEAN|VARCHAR|CHAR|TEXT|DECIMAL|NUMERIC|DATETIME|DATE)(?:\((\d+)(?:\s*,\s*(\d+))?\))?( UNSIGNED)?',text.strip(),re.I)
    need(match is not None,'Unsupported MySQL type')
    family=match[1].upper();family={'INTEGER':'INT','NUMERIC':'DECIMAL','BOOLEAN':'BOOL'}.get(family,family)
    need(not match[4] or family in ('BIGINT','INT','SMALLINT','TINYINT','DECIMAL'),'Unsupported unsigned type')
    a=int(match[2]) if match[2] else None;b=int(match[3]) if match[3] else None
    if family=='BOOL':need(a is None and not match[4],'Unsupported Boolean type');family='TINYINT';a=1
    result={'family':family,'unsigned':bool(match[4])}
    if family in ('VARCHAR','CHAR'):need(a is not None and 0<a<=(255 if family=='CHAR' else 65535) and b is None,'Missing/unsupported string length');result['length']=a
    elif family=='DECIMAL':need(a is not None and b is not None and 0<a<=65 and 0<=b<=min(a,30),'Missing decimal scale');result.update(precision=a,scale=b)
    elif family=='DATETIME':need(b is None and 0<=(a or 0)<=6,'Invalid datetime precision');result['fsp']=a or 0
    elif family in ('BIGINT','INT','SMALLINT','TINYINT'):
        standard={'BIGINT':20,'INT':11,'SMALLINT':6,'TINYINT':4}
        need(b is None and (a is None or a==standard[family] or family=='TINYINT' and a==1),'Unreviewed integer display width')
        if family=='TINYINT' and a==1:result['display_width']=1
    else:
        need(a is None and b is None,'Unsupported type dimensions')
        if family=='TEXT':result['max_bytes']=65535
    return result

def default_ast(node,column_type):
    if node is None:return None
    if isinstance(node,ast.Constant):
        if node.value is None:return None
        need(type(node.value) is str,'Unreviewed literal server default')
        return {'kind':'literal','value':node.value}
    need(isinstance(node,ast.Call),'Unsupported server default')
    kind=name(node.func)
    if kind=='text':return default_sql(lit(node.args[0]),column_type)
    if kind=='now':need(not node.args and not node.keywords,'Unreviewed clock arguments');return {'kind':'current_timestamp','fsp':0}
    if kind in ('false','true'):return {'kind':'literal','value':'0' if kind=='false' else '1'}
    raise ValueError('Unsupported server default function')

def default_sql(text,column_type):
    text=text.strip()
    clock=re.fullmatch(r'(?:CURRENT_TIMESTAMP|now)(?:\((\d*)\))?',text,re.I)
    if clock:
        precision=int(clock[1] or 0);need(0<=precision<=6,'Invalid default precision');return {'kind':'current_timestamp','fsp':precision}
    if re.fullmatch(r"'(?:[^'\\]|'')*'",text):return {'kind':'literal','value':text[1:-1].replace("''","'")}
    if re.fullmatch(r'-?\d+(?:\.\d+)?',text) and column_type['family'] in ('BIGINT','INT','SMALLINT','TINYINT','DECIMAL'):
        return {'kind':'literal','value':number(text)}
    raise ValueError('Unsupported SQL default')

def column_ast(call,annotation=None):
    options=kw(call);is_model=annotation is not None;column_name=None if is_model else lit(call.args[0]);args=call.args if is_model else call.args[1:]
    need(set(options)<={'primary_key','nullable','autoincrement','server_default','default','unique','index'},'Unsupported column options')
    typ,charset,collation=type_ast(args[0] if args else None,annotation or '')
    primary=lit(options['primary_key']) if 'primary_key' in options else False
    nullable=lit(options['nullable']) if 'nullable' in options else ('None' in annotation if is_model else not primary)
    need(type(nullable) is bool and type(primary) is bool,'Invalid nullability/primary key')
    auto=lit(options['autoincrement']) if 'autoincrement' in options else 'auto'
    need(auto in (True,False,'auto'),'Unreviewed autoincrement mode')
    client=ast.unparse(options['default']) if 'default' in options else None
    value=dict(type=typ,nullable=nullable,server_default=default_ast(options.get('server_default'),typ),autoincrement=auto,charset=charset,collation=collation,client_default=client,original=ast.unparse(call),_primary=primary)
    fks=[]
    for child in args[1:]:
        if isinstance(child,ast.Call) and name(child.func)=='ForeignKey':
            ref=lit(child.args[0]);target,remote=ref.split('.');opts=kw(child)
            fks.append(dict(name=lit(opts['name']) if 'name' in opts else None,columns=[column_name],referred_table=target,referred_columns=[remote],ondelete=action(lit(opts['ondelete']) if 'ondelete' in opts else None),onupdate=action(lit(opts['onupdate']) if 'onupdate' in opts else None)))
    return column_name,value,fks

def column_sql(text):
    match=re.match(r'`?(\w+)`?\s+([A-Z]+(?:\(\d+(?:,\s*\d+)?\))?(?: UNSIGNED)?)(.*)$',text,re.I|re.S)
    need(match is not None,'Unparsed column')
    column_name,type_text,rest=match.groups();typ=type_sql(type_text)
    nullable=True;auto=False;charset=collation=None;default=None
    while rest.strip():
        rest=rest.strip();token=re.match(r'^(NOT NULL|NULL|AUTO_INCREMENT|CHARACTER SET\s+\w+|COLLATE\s+\w+|DEFAULT\s+(?:CURRENT_TIMESTAMP(?:\(\d*\))?|\S+))\s*',rest,re.I)
        need(token is not None,'Unparsed column suffix');value=token[1];rest=rest[token.end():]
        upper=value.upper()
        if upper=='NOT NULL':nullable=False
        elif upper=='NULL':nullable=True
        elif upper=='AUTO_INCREMENT':auto=True
        elif upper.startswith('CHARACTER SET'):charset=value.split()[-1]
        elif upper.startswith('COLLATE'):collation=value.split()[-1]
        else:default=default_sql(value[8:],typ)
    return column_name,dict(type=typ,nullable=nullable,server_default=default,autoincrement=auto,charset=charset,collation=collation,client_default=None,original=text,_primary=False),[]

def action(value):
    value=(value or 'RESTRICT').upper()
    need(value in ('RESTRICT','NO ACTION','CASCADE','SET NULL'),'Unsupported FK action')
    return 'RESTRICT' if value=='NO ACTION' else value

def cols(text):
    result=[c.strip(' `') for c in text.split(',')]
    need(all(re.fullmatch('[a-z][a-z0-9_]*',c) for c in result),'Unsupported index/FK expression')
    return result

def constraint(entry,category):
    text=entry['declaration'];source_name=entry['name']
    if text.startswith(('CONSTRAINT ','PRIMARY KEY','FOREIGN KEY','UNIQUE','CHECK','CREATE ')):
        body=re.sub(r'^CONSTRAINT\s+\w+\s+','',text)
        if category=='checks':return {'name':source_name,'definition':check_key(re.fullmatch(r'CHECK\s*\((.*)\)',body,re.S)[1]),'enforced':True}
        if category=='foreign_keys':
            match=re.fullmatch(r'FOREIGN KEY\((.*?)\) REFERENCES (\w+) \((.*?)\)(.*)',body,re.S);need(match is not None,'Unparsed FK')
            suffix=match[4];delete=re.search(r'ON DELETE (RESTRICT|NO ACTION|CASCADE|SET NULL)',suffix);update=re.search(r'ON UPDATE (RESTRICT|NO ACTION|CASCADE|SET NULL)',suffix)
            need(re.fullmatch(r'(?:\s+ON (?:DELETE|UPDATE) (?:RESTRICT|NO ACTION|CASCADE|SET NULL))*',suffix) is not None,'Unparsed FK actions')
            return dict(name=source_name,columns=cols(match[1]),referred_table=match[2],referred_columns=cols(match[3]),ondelete=action(delete[1] if delete else None),onupdate=action(update[1] if update else None))
        if category=='indexes':
            match=re.fullmatch(r'CREATE (UNIQUE )?INDEX \w+ ON \w+ \((.*?)\)',body);need(match is not None,'Unparsed index');return dict(name=source_name,columns=cols(match[2]),unique=bool(match[1]))
        match=re.fullmatch(r'(?:UNIQUE|PRIMARY KEY) \((.*?)\)',body);need(match is not None,'Unparsed key');return dict(name=source_name,columns=cols(match[1]))
    call=ast.parse(text,mode='eval').body;kind=name(call.func);options=kw(call);args=call.args
    if kind in ('Column','mapped_column'):
        return dict(name=source_name,columns=[lit(args[0])])
    if category=='checks':return {'name':source_name,'definition':check_key(lit(args[2 if kind=='create_check_constraint' else 0])),'enforced':True}
    if category=='foreign_keys':
        if kind=='create_foreign_key':local=lit(args[3]);target=lit(args[2]);remote=lit(args[4])
        else:
            local=lit(args[0]);references=lit(args[1]);targets={r.split('.')[0] for r in references};need(len(targets)==1,'Cross-table FK');target=targets.pop();remote=[r.split('.')[1] for r in references]
        return dict(name=source_name,columns=local,referred_table=target,referred_columns=remote,ondelete=action(lit(options['ondelete']) if 'ondelete' in options else None),onupdate=action(lit(options['onupdate']) if 'onupdate' in options else None))
    if category=='indexes':
        return dict(name=source_name,columns=lit(args[2]) if kind=='create_index' else [lit(a) for a in args[1:]],unique=lit(options['unique']) if 'unique' in options else False)
    return dict(name=source_name,columns=lit(args[2]) if kind=='create_unique_constraint' else [lit(a) for a in args])

def options_contract(entries):
    explicit={}
    for entry in entries:
        if not entry:continue
        if entry=='**=options':explicit.update(POLICY);continue # Literal checked independently in build().
        if entry.startswith('mysql_'):
            key,value=entry.split('=',1);explicit[key[6:].replace('collate','collation')]=lit(ast.parse(value,mode='eval').body)
        else:
            matches=re.findall(r'(ENGINE|CHARSET|COLLATE)(?:=|\s+)(\w+)',entry,re.I)
            need(not re.sub(r'(ENGINE|CHARSET|COLLATE)(?:=|\s+)(\w+)','',entry,flags=re.I).strip(),'Unsupported table options')
            for key,value in matches:explicit[{'ENGINE':'engine','CHARSET':'charset','COLLATE':'collation'}[key.upper()]]=value
    need(set(explicit)<=set(POLICY),'Unreviewed table option')
    return {key:{'value':explicit.get(key),'origin':'declared' if key in explicit else 'inherited_unknown','required_runtime_policy':POLICY[key]} for key in POLICY}

def finish_table(table):
    primary=[]
    for item in table['primary_keys']:
        for col in item['columns']:
            if col not in primary:primary.append(col)
    table['primary_key']=primary;table.pop('primary_keys')
    for col,value in table['columns'].items():
        if value['autoincrement']=='auto':value['autoincrement']=len(primary)==1 and col in primary and value['type']['family'] in ('INT','BIGINT','SMALLINT') and not any(col in fk['columns'] for fk in table['foreign_keys'])
        need(value['autoincrement'] is False or value['autoincrement'] is True and primary==[col] and value['type']['family'] in ('BIGINT','INT','SMALLINT','TINYINT'),'Unsupported autoincrement declaration')
        value.pop('_primary',None)
    for category in ('foreign_keys','unique_constraints','checks','indexes'):
        table[category]=sorted(table[category],key=lambda item:json.dumps(item,sort_keys=True))
    coverage=[primary]+[item['columns'] for item in table['unique_constraints']]+[item['columns'] for item in table['indexes']]
    table['permitted_implicit_indexes']=sorted({tuple(fk['columns']) for fk in table['foreign_keys'] if not any(c[:len(fk['columns'])]==fk['columns'] for c in coverage)})
    table['permitted_implicit_indexes']=[list(c) for c in table['permitted_implicit_indexes']]
    return table

def canonical_table(source):
    result={key:[] for key in ('foreign_keys','primary_keys','unique_constraints','checks','indexes')};result['columns']={};result['options']=options_contract(source['options'])
    for column_name,declaration in source['columns'].items():
        node=ast.parse(declaration,mode='eval').body if declaration.startswith('sa.Column(') else None
        _,column,fks=column_ast(node) if node else column_sql(declaration)
        result['columns'][column_name]=column;result['foreign_keys'].extend(fks)
    for category in ('primary_keys','unique_constraints','checks','indexes','foreign_keys'):
        for entry in source[category]:
            # Inline FKs were recovered with their actual owning columns above.
            if category=='foreign_keys' and entry['declaration'].startswith('sa.ForeignKey('):continue
            result[category].append(constraint(entry,category))
    return finish_table(result)

def framework_contract():
    versions={n:importlib.metadata.version(n) for n in PINNED};need(versions==PINNED,'Unreviewed framework versions')
    base=Path(importlib.metadata.distribution('alembic').locate_file('alembic'))
    impl=base/'ddl/impl.py';runtime=base/'runtime/migration.py'
    text=impl.read_text(encoding='utf-8');runtime_text=runtime.read_text(encoding='utf-8')
    need('Column("version_num", String(32), nullable=False)' in text and 'name=f"{version_table}_pkc"' in text and 'opts.get("version_table_pk", True)' in runtime_text,'Framework DDL source drift')
    table=dict(columns={'version_num':{'type':type_sql('VARCHAR(32)'),'nullable':False,'server_default':None,'autoincrement':False,'charset':None,'collation':None,'client_default':None,'original':'Alembic framework Column(version_num, String(32), nullable=False)'}},primary_key=['version_num'],foreign_keys=[],unique_constraints=[],checks=[],indexes=[],options=options_contract([]),permitted_implicit_indexes=[])
    return dict(versions=versions,source_sha256={'ddl/impl.py':hashlib.sha256(impl.read_bytes()).hexdigest(),'runtime/migration.py':hashlib.sha256(runtime.read_bytes()).hexdigest()},table=table,naming={'declared_primary_key':'alembic_version_pkc','mysql_primary_index':'PRIMARY','policy':'compare PK columns; preserve actual reflected constraint name'},requires_mysql=['effective inherited options','actual PK/reflection naming'])

def build():
    # Verify the one allowed symbolic expansion from actual source, not mocks.
    path=ROOT/'backend/alembic/versions/8c0f5e3d9b26_business_subscriptions.py'
    tree=ast.parse(path.read_text(encoding='utf-8'));upgrade=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='upgrade')
    assignment=next(n for n in upgrade.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='options' for t in n.targets))
    value={k.arg:lit(k.value) for k in assignment.value.keywords}
    need(value=={'mysql_engine':'InnoDB','mysql_charset':'utf8mb4','mysql_collate':'utf8mb4_unicode_ci'},'Symbolic option source drift')
    raw=ledger.build();framework=framework_contract();stages={}
    for revision,stage in raw['stages'].items():
        need(not stage['unresolved'],'Unresolved source declarations')
        tables={name:canonical_table(table) for name,table in stage['tables'].items()};tables['alembic_version']=copy.deepcopy(framework['table'])
        for table in tables.values():
            for fk in table['foreign_keys']:
                need(fk['referred_table'] in tables and len(fk['columns'])==len(fk['referred_columns'])>0,'Invalid FK target')
                parent=tables[fk['referred_table']]
                need(all(c in table['columns'] for c in fk['columns']) and all(c in parent['columns'] for c in fk['referred_columns']),'Unknown FK column')
                candidates=[parent['primary_key']]+[u['columns'] for u in parent['unique_constraints']]+[i['columns'] for i in parent['indexes'] if i['unique']]
                need(fk['referred_columns'] in candidates,'FK parent lacks required unique identity')
        stages[revision]={'tables':tables,'triggers':copy.deepcopy(stage['triggers'])}
    result=dict(format='mr07-canonical-source-v1',framework=framework,source_files=raw['source_files'],original_declarations=raw['stages'],canonicalizer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),check_parser_sha256=hashlib.sha256((ROOT/'backend/app/services/schema_integrity.py').read_bytes()).hexdigest(),stages=stages,real_execution_enabled=False,mysql_only_gaps=['effective inherited table/column options','generated names/supporting index behavior','CHECK enforcement','trigger DEFINER/SQL mode/creation charset and denial behavior'])
    result['head_model_parity']=model_parity(stages[ledger.STAGES[-1]]['tables'])
    return result

def model_tables():
    """Independent declarative-model AST reader; no model/config imports."""
    tables={}
    for path in (ROOT/'backend/app/models').glob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'));constants={}
        for n in tree.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                if isinstance(n.value,ast.Dict):
                    try:constants[n.targets[0].id]=lit(n.value)
                    except ValueError:pass
                elif isinstance(n.value,ast.Call) and name(n.value.func)=='dict' and not n.value.args:
                    try:constants[n.targets[0].id]={k.arg:lit(k.value) for k in n.value.keywords}
                    except ValueError:pass
        for cls in tree.body:
            if not isinstance(cls,ast.ClassDef):continue
            table_name=next((lit(n.value) for n in cls.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__tablename__' for t in n.targets)),None)
            if not table_name:continue
            table={key:[] for key in ('foreign_keys','primary_keys','unique_constraints','checks','indexes')};table['columns']={};table_options=[]
            for n in cls.body:
                if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__table_args__' for t in n.targets):
                    entries=n.value.elts if isinstance(n.value,ast.Tuple) else [n.value]
                    for entry in entries:
                        if isinstance(entry,(ast.Dict,ast.Name)):
                            values=lit(entry) if isinstance(entry,ast.Dict) else constants[entry.id]
                            table_options.extend(k+'='+repr(v) for k,v in values.items());continue
                        kind=name(entry.func);category={'ForeignKeyConstraint':'foreign_keys','UniqueConstraint':'unique_constraints','CheckConstraint':'checks','Index':'indexes'}[kind]
                        opts=kw(entry);object_name=lit(entry.args[0]) if kind=='Index' else lit(opts['name']) if 'name' in opts else None
                        # constraint() supports the same constructor argument layout;
                        # convert only the callable qualifier, not its semantics.
                        call=copy.deepcopy(entry);call.func=ast.Attribute(value=ast.Name(id='sa',ctx=ast.Load()),attr=kind,ctx=ast.Load())
                        table[category].append(constraint({'name':object_name,'declaration':ast.unparse(call)},category))
                if isinstance(n,ast.AnnAssign) and isinstance(n.value,ast.Call) and name(n.value.func)=='mapped_column':
                    _,column,fks=column_ast(n.value,ast.unparse(n.annotation));field=n.target.id;table['columns'][field]=column
                    for fk in fks:fk['columns']=[field]
                    table['foreign_keys'].extend(fks);opts=kw(n.value)
                    if column['_primary']:table['primary_keys'].append({'name':None,'columns':[field]})
                    indexed=lit(opts['index']) if 'index' in opts else False;unique=lit(opts['unique']) if 'unique' in opts else False
                    if indexed:table['indexes'].append({'name':'ix_'+table_name+'_'+field,'columns':[field],'unique':unique})
                    elif unique:table['unique_constraints'].append({'name':None,'columns':[field]})
            table['options']=options_contract(table_options);tables[table_name]=finish_table(table)
    return tables

def model_parity(expected):
    actual=model_tables();need(set(actual)==set(expected)-{'alembic_version'},'Model table inventory mismatch')
    differences=[];naming_observations=[]
    for table,found in actual.items():
        wanted=expected[table]
        if set(found['columns'])!=set(wanted['columns']):differences.append(table+':column_inventory');continue
        for col in found['columns']:
            if ddl_column(found['columns'][col])!=ddl_column(wanted['columns'][col]):differences.append(table+'.'+col+':column_definition')
        for category in ('foreign_keys','unique_constraints','checks','indexes'):
            if Counter(signature(v) for v in found[category])!=Counter(signature(v) for v in wanted[category]):differences.append(table+':'+category)
            model_names={(v['name'],signature(v)) for v in found[category] if v['name'] is not None};source_names={(v['name'],signature(v)) for v in wanted[category] if v['name'] is not None}
            if not model_names<=source_names:differences.append(table+':named_'+category)
            elif model_names!=source_names:naming_observations.append(table+':source names retained; model leaves some names unspecified')
        if found['primary_key']!=wanted['primary_key']:differences.append(table+':primary_key')
        if found['options']!=wanted['options']:differences.append(table+':table_options')
    return {'tables_compared':len(actual),'columns_compared':sum(len(t['columns']) for t in actual.values()),'differences':differences,'naming_observations':naming_observations}

def ddl_column(value):return {k:v for k,v in value.items() if k not in ('original','client_default')}
def signature(value):return json.dumps({k:v for k,v in value.items() if k!='name'},sort_keys=True)

def verify_table(actual,expected):
    """Canonical metadata comparison; callers must capture independently."""
    need(set(actual['columns'])==set(expected['columns']),'Column inventory mismatch')
    for col in expected['columns']:need(ddl_column(actual['columns'][col])==ddl_column(expected['columns'][col]),'Column definition mismatch: '+col)
    need(actual['primary_key']==expected['primary_key'],'Primary key mismatch')
    for category in ('foreign_keys','unique_constraints','checks'):
        wanted=expected[category];found=actual[category]
        need(Counter(signature(x) for x in found)==Counter(signature(x) for x in wanted),category+' mismatch')
        for item in wanted:
            if item['name'] is not None:need(any(x['name']==item['name'] and signature(x)==signature(item) for x in found),'Named object mismatch')
    for key,spec in expected['options'].items():
        found=actual['options'][key]['value']
        need(found==spec['value'] if spec['origin']=='declared' else found==spec['required_runtime_policy'],'Table options mismatch')
    declared={x['name']:x for x in expected['indexes']};found=actual['indexes'];seen=set();extra=set()
    for index in found:
        need(index['name'] not in seen,'Duplicate index name');seen.add(index['name'])
        if index['name'] in declared:need(index==declared[index['name']],'Explicit index mismatch')
        else:
            columns=tuple(index['columns']);need(index.get('unique') is False and list(columns) in expected['permitted_implicit_indexes'] and columns not in extra and set(index)=={'name','columns','unique'},'Unexpected supporting index');extra.add(columns)
    need(set(declared)<=seen,'Missing explicit index')
    covering=[expected['primary_key']]+[u['columns'] for u in actual['unique_constraints']]+[i['columns'] for i in found]
    for fk in expected['foreign_keys']:need(any(c[:len(fk['columns'])]==fk['columns'] for c in covering),'Missing FK supporting index')
