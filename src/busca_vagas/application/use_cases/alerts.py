"""Controle de alertas: avisa uma falha uma vez, e de novo só quando ela se resolve.

Sem isso, uma fonte fora do ar geraria a mesma notificação a cada execução do cron.
"""

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime

from busca_vagas.application.ports.inbound import Issue, SearchReport
from busca_vagas.application.ports.notifier import Notifier, NotifierError
from busca_vagas.application.ports.storage import KeyValueStore

ALERTS_NAMESPACE = "alerts"
_ACTIVE_KEY = "active"


class AlertState:
    """Falhas já avisadas, por `Issue.subject`."""

    def __init__(self, store: KeyValueStore):
        self._store = store

    def active(self) -> dict[str, dict]:
        return dict(self._store.get(ALERTS_NAMESPACE, _ACTIVE_KEY) or {})

    def diff(self, issues: Iterable[Issue]) -> tuple[list[Issue], list[str]]:
        """(falhas ainda não avisadas, subjects avisados antes que não aconteceram agora)."""
        issues = list(issues)
        active = self.active()
        current = {i.subject for i in issues}
        new = [i for i in issues if i.subject not in active]
        resolved = sorted(s for s in active if s not in current)
        return new, resolved

    def replace(self, issues: Iterable[Issue], now: datetime) -> None:
        """As falhas ativas passam a ser exatamente `issues` (preserva a data da 1ª vez)."""
        active = self.active()
        self._save({i.subject: active.get(i.subject) or _entry(i, now) for i in issues})

    def add(self, issue: Issue, now: datetime) -> None:
        active = self.active()
        active.setdefault(issue.subject, _entry(issue, now))
        self._save(active)

    def _save(self, active: dict[str, dict]) -> None:
        self._store.set(ALERTS_NAMESPACE, _ACTIVE_KEY, active)


def _entry(issue: Issue, now: datetime) -> dict:
    return {"message": issue.message, "since": now.isoformat()}


class AlertFailure:
    """Avisa uma falha que impediu a busca de rodar (config inválida, bug...)."""

    def __init__(
        self,
        notifiers: Sequence[Notifier],
        store: KeyValueStore,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self._notifiers = notifiers
        self._state = AlertState(store)
        self._clock = clock

    def alert(self, issue: Issue) -> bool:
        """Envia, se ainda não foi avisada. Retorna True se alguém recebeu agora."""
        if issue.subject in self._state.active():
            return False
        now = self._clock()
        report = SearchReport(generated_at=now, total_fetched=0, results=[], errors=[issue], new_issues=[issue])
        delivered = False
        for notifier in self._notifiers:
            try:
                notifier.notify(report)
                delivered = True
            except NotifierError:
                pass
        if delivered:
            self._state.add(issue, now)
        return delivered
