"""El preparador de Neon debe evitar destinos erróneos y escrituras implícitas."""
import pytest

from scripts import setup_neon


DIRECT_URL = "postgresql://owner:secret@ep-example.us-east-2.aws.neon.tech/vetchain?sslmode=require"


@pytest.mark.parametrize("url", [
    "postgresql://owner:secret@localhost:5432/VetChainDb?sslmode=require",
    "postgresql://owner:secret@ep-example-pooler.us-east-2.aws.neon.tech/vetchain?sslmode=require",
    "postgresql://owner:secret@ep-example.us-east-2.aws.neon.tech/vetchain",
])
def test_rejects_unsafe_database_urls(url):
    with pytest.raises(ValueError):
        setup_neon.validate_neon_url(url)


def test_preview_checks_csvs_without_running_commands(tmp_path, monkeypatch, capsys):
    for number in range(1, 8):
        (tmp_path / f"mederi-{number}-datos.csv").touch()
    monkeypatch.setenv("DATABASE_URL", DIRECT_URL)
    monkeypatch.setattr(setup_neon.subprocess, "run", lambda *args, **kwargs: pytest.fail("Escritura inesperada"))

    assert setup_neon.main(["--csv-dir", str(tmp_path)]) == 0
    assert "No se escribió" in capsys.readouterr().out


def test_seed_requires_explicit_environment_variables():
    with pytest.raises(ValueError, match="SEED_MANAGER_EMAIL"):
        setup_neon.validate_seed_environment({})


def test_apply_runs_in_order_and_masks_local_seed_values(tmp_path, monkeypatch):
    for number in range(1, 8):
        (tmp_path / f"mederi-{number}-datos.csv").touch()
    monkeypatch.setenv("DATABASE_URL", DIRECT_URL)
    monkeypatch.setenv("SEED_MANAGER_EMAIL", "gerencia@example.com")
    monkeypatch.setenv("SEED_MANAGER_PASSWORD", "test-password")
    monkeypatch.delenv("SEED_SALESPERSON_EMAIL", raising=False)
    calls = []
    monkeypatch.setattr(setup_neon.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))

    assert setup_neon.main(["--csv-dir", str(tmp_path), "--apply", "--seed-users"]) == 0
    assert [call[0][2:] for call in calls] == [
        ["alembic", "upgrade", "head"],
        ["scripts.load_csv", str(tmp_path)],
        ["scripts.seed_users"],
    ]
    assert all(call[1]["check"] is True for call in calls)
    assert calls[-1][1]["env"]["SEED_SALESPERSON_EMAIL"] == ""


def test_explicit_seed_file_supplies_users_without_replacing_database_url(tmp_path, monkeypatch):
    seed_file = tmp_path / ".env"
    seed_file.write_text(
        "DATABASE_URL=postgresql://owner:secret@localhost/local\n"
        "SEED_MANAGER_EMAIL=gerencia@example.com\n"
        "SEED_MANAGER_PASSWORD=test-password\n"
        "SEED_SALESPERSON_EMAIL=vendedor@example.com\n"
        "SEED_SALESPERSON_PASSWORD=other-password\n"
        "SEED_SALESPERSON_CODE=004\n"
    )
    monkeypatch.setenv("DATABASE_URL", DIRECT_URL)
    for key in setup_neon.SEED_KEYS:
        monkeypatch.delenv(key, raising=False)

    environment = setup_neon.seed_environment(seed_file)

    assert environment["DATABASE_URL"] == DIRECT_URL
    assert environment["SEED_MANAGER_EMAIL"] == "gerencia@example.com"
    assert environment["SEED_SALESPERSON_CODE"] == "004"
    setup_neon.validate_seed_environment(environment)
