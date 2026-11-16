"""Offline TLS contract tests; never open a database connection."""
import socket
import ssl
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pymysql
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from app.core.config import Settings
from app.core.database import connection_options


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden in offline tests')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


def viva(**updates):
    values = dict(APP_ENV='development', MYSQL_HOST='127.0.0.1', MYSQL_PORT=3306,
                  MYSQL_DATABASE='lankapex_viva_db', MYSQL_USER='synthetic',
                  MYSQL_PASSWORD='synthetic', JWT_SECRET_KEY='synthetic',
                  MYSQL_SSL_CA=None, MYSQL_TLS_MODE='local_viva_required', AI_ENABLED=False)
    values.update(updates)
    return Settings(_env_file=None, **values)


def test_allowed_context_and_sqlalchemy_pymysql_required_tls():
    options = connection_options(viva())
    ctx = options['ssl']
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE
    engine = create_engine('mysql+pymysql://synthetic:synthetic@127.0.0.1:3306/lankapex_viva_db',
                           connect_args=options)
    captured = {}
    def deferred_connect(*args, **kwargs):
        captured.update(kwargs)
        return pymysql.connections.Connection(*args, **kwargs, defer_connect=True)
    try:
        with patch.object(engine.dialect.loaded_dbapi, 'connect', deferred_connect):
            connection = engine.pool._creator()
        assert captured['ssl'] is ctx
        assert connection.ctx is ctx
        assert connection.ssl and connection._ssl_required
        # Simulate the installed driver's handshake against a non-TLS server.
        connection.server_version = '8.0.0'
        connection.server_capabilities = 0
        connection.write_packet = Mock(side_effect=AssertionError('Must not send credentials'))
        with pytest.raises(pymysql.err.OperationalError, match='SSL is required'):
            connection._request_authentication()
        connection.write_packet.assert_not_called()
    finally:
        engine.dispose()


@pytest.mark.parametrize('updates', [
    {'APP_ENV': 'production'}, {'APP_ENV': 'testing'},
    {'MYSQL_HOST': 'localhost'}, {'MYSQL_HOST': '127.0.0.2'},
    {'MYSQL_PORT': 3307}, {'MYSQL_DATABASE': 'lankapex_demo_db'},
    {'MYSQL_DATABASE': 'lankapex_db'}, {'MYSQL_SSL_CA': 'conflicting-ca.pem'},
    {'MYSQL_TLS_MODE': 'unknown'},
])
def test_rejected_settings(updates):
    with pytest.raises(ValidationError):
        viva(**updates)


@pytest.mark.parametrize('updates', [
    {'APP_ENV': 'production'}, {'MYSQL_HOST': 'localhost'}, {'MYSQL_PORT': 3307},
    {'MYSQL_DATABASE': 'lankapex_demo_db'}, {'MYSQL_SSL_CA': 'conflicting-ca.pem'},
])
def test_connection_options_defense_in_depth(updates):
    values = viva().model_dump()
    values.update(updates)
    with pytest.raises(ValueError):
        connection_options(SimpleNamespace(**values))


def test_default_development_options_unchanged():
    config = viva(MYSQL_TLS_MODE='default', MYSQL_HOST='localhost', MYSQL_DATABASE='lankapex_demo_db')
    assert connection_options(config) == {'connect_timeout': 5}


@pytest.mark.parametrize('mode,ca', [('production', None), ('development', 'public-ca.pem')])
def test_existing_verified_tls_branch_unchanged(mode, ca):
    config = SimpleNamespace(APP_ENV=mode, MYSQL_SSL_CA=ca, MYSQL_TLS_MODE='default')
    with patch('app.core.database.ssl.create_default_context') as factory:
        context = factory.return_value
        assert connection_options(config) == {'connect_timeout': 5, 'ssl': context}
        factory.assert_called_once_with(cafile=ca)


def test_real_production_context_verifies_identity():
    ctx = connection_options(SimpleNamespace(APP_ENV='production', MYSQL_SSL_CA=None))['ssl']
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
