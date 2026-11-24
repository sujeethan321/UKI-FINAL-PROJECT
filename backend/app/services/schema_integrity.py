"""Conservative CHECK comparison for the reviewed expression grammar only.

Parse structure rather than deleting parentheses or reordering boolean terms.
Unknown syntax fails closed. Literal case and grouping semantics are preserved.
This is not SQL execution and does not replace privileged trigger/grant review.
"""
import re
from decimal import Decimal
from sqlalchemy import CheckConstraint,text

TOKEN=re.compile(r"\s+|`[A-Za-z_][A-Za-z0-9_]*`|'(?:[^'\\]|'')*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|<>|!=|<=|>=|[(),+*/=<>-]")
MYSQL_TOKEN=re.compile(r"\s+|`[A-Za-z_][A-Za-z0-9_]*`|'(?:[^'\\]|''|\\[\\'0nrZ])*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|<>|!=|<=|>=|[(),+*/=<>-]")
MYSQL_PRINT_ESCAPES={'\\':'\\',"'":"'",'0':'\0','n':'\n','r':'\r','Z':'\x1a'}

def mysql_check_sql(metadata):
    """Decode ONE MySQL 8 I_S CHECK_CLAUSE String::print layer, not SQL.

    MySQL 8.0.46 sql/dd/dd_table.cc:fill_dd_check_constraints calls
    convert_and_print on the entire SQL expression. String::print in
    sql-common/sql_string.cc escapes quotes/backslashes/control characters.
    mysql's table display does not add this layer. Never infer this format
    from the input: only INFORMATION_SCHEMA callers select it explicitly.
    """
    if not isinstance(metadata,str) or not 0<len(metadata)<=20000:raise ValueError('Invalid CHECK definition')
    result=[];index=0
    while index<len(metadata):
        char=metadata[index];index+=1
        if char=='\\':
            if index==len(metadata) or metadata[index] not in MYSQL_PRINT_ESCAPES:raise ValueError('Unsupported MySQL CHECK metadata escape')
            char=MYSQL_PRINT_ESCAPES[metadata[index]];index+=1
        elif char in "'\0\n\r\x1a":raise ValueError('Invalid MySQL CHECK metadata encoding')
        result.append(char)
    return ''.join(result)

def mysql_literal(token):
    """Decode SQL literal contents after the independent I_S layer is removed."""
    content=token[1:-1];result=[];index=0
    while index<len(content):
        char=content[index];index+=1
        if char=='\\':
            if index==len(content) or content[index] not in MYSQL_PRINT_ESCAPES:raise ValueError('Unsupported CHECK literal escape')
            char=MYSQL_PRINT_ESCAPES[content[index]];index+=1
        elif char=="'":
            if index==len(content) or content[index]!="'":raise ValueError('Unsupported CHECK literal escape')
            index+=1
        result.append(char)
    return ''.join(result)

def mysql_check_tree(metadata):
    return check_tree(mysql_check_sql(metadata),mysql_literals=True)

def check_tree(sql,*,mysql_literals=False):
    if not isinstance(sql,str) or not 0<len(sql)<=20000:raise ValueError('Invalid CHECK definition')
    tokens=[];position=0
    while position<len(sql):
        match=(MYSQL_TOKEN if mysql_literals else TOKEN).match(sql,position)
        if match is None:raise ValueError('Unsupported CHECK syntax')
        token=match.group();position=match.end()
        if token.isspace():continue
        tokens.append(token)
    if len(tokens)>4096:raise ValueError('CHECK definition exceeds bounds')
    index=0;depth=0
    def peek():return tokens[index].lower() if index<len(tokens) else None
    def take(expected=None):
        nonlocal index
        if index>=len(tokens):raise ValueError('Incomplete CHECK')
        value=tokens[index];index+=1
        if expected is not None and value.lower()!=expected:raise ValueError('Unexpected CHECK token')
        return value
    def expression(minimum=0):
        nonlocal depth
        depth+=1
        if depth>64:raise ValueError('CHECK nesting exceeds bounds')
        try:
            value=take();lower=value.lower()
            if value=='(':
                left=expression();take(')')
            elif value in ('+','-'):left=('unary',lower,expression(70))
            elif value.startswith("'"):left=('string',mysql_literal(value) if mysql_literals else value[1:-1].replace("''","'"))
            # Decimal equality is exact; normalize() could round long literals
            # through the active decimal context and hide constraint drift.
            elif value[0].isdigit():left=('number',Decimal(value))
            elif lower=='_utf8mb4':
                literal=take()
                if not literal.startswith("'"):raise ValueError('Unsupported charset literal')
                left=('string',mysql_literal(literal) if mysql_literals else literal[1:-1].replace("''","'"))
            elif re.fullmatch(r'`?[A-Za-z_][A-Za-z0-9_]*`?',value):
                name=lower.strip('`')
                if peek()=='(':
                    if name not in ('char_length','trim','round'):raise ValueError('Unreviewed CHECK function')
                    take('(');args=[expression()]
                    while peek()==',':take(',');args.append(expression())
                    take(')');left=('function',name,tuple(args))
                else:left=('identifier',name)
            else:raise ValueError('Unsupported CHECK operand')
            precedence={'or':10,'and':20,'=':40,'<>':40,'!=':40,'>':40,'<':40,'>=':40,'<=':40,'is':40,'in':40,'between':40,'not':40,'+':50,'-':50,'*':60,'/':60}
            while peek() in precedence and precedence[peek()]>=minimum:
                operator=take().lower();power=precedence[operator]
                if operator=='not':
                    operator='not '+take().lower()
                    if operator not in ('not in','not between'):raise ValueError('Unsupported CHECK operator')
                if operator=='is':
                    negated=peek()=='not'
                    if negated:take('not')
                    take('null');left=('is not null' if negated else 'is null',left)
                elif operator in ('in','not in'):
                    take('(');items=[expression(41)]
                    while peek()==',':take(',');items.append(expression(41))
                    take(')');left=(operator,left,tuple(items))
                elif operator in ('between','not between'):
                    low=expression(41);take('and');high=expression(41);left=(operator,left,low,high)
                else:left=('<>' if operator=='!=' else operator,left,expression(power+1))
            return left
        finally:depth-=1
    tree=expression()
    if index!=len(tokens):raise ValueError('Unreviewed CHECK suffix')
    return tree

def verify_checks(db,inspector,table):
    expected={c.name:check_tree(str(c.sqltext)) for c in table.constraints if isinstance(c,CheckConstraint)}
    found=inspector.get_check_constraints(table.name)
    actual={c['name']:check_tree(c['sqltext']) for c in found}
    if len(actual)!=len(found) or actual!=expected:raise ValueError('CHECK definition drift')
    if inspector.dialect.name=='mysql':
        rows=db.execute(text("SELECT CONSTRAINT_NAME, ENFORCED FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND CONSTRAINT_TYPE='CHECK'"),{'table':table.name}).mappings().all()
        if len(rows)!=len(expected) or {r['CONSTRAINT_NAME'] for r in rows}!=set(expected) or any(r['ENFORCED']!='YES' for r in rows):raise ValueError('CHECK enforcement unverified')
        flags=db.execute(text('SELECT @@SESSION.foreign_key_checks AS fk_checks, @@SESSION.unique_checks AS unique_checks, @@SESSION.sql_mode AS sql_mode')).mappings().one()
        if flags['fk_checks']!=1 or flags['unique_checks']!=1 or not {'STRICT_TRANS_TABLES','STRICT_ALL_TABLES'}.intersection(str(flags['sql_mode']).split(',')):raise ValueError('Session integrity enforcement unverified')
