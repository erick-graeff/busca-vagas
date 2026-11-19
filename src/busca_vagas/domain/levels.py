import re
from collections.abc import Mapping

from busca_vagas.domain.models import Level


def detect_levels(title: str, patterns: Mapping[Level, re.Pattern[str]]) -> set[Level]:
    """Níveis citados no título ('Senior/Pleno' -> {SENIOR, MID}). Vazio = não informado."""
    return {level for level, pattern in patterns.items() if pattern.search(title)}
