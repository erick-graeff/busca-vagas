"""Composition root: o ÚNICO módulo que conhece os adapters concretos.

Lê a configuração, instancia os adapters e injeta tudo nos casos de uso.
"""

from importlib import resources

from busca_vagas.adapters.outbound.llm import LLM_BACKENDS
from busca_vagas.adapters.outbound.notifiers import NOTIFIER_TYPES
from busca_vagas.adapters.outbound.notifiers.console import ConsoleNotifier
from busca_vagas.adapters.outbound.notifiers.json_file import JsonFileNotifier
from busca_vagas.adapters.outbound.sources import SOURCE_TYPES
from busca_vagas.adapters.outbound.sources.cached import CachedSource
from busca_vagas.adapters.outbound.storage.json_store import JsonStore
from busca_vagas.application.ports.notifier import Notifier
from busca_vagas.application.use_cases.match_jobs import MatchJobs
from busca_vagas.application.use_cases.search_jobs import SearchJobsService, SourceSpec
from busca_vagas.config.loader import ConfigError, to_profile, to_rules
from busca_vagas.config.schema import AppConfig, MatchConfig


def _registered(registry: dict, kind: str, type_: str):
    if type_ not in registry:
        available = ", ".join(sorted(registry)) or "nenhum"
        raise ConfigError(f"{kind} '{type_}' desconhecido (disponíveis: {available})")
    return registry[type_]


def _build_matcher(cfg: MatchConfig | None, store: JsonStore, model: str | None) -> MatchJobs:
    if cfg is None:
        raise ConfigError("--match exige a seção [match] na configuração")
    if not cfg.resume.exists():
        raise ConfigError(f"currículo não encontrado: {cfg.resume}")
    options = cfg.options
    if model:
        options["model"] = model
    llm = _registered(LLM_BACKENDS, "backend de IA", cfg.backend)(options)
    if cfg.prompt:
        if not cfg.prompt.exists():
            raise ConfigError(f"prompt não encontrado: {cfg.prompt}")
        template = cfg.prompt.read_text(encoding="utf-8")
    else:
        template = resources.files("busca_vagas.prompts").joinpath("match.md").read_text("utf-8")
    return MatchJobs(llm, store, template, cfg.resume.read_text(encoding="utf-8"))


def build_search(
    config: AppConfig, *, refresh: bool = False, match: bool = False, model: str | None = None
) -> SearchJobsService:
    store = JsonStore(config.data_dir)

    sources = []
    for src in config.sources:
        factory = _registered(SOURCE_TYPES, "tipo de fonte", src.type)
        try:
            source = factory(src.options)
        except ValueError as e:
            raise ConfigError(str(e)) from e
        sources.append(
            SourceSpec(CachedSource(source, store, refresh=refresh), to_profile(config.profiles[src.profile]))
        )

    reporters: list[Notifier] = []
    if config.output.console:
        reporters.append(ConsoleNotifier())
    if config.output.json_file:
        reporters.append(JsonFileNotifier(config.output.json_file))

    notifiers = [
        _registered(NOTIFIER_TYPES, "notificador", n.type)(n.options) for n in config.notifiers
    ]

    return SearchJobsService(
        sources=sources,
        rules=to_rules(config.filter, config.levels),
        store=store,
        reporters=reporters,
        notifiers=notifiers,
        matcher=_build_matcher(config.match, store, model) if match else None,
    )
