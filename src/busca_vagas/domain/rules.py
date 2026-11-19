"""Regras do filtro como dados. Os valores vêm da configuração; aqui só a forma."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from busca_vagas.domain.models import Level


def word_pattern(terms: Iterable[str]) -> re.Pattern[str] | None:
    """Regex case-insensitive que casa qualquer um dos termos como palavra inteira.

    Usa lookarounds em vez de `\\b` para tratar `+` e `#` como parte da palavra:
    não casa 'SQL' em 'NoSQL'/'PostgreSQL', 'Java' em 'JavaScript', nem 'C' em 'C#'.
    Retorna None se não houver termos.
    """
    terms = [t for t in terms if t]
    if not terms:
        return None
    # termos mais longos primeiro, para 'aws lambda' ganhar de 'aws' na alternância
    alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(rf"(?<![\w+#])(?:{alternatives})(?![\w+#])", re.IGNORECASE)


@dataclass(frozen=True)
class Keyword:
    name: str
    terms: tuple[str, ...]
    weight: int
    pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        pattern = word_pattern(self.terms)
        if pattern is None:
            raise ValueError(f"keyword '{self.name}' sem termos")
        object.__setattr__(self, "pattern", pattern)


@dataclass(frozen=True)
class MentionBonus:
    """Pontos extras por menção adicional de uma palavra obrigatória."""

    points: int = 3
    cap: int = 5  # número máximo de menções extras que pontuam


@dataclass(frozen=True)
class FilterRules:
    required: tuple[Keyword, ...]  # a vaga precisa citar ao menos uma
    keywords: tuple[Keyword, ...] = ()  # só pontuam
    title_include: re.Pattern[str] | None = None  # se definido, o título precisa casar
    title_exclude: re.Pattern[str] | None = None
    stack_exclude: re.Pattern[str] | None = None  # ignorado se o título citar uma obrigatória
    level_patterns: Mapping[Level, re.Pattern[str]] = field(default_factory=dict)
    title_bonus: int = 2  # multiplicador quando a palavra aparece no título
    mention_bonus: MentionBonus = MentionBonus()


@dataclass(frozen=True)
class SearchProfile:
    """Critérios que podem variar por fonte/empresa."""

    levels: frozenset[Level] = frozenset({Level.SENIOR})
    countries: frozenset[str] = frozenset()  # vazio = qualquer país
    remote_only: bool = False
    accept_unspecified_level: bool = True
