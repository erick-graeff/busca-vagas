# busca-vagas

Busca vagas em fontes configuráveis, aplica um **filtro determinístico** por palavras-chave e,
opcionalmente, pede a uma IA (via [opencode](https://opencode.ai)) uma avaliação de aderência entre
cada vaga e o seu currículo. Pensado para rodar no cron e avisar só das vagas novas.

Fontes suportadas hoje: **Lever** (qualquer empresa em `jobs.lever.co/<empresa>`).

## Instalação

Requisitos: Python ≥ 3.13, [uv](https://docs.astral.sh/uv/) e, só para `--match`,
o [opencode](https://opencode.ai) no `PATH`.

```bash
uv sync
cp config.example.toml config.toml        # ajuste ao seu perfil
cp examples/curriculo.example.md curriculo.md   # só se for usar --match
```

## Uso

```bash
uv run busca-vagas run                    # usa o cache, filtra e lista
uv run busca-vagas run --refresh          # consulta as fontes de novo
uv run busca-vagas run --match            # avalia as vagas filtradas com IA
uv run busca-vagas run --new-only         # só vagas ainda não vistas
uv run busca-vagas run --match --model opencode/big-pickle
```

| Flag         | Descrição                                                                    |
| ------------ | ---------------------------------------------------------------------------- |
| `--config`   | Arquivo de config (padrão: `$BUSCA_VAGAS_CONFIG` ou `./config.toml`).         |
| `--refresh`  | Ignora o cache e consulta as fontes. Sem cache, a fonte é consultada sempre. |
| `--new-only` | Mostra só vagas que ainda não apareceram em execuções anteriores.             |
| `--match`    | Avalia as vagas filtradas com IA (resultado em cache).                       |
| `--model`    | Sobrescreve o modelo de `[match]` (`opencode models` lista os disponíveis).  |
| `--notify`   | Aciona os notificadores extras de `[[notifiers]]` (ex.: Telegram).           |

Códigos de saída: `0` ok · `1` erro de configuração · `2` executou com falhas parciais
(fonte fora do ar, erro da IA), com avisos no stderr.

### Cron

```cron
0 8,13,18 * * 1-5  /caminho/busca-vagas/.venv/bin/busca-vagas run --config /caminho/busca-vagas/config.toml --refresh --new-only --match --notify >> /caminho/busca-vagas/data/cron.log 2>&1
```

Caminhos relativos da config são resolvidos a partir da pasta do arquivo, então o cron funciona
de qualquer diretório. Uma vaga só é marcada como vista depois de avaliada com sucesso. Se a IA
falhar, ela volta na próxima execução.

## Configuração

Tudo fica no `config.toml`. O [`config.example.toml`](config.example.toml) é comentado; o resumo:

```toml
data_dir = "data"                    # caches e vagas vistas

[filter]
title_include = ["developer", "engineer", "software"]   # o título precisa citar um
title_exclude = ["devops", "qa", "manager"]             # descarta o título
stack_exclude = ["java", ".net"]     # descarta, a menos que o título cite uma obrigatória

[[filter.required]]                  # a vaga precisa citar ao menos uma
name = "Python"
terms = ["python"]
weight = 10

[[filter.keywords]]                  # só pontuam
name = "AWS"
terms = ["aws", "amazon web services"]
weight = 5

[profiles.senior_remoto_br]          # perfis reutilizáveis entre fontes
levels = ["senior"]                  # junior | pleno | senior | master
countries = ["BR"]
remote_only = true

[[sources]]
type = "lever"
company = "ciandt"
profile = "senior_remoto_br"

[match]
backend = "opencode"
model = "opencode/deepseek-v4.1-flash-free"
resume = "curriculo.md"
```

Os termos são palavras inteiras, sem diferenciar maiúsculas: `sql` não casa em "NoSQL", `java`
não casa em "JavaScript".

### Como a vaga é pontuada

1. **Perfil da fonte:** país, modalidade (remoto) e senioridade detectada no título. Campos que a
   fonte não informa não reprovam a vaga.
2. **Título:** precisa casar `title_include` e não casar `title_exclude` nem `stack_exclude`.
3. **Palavras obrigatórias:** pelo menos uma no título ou na descrição.
4. **Pontuação:** peso de cada termo encontrado, mais `mention_bonus` por menção extra das
   obrigatórias. Termos no título valem `title_bonus` vezes mais.

## Arquitetura

Hexagonal (ports & adapters). O núcleo não conhece nenhuma fonte, IA, armazenamento ou
canal de notificação: só as **portas** (interfaces) que eles implementam.

```
 ENTRADA                       NÚCLEO                                SAÍDA
                ┌─────────────────────────────────────────┐
 ┌─────────┐    │ application/ports/inbound  SearchJobs   │
 │ cli.py  │───▶│        ▲                                │
 └─────────┘    │ use_cases/search_jobs.py ──────────────────▶ JobSource  ◀── LeverSource, CachedSource
 ┌─────────┐    │        │                                │
 │ setup   │    │ use_cases/match_jobs.py ───────────────────▶ LLMClient  ◀── OpencodeCLI
 │ (futuro)│    │        │                                │
 └─────────┘    │        ▼                         ──────────▶ KeyValueStore ◀── JsonStore
                │ domain/ (puro): Posting, regras,  ──────────▶ Notifier   ◀── Console, JsonFile
                │ filtro, níveis                          │                    (Telegram: futuro)
                └─────────────────────────────────────────┘
 config.toml ─▶ config/loader ─▶ bootstrap.py (único que conhece os adapters concretos)
```

As dependências apontam sempre para dentro: `adapters → application → domain`. O teste
`tests/test_architecture.py` garante isso.

### Pipeline (`application/use_cases/search_jobs.py`)

```
 [1] fetch          cada fonte da config (com cache, a menos que --refresh)
 [2] dedupe         por Posting.key = "fonte:empresa:id"
 [3] perfil         país · remoto · senioridade
 [4] regras         título · stacks · palavra obrigatória · pontuação
 [5] novas?         --new-only: descarta as já vistas
 [6] match IA       --match: prompt + currículo → LLMClient → JSON (com cache)
 [7] marcar vistas  com match ativo, só as avaliadas com sucesso
 [8] report         console + arquivo JSON (sempre)
 [9] notify         --notify: notificadores extras
```

### Estrutura

```
src/busca_vagas/
├── domain/                  # entidades e regras puras (sem I/O)
├── application/
│   ├── ports/               # interfaces: inbound, sources, llm, storage, notifier
│   └── use_cases/           # search_jobs (pipeline), match_jobs
├── adapters/
│   ├── inbound/cli.py
│   └── outbound/            # sources/, llm/, storage/, notifiers/ (cada um com registro)
├── config/                  # schema (pydantic) e loader (TOML → domínio)
├── bootstrap.py             # composition root
└── prompts/match.md         # prompt padrão do match
```

## Estendendo

Cada extensão é um módulo novo, mais uma linha no registro do pacote correspondente.

| Quero adicionar...           | Implemente a porta                   | Registre em                              |
| ---------------------------- | ------------------------------------ | ---------------------------------------- |
| Fonte (Greenhouse, Ashby...) | `JobSource` (`name`, `fetch()`)      | `adapters/outbound/sources/__init__.py`  |
| IA (Claude, Ollama...)       | `LLMClient` (`model_id`, `complete`) | `adapters/outbound/llm/__init__.py`      |
| Notificação (Telegram...)    | `Notifier` (`notify(report)`)        | `adapters/outbound/notifiers/__init__.py`|

Cada classe recebe as opções do seu bloco na config via `from_options(dict)`. Por exemplo,
`[[sources]] type = "greenhouse"` com `board = "..."`.

## Privacidade

- O currículo enviado à IA é o arquivo de `[match].resume`. **Remova dele nome, contatos e links.**
  Os modelos gratuitos do opencode rodam num serviço externo.
- O opencode roda numa pasta temporária, então o agente não enxerga os arquivos do projeto.
- `config.toml`, `data/`, `curriculo*` e as saídas ficam fora do git (veja o `.gitignore`).

## Desenvolvimento

```bash
uv run pytest
```

Os testes de `application/` usam fakes das portas, sem rede e sem IA. Os de `domain/` incluem
uma caracterização com 107 vagas reais (`tests/fixtures/`).
