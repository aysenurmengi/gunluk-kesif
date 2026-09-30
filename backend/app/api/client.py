"""İsteği yapan tarayıcının adresi ve protokolü.

Vercel'de uygulama bir vekil sunucunun arkasındadır: tarayıcı HTTPS kullanır,
fonksiyona gelen istek ise iç ağdan gelir. Gerçek değerler X-Forwarded-* ve
X-Real-IP başlıklarındadır. Vercel bu başlıkları kendisi yazar; yerelde ise
herkes uydurabileceği için yalnızca Vercel'de dikkate alınır.
"""
from fastapi import Request

from ..config import running_on_vercel


def _forwarded(request: Request, name: str):
    if not running_on_vercel():
        return None
    value = request.headers.get(name)
    return value.split(",")[0].strip() if value else None


def scheme(request: Request) -> str:
    return _forwarded(request, "x-forwarded-proto") or request.url.scheme


def host(request: Request) -> str:
    return _forwarded(request, "x-forwarded-host") or request.headers.get("host", "")


def origin(request: Request) -> str:
    return f"{scheme(request)}://{host(request)}"


def ip(request: Request) -> str:
    return (_forwarded(request, "x-real-ip") or _forwarded(request, "x-forwarded-for")
            or (request.client.host if request.client else ""))
