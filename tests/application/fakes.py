"""Implementações em memória das portas de saída, para testar o núcleo sem I/O."""

from typing import Any

from busca_vagas.application.ports.inbound import SearchReport
from busca_vagas.application.ports.llm import LLMError
from busca_vagas.application.ports.sources import SourceError
from busca_vagas.domain.models import Posting


class FakeSource:
    def __init__(self, postings: list[Posting], name: str = "fake:acme", fail: bool = False):
        self._postings = postings
        self._name = name
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    def fetch(self) -> list[Posting]:
        if self._fail:
            raise SourceError("fora do ar")
        return list(self._postings)


class FakeLLM:
    def __init__(self, response: str = '{"score": 80, "summary": "ok"}', fail: bool = False):
        self.response = response
        self.fail = fail
        self.calls: list[str] = []

    @property
    def model_id(self) -> str:
        return "fake/model"

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.fail:
            raise LLMError("timeout")
        return self.response


class InMemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, Any]] = {}

    def get(self, namespace: str, key: str) -> Any | None:
        return self.data.get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value: Any) -> None:
        self.data.setdefault(namespace, {})[key] = value

    def has(self, namespace: str, key: str) -> bool:
        return key in self.data.get(namespace, {})


class FakeNotifier:
    def __init__(self):
        self.reports: list[SearchReport] = []

    def notify(self, report: SearchReport) -> None:
        self.reports.append(report)
