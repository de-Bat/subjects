"""Resolver registry: run every detect(), pick argmax, ties/low scores fall to generic."""
import logging

from ..models.schemas import Signals
from .base import Resolver

log = logging.getLogger(__name__)

# Below this detect() score a typed resolver is not trusted and generic wins.
MIN_DETECT = 0.5

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
    generic = None
    best: tuple[float, Resolver] | None = None
    for r in all_resolvers():
        if r.id == "generic":
            generic = r
            continue
        try:
            score = r.detect(signals)
        except Exception as exc:
            log.warning("resolver %s detect failed: %s", r.id, exc)
            continue
        log.info("detect %s -> %.2f", r.id, score)
        if best is None or score > best[0]:
            best = (score, r)
    if best and best[0] >= MIN_DETECT:
        return best[1]
    assert generic is not None, "generic resolver must be registered"
    return generic
