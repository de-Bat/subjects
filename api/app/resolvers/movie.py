"""Movie resolver: screenshot/blurb/IMDb link -> TMDb entity with LLM disambiguation (B.3)."""
import json
import re

import httpx

from ..ai import prompts
from ..ai.provider import complete_json, get_provider
from ..config import get_settings
from ..models.schemas import EnrichedItem, MoviePick, Signals
from ..pipeline.subject import subject_entities
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
        for ent in subject_entities(signals.vision):
            if ent.type == "imdb_id" and ent.value.startswith("tt"):
                return ent.value
    return None


def title_year_from_signals(signals: Signals) -> tuple[str | None, str | None]:
    title = None
    year = None
    if signals.vision:
        for ent in subject_entities(signals.vision):
            if ent.type in ("movie", "media_title") and not title:
                title = ent.value
            if ent.type == "year" and not year:
                year = ent.value
        title = title or signals.vision.title_guess
    title = title or signals.og.get("og:title") or signals.title
    return title, year


def _subject_title(signals: Signals) -> str | None:
    """Best-known subject title without a TMDb hit: primary subject, then vision, then source."""
    if signals.vision and signals.vision.primary_subject and signals.vision.primary_subject.title:
        return signals.vision.primary_subject.title
    title, _ = title_year_from_signals(signals)
    return title


def _subject_description(signals: Signals) -> str | None:
    ps = signals.vision.primary_subject if signals.vision else None
    if ps and ps.why:
        return ps.why
    if signals.vision and signals.vision.ocr_text:
        return signals.vision.ocr_text[:280].strip() or None
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _subject_media_type(signals: Signals) -> str:
    ps = signals.vision.primary_subject if signals.vision else None
    return "show" if (ps and ps.subject_type == "show") else "movie"


def build_media_item(details: dict, media_type: str, pick_confidence: float) -> EnrichedItem:
    """Pure: turn a TMDb movie|tv detail payload into an EnrichedItem. No network."""
    is_tv = media_type == "tv"
    tmdb_id = details.get("id")
    title = details.get("title") or details.get("name")
    date = details.get("release_date") or details.get("first_air_date") or ""
    year = date[:4] or None
    runtime = details.get("runtime")
    if runtime is None:
        ert = details.get("episode_run_time") or []
        runtime = ert[0] if ert else None

    cast = [c.get("name") for c in (details.get("credits") or {}).get("cast", [])[:8] if c.get("name")]

    us = (((details.get("watch/providers") or {}).get("results") or {}).get("US") or {})
    providers = [p.get("provider_name") for p in (us.get("flatrate") or []) if p.get("provider_name")]
    apple_original = any("apple tv" in p.lower() for p in providers)
    networks = [n.get("name") for n in (details.get("networks") or []) if n.get("name")]

    trailer = next(
        (f"https://www.youtube.com/watch?v={v['key']}"
         for v in (details.get("videos", {}).get("results") or [])
         if v.get("site") == "YouTube" and v.get("type") == "Trailer"),
        None,
    )
    imdb_id = (details.get("external_ids") or {}).get("imdb_id") or details.get("imdb_id")
    poster = details.get("poster_path")
    path = "tv" if is_tv else "movie"

    attributes = {
        "type": "show" if is_tv else "movie",
        "rating": details.get("vote_average"),
        "votes": details.get("vote_count"),
        "runtime": runtime,
        "year": year,
        "tmdb_id": tmdb_id,
        "genres": [g.get("name") for g in (details.get("genres") or []) if g.get("name")],
        "cast": cast,
        "provider": providers,
        "apple_original": apple_original,
    }
    if is_tv:
        attributes["network"] = networks

    tags = [g["name"].lower() for g in (details.get("genres") or [])]
    tags += [f"actor:{_slug(n)}" for n in cast]
    tags += [f"provider:{_slug(p)}" for p in providers]
    if apple_original:
        tags.append("apple-original")
    if year:
        tags.append(year)

    return EnrichedItem(
        type="show" if is_tv else "movie",
        title=title,
        description=details.get("overview"),
        canonical_url=f"https://www.themoviedb.org/{path}/{tmdb_id}",
        thumbnail_url=f"{IMG}/w500{poster}" if poster else None,
        icon_url=f"{IMG}/w92{poster}" if poster else None,
        attributes=attributes,
        links={
            "trailer": trailer,
            "imdb": f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None,
            "homepage": details.get("homepage") or None,
        },
        tags=tags,
        category_hints=["TV Shows"] if is_tv else ["Movies"],
        confidence=min(0.97, max(pick_confidence, 0.5) * 0.97),
    )


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
            subject_type = _subject_media_type(signals)
            return EnrichedItem(
                type=subject_type, title=_subject_title(signals),
                description=_subject_description(signals),
                attributes={"_enrich_incomplete": "No TMDb API key configured"},
                category_hints=["TV Shows"] if subject_type == "show" else ["Movies"],
                confidence=0.2,
            )

        async with httpx.AsyncClient(timeout=20.0) as client:
            tmdb_id, media_type, pick_confidence = await self._identify(client, api_key, signals)
            if tmdb_id is None:
                subject_type = _subject_media_type(signals)
                return EnrichedItem(
                    type=subject_type, title=_subject_title(signals),
                    description=_subject_description(signals),
                    attributes={"_enrich_incomplete": "No confident match on TMDb"},
                    category_hints=["TV Shows"] if subject_type == "show" else ["Movies"],
                    confidence=min(pick_confidence, 0.3),
                )

            details = (await client.get(
                f"{TMDB}/{media_type}/{tmdb_id}",
                params={"api_key": api_key,
                        "append_to_response": "videos,external_ids,credits,watch/providers"},
            )).json()

        return build_media_item(details, media_type, pick_confidence)

    async def _identify(self, client, api_key, signals):
        """Return (tmdb_id, media_type, confidence)."""
        if imdb_id := imdb_id_from_signals(signals):
            resp = await client.get(
                f"{TMDB}/find/{imdb_id}", params={"api_key": api_key, "external_source": "imdb_id"}
            )
            data = resp.json()
            if data.get("movie_results"):
                return data["movie_results"][0]["id"], "movie", 0.98
            if data.get("tv_results"):
                return data["tv_results"][0]["id"], "tv", 0.98

        title, year = title_year_from_signals(signals)
        if not title:
            return None, "movie", 0.0

        candidates = []
        for media_type in ("movie", "tv"):
            params = {"api_key": api_key, "query": title}
            if year:
                params["first_air_date_year" if media_type == "tv" else "year"] = year
            resp = await client.get(f"{TMDB}/search/{media_type}", params=params)
            for c in (resp.json().get("results") or [])[:5]:
                date = c.get("release_date") or c.get("first_air_date") or ""
                candidates.append({
                    "id": c["id"], "media_type": media_type,
                    "title": c.get("title") or c.get("name"),
                    "release_year": int(date[:4]) if date[:4].isdigit() else None,
                })
        if not candidates:
            return None, "movie", 0.0

        payload = {
            "context": {"title_guess": title, "year": year,
                        "ocr_text": (signals.vision.ocr_text[:1000] if signals.vision else None)},
            "candidates": candidates,
        }
        pick = await complete_json(
            get_provider(), MoviePick, json.dumps(payload), system=prompts.MOVIE_PICK_SYSTEM
        )
        if not pick or pick.tmdb_id is None:
            return None, "movie", pick.confidence if pick else 0.0
        media_type = pick.media_type or "movie"
        valid_ids = {c["id"] for c in candidates if c["media_type"] == media_type}
        if pick.tmdb_id not in valid_ids:
            return None, media_type, 0.2
        return pick.tmdb_id, media_type, pick.confidence
