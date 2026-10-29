import re
from datetime import UTC, datetime
from html import unescape

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import SourceAdapter

_TAGS = re.compile(r"<[^>]+>")
SITES = ["stackoverflow", "softwarerecs", "webapps", "superuser"]


class StackExchangeAdapter(SourceAdapter):
    """Unanswered questions are a direct proxy for missing supply."""

    id = "stackexchange"
    name = "Stack Exchange"

    async def search(self, client, query, since):
        out: list[Signal] = []
        for site in SITES:
            resp = await client.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params={
                    "order": "desc",
                    "sort": "relevance",
                    "q": query,
                    "site": site,
                    "pagesize": 50,
                    "fromdate": int(since.timestamp()),
                    "filter": "withbody",
                },
            )
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                out.append(
                    Signal(
                        source=self.id,
                        external_id=f"{site}:{item.get('question_id')}",
                        url=item.get("link", ""),
                        title=unescape(item.get("title", "")),
                        text=unescape(_TAGS.sub(" ", item.get("body", "")))[:4000],
                        created_at=datetime.fromtimestamp(item.get("creation_date", 0), tz=UTC),
                        engagement=int(item.get("score") or 0) + int(item.get("view_count") or 0) // 100,
                        comments=int(item.get("answer_count") or 0),
                        answered=bool(item.get("is_answered")),
                    )
                )
        return out
