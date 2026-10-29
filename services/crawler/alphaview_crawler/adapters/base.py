from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

import httpx

from alphaview_common.signals import Signal

# Query expansions that surface demand-side language (wishes, complaints, alternative seeking).
INTENT_EXPANSIONS = ["", "is there a tool", "alternative to", "frustrated with", "I wish"]


class SourceAdapter(ABC):
    id: ClassVar[str]
    name: ClassVar[str]

    @abstractmethod
    async def search(self, client: httpx.AsyncClient, query: str, since: datetime) -> list[Signal]: ...
