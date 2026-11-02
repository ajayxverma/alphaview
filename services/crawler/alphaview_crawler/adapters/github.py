from datetime import datetime

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import SourceAdapter


class GitHubAdapter(SourceAdapter):
    id = "github"
    name = "GitHub Issues"

    async def search(self, client, query, since):
        response = await client.get(
            "https://api.github.com/search/issues",
            params={
                "q": f"{query} is:issue is:public created:>={since.date().isoformat()}",
                "sort": "created", "order": "desc", "per_page": 50,
            },
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        response.raise_for_status()
        signals: list[Signal] = []
        for issue in response.json().get("items", []):
            if "pull_request" in issue:
                continue
            created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
            if created < since:
                continue
            signals.append(Signal(
                source=self.id,
                external_id=str(issue["id"]),
                url=issue["html_url"],
                title=issue.get("title", ""),
                text=(issue.get("body") or "")[:4000],
                created_at=created,
                engagement=int((issue.get("reactions") or {}).get("total_count") or 0),
                comments=int(issue.get("comments") or 0),
            ))
        return signals