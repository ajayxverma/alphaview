import re
from datetime import UTC, datetime
from html import unescape

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import SourceAdapter

_TAGS = re.compile(r"<[^>]+>")


class HackerNewsAdapter(SourceAdapter):
    id = "hackernews"
    name = "Hacker News"

    async def search(self, client, query, since):
        resp = await client.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": query,
                "tags": "(story,comment)",
                "hitsPerPage": 100,
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
            },
        )
        resp.raise_for_status()
        out: list[Signal] = []
        for h in resp.json().get("hits", []):
            body = h.get("story_text") or h.get("comment_text") or ""
            out.append(
                Signal(
                    source=self.id,
                    external_id=str(h.get("objectID")),
                    url=f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                    title=h.get("title") or h.get("story_title") or "",
                    text=unescape(_TAGS.sub(" ", body))[:4000],
                    created_at=datetime.fromtimestamp(h.get("created_at_i", 0), tz=UTC),
                    engagement=int(h.get("points") or 0),
                    comments=int(h.get("num_comments") or 0),
                )
            )
        return out
