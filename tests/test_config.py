from app.config import Settings


def test_generic_debug_environment_variable_does_not_collide(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.delenv("HARELO_DEBUG", raising=False)

    assert Settings().debug is False


def test_prefixed_environment_variable_is_applied(monkeypatch):
    monkeypatch.setenv("HARELO_DEBUG", "true")

    assert Settings().debug is True
