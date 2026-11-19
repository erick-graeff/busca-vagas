"""Match vaga x currículo: monta o prompt, chama a IA, interpreta a resposta e cacheia."""

import hashlib
import json
import re
from dataclasses import asdict

from busca_vagas.application.ports.llm import LLMClient, LLMError
from busca_vagas.application.ports.storage import KeyValueStore
from busca_vagas.domain.models import MatchResult, Posting

CACHE_NAMESPACE = "match"


def build_prompt(posting: Posting, resume: str, template: str) -> str:
    # str.replace (e não .format) porque a descrição e o JSON do template têm chaves.
    values = {
        "{curriculo}": resume,
        "{title}": posting.title,
        "{company}": posting.company,
        "{location}": posting.location,
        "{description}": posting.description.strip(),
    }
    for placeholder, value in values.items():
        template = template.replace(placeholder, value)
    return template


def parse_response(raw: str) -> MatchResult:
    """Extrai o JSON da resposta, tolerando cercas ```json e texto em volta."""
    found = re.search(r"\{.*\}", raw, re.DOTALL)
    if not found:
        return MatchResult(raw=raw, error="resposta sem JSON")
    try:
        data = json.loads(found.group(0))
    except json.JSONDecodeError as e:
        return MatchResult(raw=raw, error=f"JSON inválido: {e}")
    if not isinstance(data, dict):
        return MatchResult(raw=raw, error="JSON não é um objeto")
    return MatchResult(
        score=data.get("score"),
        summary=data.get("summary", ""),
        strengths=data.get("strengths", []),
        gaps=data.get("gaps", []),
        raw=raw,
    )


class MatchJobs:
    def __init__(self, llm: LLMClient, store: KeyValueStore, prompt_template: str, resume: str):
        self._llm = llm
        self._store = store
        self._template = prompt_template
        self._resume = resume

    def match(self, posting: Posting) -> MatchResult:
        prompt = build_prompt(posting, self._resume, self._template)
        # A chave inclui modelo + prompt completo: mudar prompt, currículo ou vaga reavalia.
        key = hashlib.sha256(f"{self._llm.model_id}\n{prompt}".encode()).hexdigest()
        if (cached := self._store.get(CACHE_NAMESPACE, key)) is not None:
            return MatchResult(**cached)
        try:
            result = parse_response(self._llm.complete(prompt))
        except LLMError as e:
            return MatchResult(error=str(e))
        if result.ok:  # falhas não são cacheadas, para serem retentadas
            self._store.set(CACHE_NAMESPACE, key, asdict(result))
        return result
