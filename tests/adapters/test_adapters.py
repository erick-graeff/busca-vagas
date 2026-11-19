import json

from busca_vagas.adapters.outbound.llm.opencode_cli import OpencodeCLI
from busca_vagas.adapters.outbound.sources.cached import CachedSource
from busca_vagas.adapters.outbound.storage.json_store import JsonStore
from tests.application.fakes import FakeSource
from tests.conftest import make_posting


def test_lever_parse(ciandt_postings, lever_raw):
    p = ciandt_postings[0]
    assert p.source == "lever" and p.company == "ciandt"
    assert p.id == lever_raw[0]["id"]
    assert p.key == f"lever:ciandt:{lever_raw[0]['id']}"
    assert p.workplace_type == "remote" and p.country == "BR"
    assert p.description == lever_raw[0]["descriptionBodyPlain"]


def test_opencode_extract_text():
    stdout = "\n".join(
        [
            json.dumps({"type": "step_start"}),
            json.dumps({"type": "text", "part": {"text": '{"score":'}}),
            json.dumps({"type": "text", "part": {"text": " 1}"}}),
            "lixo não-json",
            json.dumps({"type": "step_finish"}),
        ]
    )
    assert OpencodeCLI._extract_text(stdout) == '{"score": 1}'


def test_json_store_roundtrip(tmp_path):
    JsonStore(tmp_path).set("seen", "k", {"first_seen": "x"})
    store = JsonStore(tmp_path)  # nova instância lê do disco
    assert store.has("seen", "k") and store.get("seen", "k") == {"first_seen": "x"}
    assert not store.has("seen", "outra")
    assert [p.name for p in tmp_path.iterdir()] == ["seen.json"]  # sem temporários sobrando


def test_cached_source(tmp_path):
    store = JsonStore(tmp_path)
    CachedSource(FakeSource([make_posting()]), store).fetch()  # popula o cache

    offline = FakeSource([], fail=True)  # se consultar a fonte, falha
    assert CachedSource(offline, store).fetch() == [make_posting()]

    fresh = FakeSource([make_posting(id="2")])
    assert [p.id for p in CachedSource(fresh, store, refresh=True).fetch()] == ["2"]
