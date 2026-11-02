import re
from datetime import datetime

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import INTENT_EXPANSIONS, SourceAdapter


class DevCommunityAdapter(SourceAdapter):
    id = "devto"
    name = "DEV Community"

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
            "https://dev.to/api/articles",
            params={"tag": terms[0], "per_page": 100},
        )
        response.raise_for_status()
        signals: list[Signal] = []
        for article in response.json():
            timestamp = article.get("published_at")
            if not timestamp:
                continue
            created = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            title = article.get("title") or ""
            description = article.get("description") or ""
            searchable = f"{title} {description} {' '.join(article.get('tag_list') or [])}".lower()
            if created < since or not all(term in searchable for term in terms):
                continue
            signals.append(Signal(
                source=self.id,
                external_id=str(article["id"]),
                url=article["url"],
                title=title,
                text=description[:4000],
                created_at=created,
                engagement=int(article.get("public_reactions_count") or 0),
                comments=int(article.get("comments_count") or 0),
            ))
        return signals