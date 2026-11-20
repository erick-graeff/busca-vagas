import json

from busca_vagas.adapters.inbound import cli
from busca_vagas.adapters.outbound import notifiers, sources
from tests.application.fakes import FakeNotifier, FakeSource

GOOD = json.dumps(
    {
        "filter": {"required": [{"name": "P", "terms": ["python"]}]},
        "profiles": {"a": {}},
        "sources": [{"type": "fake", "profile": "a"}],
        "output": {"console": False},
        "notifiers": [{"type": "fake"}],
    }
)


def fake_registry(monkeypatch):
    sent = FakeNotifier()
    monkeypatch.setitem(sources.SOURCE_TYPES, "fake", lambda options: FakeSource([]))
    monkeypatch.setitem(notifiers.NOTIFIER_TYPES, "fake", lambda options: sent)
    return sent


def test_run_log_has_timestamped_header_and_footer(tmp_path, capsys, monkeypatch):
    fake_registry(monkeypatch)
    (cfg := tmp_path / "c.json").write_text(GOOD)
    assert cli.main(["run", "--config", str(cfg)]) == cli.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("=== 20") and "busca-vagas run" in out[0]
    assert out[-2].startswith("=== fim · exit=0 · 0 selecionadas, 0 novas, 0 avisos")


def test_config_error_is_alerted_once_with_notify(tmp_path, capsys, monkeypatch):
    sent = fake_registry(monkeypatch)
    (cfg := tmp_path / "c.json").write_text('{"type": telegram}')  # JSON inválido
    for _ in range(2):
        assert cli.main(["run", "--config", str(cfg), "--notify"]) == cli.EXIT_CONFIG_ERROR
    assert len(sent.reports) == 1  # avisou uma vez só
    assert sent.reports[0].issues_to_alert[0].subject == "configuração"
    assert (tmp_path / "data" / "alerts.json").exists()  # estado ao lado da config
    assert "exit=1" in capsys.readouterr().out


def test_unexpected_error_is_alerted_and_resolved(tmp_path, capsys, monkeypatch):
    sent = fake_registry(monkeypatch)
    (cfg := tmp_path / "c.json").write_text(GOOD)
    from busca_vagas.application.use_cases.search_jobs import SearchJobsService

    original = SearchJobsService.run
    monkeypatch.setattr(SearchJobsService, "run", lambda self, req: 1 / 0)
    assert cli.main(["run", "--config", str(cfg), "--notify"]) == cli.EXIT_UNEXPECTED
    assert "ZeroDivisionError" in capsys.readouterr().err  # traceback no log
    assert sent.reports[-1].issues_to_alert[0].subject == "erro inesperado (ZeroDivisionError)"

    monkeypatch.setattr(SearchJobsService, "run", original)
    assert cli.main(["run", "--config", str(cfg), "--notify"]) == cli.EXIT_OK
    assert sent.reports[-1].resolved == ["erro inesperado (ZeroDivisionError)"]


def test_no_alert_without_notify(tmp_path, monkeypatch):
    sent = fake_registry(monkeypatch)
    (cfg := tmp_path / "c.json").write_text("{")
    assert cli.main(["run", "--config", str(cfg)]) == cli.EXIT_CONFIG_ERROR
    assert sent.reports == []
