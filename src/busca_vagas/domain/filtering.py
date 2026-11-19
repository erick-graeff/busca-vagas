"""Filtro determinístico de vagas. Funções puras, parametrizadas por FilterRules/SearchProfile."""

from busca_vagas.domain.levels import detect_levels
from busca_vagas.domain.models import Posting, ScoredPosting
from busca_vagas.domain.rules import FilterRules, SearchProfile

_NOT_REMOTE = {"hybrid", "onsite", "on-site"}


def passes_profile(posting: Posting, profile: SearchProfile, rules: FilterRules) -> bool:
    """País, modalidade e senioridade. Campos desconhecidos (vazios) não reprovam."""
    if profile.countries and posting.country.upper() not in profile.countries:
        return False
    if profile.remote_only and posting.workplace_type.lower() in _NOT_REMOTE:
        return False
    levels = detect_levels(posting.title, rules.level_patterns)
    if not levels:
        return profile.accept_unspecified_level
    return bool(levels & profile.levels)


def score(posting: Posting, rules: FilterRules) -> ScoredPosting | None:
    """Pontua a vaga, ou None se ela não passar nas regras de título/stack/palavra obrigatória."""
    title = posting.title
    if rules.title_include and not rules.title_include.search(title):
        return None
    if rules.title_exclude and rules.title_exclude.search(title):
        return None

    required_in_title = any(kw.pattern.search(title) for kw in rules.required)
    if rules.stack_exclude and rules.stack_exclude.search(title) and not required_in_title:
        return None

    text = posting.searchable_text
    total = 0
    matched: list[str] = []
    title_matched: list[str] = []

    for kw in rules.required:
        mentions = len(kw.pattern.findall(text))
        if mentions == 0:
            continue
        in_title = bool(kw.pattern.search(title))
        extra = min(mentions - 1, rules.mention_bonus.cap) * rules.mention_bonus.points
        total += (kw.weight + extra) * (rules.title_bonus if in_title else 1)
        matched.append(f"{kw.name} x{mentions}")
        if in_title:
            title_matched.append(kw.name)

    if not matched:  # nenhuma palavra obrigatória
        return None

    for kw in rules.keywords:
        in_title = bool(kw.pattern.search(title))
        if not (in_title or kw.pattern.search(text)):
            continue
        total += kw.weight * (rules.title_bonus if in_title else 1)
        matched.append(kw.name)
        if in_title:
            title_matched.append(kw.name)

    return ScoredPosting(posting=posting, score=total, matched=matched, title_matched=title_matched)


def rank(results: list[ScoredPosting]) -> list[ScoredPosting]:
    return sorted(results, key=lambda s: (-s.score, s.posting.title))
