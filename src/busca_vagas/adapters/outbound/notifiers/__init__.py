"""Registro dos notificadores extras (acionados com --notify), por `type` da configuração.

Para adicionar um (ex.: Telegram): implemente `busca_vagas.application.ports.Notifier`
com um `from_options(dict)` e registre aqui. Console e arquivo JSON são sempre
acionados e configurados em [output].
"""

from collections.abc import Callable, Mapping
from typing import Any

from busca_vagas.application.ports.notifier import Notifier

NOTIFIER_TYPES: dict[str, Callable[[Mapping[str, Any]], Notifier]] = {}
