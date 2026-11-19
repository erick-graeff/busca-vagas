"""Decorator que adiciona cache a qualquer JobSource."""

from dataclasses import asdict
from datetime import datetime

from busca_vagas.application.ports.sources import JobSource
from busca_vagas.application.ports.storage import KeyValueStore
from busca_vagas.domain.models import Posting

NAMESPACE = "sources"


class CachedSource:
    """Usa as vagas salvas no store; consulta a fonte real se não houver cache ou se refresh=True."""

    def __init__(self, inner: JobSource, store: KeyValueStore, refresh: bool = False):
        self._inner = inner
        self._store = store
        self._refresh = refresh

    @property
    def name(self) -> str:
        return self._inner.name

    def fetch(self) -> list[Posting]:
        if not self._refresh and (cached := self._store.get(NAMESPACE, self.name)) is not None:
            return [Posting(**p) for p in cached["postings"]]
        postings = self._inner.fetch()
        self._store.set(
            NAMESPACE,
            self.name,
            {"fetched_at": datetime.now().isoformat(), "postings": [asdict(p) for p in postings]},
        )
        return postings
