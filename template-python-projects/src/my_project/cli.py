"""Command-line entry point: `uv run my-project --help`."""

from __future__ import annotations

from importlib.metadata import version as pkg_version

import typer

app = typer.Typer(help="my-project tools", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed package version."""
    typer.echo(pkg_version("my-project"))


@app.command()
def hello(name: str = "world") -> None:
    """Smoke-test command; replace with real ones."""
    typer.echo(f"Hello, {name}!")
