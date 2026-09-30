"""Bugünün seçkisi ve yalnızca gerçekten kaydedilmiş günlerin arşivi."""
from datetime import date
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from ..models import ContentItem, Source
from ..repositories import daily as repository, database
from ..services.daily import get_daily, today, CollectionUnavailable

router = APIRouter(prefix="/api", tags=["Günlük seçki"])

class DailyResponse(BaseModel):
    date: date
    items: list[ContentItem]
    sources: list[Source]
    errors: dict[str, str]
    generated_at: str
    available_dates: list[date]
    today: date
    supported_topics: list[str] | None = None
    policy_version: int = 1
    topic_shortfalls: dict[str, int] = Field(default_factory=dict)

@router.get("/recommendations", response_model=DailyResponse)
def recommendations(response: Response, day: date | None = None):
    current = today()
    requested = day or current
    if requested > current:
        raise HTTPException(400, detail={"message": "Gelecek günler için öneri oluşturulmaz."})
    try:
        # Eksik konuları tamamlama isteği bekletmez; mevcut kartlar hemen döner.
        payload = get_daily(requested, database.DATABASE, wait_for_refresh=False)
    except CollectionUnavailable as error:
        raise HTTPException(503, detail={"message": str(error)}) from error
    if payload is None:
        raise HTTPException(404, detail={"message": "Bu tarihte kaydedilmiş bir seçki yok."})
    with repository.connect(database.DATABASE) as db:
        dates = repository.list_dates(db)
    response.headers["Cache-Control"] = "no-store"
    return {**payload, "available_dates": dates, "today": current}
