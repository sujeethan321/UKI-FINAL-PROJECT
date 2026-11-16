"""Run from backend root. No reload, migrations, proxy trust or raw access logs."""
import os
import sys
from pathlib import Path


def runtime_options(environment):
    if environment.get('APP_ENV') != 'production':
        raise ValueError('Production launcher requires APP_ENV=production')
    value = environment.get('PORT', '')
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise ValueError('Production launcher requires a valid platform PORT')
    return dict(host='0.0.0.0', port=int(value), reload=False, proxy_headers=False,
                access_log=False, log_level='info')


def main():
    try:
        options = runtime_options(os.environ)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app.core.config import settings
        if settings.APP_ENV != 'production':
            raise ValueError('Production environment selection is inconsistent')
    except (ValueError, RuntimeError):
        print('Production startup rejected: check APP_ENV, PORT and documented backend settings.', file=sys.stderr)
        return 1
    import uvicorn
    uvicorn.run('app.main:app', **options)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
