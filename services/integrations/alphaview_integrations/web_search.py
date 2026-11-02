import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from temporalio.exceptions import ApplicationError

from alphaview_common.geo import place_name
from alphaview_common.security import create_token, decrypt_json
from alphaview_common.settings import get_common_settings
from alphaview_integrations.models import Connection, SessionLocal

MAX_WEB_URLS = 15


async def deep_search(workspace_id: str, question: dict, options: dict, geo: dict | None, operation_id: str, run_id: str) -> dict:
    async with SessionLocal() as session:
        connection = await session.scalar(select(Connection).where(
            Connection.workspace_id == uuid.UUID(workspace_id), Connection.status == "active",
            Connection.provider.in_(["serpapi", "dataforseo"]),
        ).order_by(Connection.created_at).limit(1))
        if connection is None:
            return {"outcome": "unsupported", "detail": "Deep search requires an active SerpApi or DataForSEO connection", "candidates": []}
        token = create_token(uuid.UUID(workspace_id), purpose="research_ingest", ttl=timedelta(minutes=5),
                             ws=workspace_id, run=run_id, operation=operation_id)
        async with httpx.AsyncClient(base_url=get_common_settings().research_ingest_url, timeout=20,
                                    headers={"Authorization": f"Bearer {token}"}) as storage:
            permit = await storage.post("/research/internal/request", json={"index": 1,
                "url": "https://serpapi.com/search.json" if connection.provider == "serpapi" else "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"})
            permit.raise_for_status()
            if not permit.json()["allowed"]:
                return {"outcome": "budget_limited", "detail": "Search request denied by budget, deadline or cancellation", "candidates": []}
        creds = decrypt_json(connection.encrypted_credentials)
        query = question["query"]
        excluded = " ".join(f"-site:{domain}" for domain in options.get("excluded_domains", []))
        query = f"{query} {excluded}".strip()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if connection.provider == "serpapi":
                    params = {"engine": "google", "q": query, "num": 10, "api_key": creds["api_key"], "hl": options.get("language", "en")}
                    if geo and geo.get("country_code"):
                        params["gl"] = geo["country_code"].lower()
                        params["location"] = geo["label"]
                    if options.get("date_from") or options.get("date_to"):
                        params["tbs"] = "cdr:1" + (f",cd_min:{options['date_from']}" if options.get("date_from") else "") + (f",cd_max:{options['date_to']}" if options.get("date_to") else "")
                    response = await client.get("https://serpapi.com/search.json", params=params)
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("error"):
                        raise ValueError("Provider rejected search")
                    results = [{"url": item.get("link", ""), "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""), "position": item.get("position", index + 1)}
                               for index, item in enumerate(payload.get("organic_results", []))]
                else:
                    task = {"keyword": query, "language_code": options.get("language", "en"), "depth": 10}
                    if geo and "lat" in geo:
                        task["location_coordinate"] = f"{geo['lat']},{geo['lon']}"
                    else:
                        task["location_code"] = int(connection.config.get("location_code") or 2840)
                    date_terms = (f" after:{options['date_from']}" if options.get("date_from") else "") + (f" before:{options['date_to']}" if options.get("date_to") else "")
                    task["keyword"] += date_terms
                    response = await client.post("https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
                        auth=httpx.BasicAuth(creds["login"], creds["password"]), json=[task])
                    response.raise_for_status()
                    payload = response.json()
                    tasks = payload.get("tasks") or []
                    if not tasks or any(item.get("status_code") != 20000 for item in tasks):
                        raise ValueError("Provider rejected search")
                    results = [{"url": item.get("url", ""), "title": item.get("title", ""), "snippet": item.get("description", ""),
                                "position": item.get("rank_absolute")} for result_task in tasks for result in result_task.get("result") or []
                               for item in result.get("items") or [] if item.get("type") == "organic"]
            candidates = []
            for item in results[:10]:
                url = normalize_url(item["url"])
                if url:
                    candidates.append({"url": url, "title": str(item["title"])[:300], "snippet": str(item["snippet"])[:600],
                        "position": item["position"], "provider": connection.provider, "query": query,
                        "question_id": question["id"], "retrieved_at": datetime.now(UTC).isoformat()})
            return {"outcome": "fetched", "detail": "Search results are discovery hints, not verified evidence", "candidates": candidates}
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            outcome = "rate_limited" if status == 429 else "blocked" if status in (401, 403) else "failed"
            return {"outcome": outcome, "detail": f"Search failed ({type(exc).__name__})", "candidates": []}


def search_queries(query: str, geo: dict | None) -> list[str]:
    place = place_name(geo)
    theme = f"{query} {place}" if place else query
    return [f'{theme} "frustrated"', f'{theme} "alternative to"', f'{theme} "wish"']


def normalize_url(url: str) -> str | None:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.port not in (None, 443):
            return None
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    except ValueError:
        return None


async def search_urls(client: httpx.AsyncClient, provider: str, creds: dict, config: dict, query: str, geo: dict | None) -> list[str]:
    found: dict[str, None] = {}
    for term in search_queries(query, geo):
        if provider == "serpapi":
            params = {"engine": "google", "q": term, "num": 10, "api_key": creds["api_key"]}
            if geo and geo.get("country_code"):
                params["gl"] = geo["country_code"].lower()
                if geo.get("label"):
                    params["location"] = geo["label"]
            response = await client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise ValueError("Search provider rejected the search")
            links = [item.get("link", "") for item in payload.get("organic_results", [])]
        else:
            task = {"keyword": term, "language_code": "en", "depth": 10}
            if geo and "lat" in geo and "lon" in geo:
                task["location_coordinate"] = f"{geo['lat']},{geo['lon']}"
            else:
                task["location_code"] = int(config.get("location_code") or 2840)
            response = await client.post(
                "https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
                auth=httpx.BasicAuth(creds["login"], creds["password"]), json=[task],
            )
            response.raise_for_status()
            payload = response.json()
            tasks = payload.get("tasks") or []
            if payload.get("status_code") != 20000 or not tasks or any(item.get("status_code") != 20000 for item in tasks):
                raise ValueError("Search provider rejected the search")
            links = [item.get("url", "") for item_task in tasks for result in item_task.get("result") or []
                     for item in result.get("items") or [] if item.get("type") == "organic"]
        for link in links:
            normalized = normalize_url(link)
            if normalized:
                found.setdefault(normalized, None)
        if len(found) >= MAX_WEB_URLS:
            break
    return list(found)[:MAX_WEB_URLS]


async def discover_web_urls(workspace_id: str, query: str, geo: dict | None) -> list[str]:
    async with SessionLocal() as session:
        connections = list(await session.scalars(
            select(Connection).where(
                Connection.workspace_id == uuid.UUID(workspace_id), Connection.status == "active",
                Connection.provider.in_(["serpapi", "dataforseo"]),
            ).order_by(Connection.created_at)
        ))
        if not connections:
            raise ApplicationError(
                "Web & Blogs requires an active SerpApi or DataForSEO connection in Integrations.",
                non_retryable=True,
            )
        async with httpx.AsyncClient(timeout=30) as client:
            for connection in connections:
                try:
                    return await search_urls(client, connection.provider, decrypt_json(connection.encrypted_credentials),
                                             connection.config, query, geo)
                except (httpx.HTTPError, ValueError, KeyError):
                    continue
        raise ApplicationError("Web search failed. Test your SerpApi or DataForSEO connection and check its quota.",
                               non_retryable=True)