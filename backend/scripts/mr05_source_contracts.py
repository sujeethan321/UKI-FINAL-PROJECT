"""Source-only declaration ledger. Never imports/evaluates migration functions.

AST/literal DDL extraction is separate from observed catalogs. Unresolved runtime
reflection equivalence is explicit: this ledger is NOT a live-schema translator.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
STAGES=('9d1a6f4e0c37','ae2b7c5f1d48','bf38d2a90176','c04d9e7a6201','d15a8c902e64')

def literal(node,env):
    if isinstance(node,ast.Name) and node.id in env:return env[node.id]
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):return literal(node.left,env)+literal(node.right,env)
    if isinstance(node,ast.Call):
        if isinstance(node.func,ast.Attribute) and node.func.attr in ('text','f'):return literal(node.args[0],env)
        if isinstance(node.func,ast.Attribute) and node.func.attr=='lower' and not node.args:return literal(node.func.value,env).lower()
    return ast.literal_eval(node)

def split_sql(text):
    result=[];start=0;depth=0;quote=None;i=0
    while i<len(text):
        char=text[i]
        if quote:
            if char=='\\':i+=2;continue
            if char==quote:
                if i+1<len(text) and text[i+1]==quote:i+=2;continue
                quote=None
        elif char in "'\"`":quote=char
        elif char=='(':depth+=1
        elif char==')':depth-=1
        elif char==',' and depth==0:result.append(text[start:i].strip());start=i+1
        i+=1
    if quote or depth:raise ValueError('Unbalanced source declaration')
    result.append(text[start:].strip());return result

def empty_table():return dict(columns={},primary_keys=[],foreign_keys=[],unique_constraints=[],checks=[],indexes=[],options=[])

def raw_clause(table,clause):
    named=re.match(r'CONSTRAINT\s+`?(\w+)`?\s+(.*)',clause,re.I|re.S)
    name=named[1] if named else None;body=named[2] if named else clause
    category=next((cat for prefix,cat in [('PRIMARY KEY','primary_keys'),('FOREIGN KEY','foreign_keys'),('UNIQUE','unique_constraints'),('CHECK','checks')] if body.upper().startswith(prefix)),None)
    if category:table[category].append({'name':name,'declaration':clause});return
    column=re.match(r'`?(\w+)`?\s+(.+)',clause,re.S)
    if not column:raise ValueError('Unresolved source column')
    table['columns'][column[1]]=clause

def build():
    files={};graph={};trees={}
    for path in (ROOT/'backend/alembic/versions').glob('*.py'):
        text=path.read_text(encoding='utf-8');tree=ast.parse(text);values={}
        for n in tree.body:
            if isinstance(n,(ast.Assign,ast.AnnAssign)):
                for t in (n.targets if isinstance(n,ast.Assign) else [n.target]):
                    if isinstance(t,ast.Name) and t.id in ('revision','down_revision'):values[t.id]=ast.literal_eval(n.value)
        if 'revision' in values:
            r=values['revision'];graph[r]=values['down_revision'];trees[r]=tree
            files[path.relative_to(ROOT).as_posix()]=hashlib.sha256(text.encode()).hexdigest().upper()
    order=[];r=STAGES[-1]
    while r is not None:
        if r in order:raise ValueError('Revision cycle')
        order.append(r);r=graph[r]
    tables={};triggers={};snapshots={};unresolved=[];helpers={}
    def sql(text):
        text=text.strip()
        match=re.match(r'CREATE TABLE\s+`?(\w+)`?\s*\((.*)\)\s*([^)]*)$',text,re.I|re.S)
        if match:
            table=empty_table()
            for clause in split_sql(match[2]):raw_clause(table,clause)
            table['options']=[match[3]];tables[match[1]]=table;return
        match=re.match(r'CREATE (?:UNIQUE )?INDEX\s+`?(\w+)`?\s+ON\s+`?(\w+)`?',text,re.I)
        if match:tables[match[2]]['indexes'].append({'name':match[1],'declaration':text});return
        match=re.match(r'ALTER TABLE\s+`?(\w+)`?\s+(.*)',text,re.I|re.S)
        if match:
            table=tables[match[1]]
            for action in split_sql(match[2]):
                drop=re.fullmatch(r'DROP CHECK\s+`?(\w+)`?',action,re.I)
                if drop:table['checks']=[c for c in table['checks'] if c['name']!=drop[1]]
                elif action.upper().startswith('ADD CONSTRAINT '):raw_clause(table,action[4:])
                else:raise ValueError('Unresolved ALTER declaration')
            return
        match=re.match(r'CREATE TRIGGER\s+`?(\w+)`?\s+BEFORE\s+(UPDATE|DELETE)\s+ON\s+`?(\w+)`?\s+FOR EACH ROW\s+(.*)',text,re.I|re.S)
        if match:triggers[match[1]]={'table':match[3],'timing':'BEFORE','event':match[2].upper(),'body':match[4]};return
        if text.startswith('UPDATE driver_profiles SET legacy_document_exempt=1 ') or text.startswith('INSERT INTO subscription_trial_grants'):return
        raise ValueError('Unresolved literal SQL declaration')
    def op(call,env):
        name=call.func.attr;args=call.args;kw={k.arg:k.value for k in call.keywords}
        val=lambda node:literal(node,env)
        entry=lambda node:{'name':val(next(k.value for k in node.keywords if k.arg=='name')) if any(k.arg=='name' for k in node.keywords) else None,'declaration':ast.unparse(node)}
        if name in ('get_bind','f'):return
        if name=='execute':sql(val(args[0]));return
        if name in ('create_table','add_column'):
            table=empty_table() if name=='create_table' else tables[val(args[0])]
            for node in args[1:]:
                if isinstance(node.func,ast.Name):
                    helper=helpers[node.func.id]
                    if len(helper.body)!=1 or not isinstance(helper.body[0],ast.Return):raise ValueError('Unresolved helper body')
                    bound={p.arg:v for p,v in zip(helper.args.args,node.args)}
                    for parameter,default in zip(helper.args.args[-len(helper.args.defaults):],helper.args.defaults):bound.setdefault(parameter.arg,default)
                    for k in node.keywords:bound[k.arg]=k.value
                    class Substitute(ast.NodeTransformer):
                        def visit_Name(self,n):return copy.deepcopy(bound[n.id]) if n.id in bound else n
                    node=Substitute().visit(copy.deepcopy(helper.body[0].value))
                kind=node.func.attr
                if kind=='Column':
                    column=val(node.args[0]);table['columns'][column]=ast.unparse(node)
                    for child in node.args[1:]:
                        if isinstance(child,ast.Call) and isinstance(child.func,ast.Attribute) and child.func.attr=='ForeignKey':table['foreign_keys'].append(entry(child))
                    for k in node.keywords:
                        if k.arg in ('primary_key','unique') and val(k.value) is True:table['primary_keys' if k.arg=='primary_key' else 'unique_constraints'].append({'name':None,'declaration':ast.unparse(node)})
                else:
                    category={'ForeignKeyConstraint':'foreign_keys','UniqueConstraint':'unique_constraints','CheckConstraint':'checks','PrimaryKeyConstraint':'primary_keys'}[kind]
                    table[category].append(entry(node))
            if name=='create_table':
                table['options']=[(k.arg or '**')+'='+ast.unparse(k.value) for k in call.keywords];tables[val(args[0])]=table
            return
        if name=='drop_constraint':
            table=tables[val(args[1])];constraint=val(args[0])
            for category in ('checks','unique_constraints','foreign_keys'):table[category]=[e for e in table[category] if e['name']!=constraint]
            return
        category={'create_index':'indexes','create_unique_constraint':'unique_constraints','create_check_constraint':'checks','create_foreign_key':'foreign_keys'}[name]
        tables[val(args[1])][category].append({'name':val(args[0]),'declaration':ast.unparse(call)})
    def walk(statements,env,revision):
        for node in statements:
            if isinstance(node,ast.For):
                try:
                    for value in literal(node.iter,env):walk(node.body,{**env,node.target.id:value},revision)
                except Exception:unresolved.append({'revision':revision,'line':node.lineno,'reason':'UNRESOLVED_LOOP'})
            elif isinstance(node,ast.If):walk(node.body,env,revision);walk(node.orelse,env,revision)
            elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call):
                call=node.value
                if isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='op':
                    try:op(call,env)
                    except Exception:unresolved.append({'revision':revision,'line':node.lineno,'reason':'UNRESOLVED_DECLARATION','source':ast.unparse(call)})
    for revision in reversed(order):
        helpers={n.name:n for n in trees[revision].body if isinstance(n,ast.FunctionDef) and n.name not in ('upgrade','downgrade')}
        upgrade=next(n for n in trees[revision].body if isinstance(n,ast.FunctionDef) and n.name=='upgrade')
        walk(upgrade.body,{},revision)
        if revision in STAGES:snapshots[revision]={'tables':copy.deepcopy(tables),'triggers':copy.deepcopy(triggers),'unresolved':copy.deepcopy(unresolved)}
    model_columns={}
    for path in (ROOT/'backend/app/models').glob('*.py'):
        files[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest().upper()
        for cls in ast.parse(path.read_text(encoding='utf-8')).body:
            if not isinstance(cls,ast.ClassDef):continue
            table=None;cols=set()
            for node in cls.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__tablename__' for t in node.targets):table=ast.literal_eval(node.value)
                if isinstance(node,ast.AnnAssign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='mapped_column':cols.add(node.target.id)
            if table:model_columns[table]=cols
    parity={name:sorted(set(snapshots[STAGES[-1]]['tables'].get(name,{}).get('columns',{}))^cols) for name,cols in model_columns.items()}
    return {'format':'mr05-source-declarations-v1','source_files':files,'stages':snapshots,'head_model_column_differences':{k:v for k,v in parity.items() if v},
        'unresolved_runtime_contracts':['ALEMBIC_VERSION_FRAMEWORK_DDL','MYSQL_REFLECTION_TO_SOURCE_DECLARATION_TRANSLATION','FULL_MODEL_TYPE_DEFAULT_CONSTRAINT_SEMANTICS'],
        'execution_ready':False}

def verify_required_objects(observed,expected):
    """Declaration-level test/review comparison, not a MySQL reflection adapter."""
    if expected['unresolved']:raise ValueError('Unresolved declaration ledger')
    if observed!=expected:raise ValueError('Required source object missing or changed')

def require_runtime_parity(ledger):
    if ledger.get('unresolved_runtime_contracts') or ledger.get('head_model_column_differences') or any(s['unresolved'] for s in ledger['stages'].values()):
        raise ValueError('SOURCE_CONTRACT_RUNTIME_PARITY_UNRESOLVED')

if __name__=='__main__':
    value=build()
    print(json.dumps({'status':'SOURCE_LEDGER_ONLY_NOT_REHEARSAL_READY','stages':{r:{'tables_excluding_alembic':len(s['tables']),'triggers':len(s['triggers']),'unresolved':len(s['unresolved'])} for r,s in value['stages'].items()},'model_column_differences':value['head_model_column_differences']}))
