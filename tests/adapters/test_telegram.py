from datetime import datetime

import pytest
import requests

from busca_vagas.adapters.outbound.notifiers import telegram
from busca_vagas.adapters.outbound.notifiers.telegram import TelegramNotifier, _pack
from busca_vagas.application.ports.inbound import Issue, SearchReport
from busca_vagas.application.ports.notifier import NotifierError
from busca_vagas.domain.models import MatchResult, ScoredPosting
from tests.conftest import make_posting

TOKEN = "123:SEGREDO"


def scored(id_, title="Dev <Python> & AWS", score=30, match=None):
    return ScoredPosting(
        posting=make_posting(id=id_, title=title),
        score=score,
        matched=["Python x2"],
        title_matched=True,
        match=match,
    )


def report(results, new=None, errors=()):
    keys = {r.posting.key for r in results} if new is None else {r.posting.key for r in new}
    return SearchReport(
        generated_at=datetime(2026, 11, 19),
        total_fetched=100,
        results=results,
        new_keys=frozenset(keys),
        errors=list(errors),
    )


def notifier(**kw):
    return TelegramNotifier(TOKEN, "42", **kw)


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self.ok, self._body = status, status < 400, body or {"ok": True}

    def json(self):
        return self._body


def test_from_options_reads_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    n = TelegramNotifier.from_options({"max_results": 5})
    assert n._token == TOKEN and n._chat_id == "42" and n.max_results == 5


def test_from_options_requires_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(ValueError, match="token e chat_id"):
        TelegramNotifier.from_options({})


def test_render_only_new_and_escapes_html():
    a, b = scored("a"), scored("b")
    a.match = MatchResult(score=80, job_summary="Backend <APIs>", summary="bom <fit>")
    [msg] = notifier().render(report([a, b], new=[a]))
    assert "1 vagas novas" in msg
    assert "Dev &lt;Python&gt; &amp; AWS" in msg and "bom &lt;fit&gt;" in msg
    assert "📋 Backend &lt;APIs&gt;" in msg and "🤖 80/100" in msg
    assert msg.count("<a href=") == 1


def test_render_nothing_new_sends_nothing():
    assert notifier().render(report([scored("a")], new=[])) == []
    down = [Issue("lever:x", "fora <do ar>")]
    assert notifier(include_errors=False).render(report([], errors=down)) == []
    [msg] = notifier().render(report([], errors=down))
    assert "falhas" in msg and "lever:x: fora &lt;do ar&gt;" in msg
    assert "🔎" not in msg  # sem vagas, sem cabeçalho de vagas


def test_render_only_unalerted_issues_and_resolved():
    r = report([], errors=[Issue("lever:x", "fora")])
    r.new_issues = []  # já avisada antes
    assert notifier().render(r) == []
    r.resolved = ["match lever:x:1"]
    [msg] = notifier().render(r)
    assert "Voltou a funcionar" in msg and "match lever:x:1" in msg and "fora" not in msg


def test_render_max_results():
    [msg] = notifier(max_results=2).render(report([scored(str(i)) for i in range(5)]))
    assert msg.count("<a href=") == 2 and "e mais 3" in msg


def test_pack_respects_limit():
    msgs = _pack(["x" * 40] * 10, limit=100)
    assert all(len(m) <= 100 for m in msgs) and sum(m.count("x" * 40) for m in msgs) == 10


def test_notify_posts_html(monkeypatch):
    calls = []
    monkeypatch.setattr(
        telegram.requests, "post", lambda url, json, timeout: calls.append((url, json)) or FakeResponse()
    )
    notifier().notify(report([scored("a")]))
    [(url, payload)] = calls
    assert url.endswith(f"/bot{TOKEN}/sendMessage")
    assert payload["chat_id"] == "42" and payload["parse_mode"] == "HTML"


def test_notify_api_error(monkeypatch):
    monkeypatch.setattr(
        telegram.requests, "post", lambda *a, **k: FakeResponse(400, {"description": "chat not found"})
    )
    with pytest.raises(NotifierError, match="400: chat not found"):
        notifier().notify(report([scored("a")]))


def test_network_error_does_not_leak_token(monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError(f"falhou em {url}")

    monkeypatch.setattr(telegram.requests, "post", boom)
    with pytest.raises(NotifierError) as exc:
        notifier().notify(report([scored("a")]))
    assert TOKEN not in str(exc.value) and exc.value.__cause__ is None
