"""GitHub resolver: screenshot/link/text -> canonical repo item via the GitHub REST API."""
import json
import re

import httpx

from ..ai import prompts
from ..ai.provider import complete_json, get_provider
from ..config import get_settings
from ..models.schemas import EnrichedItem, RepoGuess, Signals
from .base import Resolver

REPO_URL_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
OWNER_REPO_RE = re.compile(r"\b([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]{1,100})\b")
RESERVED_OWNERS = {"features", "topics", "orgs", "sponsors", "settings", "marketplace", "search"}


def github_icon(data: dict, owner: str) -> str:
    return (data.get("owner") or {}).get("avatar_url") or f"https://github.com/{owner}.png"


def repo_from_signals(signals: Signals) -> tuple[str, str] | None:
    """Unambiguous owner/repo from URL or VLM-visible URL; None if it needs the LLM."""
    for candidate in (signals.canonical_url, signals.url,
                      signals.vision.visible_url if signals.vision else None,
                      signals.text):
        if not candidate:
            continue
        if m := REPO_URL_RE.search(candidate):
            owner, repo = m.group(1), m.group(2).removesuffix(".git")
            if owner.lower() not in RESERVED_OWNERS:
                return owner, repo
    if signals.vision:
        for ent in signals.vision.candidate_entities:
            if ent.type == "repo" and (m := OWNER_REPO_RE.fullmatch(ent.value.strip())):
                return m.group(1), m.group(2)
    return None


class GitHubResolver(Resolver):
    id = "github"
    item_type = "github"
    category_hints = ["Development", "Links"]

    def detect(self, signals: Signals) -> float:
        if repo_from_signals(signals):
            return 0.95
        if signals.vision and signals.vision.detected_service == "github":
            return 0.85
        text = " ".join(filter(None, [signals.text, signals.vision.ocr_text if signals.vision else None]))
        if "github" in text.lower() and OWNER_REPO_RE.search(text):
            return 0.6
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        pair = repo_from_signals(signals)
        llm_confidence = 1.0
        if pair is None:
            # OCR is ambiguous -> Appendix B.2 disambiguation. Never an LLM call otherwise.
            ocr = signals.vision.ocr_text if signals.vision else (signals.text or "")
            guess = await complete_json(
                get_provider(), RepoGuess, f"ocr_text: {json.dumps(ocr[:2000])}",
                system=prompts.GITHUB_DISAMBIGUATE_SYSTEM,
            )
            if not guess or not guess.owner or not guess.repo:
                return EnrichedItem(type="github", title=signals.title, confidence=0.2)
            pair = (guess.owner, guess.repo)
            llm_confidence = guess.confidence

        owner, repo = pair
        headers = {"Accept": "application/vnd.github+json"}
        if token := get_settings().github_token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if resp.status_code == 404:
                # Guessed repo doesn't exist -> low confidence, review queue.
                return EnrichedItem(type="github", title=f"{owner}/{repo}", confidence=0.3)
            resp.raise_for_status()
            data = resp.json()

        return EnrichedItem(
            type="github",
            title=data["full_name"],
            description=data.get("description"),
            canonical_url=data["html_url"],
            icon_url=github_icon(data, owner),
            thumbnail_url=github_icon(data, owner),
            attributes={
                "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "language": data.get("language"),
                "license": (data.get("license") or {}).get("spdx_id"),
                "archived": data.get("archived"),
            },
            links={
                "repo": data["html_url"],
                "homepage": data.get("homepage") or None,
            },
            tags=[t.lower() for t in (data.get("topics") or [])]
            + ([data["language"].lower()] if data.get("language") else []),
            category_hints=self.category_hints,
            confidence=min(0.97, 0.97 * llm_confidence),
        )
