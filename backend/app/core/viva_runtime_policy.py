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


def dotenv_disabled(environ=None):
    env = os.environ if environ is None else environ
    if FLAG not in env:
        return False
    if any(env.get(k) != v for k, v in ENVIRONMENT.items()):
        raise ValueError('VIVA_RUNTIME_CONFIGURATION_MISMATCH')
    if any(k in env for k in FORBIDDEN):
        raise ValueError('VIVA_RUNTIME_INHERITED_INTEGRATION')
    if not env.get('MYSQL_PASSWORD') or len(env.get('JWT_SECRET_KEY', '')) < 64:
        raise ValueError('VIVA_RUNTIME_CREDENTIALS_REQUIRED')
    return True
