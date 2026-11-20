"""Adapter de entrada: linha de comando. Só traduz argumentos para a porta SearchJobs."""

import argparse
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from busca_vagas.application.ports.inbound import Issue, SearchRequest

DEFAULT_CONFIG = "config.json"

EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_PARTIAL = 2  # executou, mas houve falhas não fatais (fonte fora do ar, erro da IA...)
EXIT_UNEXPECTED = 3  # bug: exceção não tratada (o traceback vai para o stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="busca-vagas", description="Busca e filtra vagas de emprego")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="busca, filtra e (opcionalmente) avalia vagas com IA")
    run.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("BUSCA_VAGAS_CONFIG", DEFAULT_CONFIG)),
        help=f"arquivo de configuração (padrão: $BUSCA_VAGAS_CONFIG ou ./{DEFAULT_CONFIG})",
    )
    run.add_argument("--refresh", action="store_true", help="ignora o cache e consulta as fontes")
    run.add_argument("--new-only", action="store_true", help="só vagas ainda não vistas")
    run.add_argument("--match", action="store_true", help="avalia as vagas filtradas com IA")
    run.add_argument("--model", help="sobrescreve o modelo de IA da configuração")
    run.add_argument(
        "--notify",
        action="store_true",
        help="aciona os notificadores de 'notifiers' (vagas novas, falhas e erros graves)",
    )
    sub.add_parser("schema", help="imprime o JSON Schema da configuração (config.schema.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "schema":
        import json

        from busca_vagas.config.schema import json_schema

        print(json.dumps(json_schema(), indent=2, ensure_ascii=False))
        return EXIT_OK

    # com saída redirecionada (cron), mantém stdout e stderr na ordem certa no log
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True)

    started = time.monotonic()
    print(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} · busca-vagas run ===")
    code, summary = _run(args)
    print(f"=== fim · exit={code} · {summary} · {time.monotonic() - started:.1f}s ===\n")
    return code


def _run(args: argparse.Namespace) -> tuple[int, str]:
    # imports tardios: `--help` responde sem carregar pydantic/requests
    from busca_vagas.bootstrap import build_search
    from busca_vagas.config.loader import ConfigError, load_config

    config = None
    try:
        config = load_config(args.config)
        search = build_search(
            config, refresh=args.refresh, match=args.match, model=args.model, notify=args.notify
        )
        if args.notify and not config.notifiers:
            print("aviso: --notify sem nenhum item em 'notifiers' na configuração", file=sys.stderr)
        report = search.run(SearchRequest(new_only=args.new_only, match=args.match, notify=args.notify))
    except ConfigError as e:
        print(f"erro: {e}", file=sys.stderr)
        _alert(args, config, Issue("configuração", str(e)))
        return EXIT_CONFIG_ERROR, "erro de configuração"
    except Exception as e:
        traceback.print_exc()
        _alert(args, config, Issue(f"erro inesperado ({type(e).__name__})", f"{e} (detalhes no log)"))
        return EXIT_UNEXPECTED, "erro inesperado"

    code = EXIT_PARTIAL if report.errors else EXIT_OK
    return (
        code,
        f"{len(report.results)} selecionadas, {len(report.new_results)} novas, {len(report.errors)} avisos",
    )


def _alert(args: argparse.Namespace, config, issue: Issue) -> None:
    """Com --notify, tenta avisar o erro grave. Nunca deixa o alerta derrubar a saída."""
    if not args.notify:
        return
    from busca_vagas.bootstrap import build_failure_alert

    try:
        alerter = build_failure_alert(config, args.config)
        if alerter is None:
            print("aviso: nenhum notificador disponível para avisar o erro", file=sys.stderr)
        elif alerter.alert(issue):
            print("erro avisado pelos notificadores", file=sys.stderr)
    except Exception as e:  # o alerta é best-effort
        print(f"aviso: falha ao avisar o erro: {type(e).__name__}: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
