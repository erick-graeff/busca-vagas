"""Notificador Telegram: um bot envia as vagas para um chat (o seu chat privado com ele).

Credenciais na config ou, de preferência, em variáveis de ambiente:
  TELEGRAM_BOT_TOKEN  token dado pelo @BotFather
  TELEGRAM_CHAT_ID    id do chat de destino
"""

import os
from collections.abc import Mapping
from html import escape
from typing import Any

import requests

from busca_vagas.application.ports.inbound import SearchReport
from busca_vagas.application.ports.notifier import NotifierError
from busca_vagas.domain.models import ScoredPosting

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LEN = 4096  # limite do Telegram por mensagem
MAX_SUMMARY_LEN = 500  # mantém cada vaga bem abaixo do limite
TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
CHAT_ID_ENV = "TELEGRAM_CHAT_ID"


class TelegramNotifier:
    type = "telegram"

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        only_new: bool = True,
        max_results: int = 20,
        include_errors: bool = True,
        timeout: float = 30,
    ):
        self._token = token
        self._chat_id = chat_id
        self.only_new = only_new
        self.max_results = max_results
        self.include_errors = include_errors
        self.timeout = timeout

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> "TelegramNotifier":
        token = options.get("token") or os.environ.get(TOKEN_ENV)
        chat_id = options.get("chat_id") or os.environ.get(CHAT_ID_ENV)
        if not token or not chat_id:
            raise ValueError(
                f"notificador 'telegram' exige token e chat_id (na config ou em ${TOKEN_ENV} e ${CHAT_ID_ENV})"
            )
        return cls(
            token=str(token),
            chat_id=str(chat_id),
            only_new=options.get("only_new", True),
            max_results=options.get("max_results", 20),
            include_errors=options.get("include_errors", True),
            timeout=options.get("timeout", 30),
        )

    # ---------------------------------------------------------------- envio

    def notify(self, report: SearchReport) -> None:
        for text in self.render(report):
            self._send(text)

    def _send(self, text: str) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(API_URL.format(token=self._token), json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            # a URL da requisição contém o token: nunca deixar vazar para logs
            raise NotifierError(f"falha de rede ao enviar ({type(e).__name__})") from None
        if not response.ok:
            try:
                detail = response.json().get("description", "")
            except ValueError:
                detail = ""
            raise NotifierError(f"API do Telegram respondeu {response.status_code}: {detail}".rstrip(": "))

    # ---------------------------------------------------------- formatação

    def render(self, report: SearchReport) -> list[str]:
        """Monta as mensagens (HTML do Telegram). Lista vazia = nada a enviar."""
        results = report.new_results if self.only_new else report.results
        issues = report.issues_to_alert if self.include_errors else []
        resolved = report.resolved if self.include_errors else []
        if not results and not issues and not resolved:
            return []

        blocks: list[str] = []
        if results:
            shown = results[: self.max_results]
            label = "novas" if self.only_new else "selecionadas"
            blocks.append(f"🔎 <b>{len(results)} vagas {label}</b> ({report.total_fetched} buscadas)")
            blocks += [self._format(r) for r in shown]
            if len(results) > len(shown):
                blocks.append(f"… e mais {len(results) - len(shown)} (veja o relatório local)")
        if issues:
            items = "\n".join(f"• {escape(_cut(str(i), MAX_SUMMARY_LEN))}" for i in issues)
            blocks.append(f"⚠️ <b>busca-vagas: falhas</b>\n{items}\n<i>Só aviso de novo quando resolver.</i>")
        if resolved:
            blocks.append("✅ <b>Voltou a funcionar</b>\n" + "\n".join(f"• {escape(s)}" for s in resolved))
        return _pack(blocks)

    @staticmethod
    def _format(r: ScoredPosting) -> str:
        p = r.posting
        where = " / ".join(x for x in (p.company, p.location) if x)
        lines = [f'<b>[{r.score}]</b> <a href="{escape(p.url, quote=True)}">{escape(p.title)}</a>']
        if where:
            lines.append(escape(where))
        if r.matched:
            lines.append(f"<i>{escape(', '.join(r.matched))}</i>")
        if r.match and r.match.ok:
            if r.match.job_summary:
                lines.append(f"📋 {escape(_cut(r.match.job_summary, MAX_SUMMARY_LEN))}")
            lines.append(f"🤖 {r.match.score}/100 · {escape(_cut(r.match.summary, MAX_SUMMARY_LEN))}")
        return "\n".join(lines)


def _pack(blocks: list[str], limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Agrupa blocos em mensagens de até `limit` caracteres, sem quebrar um bloco ao meio."""
    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit:
            messages.append(current)
            candidate = block
        current = candidate
    if current:
        messages.append(current)
    return messages


def _cut(text: str, size: int) -> str:
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"
