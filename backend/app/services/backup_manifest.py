# Purpose: Build backup/restore arguments and verify manifest structure and checksums for maintenance tooling.
"""Offline backup planning/validation only. Never starts a dump or restoration."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.db_maintenance import MaintenanceSafetyError, validate_target


# Build an explicit backup argument list so callers do not assemble shell command text.
def backup_command(*, option_file, database, output, transactional=True):
    # Credentials/host/TLS belong in a private MySQL option file, not CLI arguments.
    if not re.fullmatch(r'[a-z][a-z0-9_]{2,63}', database or ''):
        raise MaintenanceSafetyError('Explicit source database name required')
    if not transactional:
        raise MaintenanceSafetyError('Non-InnoDB sources require an operator-reviewed consistency plan')
    return ['mysqldump', f'--defaults-file={Path(option_file)}', '--single-transaction',
            '--quick', '--skip-lock-tables', '--skip-add-drop-table', '--no-tablespaces', '--set-gtid-purged=OFF',
            '--column-statistics=0', '--hex-blob', '--routines', '--events', '--triggers',
            '--default-character-set=utf8mb4', f'--result-file={Path(output)}', database]


# Build an explicit restore argument list for the validated maintenance target.
def restore_command(*, option_file, environment, database):
    validate_target(environment, database, 'restore')
    # Feed the validated trusted dump through stdin; never shell-concatenate SQL.
    return ['mysql', f'--defaults-file={Path(option_file)}', '--binary-mode',
            '--default-character-set=utf8mb4', f'--database={database}']


# Compute a file digest so a manifest can detect changed backup content.
def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(manifest, dump, *, now=None):
    """A checksum validates bytes, not restoreability, provenance or encryption."""
    try:
        required = {'format_version', 'format', 'created_at', 'source_environment',
                    'source_database', 'mysql_version', 'schema_revision', 'sha256', 'size_bytes'}
        if not isinstance(manifest, dict) or set(manifest) != required:
            raise ValueError
        if (type(manifest['format_version']) is not int or manifest['format_version'] != 1
                or manifest['format'] != 'mysql-logical-sql'):
            raise ValueError
        if manifest['source_environment'] not in {'development', 'testing', 'production'}:
            raise ValueError
        if not re.fullmatch(r'[a-z][a-z0-9_]{2,63}', manifest['source_database']):
            raise ValueError
        if not re.fullmatch(r'8\.0\.\d+(?:[-+][A-Za-z0-9.-]+)?', manifest['mysql_version']):
            raise ValueError
        if not re.fullmatch(r'[a-f0-9]{12}', manifest['schema_revision']):
            raise ValueError
        if not re.fullmatch(r'[a-f0-9]{64}', manifest['sha256']):
            raise ValueError
        created = datetime.fromisoformat(manifest['created_at'].replace('Z', '+00:00'))
        if created.tzinfo is None or created > (now or datetime.now(timezone.utc)):
            raise ValueError
        path = Path(dump)
        if (not path.is_file() or type(manifest['size_bytes']) is not int
                or manifest['size_bytes'] <= 0 or path.stat().st_size != manifest['size_bytes']):
            raise ValueError
        with path.open('rb') as stream:
            if not stream.read(256).startswith(b'-- MySQL dump'):
                raise ValueError
        if checksum(path) != manifest['sha256']:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        raise MaintenanceSafetyError('Invalid backup artifact or metadata; do not restore') from None
    return manifest


# Read manifest for the backup manifest workflow.
def read_manifest(path, dump):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise MaintenanceSafetyError('Unreadable backup metadata; do not restore') from None
    return validate_manifest(data, dump)
