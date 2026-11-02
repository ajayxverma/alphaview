import re
from datetime import datetime
from html.parser import HTMLParser

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import INTENT_EXPANSIONS, SourceAdapter


class PostTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag, attrs) -> None:
        if tag in ("p", "br"):
            self.parts.append(" ")


class MastodonAdapter(SourceAdapter):
    id = "mastodon"
    name = "Mastodon (mastodon.social)"

    async def search(self, client, query, since):
        theme = query
        for expansion in INTENT_EXPANSIONS:
            if expansion and theme.endswith(f" {expansion}"):
                theme = theme[: -(len(expansion) + 1)]
                break
        terms = re.findall(r"[a-z0-9]+", theme.lower())
        if not terms:
            return []
        response = await client.get(
            f"https://mastodon.social/api/v1/timelines/tag/{terms[0]}",
            params={"limit": 40},
        )
        response.raise_for_status()
        signals: list[Signal] = []
        for post in response.json():
            if post.get("visibility") != "public" or not post.get("url"):
                continue
            created = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
            parser = PostTextParser()
            parser.feed(post.get("content") or "")
            text = " ".join("".join(parser.parts).split())
            if created < since or not text or not all(term in text.lower() for term in terms):
                continue
            signals.append(Signal(
                source=self.id,
                external_id=post.get("uri") or post["url"],
                url=post["url"],
                title=text[:200],
                text=text[:4000],
                created_at=created,
                engagement=int(post.get("favourites_count") or 0) + int(post.get("reblogs_count") or 0),
                comments=int(post.get("replies_count") or 0),
            ))
        return signals