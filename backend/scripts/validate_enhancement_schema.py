"""Database-free Phase 3.1 checks; never loads Alembic env.py.

Run from the project root with backend/.venv/Scripts/python.exe and this path.
All SQL is compiled to memory, never sent to a server. No pytest DB fixtures.
"""
import ast
from collections import Counter
from contextlib import ExitStack
import importlib.util
from io import StringIO
from pathlib import Path
import re
import sys
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateIndex, CreateTable
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
REVISION = '14c0d3e2f782'
NAMES = ['customer_addresses', 'user_preferences', 'business_settings',
         'vehicles', 'vehicle_documents']
sys.path.insert(0, str(BACKEND))


def refuse_connection(*args, **kwargs):
    raise AssertionError('Database/network access forbidden during static validation')


def table_signature(table):
    dialect = mysql.dialect()
    return {
        'columns': [(c.name, str(c.type.compile(dialect=dialect)), c.nullable,
                     str(c.server_default.arg) if c.server_default else None,
                     c.autoincrement) for c in table.columns],
        'pk': tuple(c.name for c in table.primary_key),
        'unique': sorted((c.name, tuple(c.columns.keys())) for c in table.constraints
                         if isinstance(c, sa.UniqueConstraint)),
        'checks': sorted((c.name, str(c.sqltext)) for c in table.constraints
                         if isinstance(c, sa.CheckConstraint)),
        'fk': sorted((c.name, tuple(c.column_keys), tuple(e.target_fullname for e in c.elements),
                      c.ondelete, c.onupdate) for c in table.foreign_key_constraints),
        'indexes': sorted((i.name, tuple(c.name for c in i.columns), i.unique) for i in table.indexes),
        'options': dict(table.dialect_kwargs),
    }


class Recorder:
    """Interpret only allowed migration construction operations in memory."""
    def __init__(self, metadata):
        self.metadata = metadata
        self.created = []

    def create_table(self, name, *items, **kwargs):
        assert name in NAMES and name not in self.metadata.tables
        self.created.append(name)
        return sa.Table(name, self.metadata, *items, **kwargs)

    def create_index(self, name, table, columns, unique=False):
        assert table in self.created
        sa.Index(name, *(self.metadata.tables[table].c[c] for c in columns), unique=unique)


def main():
    # Even the actual normal model import is protected, including DBAPI sockets.
    with ExitStack() as stack:
        for target in ('socket.create_connection', 'socket.socket.connect', 'socket.socket.connect_ex'):
            stack.enter_context(patch(target, refuse_connection))
        stack.enter_context(patch.object(Engine, 'connect', refuse_connection))
        stack.enter_context(patch.object(Engine, 'raw_connection', refuse_connection))
        stack.enter_context(patch.object(Pool, 'connect', refuse_connection))
        sources = list((BACKEND / 'app/models').glob('*.py')) + list((BACKEND / 'alembic/versions').glob('*.py'))
        sources += [Path(__file__)]
        for path in sources:
            compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
        print(f'PASS Python syntax: {len(sources)} files')

        from app.core.database import Base
        import app.models  # noqa: F401
        configure_mappers()
        assert len(Base.metadata.tables) == 25
        assert len(Base.registry.mappers) == 25
        assert set(NAMES).issubset(Base.metadata.tables)
        print('PASS normal model imports and mapper configuration: 25 tables/mappers')

        # Independently parse the approved five column dictionaries from design.
        design = (ROOT / 'docs/phase2-database-enhancement-schema-design.md').read_text(encoding='utf-8')
        for name in NAMES:
            section = design.split('### ' + name + ' ', 1)[1].split('\n### ', 1)[0].split('\n## ', 1)[0]
            rows = [line.split('|')[1:-1] for line in section.splitlines()
                    if line.startswith('| ') and not line.startswith('| Column ')]
            expected = [(r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()) for r in rows]
            table = Base.metadata.tables[name]
            assert [r[0] for r in expected] == list(table.columns.keys()), name
            for col_name, dtype, nullable, default in expected:
                col = table.c[col_name]
                actual_type = str(col.type.compile(dialect=mysql.dialect()))
                expected_type = dtype.replace('BOOLEAN', 'BOOL').replace('DECIMAL', 'NUMERIC')
                if expected_type == 'INT':
                    expected_type = 'INTEGER'
                normalized_type = actual_type.replace('DECIMAL', 'NUMERIC')
                if dtype == 'CHAR(64) ASCII':
                    assert col.type.length == 64 and col.type.charset == 'ascii'
                else:
                    assert normalized_type.replace(' ', '') == expected_type.replace(' ', ''), (name, col_name)
                assert col.nullable == (nullable == 'Y'), (name, col_name)
                actual_default = str(col.server_default.arg) if col.server_default else None
                if default == 'CURRENT_TIMESTAMP(6)':
                    assert actual_default == default
                elif default in ("'system'", "'active'", "'submitted'", "'pending'"):
                    assert actual_default == default.strip("'")
                elif default in ('TRUE', 'FALSE', '1'):
                    assert actual_default == {'TRUE': '1', 'FALSE': '0', '1': '1'}[default]
                else:
                    assert actual_default is None
                if default == 'AUTO_INCREMENT PK':
                    assert col.primary_key and col.autoincrement is True
                if default == 'PK, none':
                    assert col.primary_key and col.autoincrement is False
        print('PASS five approved column/type/null/default/PK specifications')

        config = Config()
        config.set_main_option('script_location', str(BACKEND / 'alembic'))
        script = ScriptDirectory.from_config(config)  # no env.py; no current()/upgrade()
        assert script.get_heads() == [REVISION]
        chain = list(reversed(list(script.walk_revisions())))
        assert len(chain) == len({r.revision for r in chain}) == 14
        assert script.get_revision(REVISION).down_revision == '03b9c2d1e671'
        tail = [r.revision for r in reversed(list(script.iterate_revisions(REVISION, 'c9d5e8f7a237')))]
        assert tail == ['d0e6f9a8b348', 'e1f7a0b9c459', 'f2a8b1c0d560', '03b9c2d1e671', REVISION]
        print('PASS revision graph: 14 revisions, one root/head, expected prerequisite tail')

        migration_path = Path(script.get_revision(REVISION).path)
        spec = importlib.util.spec_from_file_location('enhancement_revision', migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        tree = ast.parse(migration_path.read_text())
        upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'upgrade')
        calls = [n for n in ast.walk(upgrade) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == 'op']
        assert all(n.func.attr in ('create_table', 'create_index') for n in calls)
        metadata = sa.MetaData()
        for name, table in Base.metadata.tables.items():
            if name not in NAMES:
                table.to_metadata(metadata)
        recorder = Recorder(metadata)
        migration.op = recorder
        migration.upgrade()  # recorder only, never Alembic online operations
        assert recorder.created == NAMES
        for name in NAMES:
            assert table_signature(metadata.tables[name]) == table_signature(Base.metadata.tables[name]), name
        try:
            migration.downgrade()
        except RuntimeError as exc:
            assert 'Preserve' in str(exc)
        else:
            raise AssertionError('Destructive downgrade not refused')
        print('PASS migration/model parity, creation order, additive-only operations and downgrade refusal')

        # Resolve every FK, check signed matching MySQL types and supporting keys.
        constraint_names = []
        for name in NAMES:
            table = Base.metadata.tables[name]
            for obj in list(table.constraints) + list(table.indexes):
                if obj.name:
                    assert len(obj.name) <= 64
            constraint_names += [c.name for c in table.constraints if c.name]
            for fk in table.foreign_key_constraints:
                target = fk.referred_table
                remote = tuple(e.column.name for e in fk.elements)
                target_keys = [tuple(target.primary_key.columns.keys())] + [
                    tuple(c.columns.keys()) for c in target.constraints if isinstance(c, sa.UniqueConstraint)]
                assert remote in target_keys, (name, fk.name)
                keys = [tuple(table.primary_key.columns.keys())] + [
                    tuple(c.columns.keys()) for c in table.constraints if isinstance(c, sa.UniqueConstraint)] + [
                    tuple(c.name for c in i.columns) for i in table.indexes]
                assert any(key[:len(fk.column_keys)] == tuple(fk.column_keys) for key in keys), fk.name
                for element in fk.elements:
                    assert str(element.parent.type) == str(element.column.type)
                assert fk.ondelete == fk.onupdate == 'RESTRICT'
            for check in (c for c in table.constraints if isinstance(c, sa.CheckConstraint)):
                for col in table.columns:
                    if col.autoincrement is True:
                        assert not re.search(r'\b' + col.name + r'\b', str(check.sqltext)), check.name
            CreateTable(table).compile(dialect=mysql.dialect())
            for index in table.indexes:
                CreateIndex(index).compile(dialect=mysql.dialect())
        all_names = [c.name for t in Base.metadata.tables.values() for c in t.constraints if c.name]
        assert all(count == 1 for count in Counter(all_names).values())
        print('PASS FK targets/types/ownership keys, FK indexes, names and MySQL AUTO_INCREMENT CHECK restrictions')

        output = StringIO()
        context = MigrationContext.configure(dialect_name='mysql', opts={'as_sql': True, 'output_buffer': output})
        migration.op = Operations(context)
        migration.upgrade()  # offline SQL rendering, not a database execution
        sql = output.getvalue()
        assert sql.count('CREATE TABLE ') == 5
        assert not re.search(r'\b(ALTER|DROP|INSERT|UPDATE|DELETE|TRUNCATE)\s+(TABLE|INTO|FROM)', sql, re.I)
        assert 'REFERENCES customer_addresses (address_id, user_id)' in sql
        assert 'REFERENCES vehicle_documents (document_id, vehicle_id)' in sql
        assert 'CHAR(64) CHARACTER SET ascii' in sql
        print('PASS offline MySQL rendering: five CREATE TABLE statements; zero database connections')


if __name__ == '__main__':
    main()
