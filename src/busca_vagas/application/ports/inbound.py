"""Porta de entrada: o que um ponto de entrada (CLI, cron, setup, API) pode pedir ao núcleo."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from busca_vagas.domain.models import ScoredPosting


@dataclass(frozen=True, kw_only=True)
class SearchRequest:
    new_only: bool = False  # só vagas ainda não vistas em execuções anteriores
    match: bool = False  # avaliar as vagas filtradas com IA
    notify: bool = False  # acionar os notificadores extras (ex.: Telegram)


@dataclass(kw_only=True)
class SearchReport:
    generated_at: datetime
    total_fetched: int
    results: list[ScoredPosting]  # vagas que passaram no filtro, ordenadas por pontuação
    new_keys: frozenset[str] = frozenset()  # Posting.key das vagas vistas pela 1ª vez
    errors: list[str] = field(default_factory=list)  # falhas não fatais (fonte, IA...)

    @property
    def new_results(self) -> list[ScoredPosting]:
        return [r for r in self.results if r.posting.key in self.new_keys]


class SearchJobs(Protocol):
    def run(self, request: SearchRequest) -> SearchReport: ...
