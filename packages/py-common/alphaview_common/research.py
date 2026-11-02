from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


class ResearchBudget(BaseModel):
    seconds: int = Field(default=180, ge=30, le=1800)
    pages: int = Field(default=15, ge=1, le=100)
    queries: int = Field(default=6, ge=1, le=30)
    paid_calls: int = Field(default=6, ge=0, le=30)
    rounds: int = Field(default=1, ge=1, le=5)
    requests: int = Field(default=120, ge=1, le=2000)


class ResearchOptions(BaseModel):
    mode: Literal["quick", "deep"] = "quick"
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    date_from: date | None = None
    date_to: date | None = None
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")
    preferred_domains: list[str] = Field(default_factory=list, max_length=10)
    excluded_domains: list[str] = Field(default_factory=list, max_length=20)
    seed_urls: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.mode == "deep" and "budget" not in self.model_fields_set:
            self.budget = ResearchBudget(seconds=600, pages=15, queries=12, paid_calls=12, rounds=3, requests=120)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        for domain in self.preferred_domains + self.excluded_domains:
            if not domain or "/" in domain or ":" in domain or len(domain) > 253:
                raise ValueError("Domain filters must be hostnames, not URLs")
        for url in self.seed_urls:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Seed URLs must be HTTPS without embedded credentials")
        return self


QUESTIONS = {
    "problems": "Customer problems and workflows",
    "solutions": "Existing products and successful solutions",
    "buying": "Pricing, buying criteria and switching costs",
    "experience": "Direct customer experiences",
    "context": "Market context and credible statistics",
    "counter": "Counter-evidence and satisfied customers",
}