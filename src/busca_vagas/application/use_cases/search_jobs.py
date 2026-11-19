"""Pipeline de busca: fetch → dedupe → perfil → regras → novas? → match → marcar vistas → report → notify."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from busca_vagas.application.ports.inbound import SearchReport, SearchRequest
from busca_vagas.application.ports.notifier import Notifier
from busca_vagas.application.ports.sources import JobSource, SourceError
from busca_vagas.application.ports.storage import KeyValueStore
from busca_vagas.application.use_cases.match_jobs import MatchJobs
from busca_vagas.domain.filtering import passes_profile, rank, score
from busca_vagas.domain.models import Posting, ScoredPosting
from busca_vagas.domain.rules import FilterRules, SearchProfile

SEEN_NAMESPACE = "seen"


@dataclass(frozen=True)
class SourceSpec:
    source: JobSource
    profile: SearchProfile


class SearchJobsService:
    """Implementa a porta de entrada `SearchJobs`."""

    def __init__(
        self,
        *,
        sources: Sequence[SourceSpec],
        rules: FilterRules,
        store: KeyValueStore,
        reporters: Sequence[Notifier] = (),  # sempre acionados (console, arquivo)
        notifiers: Sequence[Notifier] = (),  # só com request.notify (Telegram...)
        matcher: MatchJobs | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._sources = sources
        self._rules = rules
        self._store = store
        self._reporters = reporters
        self._notifiers = notifiers
        self._matcher = matcher
        self._clock = clock

    def run(self, request: SearchRequest) -> SearchReport:
        if request.match and self._matcher is None:
            raise ValueError("match solicitado, mas nenhum matcher foi configurado")

        now = self._clock()
        errors: list[str] = []

        # [1] fetch e [2] dedupe por Posting.key (a primeira fonte que trouxer a vaga vence)
        candidates: dict[str, tuple[Posting, SearchProfile]] = {}
        total = 0
        for spec in self._sources:
            try:
                postings = spec.source.fetch()
            except SourceError as e:
                errors.append(f"{spec.source.name}: {e}")
                continue
            total += len(postings)
            for p in postings:
                candidates.setdefault(p.key, (p, spec.profile))

        # [3] perfil e [4] regras
        results: list[ScoredPosting] = []
        for posting, profile in candidates.values():
            if not passes_profile(posting, profile, self._rules):
                continue
            if (scored := score(posting, self._rules)) is not None:
                results.append(scored)

        # [5] novas?
        new_keys = frozenset(
            r.posting.key for r in results if not self._store.has(SEEN_NAMESPACE, r.posting.key)
        )
        if request.new_only:
            results = [r for r in results if r.posting.key in new_keys]

        # [6] match com IA
        if request.match:
            for r in results:
                r.match = self._matcher.match(r.posting)
                if not r.match.ok:
                    errors.append(f"match {r.posting.key}: {r.match.error}")

        # [7] marcar vistas (com match ativo, só as avaliadas com sucesso, para retentar as falhas)
        for r in results:
            if r.posting.key in new_keys and (r.match is None or r.match.ok):
                self._store.set(SEEN_NAMESPACE, r.posting.key, {"first_seen": now.isoformat()})

        report = SearchReport(
            generated_at=now,
            total_fetched=total,
            results=rank(results),
            new_keys=new_keys,
            errors=errors,
        )

        # [8] report e [9] notify
        for reporter in self._reporters:
            reporter.notify(report)
        if request.notify:
            for notifier in self._notifiers:
                notifier.notify(report)
        return report
