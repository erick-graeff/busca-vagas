"""Registro dos backends de IA disponíveis, por `backend` da configuração.

Para adicionar um backend: implemente `busca_vagas.application.ports.LLMClient`
com um `from_options(dict)` e registre aqui.
"""

from collections.abc import Callable, Mapping
from typing import Any

from busca_vagas.adapters.outbound.llm.opencode_cli import OpencodeCLI
from busca_vagas.application.ports.llm import LLMClient

LLM_BACKENDS: dict[str, Callable[[Mapping[str, Any]], LLMClient]] = {
    "opencode": OpencodeCLI.from_options,
}
