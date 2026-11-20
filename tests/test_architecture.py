"""Garante a regra da arquitetura hexagonal: dependências só apontam para dentro."""

import ast
from pathlib import Path

import pytest

PKG = Path(__file__).parent.parent / "src" / "busca_vagas"

# camada -> prefixos de import proibidos dentro dela
FORBIDDEN = {
    "domain": [
        "busca_vagas.application",
        "busca_vagas.adapters",
        "busca_vagas.config",
        "busca_vagas.bootstrap",
        "requests",
        "pydantic",
        "subprocess",
    ],
    "application": [
        "busca_vagas.adapters",
        "busca_vagas.config",
        "busca_vagas.bootstrap",
        "requests",
        "pydantic",
        "subprocess",
    ],
}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", FORBIDDEN)
def test_layer_does_not_depend_on_outer_layers(layer):
    violations = [
        f"{f.relative_to(PKG)} importa {name}"
        for f in (PKG / layer).rglob("*.py")
        for name in _imports(f)
        if any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN[layer])
    ]
    assert not violations, "\n".join(violations)
