from typing import Any, Protocol


class KeyValueStore(Protocol):
    """Armazenamento chave-valor persistente, separado por namespace.

    Namespaces usados hoje: "sources" (cache das fontes), "match" (cache da IA),
    "seen" (vagas já vistas). Valores precisam ser serializáveis em JSON.
    """

    def get(self, namespace: str, key: str) -> Any | None: ...

    def set(self, namespace: str, key: str, value: Any) -> None: ...

    def has(self, namespace: str, key: str) -> bool: ...
