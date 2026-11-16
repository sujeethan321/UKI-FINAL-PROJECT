"""Database-free validation of backend-only AI provider settings."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings, load_settings


def values(**updates):
    base = dict(MYSQL_USER='fixture', MYSQL_PASSWORD='fixture-password',
                MYSQL_DATABASE='lankapex_db', JWT_SECRET_KEY='fixture-signing-secret')
    return base | updates


def test_ai_disabled_does_not_require_a_key():
    config = Settings(_env_file=None, **values())
    assert config.AI_ENABLED is False
    assert config.GROQ_API_KEY is None
    assert config.GROQ_MODEL == 'openai/gpt-oss-120b'
    assert config.GROQ_BASE_URL == 'https://api.groq.com/openai/v1'


def test_ai_enabled_accepts_a_private_synthetic_key_and_redacts_it():
    secret = 'gsk_offline_test_7Qx2mN9pL4vR8sT6'
    config = Settings(_env_file=None, **values(AI_ENABLED=True, GROQ_API_KEY=secret))
    assert config.GROQ_API_KEY.get_secret_value() == secret
    assert secret not in repr(config)
    assert secret not in str(config)


@pytest.mark.parametrize('key', [None, '', 'secret', 'changeme', '<backend-only-secret>',
                                 'replace_me_with_your_api_key'])
def test_enabled_ai_rejects_missing_empty_and_placeholder_keys(key):
    supplied = {} if key is None else {'GROQ_API_KEY': key}
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **values(AI_ENABLED=True, **supplied))
    assert not key or key not in str(error.value)


@pytest.mark.parametrize('url', [
    'http://api.groq.com/openai/v1',
    'https://api.groq.com.example.com/openai/v1',
    'https://groq.com/openai/v1',
    'https://user:password@api.groq.com/openai/v1',
    'https://api.groq.com/openai/v1?debug=true',
    'https://api.groq.com/openai/v1#fragment',
    'https://api.groq.com/v1',
    'https://api.groq.com:444/openai/v1',
])
def test_unapproved_groq_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values(GROQ_BASE_URL=url))


def test_approved_groq_url_normalizes_one_trailing_slash():
    config = Settings(_env_file=None, **values(
        GROQ_BASE_URL='https://api.groq.com/openai/v1/'))
    assert config.GROQ_BASE_URL == 'https://api.groq.com/openai/v1'


@pytest.mark.parametrize(('name', 'value'), [
    ('GROQ_TIMEOUT_SECONDS', 0.9), ('GROQ_TIMEOUT_SECONDS', 30.1),
    ('GROQ_MAX_OUTPUT_TOKENS', 63), ('GROQ_MAX_OUTPUT_TOKENS', 1001),
    ('RATE_LIMIT_AI_GENERATION', 0), ('RATE_LIMIT_AI_GENERATION', 101),
])
def test_ai_numeric_limits_are_enforced(name, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values(**{name: value}))


def test_load_settings_redacts_ai_secret_and_suppresses_validation_context():
    secret = 'gsk_private_sentinel_should_never_appear'
    with pytest.raises(RuntimeError) as error:
        load_settings(_env_file=None, **values(
            AI_ENABLED=True, GROQ_API_KEY=secret,
            GROQ_BASE_URL='http://api.groq.com/openai/v1'))
    assert secret not in str(error.value)
    assert error.value.__suppress_context__


def test_existing_non_ai_settings_remain_compatible():
    config = Settings(_env_file=None, **values(
        ACCESS_TOKEN_EXPIRE_MINUTES=45, RATE_LIMIT_EXPORT=7,
        CORS_ALLOWED_ORIGINS='http://localhost:5173',
        ALLOWED_HOSTS='localhost,127.0.0.1'))
    assert config.ACCESS_TOKEN_EXPIRE_MINUTES == 45
    assert config.RATE_LIMIT_EXPORT == 7
    assert config.CORS_ALLOWED_ORIGINS == ['http://localhost:5173']
    assert config.ALLOWED_HOSTS == ['localhost', '127.0.0.1']


def test_ai_snapshot_test_mode_is_an_exact_database_and_account_allowlist():
    config = Settings(_env_file=None, **values(
        APP_ENV='ai_snapshot_testing', MYSQL_DATABASE='lankapex_ai_snapshot_test_db',
        MYSQL_USER='lankapex_ai_snap_runtime'))
    assert config.APP_ENV == 'ai_snapshot_testing'
    for change in ({'MYSQL_DATABASE': 'lankapex_test_db'},
                   {'MYSQL_USER': 'lankapex_qr_test_runtime'}):
        with pytest.raises(ValidationError):
            supplied = values(
                APP_ENV='ai_snapshot_testing', MYSQL_DATABASE='lankapex_ai_snapshot_test_db',
                MYSQL_USER='lankapex_ai_snap_runtime') | change
            Settings(_env_file=None, **supplied)


def test_ai_snapshot_migration_mode_is_a_distinct_exact_allowlist():
    config = Settings(_env_file=None, **values(
        APP_ENV='ai_snapshot_migration', MYSQL_DATABASE='lankapex_ai_snapshot_test_db',
        MYSQL_USER='lankapex_ai_snap_migrator'))
    assert config.APP_ENV == 'ai_snapshot_migration'
    for change in ({'MYSQL_DATABASE': 'lankapex_test_db'},
                   {'MYSQL_USER': 'lankapex_ai_snap_runtime'}):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **(values(
                APP_ENV='ai_snapshot_migration', MYSQL_DATABASE='lankapex_ai_snapshot_test_db',
                MYSQL_USER='lankapex_ai_snap_migrator') | change))


def test_mysql_username_limit_rejects_previous_overlength_identities():
    assert len('lankapex_ai_snap_runtime') <= 32
    assert len('lankapex_ai_snap_migrator') <= 32
    for username in ('lankapex_ai_snapshot_test_runtime',
                     'lankapex_ai_snapshot_test_migrator', 'x' * 33):
        assert len(username) > 32
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **values(MYSQL_USER=username))
