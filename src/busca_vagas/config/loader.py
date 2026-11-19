"""Lê o TOML, valida e converte para os tipos do domínio."""

import tomllib
from pathlib import Path

from pydantic import ValidationError

from busca_vagas.config.schema import AppConfig, FilterConfig, LevelsConfig, ProfileConfig
from busca_vagas.domain.models import Level
from busca_vagas.domain.rules import FilterRules, Keyword, MentionBonus, SearchProfile, word_pattern


class ConfigError(Exception):
    pass


def load_config(path: Path) -> AppConfig:
    """Carrega a config. Caminhos relativos são resolvidos a partir da pasta do arquivo
    (assim o cron funciona de qualquer diretório)."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"arquivo de configuração não encontrado: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: TOML inválido: {e}") from e
    try:
        config = AppConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"{path}: configuração inválida:\n{e}") from e
    return _resolve_paths(config, path.parent.resolve())


def _resolve_paths(config: AppConfig, base: Path) -> AppConfig:
    def resolve(p: Path | None) -> Path | None:
        return p if p is None or p.is_absolute() else base / p

    config.data_dir = resolve(config.data_dir)
    config.output.json_file = resolve(config.output.json_file)
    if config.match:
        config.match.resume = resolve(config.match.resume)
        config.match.prompt = resolve(config.match.prompt)
    return config


def to_rules(filter_cfg: FilterConfig, levels_cfg: LevelsConfig) -> FilterRules:
    def keywords(items) -> tuple[Keyword, ...]:
        return tuple(Keyword(k.name, tuple(k.terms), k.weight) for k in items)

    level_terms = {
        Level.JUNIOR: levels_cfg.junior,
        Level.MID: levels_cfg.pleno,
        Level.SENIOR: levels_cfg.senior,
        Level.MASTER: levels_cfg.master,
    }
    return FilterRules(
        required=keywords(filter_cfg.required),
        keywords=keywords(filter_cfg.keywords),
        title_include=word_pattern(filter_cfg.title_include),
        title_exclude=word_pattern(filter_cfg.title_exclude),
        stack_exclude=word_pattern(filter_cfg.stack_exclude),
        level_patterns={lvl: p for lvl, terms in level_terms.items() if (p := word_pattern(terms))},
        title_bonus=filter_cfg.title_bonus,
        mention_bonus=MentionBonus(filter_cfg.mention_bonus.points, filter_cfg.mention_bonus.cap),
    )


def to_profile(profile_cfg: ProfileConfig) -> SearchProfile:
    return SearchProfile(
        levels=frozenset(profile_cfg.levels),
        countries=frozenset(c.upper() for c in profile_cfg.countries),
        remote_only=profile_cfg.remote_only,
        accept_unspecified_level=profile_cfg.accept_unspecified_level,
    )
