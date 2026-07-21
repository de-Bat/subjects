"""Resolver registry: run every detect(), pick argmax, ties/low scores fall to generic."""
import logging

from ..models.schemas import Signals
from .base import Resolver

log = logging.getLogger(__name__)

# Below this detect() score a typed resolver is not trusted and generic wins.
MIN_DETECT = 0.5

# A confident primary-subject type routes straight to its resolver, so the container
# service (e.g. an Instagram post wrapping a film) cannot outvote the real subject.
SUBJECT_TYPE_TO_RESOLVER = {
    "movie": "movie", "show": "movie",
    "repo": "github", "product": "product", "article": "article",
    "paper": "paper", "recipe": "recipe", "social": "social", "youtube": "youtube",
}
# The mapped resolver still has to look at least plausible before we trust the route.
SUBJECT_ROUTE_FLOOR = 0.3

_resolvers: list[Resolver] = []


def register(resolver: Resolver) -> None:
    _resolvers.append(resolver)


def all_resolvers() -> list[Resolver]:
    if not _resolvers:
        _load_defaults()
    return _resolvers


def _load_defaults() -> None:
    from .article import ArticleResolver
    from .generic import GenericResolver
    from .github import GitHubResolver
    from .movie import MovieResolver
    from .paper import PaperResolver
    from .product import ProductResolver
    from .recipe import RecipeResolver
    from .social import SocialResolver
    from .youtube import YouTubeResolver

    for r in (
        GitHubResolver(),
        MovieResolver(),
        YouTubeResolver(),
        PaperResolver(),
        RecipeResolver(),
        ProductResolver(),
        ArticleResolver(),
        SocialResolver(),
        GenericResolver(),
    ):
        register(r)


def pick(signals: Signals) -> Resolver:
    resolvers = all_resolvers()
    by_id = {r.id: r for r in resolvers}
    generic = by_id.get("generic")

    scores: dict[str, float] = {}
    for r in resolvers:
        if r.id == "generic":
            continue
        try:
            scores[r.id] = r.detect(signals)
        except Exception as exc:
            log.warning("resolver %s detect failed: %s", r.id, exc)
    for rid, sc in scores.items():
        log.info("detect %s -> %.2f", rid, sc)

    # Subject-first routing.
    subject = signals.vision.primary_subject if signals.vision else None
    if subject:
        target = SUBJECT_TYPE_TO_RESOLVER.get(subject.subject_type)
        if target and target in by_id and scores.get(target, 0.0) >= SUBJECT_ROUTE_FLOOR:
            return by_id[target]

    best = max(scores.items(), key=lambda kv: kv[1], default=None)
    if best and best[1] >= MIN_DETECT:
        return by_id[best[0]]
    assert generic is not None, "generic resolver must be registered"
    return generic
