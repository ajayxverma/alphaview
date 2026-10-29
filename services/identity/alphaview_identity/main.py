import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphaview_common import ratelimit
from alphaview_common.auth import Principal, get_principal
from alphaview_common.db import init_schema
from alphaview_common.security import create_token, hash_password, verify_password
from alphaview_common.web import create_app
from alphaview_identity.models import SCHEMA, Base, Membership, User, Workspace, engine, get_db


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str
    workspace_id: uuid.UUID | None = None


@asynccontextmanager
async def lifespan(_app):
    await init_schema(engine, Base, SCHEMA)
    yield


app = create_app("identity", lifespan)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _token(user_id: uuid.UUID, workspace_id: uuid.UUID) -> TokenOut:
    return TokenOut(access_token=create_token(user_id, ws=str(workspace_id)))


@app.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenOut:
    await ratelimit.enforce(f"register:{_ip(request)}", limit=10, window_seconds=3600)
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    workspace = Workspace(name=f"{body.name.strip()}'s workspace")
    db.add_all([user, workspace])
    await db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
    await db.commit()
    return _token(user.id, workspace.id)


@app.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenOut:
    email = body.email.lower()
    await ratelimit.enforce(f"login:{_ip(request)}:{email}", limit=10, window_seconds=900)
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    workspace_id = await db.scalar(
        select(Membership.workspace_id).where(Membership.user_id == user.id).order_by(Membership.created_at).limit(1)
    )
    if workspace_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no workspace")
    return _token(user.id, workspace_id)


@app.get("/auth/me", response_model=UserOut)
async def me(principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)) -> UserOut:
    user = await db.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return UserOut(id=user.id, email=user.email, name=user.name, workspace_id=principal.workspace_id)
