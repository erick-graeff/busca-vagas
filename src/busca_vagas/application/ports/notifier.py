from typing import Protocol

from busca_vagas.application.ports.inbound import SearchReport


class Notifier(Protocol):
    """Destino do relatório de uma busca (console, arquivo, Telegram, e-mail...)."""

    def notify(self, report: SearchReport) -> None: ...
