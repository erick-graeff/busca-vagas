"""Entidades do domínio. Sem I/O e sem dependências externas."""

from dataclasses import dataclass, field
from enum import StrEnum


class Level(StrEnum):
    JUNIOR = "junior"
    MID = "pleno"
    SENIOR = "senior"
    MASTER = "master"  # acima de senior: master/lead/specialist/principal/staff


@dataclass(frozen=True, kw_only=True)
class Posting:
    """Vaga normalizada, independente da fonte de origem.

    Só `source`, `company`, `id`, `title` e `url` são obrigatórios: fontes mais pobres
    (ex.: resultados de busca) podem não ter descrição, país ou modalidade.
    """

    source: str  # tipo da fonte, ex: "lever"
    company: str
    id: str  # id nativo da vaga na fonte
    title: str
    url: str
    apply_url: str = ""
    country: str = ""
    location: str = ""
    team: str = ""
    workplace_type: str = ""  # "remote" | "hybrid" | "onsite" | "" (desconhecido)
    description: str = ""

    @property
    def key(self) -> str:
        """Identidade estável da vaga entre execuções (usada para detectar vagas novas)."""
        return f"{self.source}:{self.company}:{self.id}"

    @property
    def searchable_text(self) -> str:
        return f"{self.title}\n{self.description}"


@dataclass(kw_only=True)
class MatchResult:
    """Avaliação de aderência vaga x currículo feita por uma IA."""

    score: int | None = None
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    raw: str = ""  # resposta original (útil para depurar o prompt)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass(kw_only=True)
class ScoredPosting:
    posting: Posting
    score: int
    matched: list[str] = field(default_factory=list)
    title_matched: list[str] = field(default_factory=list)
    match: MatchResult | None = None
