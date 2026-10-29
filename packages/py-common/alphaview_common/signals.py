import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Signal:
    source: str
    external_id: str
    url: str
    title: str
    text: str
    created_at: datetime
    engagement: int = 0
    comments: int = 0
    answered: bool | None = None
    sentiment: float = 0.0
    intent: str = "discussion"
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = hashlib.sha1(f"{self.source}:{self.external_id}".encode()).hexdigest()

    @property
    def content(self) -> str:
        return f"{self.title}\n{self.text}".strip()
