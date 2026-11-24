"""All production values here are offline, non-resolving test fixtures."""
import ssl
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, load_settings
from app.core.database import connection_options
from app.core.http_security import configure_http_security


@pytest.fixture
def clean_env(monkeypatch):
    for key in Settings.model_fields:
        monkeypatch.delenv(key, raising=False)


def production_values():
    return dict(APP_ENV='production', RATE_LIMIT_MODE='external', MYSQL_HOST='db.example.invalid', MYSQL_USER='app_user',
                MYSQL_PASSWORD='offline-fixture-password', MYSQL_DATABASE='isolated_release_fixture',
                JWT_SECRET_KEY='Offline-Fixture-Only-0123456789-Not-A-Live-Key',
                CORS_ALLOWED_ORIGINS=['https://frontend.example.invalid'],
                ALLOWED_HOSTS=['api.example.invalid'])


def test_development_testing_and_disabled_ai_need_no_key(clean_env):
    values = dict(MYSQL_USER='fixture', MYSQL_PASSWORD='fixture',
                  MYSQL_DATABASE='lankapex_db', JWT_SECRET_KEY='fixture')
    assert Settings(_env_file=None, **values).APP_ENV == 'development'
    values['MYSQL_DATABASE'] = 'lankapex_test_db'
    assert Settings(_env_file=None, APP_ENV='testing', **values).APP_ENV == 'testing'
    assert Settings(_env_file=None, **values).AI_ENABLED is False


@pytest.mark.parametrize('database', ['lankapex_db', 'release_database'])
def test_testing_rejects_other_databases(clean_env, database):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV='testing', MYSQL_DATABASE=database,
                 MYSQL_USER='fixture', MYSQL_PASSWORD='fixture', JWT_SECRET_KEY='fixture')


def test_production_ignores_dotenv(clean_env, tmp_path):
    dotenv = tmp_path / '.env'
    dotenv.write_text('MYSQL_PASSWORD=dotenv-private-sentinel\nJWT_SECRET_KEY=dotenv-private-sentinel\n')
    values = production_values()
    del values['JWT_SECRET_KEY']
    with pytest.raises(RuntimeError) as error:
        load_settings(_env_file=dotenv, **values)
    assert 'dotenv-private-sentinel' not in str(error.value)
    assert error.value.__suppress_context__


def test_production_mode_must_not_be_selected_by_dotenv(clean_env, tmp_path):
    dotenv = tmp_path / '.env'
    dotenv.write_text('APP_ENV=production\n')
    with pytest.raises(RuntimeError):
        load_settings(_env_file=dotenv, **(production_values() | {'APP_ENV': 'development'}))


@pytest.mark.parametrize(('mode', 'database'), [
    ('development', 'lankapex_test_db'), ('production', 'release_database'),
    ('testing', 'lankapex_db'),
])
def test_pytest_guard_refuses_unsafe_selection_before_connecting(mode, database):
    namespace = runpy.run_path(str(Path(__file__).with_name('conftest.py')))
    guard = namespace['pytest_sessionstart']
    guard.__globals__['settings'] = SimpleNamespace(APP_ENV=mode, MYSQL_DATABASE=database)
    guard.__globals__['engine'] = SimpleNamespace(url=SimpleNamespace(database=database))
    with pytest.raises(pytest.UsageError):
        guard(None)


@pytest.mark.parametrize('missing', ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE',
                                     'JWT_SECRET_KEY', 'CORS_ALLOWED_ORIGINS', 'ALLOWED_HOSTS'])
def test_explicit_production_settings_required(clean_env, missing):
    values = production_values()
    del values[missing]
    with pytest.raises(RuntimeError):
        load_settings(_env_file=None, **values)


@pytest.mark.parametrize(('key', 'value'), [
    ('JWT_SECRET_KEY', 'secret'), ('JWT_SECRET_KEY', 'a' * 64),
    ('JWT_SECRET_KEY', 'change-me-use-a-private-secret-in-production'),
    ('MYSQL_PASSWORD', '<database-password>'), ('MYSQL_PASSWORD', ''),
    ('ACCESS_TOKEN_EXPIRE_MINUTES', 0), ('ACCESS_TOKEN_EXPIRE_MINUTES', -1),
    ('CORS_ALLOWED_ORIGINS', ['*']), ('CORS_ALLOWED_ORIGINS', []),
    ('CORS_ALLOWED_ORIGINS', ['http://localhost:5173']),
    ('CORS_ALLOWED_ORIGINS', ['https://frontend.example.invalid/path']),
    ('CORS_ALLOWED_ORIGINS', ['https://user:private@frontend.example.invalid']),
    ('ALLOWED_HOSTS', ['*']), ('ALLOWED_HOSTS', ['localhost']), ('ALLOWED_HOSTS', []),
    ('APP_DEBUG', True), ('LOG_LEVEL', 'DEBUG'), ('MYSQL_DATABASE', 'lankapex_db'),
    ('MYSQL_DATABASE', 'lankapex_test_db'), ('MYSQL_HOST', 'localhost'),
    ('MYSQL_HOST', 'localhost.'), ('MYSQL_HOST', '127.2.3.4'),
    ('CORS_ALLOWED_ORIGINS', ['https://dev.localhost']),
    ('CORS_ALLOWED_ORIGINS', ['https://0.0.0.0']), ('ALLOWED_HOSTS', ['LOCALHOST']),
])
def test_unsafe_production_settings_rejected(clean_env, key, value):
    values = production_values() | {key: value}
    with pytest.raises(RuntimeError) as error:
        load_settings(_env_file=None, **values)
    if values['MYSQL_PASSWORD']:
        assert values['MYSQL_PASSWORD'] not in str(error.value)
    assert values['JWT_SECRET_KEY'] not in str(error.value)


def test_safe_production_csv_json_and_verified_tls(clean_env):
    values = production_values() | {
        'CORS_ALLOWED_ORIGINS': '["https://frontend.example.invalid"]',
        'ALLOWED_HOSTS': 'api.example.invalid,other.example.invalid',
    }
    config = Settings(_env_file=None, **values)
    assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert len(config.ALLOWED_HOSTS) == 2
    assert config.JWT_SECRET_KEY not in repr(config)
    assert config.MYSQL_PASSWORD not in repr(config)
    context = connection_options(config)['ssl']
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert connection_options(SimpleNamespace(APP_ENV='testing', MYSQL_SSL_CA=None)) == {'connect_timeout': 5}


def secured_app():
    app = FastAPI()
    configure_http_security(app, SimpleNamespace(APP_ENV='production', LOG_LEVEL='INFO',
        CORS_ALLOWED_ORIGINS=['https://frontend.example.invalid'], ALLOWED_HOSTS=['testserver']))

    @app.get('/protected')
    def protected():
        raise HTTPException(401, 'Not authenticated', headers={'WWW-Authenticate': 'Bearer'})

    @app.get('/explode')
    def explode():
        raise ValueError('private-sentinel SQL password JWT financial data')

    class Body(BaseModel):
        password: str = Field(min_length=12)

    @app.post('/validate')
    def validate(body: Body):
        return {'ok': True}
    return app


def test_cors_authorization_preflight_and_rejected_origin():
    client = TestClient(secured_app())
    headers = {'Origin': 'https://frontend.example.invalid',
               'Access-Control-Request-Method': 'PATCH',
               'Access-Control-Request-Headers': 'Authorization,Content-Type'}
    response = client.options('/protected', headers=headers)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == headers['Origin']
    assert 'access-control-allow-credentials' not in response.headers
    denied = client.options('/protected', headers=headers | {'Origin': 'https://untrusted.example.invalid'})
    assert denied.status_code == 400
    assert 'access-control-allow-origin' not in denied.headers
    for origin in ['https://untrusted.example.invalid', 'http://localhost:5173', 'null']:
        denied = client.get('/protected', headers={'Origin': origin})
        assert denied.status_code == 401
        assert 'access-control-allow-origin' not in denied.headers
    response = client.get('/protected', headers={'Origin': headers['Origin'], 'Authorization': 'Bearer invalid'})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    assert response.headers['access-control-allow-origin'] == headers['Origin']


def test_error_redaction_headers_host_and_safe_operational_log(caplog):
    client = TestClient(secured_app())
    response = client.get('/explode', headers={'Origin': 'https://frontend.example.invalid'})
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal server error'}
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['access-control-allow-origin'] == 'https://frontend.example.invalid'
    assert 'private-sentinel' not in caplog.text
    assert 'Unhandled ValueError on GET /explode' in caplog.text
    response = client.post('/validate', json={'password': 'secret123'})
    assert response.status_code == 422
    assert 'secret123' not in response.text
    assert response.json()['detail'][0]['loc'] == ['body', 'password']
    assert client.get('/protected', headers={'Host': 'untrusted.example.invalid'}).status_code == 400


def test_examples_have_placeholders_and_backend_only_ai_configuration():
    root = Path(__file__).resolve().parents[2]
    example = (root / 'backend/.env.example').read_text()
    assert 'JWT_SECRET_KEY=<private-signing-secret>' in example
    assert 'MYSQL_PASSWORD=<local-database-password>' in example
    assert '# GROQ_API_KEY=<backend-only-secret>' in example
    assert 'GROQ_MODEL=openai/gpt-oss-120b' in example
    public = (root / 'frontend/.env.example').read_text()
    assert [line.split('=')[0] for line in public.splitlines() if line.startswith('VITE_')] == ['VITE_API_URL']
    assert 'GROQ' not in public
