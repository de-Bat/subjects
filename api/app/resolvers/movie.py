"""Movie resolver: screenshot/blurb/IMDb link -> TMDb entity with LLM disambiguation (B.3)."""
import json
import re

import httpx

from ..ai import prompts
from ..ai.provider import complete_json, get_provider
from ..config import get_settings
from ..models.schemas import EnrichedItem, MoviePick, Signals
from .base import Resolver

IMDB_URL_RE = re.compile(r"imdb\.com/title/(tt\d+)")
TMDB = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"

MOVIE_WORDS = re.compile(
    r"\b(movie|film|directed by|starring|trailer|imdb|box office|screenplay|cinema)\b", re.I
)


def imdb_id_from_signals(signals: Signals) -> str | None:
    for candidate in (signals.canonical_url, signals.url,
                      signals.vision.visible_url if signals.vision else None,
                      signals.text):
        if candidate and (m := IMDB_URL_RE.search(candidate)):
            return m.group(1)
    if signals.vision:
        for ent in signals.vision.candidate_entities:
            if ent.type == "imdb_id" and ent.value.startswith("tt"):
                return ent.value
    return None


def title_year_from_signals(signals: Signals) -> tuple[str | None, str | None]:
    title = None
    year = None
    if signals.vision:
        for ent in signals.vision.candidate_entities:
            if ent.type in ("movie", "media_title") and not title:
                title = ent.value
            if ent.type == "year" and not year:
                year = ent.value
        title = title or signals.vision.title_guess
    title = title or signals.og.get("og:title") or signals.title
    return title, year


class MovieResolver(Resolver):
    id = "movie"
    item_type = "movie"
    category_hints = ["Movies"]

    def detect(self, signals: Signals) -> float:
        if imdb_id_from_signals(signals):
            return 0.95
        if signals.vision and signals.vision.detected_service in ("imdb", "movie"):
            return 0.85
        if signals.vision:
            types = {e.type for e in signals.vision.candidate_entities}
            if "media_title" in types and (
                types & {"person", "actor"} or "provider" in types
            ):
                return 0.9
        text = " ".join(filter(None, [signals.text, signals.body_text,
                                      signals.vision.ocr_text if signals.vision else None]))
        if text and len(MOVIE_WORDS.findall(text)) >= 2:
            return 0.6
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        api_key = get_settings().tmdb_api_key
        if not api_key:
            return EnrichedItem(type="movie", title=signals.title, confidence=0.2,
                                attributes={"error": "TMDB_API_KEY not configured"})

        async with httpx.AsyncClient(timeout=20.0) as client:
            tmdb_id, pick_confidence = await self._identify(client, api_key, signals)
            if tmdb_id is None:
                title, _ = title_year_from_signals(signals)
                return EnrichedItem(type="movie", title=title, confidence=min(pick_confidence, 0.4))

            details = (await client.get(
                f"{TMDB}/movie/{tmdb_id}",
                params={"api_key": api_key, "append_to_response": "videos,external_ids"},
            )).json()

        trailer = next(
            (f"https://www.youtube.com/watch?v={v['key']}"
             for v in (details.get("videos", {}).get("results") or [])
             if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
            None,
        )
        imdb_id = (details.get("external_ids") or {}).get("imdb_id") or details.get("imdb_id")
        year = (details.get("release_date") or "")[:4]

        return EnrichedItem(
            type="movie",
            title=details.get("title"),
            description=details.get("overview"),
            canonical_url=f"https://www.themoviedb.org/movie/{tmdb_id}",
            thumbnail_url=f"{IMG}/w500{details['poster_path']}" if details.get("poster_path") else None,
            icon_url=f"{IMG}/w92{details['poster_path']}" if details.get("poster_path") else None,
            attributes={
                "rating": details.get("vote_average"),
                "votes": details.get("vote_count"),
                "runtime": details.get("runtime"),
                "release_date": details.get("release_date"),
                "year": year or None,
                "tmdb_id": tmdb_id,
            },
            links={
                "trailer": trailer,
                "imdb": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
                "homepage": details.get("homepage") or None,
            },
            tags=[g["name"].lower() for g in (details.get("genres") or [])] + ([year] if year else []),
            category_hints=self.category_hints,
            confidence=min(0.97, max(pick_confidence, 0.5) * 0.97),
        )

    async def _identify(self, client: httpx.AsyncClient, api_key: str, signals: Signals) -> tuple[int | None, float]:
        """Return (tmdb_id, confidence). Direct IMDb-id lookup when unambiguous, else search + LLM pick."""
        if imdb_id := imdb_id_from_signals(signals):
            resp = await client.get(
                f"{TMDB}/find/{imdb_id}", params={"api_key": api_key, "external_source": "imdb_id"}
            )
            results = resp.json().get("movie_results") or []
            if results:
                return results[0]["id"], 0.98

        title, year = title_year_from_signals(signals)
        if not title:
            return None, 0.0
        params = {"api_key": api_key, "query": title}
        if year:
            params["year"] = year
        resp = await client.get(f"{TMDB}/search/movie", params=params)
        candidates = (resp.json().get("results") or [])[:5]
        if not candidates:
            return None, 0.0

        # Wrong-movie/wrong-year errors are prevented here (Appendix B.3).
        payload = {
            "context": {"title_guess": title, "year": year,
                        "ocr_text": (signals.vision.ocr_text[:1000] if signals.vision else None)},
            "candidates": [
                {"id": c["id"], "title": c.get("title"),
                 "release_year": int(c["release_date"][:4]) if c.get("release_date") else None}
                for c in candidates
            ],
        }
        pick = await complete_json(
            get_provider(), MoviePick, json.dumps(payload), system=prompts.MOVIE_PICK_SYSTEM
        )
        if not pick or pick.tmdb_id is None:
            return None, pick.confidence if pick else 0.0
        if pick.tmdb_id not in {c["id"] for c in candidates}:
            return None, 0.2  # hallucinated id -> review
        return pick.tmdb_id, pick.confidence
