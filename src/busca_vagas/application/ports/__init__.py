"""Interfaces entre o núcleo e o mundo externo.

Entrada (inbound): o que adapters de entrada podem pedir ao núcleo.
Saída (outbound): o que o núcleo precisa de fora e os adapters de saída implementam.
"""

from busca_vagas.application.ports.inbound import Issue, SearchJobs, SearchReport, SearchRequest
from busca_vagas.application.ports.llm import LLMClient, LLMError
from busca_vagas.application.ports.notifier import Notifier, NotifierError
from busca_vagas.application.ports.sources import JobSource, SourceError
from busca_vagas.application.ports.storage import KeyValueStore

__all__ = [
    "Issue",
    "JobSource",
    "KeyValueStore",
    "LLMClient",
    "LLMError",
    "Notifier",
    "NotifierError",
    "SearchJobs",
    "SearchReport",
    "SearchRequest",
    "SourceError",
]
