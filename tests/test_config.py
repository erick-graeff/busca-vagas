import json
from pathlib import Path

import pytest

from busca_vagas.bootstrap import build_search
from busca_vagas.config.loader import ConfigError, load_config

ROOT = Path(__file__).parent.parent
BASE = {"filter": {"required": [{"name": "P", "terms": ["python"]}]}, "profiles": {"a": {}}}


def write(tmp_path, **overrides) -> Path:
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({**BASE, **overrides}))
    return cfg


def test_example_config_is_valid():
    config = load_config(ROOT / "config.example.json")
    assert config.sources[0].type == "lever"
    assert config.match.resume == ROOT / "curriculo.md"  # relativo à pasta da config
    build_search(config)  # monta sem match (não exige currículo)


def test_unknown_profile(tmp_path):
    cfg = write(tmp_path, sources=[{"type": "lever", "company": "x", "profile": "b"}])
    with pytest.raises(ConfigError, match="perfil 'b'"):
        load_config(cfg)


def test_unknown_source_type(tmp_path):
    cfg = write(tmp_path, sources=[{"type": "indeed", "profile": "a"}])
    with pytest.raises(ConfigError, match="tipo de fonte 'indeed' desconhecido"):
        build_search(load_config(cfg))


def test_match_requires_resume(tmp_path):
    config = load_config(ROOT / "config.example.json")
    config.match.resume = tmp_path / "nao_existe.md"
    with pytest.raises(ConfigError, match="currículo não encontrado"):
        build_search(config, match=True)


def test_telegram_credentials_only_required_with_notify(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    cfg = write(
        tmp_path, sources=[{"type": "lever", "company": "x", "profile": "a"}], notifiers=[{"type": "telegram"}]
    )
    config = load_config(cfg)
    build_search(config)  # sem --notify, não exige credenciais
    with pytest.raises(ConfigError, match="token e chat_id"):
        build_search(config, notify=True)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    build_search(config, notify=True)


def test_invalid_json_points_to_line(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text('{\n  "data_dir": "data",\n  "filter": {,}\n}')
    with pytest.raises(ConfigError, match="JSON inválido na linha 3"):
        load_config(cfg)


def test_schema_file_is_up_to_date():
    from busca_vagas.config.schema import json_schema

    committed = json.loads((ROOT / "config.schema.json").read_text(encoding="utf-8"))
    assert committed == json_schema(), "rode: uv run busca-vagas schema > config.schema.json"
