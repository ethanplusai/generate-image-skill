import pytest

import keychain


class FakeResult:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


def test_set_key_builds_namespaced_security_command(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return FakeResult()

    monkeypatch.setattr(keychain.subprocess, "run", fake_run)
    keychain.set_key("replicate", "sk-secret")
    argv = captured["argv"]
    assert argv[:2] == ["security", "add-generic-password"]
    assert "-U" in argv  # updates an existing item instead of erroring
    assert "generate-image-skill:replicate" in argv
    assert "sk-secret" in argv


def test_get_key_returns_stored_password(monkeypatch):
    monkeypatch.setattr(
        keychain.subprocess, "run", lambda *a, **k: FakeResult(0, "sk-xyz\n")
    )
    assert keychain.get_key("replicate") == "sk-xyz"


def test_get_key_missing_returns_none(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(44, ""))
    assert keychain.get_key("replicate") is None


def test_get_key_empty_output_returns_none(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(0, "\n"))
    assert keychain.get_key("replicate") is None


def test_delete_key_true_on_success(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(0, ""))
    assert keychain.delete_key("replicate") is True


def test_delete_key_false_when_absent(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(44, ""))
    assert keychain.delete_key("replicate") is False


def test_set_key_failure_raises_without_leaking_the_key(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(1, ""))
    with pytest.raises(RuntimeError) as exc_info:
        keychain.set_key("replicate", "sk-supersecretvalue")
    assert "sk-supersecretvalue" not in str(exc_info.value)


def test_key_exists_true_on_success(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(0, ""))
    assert keychain.key_exists("replicate") is True


def test_key_exists_false_when_absent(monkeypatch):
    monkeypatch.setattr(keychain.subprocess, "run", lambda *a, **k: FakeResult(44, ""))
    assert keychain.key_exists("replicate") is False
