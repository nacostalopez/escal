"""Shared rate limiter (slowapi/limits), keyed by client IP.

Import `limiter` and decorate a route with `@limiter.limit("N/period")` to
apply a stricter-than-default limit (e.g. auth and webhook endpoints).
Every other route is still covered by `default_limits` via the
SlowAPIMiddleware registered in main.py.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
