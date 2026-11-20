import hashlib

from busca_vagas.application.use_cases.match_jobs import MatchJobs, build_prompt, parse_response
from tests.application.fakes import FakeLLM, InMemoryStore
from tests.conftest import make_posting


def test_parse_response_tolerates_fences_and_text():
    r = parse_response(
        'Claro!\n```json\n{"score": 72, "job_summary": "API em Python", '
        '"summary": "bom", "gaps": ["k8s"]}\n```'
    )
    assert (r.score, r.job_summary, r.summary, r.gaps, r.ok) == (72, "API em Python", "bom", ["k8s"], True)


def test_parse_response_errors():
    assert parse_response("sem json").error == "resposta sem JSON"
    assert parse_response("{invalido}").error.startswith("JSON inválido")


def test_build_prompt_keeps_braces_from_description():
    p = make_posting(description='use {"a": 1}')
    assert (
        build_prompt(p, "cv", "{curriculo}|{title}|{description}")
        == 'cv|Senior Python Developer|use {"a": 1}'
    )


def test_cache_hit_skips_llm_and_key_is_compatible_with_prototype():
    store, llm = InMemoryStore(), FakeLLM()
    matcher = MatchJobs(llm, store, "{title}", "cv")
    matcher.match(make_posting())
    matcher.match(make_posting())
    assert len(llm.calls) == 1
    # mesma chave do protótipo: sha256(modelo + "\n" + prompt) -> o cache antigo continua válido
    expected_key = hashlib.sha256(b"fake/model\nSenior Python Developer").hexdigest()
    assert store.has("match", expected_key)


def test_failures_are_not_cached():
    store = InMemoryStore()
    MatchJobs(FakeLLM(response="nada"), store, "{title}", "cv").match(make_posting())
    assert store.data.get("match", {}) == {}
