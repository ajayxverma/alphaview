import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FieldSpec(BaseModel):
    key: str
    label: str
    secret: bool = False
    required: bool = True
    help: str | None = None


class ConnectorOut(BaseModel):
    id: str
    name: str
    description: str
    auth_type: str
    capabilities: list[str]
    credential_fields: list[FieldSpec]
    config_fields: list[FieldSpec]
    available: bool


class ConnectionCreate(BaseModel):
    provider: str
    label: str = Field(min_length=1, max_length=120)
    credentials: dict[str, str] = Field(default_factory=dict)
    config: dict[str, str] = Field(default_factory=dict)


class OAuthStartIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    config: dict[str, str] = Field(default_factory=dict)


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    label: str
    config: dict[str, Any]
    status: str
    last_error: str | None
    created_at: datetime


class ConnectionQueryIn(BaseModel):
    keywords: list[str] = Field(min_length=1, max_length=20)
