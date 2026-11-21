"""Bounded process-local development throttling, not a distributed limiter."""
import hashlib
import hmac
import math
import threading
import time
from collections import OrderedDict

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm


class LocalLimiter:
    def __init__(self, window=60, capacity=4096, clock=time.monotonic):
        self.window, self.capacity, self.clock = window, capacity, clock
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.entries.clear()

    def consume(self, rules):
        """Atomically consume all scopes. Fail closed if bounded storage is full."""
        with self.lock:
            now = self.clock()
            while self.entries and next(iter(self.entries.values()))[0] <= now:
                self.entries.popitem(last=False)
            blocked = [self.entries[key][0] for key, limit in rules
                       if key in self.entries and self.entries[key][1] >= limit]
            if blocked:
                return max(1, math.ceil(max(blocked) - now))
            new_keys = {key for key, _ in rules if key not in self.entries}
            if len(self.entries) + len(new_keys) > self.capacity:
                expiry = next(iter(self.entries.values()))[0] if self.entries else now + self.window
                return max(1, math.ceil(expiry - now))
            for key, _ in rules:
                entry = self.entries.setdefault(key, [now + self.window, 0])
                entry[1] += 1
            return None


def configure_rate_limits(app, config):
    mode = getattr(config, 'RATE_LIMIT_MODE', 'external' if config.APP_ENV == 'production' else 'local')
    app.state.rate_limit_config = config
    app.state.rate_limiter = LocalLimiter(
        getattr(config, 'RATE_LIMIT_WINDOW_SECONDS', 60),
        getattr(config, 'RATE_LIMIT_MAX_KEYS', 4096)) if mode == 'local' else None


def _key(request, scope, identity):
    config = request.app.state.rate_limit_config
    secret = config.JWT_SECRET_KEY.encode()
    digest = hmac.new(secret, identity.encode(), hashlib.sha256).hexdigest()
    return (scope, digest)


def _consume(request, scopes):
    limiter = getattr(request.app.state, 'rate_limiter', None)
    if limiter is None:
        return  # Explicit external enforcement mode; no claim of in-app protection.
    retry = limiter.consume([(_key(request, scope, identity), limit) for scope, identity, limit in scopes])
    if retry:
        raise HTTPException(429, 'Too many requests. Please wait before retrying.',
                            headers={'Retry-After': str(retry)})


def peer(request):
    # Never parse X-Forwarded-For / Forwarded here. ASGI server proxy trust must
    # be configured narrowly by the operator; default deployment guidance disables it.
    return request.client.host if request.client else '<unknown-peer>'


def login_limit(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    if len(form.username) > 320 or len(form.password.encode()) > 1024:
        raise HTTPException(422, 'Login input exceeds the supported size')
    config = request.app.state.rate_limit_config
    ip = peer(request)
    _consume(request, [('login-ip', ip, config.RATE_LIMIT_LOGIN_IP),
                       ('login-account-ip', ip + '\0' + form.username.strip().lower(), config.RATE_LIMIT_LOGIN)])


def registration_limit(request: Request):
    config = request.app.state.rate_limit_config
    _consume(request, [('registration', peer(request), config.RATE_LIMIT_REGISTRATION)])


def authenticated_limit(request, user_id):
    if request is None or not hasattr(request.app.state, 'rate_limit_config'):
        return
    route = getattr(request.scope.get('route'), 'path', '')
    config = request.app.state.rate_limit_config
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        _consume(request, [('write:' + route, str(user_id), config.RATE_LIMIT_MUTATION)])
    elif route.endswith(('/statement', '/statement.pdf', '/admin/audit-events')):
        _consume(request, [('export', str(user_id), config.RATE_LIMIT_EXPORT)])


def customer_link_limit(request, user_id):
    """Bound online guesses of six-digit account-link codes per account and peer."""
    if request is None or not hasattr(request.app.state, 'rate_limit_config'):
        return
    _consume(request, [('customer-link-user', str(user_id), 5),
                       ('customer-link-peer', peer(request), 20)])


def ai_generation_limit(request, user_id, business_id, limit_multiplier=1):
    """Bound expensive AI generation per authenticated owner and business."""
    if request is None or not hasattr(request.app.state, 'rate_limit_config'):
        return
    limit = request.app.state.rate_limit_config.RATE_LIMIT_AI_GENERATION * limit_multiplier
    _consume(request, [('ai-generation-user', str(user_id), limit),
                       ('ai-generation-business', str(business_id), limit)])
