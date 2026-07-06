"""Ortak veri tipleri ve Source base sınıfı.

Tüm kaynak modülleri `Source`'tan türetilir, `search(query) -> list[Document]` döndürür.
`Document` basit ama yeterince zengin bir veri sınıfıdır.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class Document:
    """Tek bir sonuç dokümanı (makale, forum postu, repo, wiki sayfası, vb.)."""

    title: str
    url: str
    snippet: str = ""  # kısa özet / snippet
    source: str = ""  # kaynak adı ("arxiv", "github", "wikipedia", vb.)
    authors: list[str] = field(default_factory=list)
    published: Optional[str] = None  # ISO 8601 (YYYY-MM-DD)
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    abstract: Optional[str] = None  # tam özet
    full_text: Optional[str] = None  # okuyucu doldurur
    citation_count: Optional[int] = None
    relevance_score: Optional[float] = None
    retrieved_at: float = field(default_factory=time.time)
    extra: dict = field(default_factory=dict)

    @property
    def host(self) -> str:
        try:
            return urlparse(self.url).netloc.lower()
        except Exception:
            return ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "authors": self.authors,
            "published": self.published,
            "doi": self.doi,
            "pdf_url": self.pdf_url,
            "abstract": self.abstract,
            "citation_count": self.citation_count,
            "relevance_score": self.relevance_score,
        }


class Source(ABC):
    """Veri kaynağı base sınıfı."""

    name: str = "base"

    def __init__(self, max_results: int = 8, **kwargs):
        self.max_results = max_results
        self.opts = kwargs

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[Document]:
        """Verilen sorgu için arama yap, Document listesi döndür."""
        ...

    async def fetch_full(self, doc: Document) -> Optional[str]:
        """Doc'un tam metnini (PDF veya HTML) getir. Varsayılan: yok.
        Alt sınıflar override eder.
        """
        return None


# Güvenilir bilimsel alan adı filtresi — WebSource ve ForumsSource kullanır
TRUSTED_DOMAINS = {
    # Akademik yayıncılar
    "arxiv.org",
    "doi.org",
    "sciencedirect.com",
    "nature.com",
    "springer.com",
    "springerlink.com",
    "link.springer.com",
    "ieee.org",
    "ieeexplore.ieee.org",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "acs.org",
    "pubs.acs.org",
    "plos.org",
    "frontiersin.org",
    "mdpi.com",
    "tandfonline.com",
    "oxfordacademic.com",
    "academic.oup.com",
    "aps.org",
    "journals.aps.org",
    "iopscience.iop.org",
    "bmj.com",
    "thelancet.com",
    "cell.com",
    "pnas.org",
    "science.org",
    "aaas.org",
    # Stanford AI, MIT, CERN, NASA, DOE
    "ai.stanford.edu",
    "cs.stanford.edu",
    "mit.edu",
    "cern.ch",
    "nasa.gov",
    "energy.gov",
    "lbl.gov",
    "lanl.gov",
    "ornl.gov",
    "nist.gov",
    "bnl.gov",
    "fnal.gov",
    "caltech.edu",
    "harvard.edu",
    "princeton.edu",
    "ethz.ch",
    # Mesleki kuruluşlar
    "acm.org",
    "dl.acm.org",
    "mathscinet.ams.org",
    "ams.org",
    # Veri tabanları / indeksler
    "semanticscholar.org",
    "scholar.google.com",
    "ncbi.nlm.nih.gov",
    "europepmc.org",
    "pmc.ncbi.nlm.nih.gov",
    "biorxiv.org",
    "medrxiv.org",
    "chemrxiv.org",
    "psyarxiv.com",
    "osf.io",
    "zenodo.org",
    "figshare.com",
    # Ansiklopedi / referans
    "wikipedia.org",
    "wikidata.org",
    "britannica.com",
    "mathworld.wolfram.com",
    # Kod/repos (mühendislik)
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    # Forumlar
    "physicsforums.com",
    "engineering.com",
    "scitation.org",
    "mathoverflow.net",
    "math.stackexchange.com",
    "stackoverflow.com",
    "physics.stackexchange.com",
    "chemistry.stackexchange.com",
    "biology.stackexchange.com",
    "electronics.stackexchange.com",
    "dsp.stackexchange.com",
    "mechanical.stackexchange.com",
    "cstheory.stackexchange.com",
    "ai.stackexchange.com",
}


def trusted(url: str) -> bool:
    """URL güvenilir bir bilimsel/mühendislik alanından mı?"""
    try:
        host = urlparse(url).netloc.lower()
        # subdomain'leri soyutla: "dl.acm.org" veya "journals.aps.org"
        for d in TRUSTED_DOMAINS:
            if host == d or host.endswith("." + d):
                return True
        return False
    except Exception:
        return False
