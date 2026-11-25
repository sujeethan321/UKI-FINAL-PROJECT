# Purpose: Require the exact opt-in viva environment and reject conflicting inherited configuration before disabling dotenv loading.
"""Exact opt-in VIVA runtime settings; no I/O or database imports."""
import os

FLAG = 'LANKAPEX_VIVA_RUNTIME'
REVISION = 'd15a8c902e64'
ENVIRONMENT = {
    FLAG: 'true', 'APP_ENV': 'development', 'MYSQL_HOST': '127.0.0.1',
    'MYSQL_PORT': '3306', 'MYSQL_DATABASE': 'lankapex_viva_db',
    'MYSQL_USER': 'lankapex_viva_runtime', 'MYSQL_TLS_MODE': 'local_viva_required',
    'MYSQL_SSL_CA': r'C:\Program Files\LankaPex-TLS-Trust\ca.pem',
    'APP_DEBUG': 'false', 'LOG_LEVEL': 'INFO', 'RATE_LIMIT_MODE': 'local',
    'AI_ENABLED': 'false', 'STRIPE_SANDBOX_ENABLED': 'false',
    'ADDRESS_BOOK_ENABLED': 'true', 'ADDRESS_CHECKOUT_ENABLED': 'true',
    'SUPPORT_ENABLED': 'true', 'DRIVER_FINANCE_ENABLED': 'true',
    'ADDRESS_DBA_ATTESTED_REVISION': REVISION,
    'SUPPORT_DBA_ATTESTED_REVISION': REVISION,
    'DRIVER_FINANCE_DBA_ATTESTED_REVISION': REVISION,
    'CORS_ALLOWED_ORIGINS': 'http://127.0.0.1:5173,http://127.0.0.1:5176',
    'ALLOWED_HOSTS': '127.0.0.1,localhost',
}
FORBIDDEN = ('LANKAPEX_DISABLE_DOTENV', 'GROQ_API_KEY', 'STRIPE_TEST_SECRET_KEY',
             'STRIPE_WEBHOOK_SECRET', 'DATABASE_URL', 'SQLALCHEMY_DATABASE_URI')
INTEGRATIONS_FLAG = 'LANKAPEX_VIVA_INTEGRATIONS'
# Only these dotenv fields may supplement the pinned runtime in the opt-in mode.
INTEGRATION_FIELDS = frozenset({
    'GROQ_API_KEY', 'GROQ_BASE_URL', 'GROQ_MODEL', 'GROQ_TIMEOUT_SECONDS',
    'GROQ_MAX_OUTPUT_TOKENS', 'GROQ_MAX_RESPONSE_BYTES',
    'AI_MAX_CONCURRENT_GENERATIONS', 'AI_MAX_GENERATIONS_PER_WINDOW', 'AI_USAGE_WINDOW_SECONDS',
    'STRIPE_TEST_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_PRO_MONTH_PRICE',
    'STRIPE_PRO_YEAR_PRICE', 'STRIPE_BUSINESS_MONTH_PRICE', 'STRIPE_BUSINESS_YEAR_PRICE',
    'STRIPE_RETURN_ORIGIN', 'STRIPE_PORTAL_CONFIGURATION',
})


def integrations_enabled(environ=None):
    """Require an exact process-only opt-in rather than trusting a dotenv feature flag."""
    env = os.environ if environ is None else environ
    value = env.get(INTEGRATIONS_FLAG)
    if value not in (None, 'true', 'ai-only'):
        raise ValueError('VIVA_INTEGRATIONS_FLAG_INVALID')
    return value in ('true', 'ai-only')


def integration_fields(environ=None):
    """AI-only startup does not load Stripe credentials or other Stripe configuration."""
    env = os.environ if environ is None else environ
    if env.get(INTEGRATIONS_FLAG) == 'ai-only':
        return frozenset(key for key in INTEGRATION_FIELDS if not key.startswith('STRIPE_'))
    return INTEGRATION_FIELDS


def expected_environment(environ=None):
    """Keep database/TLS policy fixed while selecting the explicit integration mode."""
    expected = dict(ENVIRONMENT)
    if integrations_enabled(environ):
        env = os.environ if environ is None else environ
        expected.update(AI_ENABLED='true', STRIPE_SANDBOX_ENABLED='true' if env.get(INTEGRATIONS_FLAG) == 'true' else 'false')
    return expected


# Disable dotenv only after the exact viva environment and required private credentials have passed validation.
def dotenv_disabled(environ=None):
    env = os.environ if environ is None else environ
    if FLAG not in env:
        return False
    if any(env.get(k) != v for k, v in expected_environment(env).items()):
        raise ValueError('VIVA_RUNTIME_CONFIGURATION_MISMATCH')
    forbidden = set(FORBIDDEN)
    if integrations_enabled(env):
        forbidden -= integration_fields(env)
    if any(k in env for k in forbidden):
        raise ValueError('VIVA_RUNTIME_INHERITED_INTEGRATION')
    if not env.get('MYSQL_PASSWORD') or len(env.get('JWT_SECRET_KEY', '')) < 64:
        raise ValueError('VIVA_RUNTIME_CREDENTIALS_REQUIRED')
    return True
