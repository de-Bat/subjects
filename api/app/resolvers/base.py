"""Resolver plugin contract (spec Section 6.3).

To add a new resolver: subclass Resolver, set id/item_type/category_hints,
implement detect() and enrich(), then register it in registry.py. Nothing else.
"""
from abc import ABC, abstractmethod

from ..models.schemas import EnrichedItem, Signals


class Resolver(ABC):
    id: str
    item_type: str
    category_hints: list[str] = []

    @abstractmethod
    def detect(self, signals: Signals) -> float:
        """Return 0..1 confidence that this resolver handles these signals."""

    @abstractmethod
    async def enrich(self, signals: Signals) -> EnrichedItem:
        """Resolve the entity and return typed, enriched data."""
