from typer.testing import CliRunner

from my_project.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_hello() -> None:
    result = runner.invoke(app, ["hello", "--name", "team"])
    assert result.exit_code == 0
    assert "Hello, team!" in result.stdout
