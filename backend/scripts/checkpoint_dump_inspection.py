"""Bounded, non-executing dump inspection for the current zero-trigger baseline.

Strict supported grammar: expected CREATE TABLE, literal INSERT tuples, and
reviewed mysqldump session SET directives. Unknown syntax fails closed.
Never logs SQL, rows or exception contents. Does not read files or execute SQL.
"""
import re
from datetime import datetime,date,time
from decimal import Decimal

MAX_BYTES=64*1024*1024
MAX_TOKENS=1000000
ATOM=re.compile(r'0x[0-9a-fA-F]+|[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_@][A-Za-z0-9_@$]*')
class DumpRejected(RuntimeError):pass
def need(value):
    if not value:raise DumpRejected('DUMP_VALIDATION_FAILED_PRESERVE_STATE')

def tokens(text):
    result=[];i=0
    while i<len(text):
        need(len(result)<MAX_TOKENS)
        ch=text[i]
        if ch.isspace():i+=1;continue
        if text.startswith('--',i) and (i+2==len(text) or text[i+2].isspace()):
            end=text.find('\n',i);i=len(text) if end<0 else end+1;continue
        if text.startswith('/*',i):
            end=text.find('*/',i+2);need(end>=0)
            body=text[i+2:end]
            if body.startswith('!'):
                match=re.fullmatch(r'!\d{5,6}\s+(SET\s+.+)',body,re.S|re.I);need(match is not None)
                result.extend(tokens(match[1]))
            i=end+2;continue
        if ch in "'`":
            quote=ch;i+=1;value='';closed=False
            while i<len(text):
                ch=text[i];i+=1
                if ch==quote:
                    if i<len(text) and text[i]==quote:value+=quote;i+=1;continue
                    closed=True;break
                if ch=='\\' and quote=="'":
                    need(i<len(text));escaped=text[i];i+=1
                    escapes={'0':'\0','n':'\n','r':'\r','b':'\b','t':'\t','Z':'\x1a',"'":"'",'"':'"','\\':'\\'}
                    need(escaped in escapes);value+=escapes[escaped]
                else:value+=ch
            need(closed);result.append(('string' if quote=="'" else 'identifier',value));continue
        match=ATOM.match(text,i)
        if match:
            value=match[0];result.append(('atom',value));i+=len(value);continue
        need(ch in '(),;.=<>!+-*/%|&');result.append(('punct',ch));i+=1
    return result

SET_DIRECTIVES=(
 'SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT','SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS',
 'SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION','SET NAMES utf8mb4','SET @OLD_TIME_ZONE=@@TIME_ZONE',
 "SET TIME_ZONE='+00:00'",'SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS,UNIQUE_CHECKS=0',
 'SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS,FOREIGN_KEY_CHECKS=0',
 "SET @OLD_SQL_MODE=@@SQL_MODE,SQL_MODE='NO_AUTO_VALUE_ON_ZERO'",'SET @OLD_SQL_NOTES=@@SQL_NOTES,SQL_NOTES=0',
 'SET TIME_ZONE=@OLD_TIME_ZONE','SET SQL_MODE=@OLD_SQL_MODE','SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS',
 'SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS','SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT',
 'SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS','SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION',
 'SET SQL_NOTES=@OLD_SQL_NOTES','SET @saved_cs_client=@@character_set_client',
 'SET character_set_client=utf8mb4','SET character_set_client=@saved_cs_client')
def normalized(values):return tuple((k,v.upper() if k=='atom' else v) for k,v in values)
ALLOWED_SETS=frozenset(normalized(tokens(text)) for text in SET_DIRECTIVES)

def literal(value,column):
    kind,text=value
    if kind=='atom' and text.upper()=='NULL':return None
    family=column['type']['family']
    if family in ('BIGINT','INT','SMALLINT','TINYINT','BOOL'):
        need(kind=='atom' and re.fullmatch(r'[+-]?\d+',text));return int(text)
    if family=='DECIMAL':
        need(kind=='atom' and re.fullmatch(r'[+-]?\d+(?:\.\d+)?',text));return Decimal(text)
    if family in ('BLOB','BINARY','VARBINARY'):
        need(kind=='atom' and re.fullmatch(r'0x(?:[a-fA-F0-9]{2})+',text));return bytes.fromhex(text[2:])
    need(kind=='string')
    if family=='DATETIME':return datetime.fromisoformat(text)
    if family=='DATE':return date.fromisoformat(text)
    if family=='TIME':return time.fromisoformat(text)
    need(family in ('VARCHAR','CHAR','TEXT','JSON'));return text

# Issued only from a successfully validated capture. No public approval issuer.
_BASELINES={}
class CapturedDumpBaseline:
    __slots__=()
    def __new__(cls):raise DumpRejected('ISSUED_DUMP_BASELINE_REQUIRED')

def _issue_captured_baseline(capture,inventory,metadata,definitions,plan):
    need(type(capture) is plan.ValidatedCapture and id(capture) in plan._CAPTURES)
    original,raw=plan._CAPTURES[id(capture)];record=__import__('json').loads(raw)
    need(original is capture and record['inventory_sha256']==plan.sha(plan.canonical(inventory)))
    need(set(metadata)==set(definitions)==set(inventory['tables'])==plan.TABLES)
    for name in plan.TABLES:
        table=inventory['tables'][name]
        need(type(definitions[name]) is str and plan.sha(definitions[name].encode('utf-8'))==table['schema_sha256'])
        need(metadata[name]==table['canonical_metadata'] and metadata[name]['columns']==table['column_metadata'])
        need(list(metadata[name]['columns'])==table['columns'])
        expected=record['fingerprints'][name]
        need(expected['columns']==table['columns'] and expected['row_count']==table['row_count'] and expected['content_sha256']==table['content_sha256'])
    value=object.__new__(CapturedDumpBaseline)
    # Retain serialized immutable copies; callers cannot modify expectations later.
    raw=plan.canonical(dict(inventory=inventory,metadata=metadata,definitions=definitions))
    _BASELINES[id(value)]=(value,capture,bytes(raw))
    return value

def baseline_record(value,plan):
    need(type(value) is CapturedDumpBaseline and id(value) in _BASELINES)
    original,capture,raw=_BASELINES[id(value)];need(original is value)
    return capture,__import__('json').loads(raw),plan.sha(raw)

def inspect_bytes(raw,baseline,plan):
    """Compare every decoded row and exact DDL tokens with the capture baseline.

    plan is the existing checkpoint module, not a connection or SQL executor.
    Unsupported MySQL serialization fails; no fallback count-only acceptance.
    """
    need(type(raw) is bytes and 0<len(raw)<=MAX_BYTES)
    capture,bound,baseline_sha256=baseline_record(baseline,plan)
    inventory=bound['inventory'];metadata=bound['metadata'];create_definitions=bound['definitions']
    try:
        text=raw.decode('utf-8');need('\0' not in text)
        need(re.search(r'(?m)^-- Dump completed on [^\r\n]+\s*\Z',text) is not None)
        names=plan.TABLES;need(set(metadata)==set(create_definitions)==set(inventory['tables'])==names)
        statements=[];part=[]
        for token in tokens(text):
            if token==('punct',';'):
                need(part);statements.append(part);part=[]
            else:part.append(token)
        need(not part)
        creates=set();rows={name:[] for name in names}
        for statement in statements:
            if statement[0]==('atom','SET') or statement[0]==('atom','set'):
                need(normalized(statement) in ALLOWED_SETS);continue
            if statement[:2]==[('atom','CREATE'),('atom','TABLE')]:
                need(len(statement)>3 and statement[2][0]=='identifier');name=statement[2][1]
                need(name in names and name not in creates)
                expected=tokens(create_definitions[name]);expected=expected[:-1] if expected[-1:]==[('punct',';')] else expected
                need(statement==expected);creates.add(name);continue
            need(statement[:2]==[('atom','INSERT'),('atom','INTO')] and len(statement)>5)
            need(statement[2][0]=='identifier');name=statement[2][1];need(name in creates)
            columns=inventory['tables'][name]['columns'];i=3
            if statement[i]==('punct','('):
                i+=1;specified=[]
                while statement[i]!=('punct',')'):
                    need(statement[i][0]=='identifier');specified.append(statement[i][1]);i+=1
                    if statement[i]==('punct',','):
                        i+=1;need(i<len(statement) and statement[i][0]=='identifier')
                    else:need(statement[i]==('punct',')'))
                need(specified==columns);i+=1
            need(statement[i]==('atom','VALUES'));i+=1
            while i<len(statement):
                need(statement[i]==('punct','('));i+=1;row={}
                for index,col in enumerate(columns):
                    need(i<len(statement));row[col]=literal(statement[i],metadata[name]['columns'][col]);i+=1
                    if index+1<len(columns):need(statement[i]==('punct',','));i+=1
                need(statement[i]==('punct',')'));i+=1
                need(len(rows[name])<plan.typed.MAX_ROWS);rows[name].append(row)
                if i<len(statement):need(statement[i]==('punct',','));i+=1;need(i<len(statement))
        need(creates==names)
        for name,values in rows.items():
            found=plan.typed.fingerprint(values,inventory['tables'][name]['columns'])
            need(found['row_count']==inventory['tables'][name]['row_count'] and found['content_sha256']==inventory['tables'][name]['content_sha256'])
        need(rows['alembic_version']==[{'version_num':plan.REVISION}])
        return dict(baseline_sha256=baseline_sha256,backup_sha256=plan.sha(raw),backup_size=len(raw),tables=sorted(names),triggers=[],events=[],routines=[],views=[],complete=True)
    except DumpRejected:raise
    except Exception:raise DumpRejected('DUMP_VALIDATION_FAILED_PRESERVE_STATE') from None
