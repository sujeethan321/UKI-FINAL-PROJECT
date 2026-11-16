"""Local checks; no cloud, migrations, backups or production database connections."""
import asyncio
import importlib.util
import json
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.readiness import ReadinessProbe
from test_catalogue import shop, api, db

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('production_launcher', ROOT / 'backend/scripts/start_production.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize('env', [{}, {'APP_ENV':'development','PORT':'8000'},
    {'APP_ENV':'production'}, {'APP_ENV':'production','PORT':'0'},
    {'APP_ENV':'production','PORT':'65536'}, {'APP_ENV':'production','PORT':'private-sentinel'}])
def test_launcher_rejects_unsafe_environment_without_echoing_values(env):
    with pytest.raises(ValueError) as error:
        launcher.runtime_options(env)
    assert 'private-sentinel' not in str(error.value)


def test_launcher_binds_platform_port_without_reload_proxy_trust_or_raw_access_logs():
    options = launcher.runtime_options({'APP_ENV':'production','PORT':'9001'})
    assert options == dict(host='0.0.0.0',port=9001,reload=False,proxy_headers=False,
                           access_log=False,log_level='info')
    manifest = json.loads((ROOT / 'backend/railway.json').read_text())
    assert manifest['deploy']['startCommand'] == 'python scripts/start_production.py'
    assert manifest['deploy']['healthcheckPath'] == '/api/v1/health/database'
    assert 'preDeployCommand' not in manifest['deploy']


def test_liveness_is_public_minimal_and_does_not_invoke_database(monkeypatch):
    operation = AsyncMock(side_effect=AssertionError('Liveness must not query DB'))
    monkeypatch.setattr('app.services.readiness.probe.check', operation)
    with TestClient(app) as client:
        response = client.get('/api/v1/health')
    assert response.status_code == 200 and response.json()['status'] == 'ok'
    assert response.headers['cache-control'] == 'no-store'
    operation.assert_not_called()
    assert 'MYSQL' not in response.text and 'password' not in response.text


@pytest.mark.parametrize('ready', [True, False])
def test_public_readiness_success_or_generic_unavailable(monkeypatch, ready):
    monkeypatch.setattr('app.services.readiness.probe.check', AsyncMock(return_value=ready))
    with TestClient(app) as client:
        response = client.get('/api/v1/health/database')
    assert response.status_code == (200 if ready else 503)
    assert response.json() == ({'status':'ok','database':'connected'} if ready else {'detail':'Database unavailable'})
    assert response.headers['cache-control'] == 'no-store'
    assert not any(value in response.text for value in ['lankapex_test_db','MYSQL','password','traceback'])


def test_probe_exception_redaction_and_connection_cleanup():
    def broken():
        raise RuntimeError('private-sentinel SQL credentials')
    probe = ReadinessProbe(broken, .1)
    try:
        assert asyncio.run(probe.check()) is False
        assert not probe.busy.locked()
    finally:
        probe.executor.shutdown(wait=True)


def test_probe_deadline_and_no_queue_of_abandoned_workers():
    release = threading.Event()
    started = threading.Event()
    def stuck():
        started.set()
        release.wait(2)
        return True
    probe = ReadinessProbe(stuck, .03)
    try:
        before = time.monotonic()
        assert asyncio.run(probe.check()) is False
        assert time.monotonic()-before < .5
        assert started.is_set() and probe.busy.locked()
        # Still-running timed-out probe prevents another queued database attempt.
        assert asyncio.run(probe.check()) is False
    finally:
        release.set()
        probe.executor.shutdown(wait=True)
    assert not probe.busy.locked()


def test_actual_test_database_probe_is_read_only():
    from app.core.config import settings
    from app.services.readiness import database_available, probe_engine
    assert settings.APP_ENV == 'testing'
    assert settings.MYSQL_DATABASE == probe_engine.url.database == 'lankapex_test_db'
    assert database_available() is True


def test_synthetic_login_cors_health_and_authenticated_read(shop):
    from app.core.security import hash_password
    shop['user'].password_hash = hash_password('Synthetic-deployment-smoke-only-2026')
    shop['db'].flush()
    client = shop['client']
    assert client.get('/api/v1/health').status_code == 200
    preflight = client.options('/api/v1/auth/me', headers={
        'Origin':'http://localhost:5173', 'Access-Control-Request-Method':'GET',
        'Access-Control-Request-Headers':'Authorization'})
    assert preflight.status_code == 200
    login = client.post('/api/v1/auth/login', data={
        'username':shop['user'].email, 'password':'Synthetic-deployment-smoke-only-2026'})
    assert login.status_code == 200
    identity = client.get('/api/v1/auth/me', headers={
        'Authorization':'Bearer '+login.json()['access_token'], 'Origin':'http://localhost:5173'})
    assert identity.status_code == 200
    assert identity.json()['user_id'] == shop['user'].user_id
    assert identity.headers['access-control-allow-origin'] == 'http://localhost:5173'
