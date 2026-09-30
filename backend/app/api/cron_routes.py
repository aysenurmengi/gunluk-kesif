"""Vercel Cron: günün seçkisini hazırla ve eksik konuları tamamla.

Vercel isteğe `Authorization: Bearer <CRON_SECRET>` ekler. Parola tanımlı değilse
veya eşleşmezse istek reddedilir; böylece dışarıdan kaynak okutma tetiklenemez.
"""
import hmac
import os

from fastapi import APIRouter, HTTPException, Request, Response

from ..services.daily import CollectionUnavailable, get_daily, today

router = APIRouter(prefix="/api/cron", tags=["Zamanlanmış görevler"], include_in_schema=False)


@router.get("/daily")
def daily(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    secret = os.environ.get("CRON_SECRET", "")
    supplied = request.headers.get("authorization", "")
    if len(secret) < 16 or not hmac.compare_digest(supplied.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(401, detail={"message": "Yetkisiz."})
    try:
        # Seçki yoksa oluşturur; eksik konu varsa 15 dakika kuralıyla yeniden dener.
        edition = get_daily(today(), wait_for_refresh=True)
    except CollectionUnavailable as error:
        raise HTTPException(503, detail={"message": str(error)}) from error
    return {"date": edition["date"], "items": len(edition["items"]),
            "topic_shortfalls": edition.get("topic_shortfalls", {}),
            "generated_at": edition.get("generated_at")}
