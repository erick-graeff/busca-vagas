"""Formato do arquivo de configuração (TOML), validado com pydantic.

Este schema é o contrato entre quem escreve a config (pessoa ou, no futuro,
o comando `setup`) e quem a usa (`run`).
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from busca_vagas.domain.models import Level


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Open(BaseModel):
    """Aceita campos extras: opções específicas de cada adapter."""

    model_config = ConfigDict(extra="allow")

    @property
    def options(self) -> dict:
        return {**self.model_dump(), **(self.model_extra or {})}


class KeywordConfig(_Strict):
    name: str
    terms: list[str] = Field(min_length=1)
    weight: int = 1


class MentionBonusConfig(_Strict):
    points: int = 3
    cap: int = 5


class FilterConfig(_Strict):
    required: list[KeywordConfig] = Field(min_length=1)
    keywords: list[KeywordConfig] = []
    title_include: list[str] = []
    title_exclude: list[str] = []
    stack_exclude: list[str] = []
    title_bonus: int = 2
    mention_bonus: MentionBonusConfig = MentionBonusConfig()


class LevelsConfig(_Strict):
    """Termos que indicam cada nível no título. Os padrões cobrem pt/en."""

    junior: list[str] = ["junior", "júnior", "jr", "entry", "intern", "estagiário", "estagiária",
                         "estagiario", "estagiaria", "estágio", "estagio"]
    pleno: list[str] = ["pleno", "pl", "mid", "mid-level", "middle", "intermediário",
                        "intermediario", "intermediate"]
    senior: list[str] = ["senior", "sênior", "sr", "snr"]
    master: list[str] = ["master", "lead", "specialist", "principal", "staff"]


class ProfileConfig(_Strict):
    levels: list[Level] = [Level.SENIOR]
    countries: list[str] = []
    remote_only: bool = False
    accept_unspecified_level: bool = True


class SourceConfig(_Open):
    type: str
    profile: str


class MatchConfig(_Open):
    backend: str = "opencode"
    resume: Path  # currículo SEM dados pessoais: é enviado para a IA
    prompt: Path | None = None  # None = prompt padrão do pacote


class OutputConfig(_Strict):
    console: bool = True
    json_file: Path | None = Path("vagas_filtradas.json")


class NotifierConfig(_Open):
    type: str


class AppConfig(_Strict):
    data_dir: Path = Path("data")
    filter: FilterConfig
    levels: LevelsConfig = LevelsConfig()
    profiles: dict[str, ProfileConfig] = Field(min_length=1)
    sources: list[SourceConfig] = Field(min_length=1)
    match: MatchConfig | None = None
    output: OutputConfig = OutputConfig()
    notifiers: list[NotifierConfig] = []

    @model_validator(mode="after")
    def _profiles_exist(self) -> "AppConfig":
        for source in self.sources:
            if source.profile not in self.profiles:
                raise ValueError(
                    f"fonte '{source.type}' usa o perfil '{source.profile}', que não existe em [profiles]"
                )
        return self
