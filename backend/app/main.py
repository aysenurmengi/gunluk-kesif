"""API ve frontend'i aynı yerel uygulamada sun."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.daily_routes import router as daily_router
from .api.account_routes import router as account_router


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app = FastAPI(title="Günlük Keşif API", version="0.1.0")
# Yalnızca kendi dosyalarımız çalışır; sayfa başka bir sitenin çerçevesine gömülemez.
# HTML'deki style="--delay:…" öznitelikleri için satır içi stile izin verilir.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def security(request, call_next):
    path = request.url.path
    # Başka bir siteden gönderilen değiştirici istekler oturum çerezini kullanamasın.
    origin = request.headers.get("origin")
    if request.method in UNSAFE_METHODS and path.startswith("/api/") and (
        request.headers.get("sec-fetch-site") == "cross-site"
        or (origin and origin != f"{request.url.scheme}://{request.headers.get('host', '')}")
    ):
        return JSONResponse({"detail": {"message": "Bu istek başka bir siteden geldiği için reddedildi."}}, 403)
    response = await call_next(request)
    if path in {"/", "/index.html"} or path.startswith(("/js/", "/css/")):
        response.headers["Cache-Control"] = "no-cache"
    response.headers.update(SECURITY_HEADERS)
    # /docs sayfası FastAPI'nin CDN'den yüklediği dosyaları kullanır.
    if not path.startswith(("/docs", "/redoc")):
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    return response


app.include_router(daily_router)
app.include_router(account_router)
# Statik frontend en son eklenir; /api ve /docs yollarını gölgelemez.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
