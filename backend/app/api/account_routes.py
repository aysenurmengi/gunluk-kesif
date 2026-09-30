"""Hesap açma, giriş/çıkış ve giriş yapmış kullanıcının kaydettikleri."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..services import auth

router = APIRouter(prefix="/api", tags=["Hesap ve kaydedilenler"])


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class SaveRequest(BaseModel):
    item: dict


class ImportRequest(BaseModel):
    items: list[dict] = Field(max_length=500)


def _error(error: auth.AuthError):
    return HTTPException(error.status, detail={"message": str(error)})


def _set_session(request: Request, response: Response, token: str):
    response.set_cookie(
        auth.SESSION_COOKIE, token, max_age=int(auth.SESSION_LIFETIME.total_seconds()),
        httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/")


def _no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


def current_user(request: Request, response: Response):
    _no_store(response)
    user = auth.session_user(request.cookies.get(auth.SESSION_COOKIE))
    if user is None:
        raise HTTPException(401, detail={"message": "Bu işlem için giriş yapmalısın."},
                            headers={"Cache-Control": "no-store"})
    return user


@router.post("/auth/register", status_code=201)
def register(credentials: Credentials, request: Request, response: Response):
    try:
        client = request.client.host if request.client else ""
        user, token = auth.register(credentials.email, credentials.password, client)
    except auth.AuthError as error:
        raise _error(error) from error
    _set_session(request, response, token)
    _no_store(response)
    return {"user": user}


@router.post("/auth/login")
def login(credentials: Credentials, request: Request, response: Response):
    client = request.client.host if request.client else ""
    try:
        user, token = auth.login(credentials.email, credentials.password, client)
    except auth.AuthError as error:
        raise _error(error) from error
    _set_session(request, response, token)
    _no_store(response)
    return {"user": user}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(auth.SESSION_COOKIE))
    response.delete_cookie(auth.SESSION_COOKIE, path="/", httponly=True, samesite="lax")


@router.get("/auth/me")
def me(request: Request, response: Response):
    """Giriş yapılmamışsa user null döner; anonim ziyaret bir hata değildir."""
    _no_store(response)
    return {"user": auth.session_user(request.cookies.get(auth.SESSION_COOKIE))}


@router.get("/saved")
def saved(user=Depends(current_user)):
    return {"items": auth.list_saved(user)}


@router.put("/saved")
def save(body: SaveRequest, user=Depends(current_user)):
    try:
        auth.save(user, [auth.clean_saved_item(body.item)])
    except auth.AuthError as error:
        raise _error(error) from error
    return {"items": auth.list_saved(user)}


@router.post("/saved/import")
def import_saved(body: ImportRequest, user=Depends(current_user)):
    """Giriş öncesi bu tarayıcıda tutulan eski kayıtları hesaba aktar."""
    skipped = auth.save(user, body.items)
    return {"items": auth.list_saved(user), "skipped": skipped}


@router.delete("/saved", status_code=204)
def remove(url: str, user=Depends(current_user)):
    auth.remove(user, url)
