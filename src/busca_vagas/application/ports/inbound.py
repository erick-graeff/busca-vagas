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


@dataclass(frozen=True)
class Issue:
    """Falha não fatal (fonte fora do ar, erro da IA...).

    `subject` identifica a origem de forma estável entre execuções (é o que evita repetir
    alertas); `message` é o detalhe, que pode variar.
    """

    subject: str
    message: str

    def __str__(self) -> str:
        return f"{self.subject}: {self.message}"


@dataclass(kw_only=True)
class SearchReport:
    generated_at: datetime
    total_fetched: int
    results: list[ScoredPosting]  # vagas que passaram no filtro, ordenadas por pontuação
    new_keys: frozenset[str] = frozenset()  # Posting.key das vagas vistas pela 1ª vez
    errors: list[Issue] = field(default_factory=list)  # falhas não fatais desta execução
    # Para notificadores: só as falhas ainda não avisadas e as que deixaram de acontecer.
    # None = sem controle de alertas (todas as falhas são novas).
    new_issues: list[Issue] | None = None
    resolved: list[str] = field(default_factory=list)  # subjects que voltaram a funcionar

    @property
    def new_results(self) -> list[ScoredPosting]:
        return [r for r in self.results if r.posting.key in self.new_keys]

    @property
    def issues_to_alert(self) -> list[Issue]:
        return self.errors if self.new_issues is None else self.new_issues


class SearchJobs(Protocol):
    def run(self, request: SearchRequest) -> SearchReport: ...
