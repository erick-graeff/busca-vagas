import json
from pathlib import Path

import pytest
import requests

from busca_vagas.adapters.outbound.sources.lever import LeverSource
from busca_vagas.config.loader import load_config, to_profile, to_rules
from busca_vagas.domain.models import Posting

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_from_outside(monkeypatch):
    """Testes nunca falam com o mundo real: sem credenciais do ambiente e sem rede.

    Sem isso, um teste de erro de config montava o Telegram com as variáveis do shell do
    desenvolvedor e mandava mensagem de verdade.
    """
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "BUSCA_VAGAS_CONFIG"):
        monkeypatch.delenv(var, raising=False)

    def no_network(self, method, url, *args, **kwargs):
        raise RuntimeError(f"teste tentou acessar a rede: {method} {url.split('/bot')[0]}")

    monkeypatch.setattr(requests.Session, "request", no_network)


@pytest.fixture(scope="session")
def test_config():
    return load_config(FIXTURES / "config_test.json")


@pytest.fixture(scope="session")
def rules(test_config):
    return to_rules(test_config.filter, test_config.levels)


@pytest.fixture(scope="session")
def profile(test_config):
    return to_profile(test_config.profiles["ciandt"])


@pytest.fixture(scope="session")
def lever_raw() -> list[dict]:
    return json.loads((FIXTURES / "lever_ciandt_sample.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def ciandt_postings(lever_raw) -> list[Posting]:
    source = LeverSource("ciandt")
    return [source.parse(item) for item in lever_raw]


@pytest.fixture(scope="session")
def baseline() -> dict:
    """Resultado do protótipo original (antes da refatoração) para cada vaga da fixture."""
    return json.loads((FIXTURES / "baseline_ciandt.json").read_text(encoding="utf-8"))


def make_posting(**overrides) -> Posting:
    defaults = dict(
        source="fake",
        company="acme",
        id="1",
        title="Senior Python Developer",
        url="https://example.com/1",
        country="BR",
        workplace_type="remote",
        description="Python, AWS, SQL",
    )
    return Posting(**{**defaults, **overrides})
