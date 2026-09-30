"""Günlük Keşif API ve arayüzünü tek komutla başlat."""

try:
    import uvicorn
except ModuleNotFoundError:
    raise SystemExit(
        "Önce backend/requirements.txt paketlerini kur ve "
        r".\.venv\Scripts\python.exe serve.py komutunu kullan."
    ) from None


if __name__ == "__main__":
    from backend.app.repositories.database import DATABASE, describe
    print("Günlük Keşif: http://127.0.0.1:8000", flush=True)
    print(f"Veritabanı: {describe(DATABASE)}", flush=True)
    print("API belgeleri: http://127.0.0.1:8000/docs", flush=True)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000)
