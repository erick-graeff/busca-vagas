from pathlib import Path

import pytest

from busca_vagas.bootstrap import build_search
from busca_vagas.config.loader import ConfigError, load_config

ROOT = Path(__file__).parent.parent


def test_example_config_is_valid():
    config = load_config(ROOT / "config.example.toml")
    assert config.sources[0].type == "lever"
    assert config.match.resume == ROOT / "curriculo.md"  # relativo à pasta da config
    build_search(config)  # monta sem match (não exige currículo)


def test_unknown_profile(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[filter]\n[[filter.required]]\nname="P"\nterms=["python"]\n'
        "[profiles.a]\n"
        '[[sources]]\ntype="lever"\ncompany="x"\nprofile="b"\n'
    )
    with pytest.raises(ConfigError, match="perfil 'b'"):
        load_config(cfg)


def test_unknown_source_type(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[filter]\n[[filter.required]]\nname="P"\nterms=["python"]\n'
        "[profiles.a]\n"
        '[[sources]]\ntype="indeed"\nprofile="a"\n'
    )
    with pytest.raises(ConfigError, match="tipo de fonte 'indeed' desconhecido"):
        build_search(load_config(cfg))


def test_match_requires_resume(tmp_path):
    config = load_config(ROOT / "config.example.toml")
    config.match.resume = tmp_path / "nao_existe.md"
    with pytest.raises(ConfigError, match="currículo não encontrado"):
        build_search(config, match=True)
