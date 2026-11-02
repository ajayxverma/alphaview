import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin, urlsplit

import aiohttp
import httpx
from temporalio import activity
from trafilatura import extract, load_html

from alphaview_common.security import create_token
from alphaview_crawler.web_pages import PageFetcher, PublicResolver, RequestPermitDenied, checked_url, paywall_flag


def reference_document(body: bytes, url: str, options: dict) -> dict | None:
    tree = load_html(body)
    if tree is None:
        return None
    page_title = " ".join(tree.xpath("//title/text()"))
    if tree.xpath('//input[@type="password"]') or re.search(r"^\s*(sign in|log in|access denied|verify you are human|captcha)\b", page_title, re.I):
        return None
    for script in tree.xpath('//script[@type="application/ld+json"]'):
        try:
            if paywall_flag(json.loads(script.text or "null")):
                return None
        except (ValueError, RecursionError):
            continue
    result = extract(tree, url=url, output_format="json", with_metadata=True, include_comments=False, favor_precision=True)
    if not result:
        return None
    data = json.loads(result)
    text = data.get("text") or ""
    if len(text) < 100:
        return None
    title = data.get("title") or url
    hint = f"{urlsplit(url).path} {title}".lower()
    document_type = "pricing" if re.search(r"pricing|plans|subscription", hint) else "documentation" if re.search(r"docs|documentation|guide", hint) else "product" if re.search(r"product|features", hint) else "article"
    published = None
    if data.get("date"):
        try:
            published = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            if published > datetime.now(UTC):
                published = None
        except ValueError:
            pass
    if document_type == "article" and published:
        date = published.date().isoformat()
        if options.get("date_from") and date < options["date_from"] or options.get("date_to") and date > options["date_to"]:
            return None
    canonical = None
    for href in tree.xpath('//link[@rel="canonical"]/@href')[:1]:
        try:
            candidate = checked_url(urljoin(url, href))
            if urlsplit(candidate).hostname == urlsplit(url).hostname:
                canonical = candidate
        except ValueError:
            pass
    tables = [[[" ".join(cell.itertext())[:200] for cell in row.xpath("./th|./td")[:10]]
               for row in table.xpath(".//tr")[:20]] for table in tree.xpath("//table")[:10]]
    links = []
    for href in tree.xpath('//a/@href'):
        try:
            link = checked_url(urljoin(url, href))
            if urlsplit(link).hostname == urlsplit(url).hostname and re.search(r"pricing|docs|plans|features|comparison", urlsplit(link).path):
                links.append(link)
        except ValueError:
            continue
    return {"requested_url": url, "final_url": url, "canonical_url": canonical, "title": title[:500], "source": "web",
            "document_type": document_type, "text": text[:64000], "truncated": len(text) > 64000,
            "language": options.get("language", "en"), "published_at": published.isoformat() if published else None,
            "retrieved_at": datetime.now(UTC).isoformat(), "tables": tables, "extraction_method": "trafilatura_static",
            "provenance": {"links": list(dict.fromkeys(links))[:5], "language_filter": "requested_not_verified"}}


async def deep_read(operation_id: str, run_id: str, workspace_id: str, url: str, options: dict, ingest_url: str) -> dict:
    token = create_token(uuid.UUID(workspace_id), purpose="research_ingest", ttl=timedelta(minutes=5), ws=workspace_id, run=run_id, operation=operation_id)
    headers = {"Authorization": f"Bearer {token}"}
    outcomes = []

    class ReferenceFetcher(PageFetcher):
        def extract_document(self, body, final_url, since):
            return reference_document(body, final_url, options)

    async with httpx.AsyncClient(base_url=ingest_url, headers=headers, timeout=20) as storage:
        request_index = 0

        async def permit(request_url):
            nonlocal request_index
            request_index += 1
            activity.heartbeat({"requests": request_index})
            response = await storage.post("/research/internal/request", json={"index": request_index, "url": request_url})
            response.raise_for_status()
            if not response.json()["allowed"]:
                raise RequestPermitDenied("Request budget or cancellation reached")

        connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False, limit=2)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20),
                                        headers={"User-Agent": "alphaview-bot/0.1"}, trust_env=False) as session:
            fetcher = ReferenceFetcher(session, "alphaview-bot/0.1", outcomes)
            fetcher.request_permit = permit
            document = await fetcher.fetch(url, datetime(2000, 1, 1, tzinfo=UTC))
        if document is None:
            return {"outcome": outcomes[-1]["outcome"] if outcomes else "failed",
                    "detail": outcomes[-1]["detail"] if outcomes else "Read interrupted", "document_id": None}
        document["requested_url"] = url
        response = await storage.post("/research/internal/document", json=document)
        response.raise_for_status()
        return {"outcome": response.json()["outcome"], "document_id": response.json()["document_id"], "detail": "Reference document stored"}