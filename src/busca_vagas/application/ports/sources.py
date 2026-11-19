from typing import Protocol

from busca_vagas.domain.models import Posting


class SourceError(Exception):
    """Falha ao buscar vagas numa fonte (rede, formato inesperado...)."""


class JobSource(Protocol):
    """Fonte de vagas (Lever, Greenhouse, busca na web...).

    Só busca e normaliza para `Posting`. Cache, filtro e persistência não são
    responsabilidade da fonte.
    """

    @property
    def name(self) -> str:
        """Identificador único e estável da fonte configurada, ex: 'lever:ciandt'."""
        ...

    def fetch(self) -> list[Posting]:
        """Retorna as vagas abertas. Levanta SourceError em caso de falha."""
        ...
