"""Generador de usuarios por defecto (scripts/seed_users.py --random)."""
import re

from scripts import seed_users


def test_random_profile_is_valid_and_avoids_taken_emails():
    profile = seed_users.random_profile(set())
    assert re.fullmatch(r"[a-z]+\.[a-z]+\d{2}@mederi\.local", profile["EMAIL"])
    assert re.fullmatch(r"9\d{8}", profile["PHONE"])
    assert len(profile["PASSWORD"]) >= 12
    assert len(profile["NAME"].split()) == 3
    other = seed_users.random_profile({profile["EMAIL"]})
    assert other["EMAIL"] != profile["EMAIL"]


def test_write_env_replaces_seed_lines_and_keeps_the_rest(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql://x\nSEED_MANAGER_EMAIL=viejo@mederi.local\n", encoding="utf-8")
    monkeypatch.setattr(seed_users, "ENV_FILE", env)
    seed_users.write_env({"SEED_MANAGER_EMAIL": "nuevo@mederi.local", "SEED_MANAGER_PHONE": "987654321"})
    assert env.read_text(encoding="utf-8") == (
        "DATABASE_URL=postgresql://x\nSEED_MANAGER_EMAIL=nuevo@mederi.local\nSEED_MANAGER_PHONE=987654321\n"
    )
