"""Fonte Lever (api.lever.co): API pública de vagas por empresa."""

from collections.abc import Mapping
from typing import Any

import requests

from busca_vagas.application.ports.sources import SourceError
from busca_vagas.domain.models import Posting

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


class LeverSource:
    type = "lever"

    def __init__(self, company: str, timeout: float = 30):
        self.company = company
        self.timeout = timeout

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> "LeverSource":
        if not options.get("company"):
            raise ValueError("fonte 'lever' exige o campo 'company' (slug em jobs.lever.co/<company>)")
        return cls(company=options["company"], timeout=options.get("timeout", 30))

    @property
    def name(self) -> str:
        return f"{self.type}:{self.company}"

    def fetch(self) -> list[Posting]:
        url = API_URL.format(company=self.company)
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            items = response.json()
        except (requests.RequestException, ValueError) as e:
            raise SourceError(f"falha ao consultar {url}: {e}") from e
        if not isinstance(items, list):
            raise SourceError(f"resposta inesperada de {url}")
        return [self.parse(item) for item in items]

    def parse(self, item: Mapping[str, Any]) -> Posting:
        cats = item.get("categories") or {}
        return Posting(
            source=self.type,
            company=self.company,
            id=str(item.get("id", "")),
            title=item.get("text", ""),
            url=item.get("hostedUrl", ""),
            apply_url=item.get("applyUrl", ""),
            country=item.get("country") or "",
            location=cats.get("location") or "",
            team=cats.get("team") or "",
            workplace_type=item.get("workplaceType") or "",
            # descriptionBodyPlain = corpo da vaga, sem o texto institucional ("opening")
            # nem os benefícios ("additional"), que só geram ruído no filtro.
            description=item.get("descriptionBodyPlain") or item.get("descriptionPlain") or "",
        )
