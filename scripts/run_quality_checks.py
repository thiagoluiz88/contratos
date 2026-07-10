from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIRS = ("app", "alembic", "scripts", "tests")


def validate_ast() -> None:
    files = [path for directory in PYTHON_DIRS for path in (ROOT / directory).rglob("*.py")]
    for path in files:
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    print(f"AST: OK ({len(files)} arquivos)")


def validate_application_and_templates() -> None:
    from app.main import app, templates

    template_files = list((ROOT / "app" / "templates").glob("*.html"))
    for path in template_files:
        templates.env.get_template(path.name)
    print(f"IMPORT: OK ({len(app.routes)} rotas)")
    print(f"JINJA: OK ({len(template_files)} templates)")


def run(label: str, *arguments: str) -> None:
    print(f"\n== {label} ==")
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def main() -> None:
    validate_ast()
    validate_application_and_templates()
    run("Alembic check", "-m", "alembic", "check")
    run("PostgreSQL", "-m", "app.db_checks")
    run("Auditoria de seguranca", "-m", "scripts.audit_security")
    run("Auditoria de persistencia", "-m", "scripts.audit_persistence")
    run("Pytest", "-m", "pytest")
    print("\nQUALITY CHECKS: OK")


if __name__ == "__main__":
    main()

