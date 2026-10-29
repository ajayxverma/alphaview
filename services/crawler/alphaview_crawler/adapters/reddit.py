from datetime import UTC, datetime

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import SourceAdapter


class RedditAdapter(SourceAdapter):
    id = "reddit"
    name = "Reddit"

    async def search(self, client, query, since):
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "relevance", "t": "year", "limit": 100, "type": "link"},
        )
        resp.raise_for_status()
        out: list[Signal] = []
        for child in resp.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=UTC)
            if created < since:
                continue
            out.append(
                Signal(
                    source=self.id,
                    external_id=d.get("id", ""),
                    url=f"https://www.reddit.com{d.get('permalink', '')}",
                    title=d.get("title", ""),
                    text=(d.get("selftext") or "")[:4000],
                    created_at=created,
                    engagement=int(d.get("score") or 0),
                    comments=int(d.get("num_comments") or 0),
                )
            )
        return out
