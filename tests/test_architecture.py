"""Verifica las reglas de docs/capas.md leyendo los imports de cada archivo (sin ejecutarlos)."""
import ast
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
STDLIB = sys.stdlib_module_names
SHARED_KERNEL = ("app.core.domain", "app.core.application")
LAYERS = ("domain", "application", "infrastructure", "interface")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _within(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _layer_files(layer: str):
    for module_dir in sorted((APP / "modules").iterdir()):
        layer_dir = module_dir / layer
        if layer_dir.is_dir():
            for path in sorted(layer_dir.rglob("*.py")):
                yield module_dir.name, path


def _violations(files, allowed_for) -> list[str]:
    problems = []
    for module, path in files:
        allowed = allowed_for(module)
        for name in _imports(path):
            if name.split(".")[0] in STDLIB:
                continue
            if not any(_within(name, prefix) for prefix in allowed):
                problems.append(f"{path.relative_to(APP.parent)} importa {name}")
    return problems


def test_shared_kernel_is_pure():
    files = [("core", path) for folder in ("domain", "application") for path in (APP / "core" / folder).rglob("*.py")]
    assert _violations(files, lambda _: SHARED_KERNEL) == []


def test_domain_only_imports_stdlib_shared_kernel_and_itself():
    allowed = lambda module: SHARED_KERNEL + (f"app.modules.{module}.domain",)  # noqa: E731
    assert _violations(_layer_files("domain"), allowed) == []


def test_application_only_imports_domain_and_shared_kernel():
    allowed = lambda module: SHARED_KERNEL + (  # noqa: E731
        f"app.modules.{module}.domain",
        f"app.modules.{module}.application",
    )
    assert _violations(_layer_files("application"), allowed) == []


def test_modules_only_talk_through_public():
    problems = []
    for layer in LAYERS:
        for module, path in _layer_files(layer):
            for name in _imports(path):
                parts = name.split(".")
                if len(parts) >= 3 and parts[:2] == ["app", "modules"] and parts[2] != module:
                    if name != f"app.modules.{parts[2]}.application.public":
                        problems.append(f"{path.relative_to(APP.parent)} importa {name}")
    assert problems == []
