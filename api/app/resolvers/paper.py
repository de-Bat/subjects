"""Paper resolver: arXiv / DOI links -> metadata via arXiv API / doi.org content negotiation."""
import re
import xml.etree.ElementTree as ET

import httpx

from ..models.schemas import EnrichedItem, Signals
from .base import Resolver

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")


def ids_from_signals(signals: Signals) -> tuple[str | None, str | None]:
    text = " ".join(filter(None, [signals.canonical_url, signals.url, signals.text,
                                  signals.vision.ocr_text if signals.vision else None]))
    arxiv = m.group(1) if (m := ARXIV_RE.search(text)) else None
    doi = m.group(1) if (m := DOI_RE.search(text)) else None
    return arxiv, doi


class PaperResolver(Resolver):
    id = "paper"
    item_type = "paper"
    category_hints = ["Papers"]

    def detect(self, signals: Signals) -> float:
        arxiv, doi = ids_from_signals(signals)
        if arxiv:
            return 0.95
        if doi:
            return 0.85
        return 0.0

    async def enrich(self, signals: Signals) -> EnrichedItem:
        arxiv, doi = ids_from_signals(signals)
        if arxiv:
            return await self._enrich_arxiv(arxiv)
        if doi:
            return await self._enrich_doi(doi)
        return EnrichedItem(type="paper", title=signals.title, confidence=0.3)

    async def _enrich_arxiv(self, arxiv_id: str) -> EnrichedItem:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query", params={"id_list": arxiv_id}
            )
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entry = ET.fromstring(resp.text).find("a:entry", ns)
        if entry is None:
            return EnrichedItem(type="paper", title=f"arXiv:{arxiv_id}", confidence=0.4)
        title = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
        summary = (entry.findtext("a:summary", "", ns) or "").strip()
        authors = [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)]
        return EnrichedItem(
            type="paper",
            title=title,
            description=summary[:1000],
            canonical_url=f"https://arxiv.org/abs/{arxiv_id}",
            attributes={"authors": authors, "arxiv_id": arxiv_id,
                        "published": entry.findtext("a:published", None, ns)},
            links={"abstract": f"https://arxiv.org/abs/{arxiv_id}",
                   "pdf": f"https://arxiv.org/pdf/{arxiv_id}"},
            tags=["paper", "arxiv"],
            category_hints=self.category_hints,
            confidence=0.95,
        )

    async def _enrich_doi(self, doi: str) -> EnrichedItem:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(
                f"https://doi.org/{doi}",
                headers={"Accept": "application/vnd.citationstyles.csl+json"},
            )
        if resp.status_code != 200:
            return EnrichedItem(type="paper", title=doi, canonical_url=f"https://doi.org/{doi}",
                                confidence=0.5)
        data = resp.json()
        authors = [
            " ".join(filter(None, [a.get("given"), a.get("family")]))
            for a in data.get("author", [])
        ]
        return EnrichedItem(
            type="paper",
            title=data.get("title"),
            description=data.get("abstract"),
            canonical_url=f"https://doi.org/{doi}",
            attributes={"authors": authors, "doi": doi,
                        "journal": data.get("container-title"),
                        "published": str((data.get("issued", {}).get("date-parts") or [[None]])[0][0])},
            links={"doi": f"https://doi.org/{doi}"},
            tags=["paper"],
            category_hints=self.category_hints,
            confidence=0.9,
        )
