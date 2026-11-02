import hashlib
import re
from urllib.parse import urlsplit

from alphaview_common.research import QUESTIONS


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9.+-]*", text.lower())) - {"the", "and", "for", "with", "a", "of", "to", "in"}


def plan_questions(query: str, geo: dict | None = None) -> list[dict]:
    place = f" {geo['label']}" if geo else ""
    suffixes = {
        "problems": "workflow problems challenges",
        "solutions": "products solutions official documentation",
        "buying": "pricing plans switching costs",
        "experience": "customer review experience",
        "context": "market statistics report study",
        "counter": "successful solution satisfied customers",
    }
    return [{"id": key, "question": question, "query": f"{query}{place} {suffixes[key]}",
             "planner": "deterministic"} for key, question in QUESTIONS.items()]


def lexical_score(query: str, text: str) -> float:
    query_terms = terms(query)
    return len(query_terms & terms(text)) / max(1, len(query_terms))


def rank_documents(query: str, documents: list[dict], preferred: list[str] | None = None) -> list[dict]:
    preferred = preferred or []
    return sorted(documents, key=lambda document: (
        lexical_score(query, document.get("title", "") + " " + document.get("text", "")),
        urlsplit(document["url"]).hostname in preferred,
    ), reverse=True)


def passages(text: str, size: int = 1400, overlap: int = 200) -> list[dict]:
    result = []
    for offset in range(0, len(text), size - overlap):
        passage = text[offset:offset + size]
        if passage.strip():
            result.append({"key": hashlib.sha256(f"{offset}:{passage}".encode()).hexdigest(),
                           "text": passage, "offset": offset})
    return result


def near_duplicate(left: str, right: str) -> bool:
    if left == right:
        return True
    left_words, right_words = left.lower().split(), right.lower().split()
    if min(len(left_words), len(right_words)) < 100:
        return False
    if min(len(left_words), len(right_words)) / max(len(left_words), len(right_words)) < 0.9:
        return False
    if set(re.findall(r"\d+(?:\.\d+)?", left)) != set(re.findall(r"\d+(?:\.\d+)?", right)):
        return False
    def shingles(words):
        return {tuple(words[index:index + 5]) for index in range(len(words) - 4)}
    first, second = shingles(left_words), shingles(right_words)
    return len(first & second) / max(1, len(first | second)) >= 0.95


def verify_attributed_claim(claim: dict, passage: dict, document: dict) -> str:
    quotation = claim.get("quotation", "")
    if not quotation or quotation not in passage["text"] or claim.get("passage_id") != str(passage["id"]):
        return "unverified"
    expected = f'According to {document["title"]}: "{quotation}"'
    if claim.get("kind") == "observation" and claim.get("text") == expected:
        return "supported"
    return "partial"