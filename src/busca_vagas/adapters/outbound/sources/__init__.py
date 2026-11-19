"""Registro das fontes de vagas disponíveis, por `type` da configuração.

Para adicionar uma fonte: crie um módulo com uma classe que implemente
`busca_vagas.application.ports.JobSource` e um `from_options(dict)`, e registre aqui.
"""

from collections.abc import Callable, Mapping
from typing import Any

from busca_vagas.adapters.outbound.sources.lever import LeverSource
from busca_vagas.application.ports.sources import JobSource

SOURCE_TYPES: dict[str, Callable[[Mapping[str, Any]], JobSource]] = {
    "lever": LeverSource.from_options,
}
