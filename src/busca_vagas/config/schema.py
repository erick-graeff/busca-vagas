"""Formato do arquivo de configuração (JSON), validado com pydantic.

Este schema é o contrato entre quem escreve a config (pessoa, agente de IA ou, no
futuro, o comando `setup`) e quem a usa (`run`). As descrições dos campos viram o
`config.schema.json` (`busca-vagas schema`), que editores e agentes usam para validar
e documentar a config.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from busca_vagas.domain.models import Level

SCHEMA_FILE = "config.schema.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Open(BaseModel):
    """Aceita campos extras: opções específicas de cada adapter."""

    model_config = ConfigDict(extra="allow")

    @property
    def options(self) -> dict:
        return {**self.model_dump(), **(self.model_extra or {})}


class KeywordConfig(_Strict):
    """Palavra-chave: um nome e os termos que a representam."""

    name: str = Field(description="Nome exibido no resultado, ex.: 'Python'.")
    terms: list[str] = Field(
        min_length=1,
        description="Termos que contam como menção. Palavras/expressões inteiras, sem diferenciar "
        "maiúsculas: 'sql' não casa em 'NoSQL', 'java' não casa em 'JavaScript'.",
    )
    weight: int = Field(1, description="Pontos quando algum termo aparece na vaga.")


class MentionBonusConfig(_Strict):
    """Pontos extras por menção adicional de uma palavra obrigatória."""

    points: int = Field(3, description="Pontos por menção extra.")
    cap: int = Field(5, description="Máximo de menções extras que pontuam.")


class FilterConfig(_Strict):
    """Filtro determinístico (sem IA): decide quais vagas passam e a pontuação de cada uma."""

    required: list[KeywordConfig] = Field(
        min_length=1, description="Palavras obrigatórias: a vaga precisa citar ao menos uma."
    )
    keywords: list[KeywordConfig] = Field([], description="Palavras que só somam pontos (ranking).")
    title_include: list[str] = Field(
        [], description="O título precisa citar ao menos um destes. Vazio = aceita qualquer título."
    )
    title_exclude: list[str] = Field([], description="Títulos com qualquer um destes são descartados.")
    stack_exclude: list[str] = Field(
        [],
        description="Stacks indesejadas, procuradas só no título. Ignorado se o título citar uma "
        "palavra obrigatória (ex.: 'Python/Golang' continua valendo).",
    )
    title_bonus: int = Field(2, description="Multiplicador do peso quando o termo aparece no título.")
    mention_bonus: MentionBonusConfig = MentionBonusConfig()


class LevelsConfig(_Strict):
    """Termos que indicam cada nível de senioridade no título. Os padrões cobrem pt/en."""

    junior: list[str] = [
        "junior",
        "júnior",
        "jr",
        "entry",
        "intern",
        "estagiário",
        "estagiária",
        "estagiario",
        "estagiaria",
        "estágio",
        "estagio",
    ]
    pleno: list[str] = [
        "pleno",
        "pl",
        "mid",
        "mid-level",
        "middle",
        "intermediário",
        "intermediario",
        "intermediate",
    ]
    senior: list[str] = ["senior", "sênior", "sr", "snr"]
    master: list[str] = ["master", "lead", "specialist", "principal", "staff"]


class ProfileConfig(_Strict):
    """Perfil de busca, reutilizável entre fontes (ex.: só sênior numa empresa, pleno em outra)."""

    levels: list[Level] = Field([Level.SENIOR], description="Níveis aceitos.")
    countries: list[str] = Field([], description="Códigos de país aceitos, ex.: ['BR']. Vazio = qualquer.")
    remote_only: bool = Field(False, description="Descarta vagas híbridas ou presenciais.")
    accept_unspecified_level: bool = Field(
        True, description="Aceita vagas cujo título não indica senioridade."
    )


class SourceConfig(_Open):
    """Fonte de vagas. Os demais campos dependem do `type`.

    lever: `company` (slug de jobs.lever.co/<company>), `timeout` (s, padrão 30).
    """

    type: str = Field(description="Tipo da fonte. Disponíveis: 'lever'.")
    profile: str = Field(description="Nome de um perfil definido em `profiles`.")


class MatchConfig(_Open):
    """Avaliação de aderência vaga x currículo com IA (usada com --match). Os demais campos
    dependem do `backend`.

    opencode: `model` (padrão 'opencode/deepseek-v4.1-flash-free'; `opencode models` lista os
    disponíveis), `timeout` (s, padrão 180), `binary` (padrão 'opencode').
    """

    backend: str = Field("opencode", description="Backend de IA. Disponíveis: 'opencode'.")
    resume: Path = Field(
        description="Currículo em texto/markdown SEM dados pessoais (nome, contato, links): "
        "ele é enviado para a IA."
    )
    prompt: Path | None = Field(None, description="Prompt próprio. Vazio = prompt padrão do pacote.")


class OutputConfig(_Strict):
    """Saídas sempre acionadas."""

    console: bool = Field(True, description="Lista as vagas no terminal.")
    json_file: Path | None = Field(
        Path("vagas_filtradas.json"), description="Relatório completo da última execução. null = desliga."
    )


class NotifierConfig(_Open):
    """Notificador extra, acionado com --notify. Os demais campos dependem do `type`.

    telegram: `token` e `chat_id` (ou $TELEGRAM_BOT_TOKEN e $TELEGRAM_CHAT_ID, preferível),
    `only_new` (padrão true), `max_results` (padrão 20), `include_errors` (padrão true).
    """

    type: str = Field(description="Tipo do notificador. Disponíveis: 'telegram'.")


class AppConfig(_Strict):
    """Configuração do busca-vagas. Caminhos relativos são resolvidos a partir da pasta do arquivo."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_ref: str | None = Field(
        None, alias="$schema", description="Caminho do JSON Schema (para editores e agentes)."
    )
    data_dir: Path = Field(Path("data"), description="Onde ficam caches e o registro de vagas vistas.")
    filter: FilterConfig
    levels: LevelsConfig = LevelsConfig()
    profiles: dict[str, ProfileConfig] = Field(min_length=1, description="Perfis de busca, por nome.")
    sources: list[SourceConfig] = Field(min_length=1, description="Fontes de vagas.")
    match: MatchConfig | None = None
    output: OutputConfig = OutputConfig()
    notifiers: list[NotifierConfig] = Field([], description="Notificadores acionados com --notify.")

    @model_validator(mode="after")
    def _profiles_exist(self) -> "AppConfig":
        for source in self.sources:
            if source.profile not in self.profiles:
                raise ValueError(
                    f"fonte '{source.type}' usa o perfil '{source.profile}', que não existe em profiles"
                )
        return self


def json_schema() -> dict:
    """JSON Schema da config (o conteúdo de config.schema.json)."""
    schema = AppConfig.model_json_schema(by_alias=True)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema, "title": "busca-vagas"}
