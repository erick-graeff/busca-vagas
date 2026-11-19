"""Adapter de entrada: linha de comando. Só traduz argumentos para a porta SearchJobs."""

import argparse
import os
import sys
from pathlib import Path

from busca_vagas.application.ports.inbound import SearchRequest

DEFAULT_CONFIG = "config.toml"

EXIT_OK = 0
EXIT_CONFIG_ERROR = 1
EXIT_PARTIAL = 2  # executou, mas houve falhas não fatais (fonte fora do ar, erro da IA...)


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
    run.add_argument("--notify", action="store_true", help="aciona os notificadores de [[notifiers]]")
    return parser


def main(argv: list[str] | None = None) -> int:
    # imports tardios: `--help` responde sem carregar pydantic/requests
    from busca_vagas.bootstrap import build_search
    from busca_vagas.config.loader import ConfigError, load_config

    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        search = build_search(config, refresh=args.refresh, match=args.match, model=args.model)
    except ConfigError as e:
        print(f"erro: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    if args.notify and not config.notifiers:
        print("aviso: --notify sem nenhum [[notifiers]] na configuração", file=sys.stderr)

    report = search.run(SearchRequest(new_only=args.new_only, match=args.match, notify=args.notify))
    return EXIT_PARTIAL if report.errors else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
