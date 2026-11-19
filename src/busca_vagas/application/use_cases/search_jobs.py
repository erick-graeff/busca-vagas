"""Pipeline de busca: fetch → dedupe → perfil → regras → novas? → match → notify → marcar vistas → report."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from busca_vagas.application.ports.inbound import Issue, SearchReport, SearchRequest
from busca_vagas.application.ports.notifier import Notifier, NotifierError
from busca_vagas.application.ports.sources import JobSource, SourceError
from busca_vagas.application.ports.storage import KeyValueStore
from busca_vagas.application.use_cases.alerts import AlertState
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
        errors: list[Issue] = []

        # [1] fetch e [2] dedupe por Posting.key (a primeira fonte que trouxer a vaga vence)
        candidates: dict[str, tuple[Posting, SearchProfile]] = {}
        total = 0
        for spec in self._sources:
            try:
                postings = spec.source.fetch()
            except SourceError as e:
                errors.append(Issue(spec.source.name, str(e)))
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
                    errors.append(Issue(f"match {r.posting.key}", r.match.error))

        report = SearchReport(
            generated_at=now,
            total_fetched=total,
            results=rank(results),
            new_keys=new_keys,
            errors=errors,
        )

        # [7] notify (antes de marcar vistas: se a entrega falhar, as vagas voltam no próximo cron)
        delivered = True
        if request.notify:
            alerts = AlertState(self._store)
            report.new_issues, report.resolved = alerts.diff(errors)  # cada falha é avisada uma vez
            current_issues = list(errors)
            for notifier in self._notifiers:
                try:
                    notifier.notify(report)
                except NotifierError as e:
                    delivered = False
                    errors.append(Issue(f"notificação {type(notifier).__name__}", str(e)))
            if delivered:
                alerts.replace(current_issues, now)

        # [8] marcar vistas (com match ativo, só as avaliadas com sucesso, para retentar as falhas)
        if delivered:
            for r in results:
                if r.posting.key in new_keys and (r.match is None or r.match.ok):
                    self._store.set(SEEN_NAMESPACE, r.posting.key, {"first_seen": now.isoformat()})

        # [9] report (console, arquivo), já com eventuais erros de notificação
        for reporter in self._reporters:
            reporter.notify(report)
        return report
