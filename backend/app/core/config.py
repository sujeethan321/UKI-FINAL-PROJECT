# Purpose: Validate backend environment settings before startup, including database, CORS, TLS, rate limits, and integration configuration.
"""Backend-only settings; production never reads local dotenv files."""
import json
import ipaddress
import os
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict, SettingsError
from app.core.viva_runtime_policy import dotenv_disabled as viva_runtime_dotenv_disabled

BASE_DIR = Path(__file__).resolve().parents[2]
OriginList = Annotated[list[str], NoDecode]
DOTENV_ISOLATION_FLAG = 'LANKAPEX_DISABLE_DOTENV'
ISOLATED_BROWSER_ENVIRONMENT = {
    'APP_ENV': 'ai_snapshot_testing',
    'MYSQL_HOST': 'localhost',
    'MYSQL_PORT': '3306',
    'MYSQL_DATABASE': 'lankapex_ai_snapshot_test_db',
    'MYSQL_USER': 'lankapex_ai_snap_runtime',
    'APP_DEBUG': 'false',
    'LOG_LEVEL': 'WARNING',
    'CORS_ALLOWED_ORIGINS': 'http://127.0.0.1:5175',
    'RATE_LIMIT_MODE': 'local',
    'AI_ENABLED': 'false',
}


def isolated_browser_dotenv_disabled():
    """Fail closed unless dotenv isolation is the exact reviewed browser context."""
    requested = os.getenv(DOTENV_ISOLATION_FLAG)
    if requested is None:
        return False
    if requested != 'true':
        raise ValueError('Dotenv isolation flag must use its exact reviewed value')
    if any(os.getenv(name) != value for name, value in ISOLATED_BROWSER_ENVIRONMENT.items()):
        raise ValueError('Dotenv isolation is restricted to the isolated AI browser context')
    if 'GROQ_API_KEY' in os.environ:
        raise ValueError('Isolated AI browser context requires GROQ_API_KEY to be absent')
    if not os.getenv('MYSQL_PASSWORD') or not os.getenv('JWT_SECRET_KEY'):
        raise ValueError('Isolated AI browser context requires private runtime credentials')
    return True


# Recognize local hostnames and IP addresses when validating environment-specific configuration.
def local_host(host):
    host = host.lower().strip('[]').rstrip('.')
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or address.is_unspecified
    except ValueError:
        return False


# Group the state and operations for settings in the config module.
class Settings(BaseSettings):
    ADDRESS_BOOK_ENABLED: bool = False
    ADDRESS_CHECKOUT_ENABLED: bool = False
    ADDRESS_DBA_ATTESTED_REVISION: str | None = None
    SUPPORT_ENABLED: bool = False
    SUPPORT_DBA_ATTESTED_REVISION: str | None = None
    DRIVER_FINANCE_ENABLED: bool = False
    DRIVER_FINANCE_DBA_ATTESTED_REVISION: str | None = None
    # Keep uploaded driver evidence outside publicly served application paths.
    DRIVER_DOCUMENT_PRIVATE_ROOT: Path | None = None
    APP_ENV: Literal['development', 'testing', 'ai_snapshot_testing',
                     'ai_snapshot_migration', 'production'] = 'development'
    # Validate the database endpoint and connection/probe time budgets before constructing SQLAlchemy engines.
    MYSQL_HOST: str = 'localhost'
    MYSQL_PORT: int = Field(default=3306, ge=1, le=65535)
    MYSQL_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)
    READINESS_DB_TIMEOUT_SECONDS: int = Field(default=2, ge=1, le=10)
    READINESS_TIMEOUT_SECONDS: float = Field(default=3, ge=0.1, le=10)
    # Load credentials from backend settings; repr=False prevents accidental disclosure in settings representations.
    MYSQL_USER: str
    MYSQL_PASSWORD: str = Field(repr=False)
    MYSQL_DATABASE: str
    # Select trusted TLS settings, with a separate explicit mode for the constrained local viva environment.
    MYSQL_SSL_CA: Path | None = None
    MYSQL_TLS_MODE: Literal['default', 'local_viva_required'] = 'default'
    # Use a backend-only signing key and a positive token lifetime for time-limited authentication.
    JWT_SECRET_KEY: str = Field(repr=False)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0)
    REMINDER_COOLDOWN_SECONDS: int = Field(default=86400, ge=0, le=31536000)
    APP_DEBUG: bool = False
    LOG_LEVEL: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    RATE_LIMIT_MODE: Literal['local', 'external'] = 'local'
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    RATE_LIMIT_LOGIN: int = Field(default=10, ge=1, le=100000)
    RATE_LIMIT_LOGIN_IP: int = Field(default=40, ge=1, le=100000)
    RATE_LIMIT_REGISTRATION: int = Field(default=10, ge=1, le=100000)
    RATE_LIMIT_MUTATION: int = Field(default=60, ge=1, le=100000)
    RATE_LIMIT_EXPORT: int = Field(default=5, ge=1, le=100000)
    RATE_LIMIT_AI_GENERATION: int = Field(default=5, ge=1, le=100)
    RATE_LIMIT_MAX_KEYS: int = Field(default=4096, ge=16, le=65536)
    MAX_REQUEST_BODY_BYTES: int = Field(default=262144, ge=1024, le=1048576)
    MAX_INTERACTIVE_CUSTOMERS: int = Field(default=1000, ge=1, le=10000)
    MAX_READ_LEDGER_ENTRIES: int = Field(default=5000, ge=1, le=100000)
    AI_ENABLED: bool = False
    REQUEST_BODY_TIMEOUT_SECONDS: float = Field(default=15, ge=1, le=60)
    AI_MAX_CONCURRENT_GENERATIONS: int = Field(default=2, ge=1, le=2)
    AI_MAX_GENERATIONS_PER_WINDOW: int = Field(default=60, ge=1, le=10000)
    AI_USAGE_WINDOW_SECONDS: int = Field(default=3600, ge=60, le=86400)
    GROQ_MAX_RESPONSE_BYTES: int = Field(default=65536, ge=1024, le=262144)
    STRIPE_SANDBOX_ENABLED: bool = False
    STRIPE_TEST_SECRET_KEY: SecretStr | None = Field(default=None, repr=False)
    STRIPE_WEBHOOK_SECRET: SecretStr | None = Field(default=None, repr=False)
    STRIPE_PRO_MONTH_PRICE: str = ''
    STRIPE_PRO_YEAR_PRICE: str = ''
    STRIPE_BUSINESS_MONTH_PRICE: str = ''
    STRIPE_BUSINESS_YEAR_PRICE: str = ''
    STRIPE_RETURN_ORIGIN: str = Field(default='http://127.0.0.1:5176', max_length=255)
    STRIPE_PORTAL_CONFIGURATION: str = ''
    GROQ_API_KEY: SecretStr | None = Field(default=None, repr=False)
    GROQ_BASE_URL: str = 'https://api.groq.com/openai/v1'
    GROQ_MODEL: str = 'openai/gpt-oss-120b'
    GROQ_TIMEOUT_SECONDS: float = Field(default=10.0, ge=1.0, le=30.0)
    GROQ_MAX_OUTPUT_TOKENS: int = Field(default=400, ge=64, le=1000)
    # Browser origins include scheme, hostname, and port; localhost and 127.0.0.1 must be allowed separately.
    CORS_ALLOWED_ORIGINS: OriginList = ['http://localhost:5173', 'http://127.0.0.1:5173']
    ALLOWED_HOSTS: OriginList = ['localhost', '127.0.0.1', 'testserver']

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env', env_file_encoding='utf-8', extra='ignore',
        hide_input_in_errors=True,
    )

    # Select the allowed settings sources so environment isolation and production dotenv rules remain explicit.
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        mode = init_settings.init_kwargs.get('APP_ENV', os.getenv('APP_ENV', 'development'))
        dotenv_isolated = isolated_browser_dotenv_disabled()
        if dotenv_isolated and mode != ISOLATED_BROWSER_ENVIRONMENT['APP_ENV']:
            raise ValueError('Dotenv isolation cannot be combined with another environment')
        if mode == 'production':
            return init_settings, env_settings, file_secret_settings
        if dotenv_isolated or viva_runtime_dotenv_disabled():
            # Also protects direct Settings() construction in this process;
            # application startup and request handling share this singleton.
            return init_settings, env_settings, file_secret_settings
        if dotenv_settings().get('APP_ENV') == 'production':
            raise ValueError('Select production through the process environment, not dotenv')
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    # Validate parse list before the schema accepts the value.
    @field_validator('CORS_ALLOWED_ORIGINS', 'ALLOWED_HOSTS', mode='before')
    @classmethod
    def parse_list(cls, value):
        if isinstance(value, str):
            if value.lstrip().startswith('['):
                return json.loads(value)
            return [item.strip() for item in value.split(',') if item.strip()]
        return value

    # Validate mysql username before the schema accepts the value.
    @field_validator('MYSQL_USER')
    @classmethod
    def validate_mysql_username(cls, value):
        if not value or value != value.strip() or len(value) > 32 or '@' in value:
            raise ValueError('MySQL username must be a local account name of at most 32 characters')
        return value

    # Validate origins before the schema accepts the value.
    @field_validator('CORS_ALLOWED_ORIGINS')
    @classmethod
    def validate_origins(cls, values):
        for origin in values:
            try:
                parsed = urlsplit(origin)
                port = parsed.port
            except ValueError:
                raise ValueError('CORS origins must be exact HTTP origins') from None
            if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path
                    or parsed.query or parsed.fragment or '*' in origin
                    or (port is not None and port < 1) or any(c.isspace() for c in origin)):
                raise ValueError('CORS origins must be exact HTTP origins without paths')
        return values

    # Validate hosts before the schema accepts the value.
    @field_validator('ALLOWED_HOSTS')
    @classmethod
    def validate_hosts(cls, values):
        if any(not host or any(char in host for char in '/*:@?# ') for host in values):
            raise ValueError('ALLOWED_HOSTS requires exact hostnames without ports')
        return values

    # Validate groq base url before the schema accepts the value.
    @field_validator('GROQ_BASE_URL')
    @classmethod
    def validate_groq_base_url(cls, value):
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except (TypeError, ValueError):
            raise ValueError('Groq base URL must be the approved HTTPS API endpoint') from None
        if (value.strip() != value or parsed.scheme != 'https'
                or parsed.hostname != 'api.groq.com'
                or parsed.username or parsed.password
                or port not in (None, 443)
                or parsed.path.rstrip('/') != '/openai/v1'
                or parsed.query or parsed.fragment):
            raise ValueError('Groq base URL must be the approved HTTPS API endpoint')
        return value.rstrip('/')

    # Validate environment before the schema accepts the value.
    @model_validator(mode='after')
    def validate_environment(self):
        if self.STRIPE_SANDBOX_ENABLED:
            key = self.STRIPE_TEST_SECRET_KEY.get_secret_value() if self.STRIPE_TEST_SECRET_KEY else ''
            hook = self.STRIPE_WEBHOOK_SECRET.get_secret_value() if self.STRIPE_WEBHOOK_SECRET else ''
            prices = [self.STRIPE_PRO_MONTH_PRICE, self.STRIPE_PRO_YEAR_PRICE,
                      self.STRIPE_BUSINESS_MONTH_PRICE, self.STRIPE_BUSINESS_YEAR_PRICE]
            origin = urlsplit(self.STRIPE_RETURN_ORIGIN)
            if (not key.startswith('sk_test_') or not hook.startswith('whsec_')
                    or len(set(prices)) != 4 or any(not p.startswith('price_') for p in prices)
                    or not self.STRIPE_PORTAL_CONFIGURATION.startswith('bpc_')
                    or self.STRIPE_RETURN_ORIGIN not in self.CORS_ALLOWED_ORIGINS
                    or origin.username or origin.password or origin.query or origin.fragment
                    or origin.path or not origin.hostname
                    or (origin.scheme != 'https' and not (self.APP_ENV == 'development'
                        and origin.scheme == 'http' and origin.hostname == '127.0.0.1'))):
                raise ValueError('Sandbox billing requires test credentials, four distinct prices, portal configuration and an approved return origin')
        if self.MYSQL_TLS_MODE == 'local_viva_required' and (
                self.APP_ENV != 'development'
                or self.MYSQL_HOST != '127.0.0.1'
                or self.MYSQL_PORT != 3306
                or self.MYSQL_DATABASE != 'lankapex_viva_db'
                or (self.MYSQL_SSL_CA is not None and self.MYSQL_SSL_CA != Path(r'C:\Program Files\LankaPex-TLS-Trust\ca.pem'))):
            raise ValueError('Local viva TLS requires the exact development loopback target and protected CA')
        if self.AI_ENABLED:
            secret = self.GROQ_API_KEY.get_secret_value().strip() if self.GROQ_API_KEY else ''
            lowered = secret.lower()
            placeholders = ('changeme', 'change-me', 'replace-me', 'replace_me',
                            'your-key', 'your_key', 'api-key', 'api_key', '<', '>')
            if (not secret or len(secret) < 20 or len(set(secret)) < 8
                    or lowered in {'password', 'secret', 'groq'}
                    or any(marker in lowered for marker in placeholders)):
                raise ValueError('AI requires a non-placeholder backend API credential')
        if self.APP_ENV == 'testing' and self.MYSQL_DATABASE != 'lankapex_test_db':
            raise ValueError('Testing requires lankapex_test_db')
        if self.APP_ENV == 'ai_snapshot_testing' and (
                self.MYSQL_DATABASE != 'lankapex_ai_snapshot_test_db'
                or self.MYSQL_USER != 'lankapex_ai_snap_runtime'):
            raise ValueError('AI snapshot testing requires its exact isolated database and runtime account')
        if self.APP_ENV == 'ai_snapshot_migration' and (
                self.MYSQL_DATABASE != 'lankapex_ai_snapshot_test_db'
                or self.MYSQL_USER != 'lankapex_ai_snap_migrator'):
            raise ValueError('AI snapshot migration requires its exact isolated database and migrator account')
        if self.APP_ENV == 'production':
            if self.RATE_LIMIT_MODE != 'external':
                raise ValueError('Production requires explicitly configured shared/edge rate-limit enforcement')
            required = {'MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE',
                        'JWT_SECRET_KEY', 'CORS_ALLOWED_ORIGINS', 'ALLOWED_HOSTS'}
            if not required.issubset(self.model_fields_set):
                raise ValueError('Production requires explicit database, JWT, CORS and host settings')
            for name in ('MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE', 'JWT_SECRET_KEY'):
                value = getattr(self, name).strip()
                if (not value or '<' in value or '>' in value
                        or value.lower() in {'password', 'secret', 'changeme', 'change-me', 'replace-me'}
                        or value.lower().startswith('replace_')):
                    raise ValueError('Production credentials must be nonempty and non-placeholder')
            if len(self.JWT_SECRET_KEY.encode()) < 32 or len(set(self.JWT_SECRET_KEY)) < 8:
                raise ValueError('Production JWT secret requires at least 32 bytes and must not be repetitive')
            if any(marker in self.JWT_SECRET_KEY.lower() for marker in (
                    'change-me', 'changeme', 'replace-me', 'replace_me',
                    'your-secret', 'your_secret', 'default-secret', 'default_secret')):
                raise ValueError('Production JWT secret must not be a placeholder')
            if self.APP_DEBUG or self.LOG_LEVEL == 'DEBUG':
                raise ValueError('Production debugging must be disabled')
            if self.MYSQL_DATABASE in {'lankapex_db', 'lankapex_test_db'}:
                raise ValueError('Production must not use local development or test databases')
            if local_host(self.MYSQL_HOST):
                raise ValueError('Production requires an explicit database host')
            if not self.CORS_ALLOWED_ORIGINS or not self.ALLOWED_HOSTS:
                raise ValueError('Production origins and hosts must not be empty')
            for origin in self.CORS_ALLOWED_ORIGINS:
                parsed = urlsplit(origin)
                if parsed.scheme != 'https' or local_host(parsed.hostname):
                    raise ValueError('Production CORS requires explicit HTTPS frontend origins')
            if any(local_host(host) or host.lower() == 'testserver' for host in self.ALLOWED_HOSTS):
                raise ValueError('Production hosts must not contain development hosts')
        if self.MYSQL_SSL_CA is not None and not self.MYSQL_SSL_CA.is_file():
            raise ValueError('MYSQL_SSL_CA must refer to an existing CA file')
        return self


# Load and validate settings before application services use them.
def load_settings(**kwargs):
    try:
        if isolated_browser_dotenv_disabled() or viva_runtime_dotenv_disabled():
            # Make the intent explicit for the application singleton in
            # addition to removing dotenv from all customized sources above.
            kwargs['_env_file'] = None
        return Settings(**kwargs)
    except (ValidationError, SettingsError, ValueError):
        # Validation exceptions may contain secret input/context. Never chain them.
        raise RuntimeError(
            'Invalid backend configuration. Check APP_ENV, MYSQL_*, JWT_SECRET_KEY, '
            'ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ALLOWED_ORIGINS, ALLOWED_HOSTS, APP_DEBUG '
            'and backend AI settings. '
            'Production requires explicit credentials, HTTPS origins, safe logging and RATE_LIMIT_MODE=external.'
        ) from None


settings = load_settings()
