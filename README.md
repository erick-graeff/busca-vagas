# busca-vagas

Busca vagas em fontes configuráveis, aplica um **filtro determinístico** por palavras-chave e,
opcionalmente, pede a uma IA (via [opencode](https://opencode.ai)) uma avaliação de aderência entre
cada vaga e o seu currículo. Pensado para rodar no cron e avisar só das vagas novas, inclusive pelo Telegram.

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
| `--notify`   | Aciona os notificadores de `[[notifiers]]` (ex.: [Telegram](#telegram)).     |

Códigos de saída: `0` ok · `1` erro de configuração · `2` executou com falhas parciais
(fonte fora do ar, erro da IA, notificação não entregue), com avisos no stderr · `3` erro
inesperado (bug), com o traceback no stderr.

### Cron

```cron
PATH=/caminho/do/opencode/bin:/usr/local/bin:/usr/bin:/bin
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
*/30 * * * *  /caminho/busca-vagas/.venv/bin/busca-vagas run --config /caminho/busca-vagas/config.toml --refresh --new-only --match --notify >> /caminho/busca-vagas/data/cron.log 2>&1
```

Caminhos relativos da config são resolvidos a partir da pasta do arquivo, então o cron funciona
de qualquer diretório. Uma vaga só é marcada como vista depois de avaliada com sucesso e
notificada. Se a IA ou a notificação falhar, ela volta na próxima execução.

O cron não lê o `.bashrc`: defina no crontab o `PATH` (para achar o `opencode`) e as variáveis
do Telegram.

#### Acompanhando falhas

Cada execução fica delimitada no log, com horário e resultado:

```
=== 2026-11-19 14:30:02 · busca-vagas run ===
...
=== fim · exit=0 · 3 selecionadas, 1 novas, 0 avisos · 32.8s ===
```

```bash
grep -nE "AVISO|erro|Traceback|exit=[123]" data/cron.log   # só os problemas
```

Com `--notify`, as falhas também chegam no Telegram, **uma vez cada**: o mesmo problema não é
avisado de novo a cada execução, e chega um "✅ voltou a funcionar" quando ele some. Isso vale
para falhas parciais (fonte, IA) e para erros graves (config inválida, bug). Se a própria
config estiver quebrada, o alerta só sai com o token e o chat_id em variáveis de ambiente.

### Telegram

As vagas chegam por um **bot** no seu chat privado com ele.

1. No Telegram, fale com o [@BotFather](https://t.me/BotFather), envie `/newbot` e guarde o
   **token** que ele devolve.
2. Abra o chat com o seu bot e mande qualquer mensagem (o bot só pode escrever para quem já
   falou com ele).
3. Descubra o **chat_id**: o número em `"chat":{"id":...}` na resposta de

   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
4. Ative o notificador no `config.toml` e passe as credenciais por variável de ambiente:

   ```toml
   [[notifiers]]
   type = "telegram"
   ```

   ```bash
   export TELEGRAM_BOT_TOKEN=123456:ABC...
   export TELEGRAM_CHAT_ID=123456789
   uv run busca-vagas run --refresh --new-only --match --notify
   ```

| Opção            | Padrão | Descrição                                                         |
| ---------------- | ------ | ----------------------------------------------------------------- |
| `only_new`       | `true` | Só vagas novas. Com `false`, envia todas as selecionadas.         |
| `max_results`    | `20`   | Máximo de vagas por execução; o resto fica no relatório local.    |
| `include_errors` | `true` | Avisa falhas (uma vez cada) e quando elas se resolvem.            |
| `token`/`chat_id`| env    | Alternativa às variáveis `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`. |

Sem vagas novas e sem avisos, nada é enviado. Para testar com vagas que você já viu, rode uma
vez com `only_new = false`.

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
                │ domain/ (puro): Posting, regras,  ──────────▶ Notifier   ◀── Console, JsonFile,
                │ filtro, níveis                          │                    Telegram
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
 [7] notify         --notify: notificadores de [[notifiers]] (vagas novas + falhas ainda não avisadas)
 [8] marcar vistas  só as avaliadas com sucesso e entregues
 [9] report         console + arquivo JSON (sempre), já com os avisos
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
| Notificação (e-mail...)      | `Notifier` (`notify(report)`)        | `adapters/outbound/notifiers/__init__.py`|

Cada classe recebe as opções do seu bloco na config via `from_options(dict)`. Por exemplo,
`[[sources]] type = "greenhouse"` com `board = "..."`.

## Privacidade

- O currículo enviado à IA é o arquivo de `[match].resume`. **Remova dele nome, contatos e links.**
  Os modelos gratuitos do opencode rodam num serviço externo.
- O opencode roda numa pasta temporária, então o agente não enxerga os arquivos do projeto.
- O token do bot dá controle total sobre ele: guarde-o em variável de ambiente, não no git. As
  mensagens de erro nunca mostram o token.
- `config.toml`, `data/`, `curriculo*` e as saídas ficam fora do git (veja o `.gitignore`).

## Desenvolvimento

```bash
uv run pytest
```

Os testes de `application/` usam fakes das portas, sem rede e sem IA. Os de `domain/` incluem
uma caracterização com 107 vagas reais (`tests/fixtures/`).

## Licença

[MIT](LICENSE)
