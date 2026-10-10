import logging
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .ratelimit import client_ip, login_ip_failures, login_user_failures
from .security import DUMMY_HASH, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("stockwatcher.auth")


class LoginIn(BaseModel):
    # length caps stop absurdly long inputs from reaching the password hasher
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Not logged in")
    return user


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    username, ip = body.username.strip().lower(), client_ip(request)

    wait = max(login_user_failures.blocked(username), login_ip_failures.blocked(ip))
    if wait > 0:
        minutes = max(1, ceil(wait / 60))
        raise HTTPException(429, f"Too many failed login attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
                            headers={"Retry-After": str(ceil(wait))})

    user = db.scalar(select(User).where(User.username == username))
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if user is None or not ok:
        login_user_failures.record(username)
        login_ip_failures.record(ip)
        log.warning("failed login for %r from %s", username[:50], ip)
        raise HTTPException(401, "Incorrect username or password")

    login_user_failures.clear(username)
    request.session.clear()
    request.session["user_id"] = user.id
    return {"username": user.username}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.get(User, uid) if uid else None
    return {"username": user.username if user else None}
