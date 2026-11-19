from typing import Protocol


class LLMError(Exception):
    """Falha ao obter resposta da IA (processo, rede, timeout...)."""


class LLMClient(Protocol):
    """Cliente de IA mínimo: recebe um prompt, devolve o texto da resposta.

    Prompt, formato esperado e parse da resposta são responsabilidade do caso de uso,
    então trocar de IA (opencode, Claude, Ollama...) é só implementar esta interface.
    """

    @property
    def model_id(self) -> str:
        """Identifica modelo/backend; entra na chave do cache de respostas."""
        ...

    def complete(self, prompt: str) -> str:
        """Levanta LLMError em caso de falha."""
        ...
