import json
import os
import time

import pytest
from PIL import Image

import backends
from backends import (
    CodexBackend,
    codex_command,
    codex_instruction,
    codex_logged_in_with_chatgpt,
    codex_orientation,
    get_backend,
    parse_codex_events,
    pick_codex_image,
)


def _events(*events):
    return [json.dumps(event) for event in events]


def test_parse_codex_events_returns_thread_id():
    lines = _events(
        {"type": "thread.started", "thread_id": "abc-123"},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": {}},
    )
    assert parse_codex_events(lines) == ("abc-123", None)


def test_parse_codex_events_ignores_noise_lines():
    lines = ["Reading additional input from stdin...", "{not json", *_events(
        {"type": "thread.started", "thread_id": "t1"}
    )]
    assert parse_codex_events(lines) == ("t1", None)


def test_parse_codex_events_collects_errors():
    lines = _events(
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "error", "message": "usage limit reached"},
        {"type": "turn.failed", "error": {"message": "stream ended"}},
    )
    thread_id, error = parse_codex_events(lines)
    assert thread_id == "t1"
    assert "usage limit reached" in error and "stream ended" in error


def test_codex_orientation():
    assert codex_orientation(1440, 800) == "landscape"
    assert codex_orientation(800, 1200) == "portrait"
    assert codex_orientation(800, 800) == "square"
    assert codex_orientation(1080, 1000) == "square"


def test_codex_instruction_carries_prompt_and_shape():
    text = codex_instruction("a red boat", 1440, 800)
    assert "image_gen" in text
    assert "landscape" in text and "1440x800" in text
    assert text.endswith("a red boat")
    assert "transparent" not in text.lower()


def test_codex_instruction_transparent_and_refs():
    text = codex_instruction("a mug", 800, 800, transparent=True, refs=2)
    assert "transparent" in text.lower()
    assert "2 attached image(s)" in text


def test_codex_command_is_isolated_and_read_only(tmp_path):
    command = codex_command("codex", tmp_path, "-starts with dash", refs=("a.png",))
    assert command[:2] == ["codex", "exec"]
    assert "--json" in command and "--ephemeral" in command
    assert command[command.index("--enable") + 1] == "image_generation"
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert command[command.index("--image") + 1] == "a.png"
    assert command[-2:] == ["--", "-starts with dash"]


def _png(path, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8)).save(path)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def test_pick_codex_image_prefers_thread_folder(tmp_path):
    other = _png(tmp_path / "other-thread" / "x.png", time.time() + 100)
    mine = _png(tmp_path / "t1" / "exec-1.png")
    assert pick_codex_image(tmp_path, "t1", before={other}) == mine


def test_pick_codex_image_falls_back_to_new_files(tmp_path):
    old = _png(tmp_path / "old" / "a.png")
    new = _png(tmp_path / "unknown" / "b.png")
    assert pick_codex_image(tmp_path, None, before={old}) == new


def test_pick_codex_image_newest_in_thread(tmp_path):
    _png(tmp_path / "t1" / "a.png", time.time() - 100)
    newest = _png(tmp_path / "t1" / "b.png", time.time())
    assert pick_codex_image(tmp_path, "t1", before=set()) == newest


def test_pick_codex_image_none_raises(tmp_path):
    with pytest.raises(ValueError, match="no image"):
        pick_codex_image(tmp_path, "t1", before=set())


def test_logged_in_false_when_codex_missing(monkeypatch):
    monkeypatch.setattr(backends.shutil, "which", lambda name: None)
    assert codex_logged_in_with_chatgpt() is False


def test_logged_in_reads_status(monkeypatch):
    class Result:
        def __init__(self, out, rc=0):
            self.stdout, self.stderr, self.returncode = out, "", rc

    monkeypatch.setattr(backends.shutil, "which", lambda name: "/bin/codex")
    monkeypatch.setattr(
        backends.subprocess, "run", lambda *a, **k: Result("Logged in using ChatGPT")
    )
    assert codex_logged_in_with_chatgpt() is True
    monkeypatch.setattr(
        backends.subprocess, "run", lambda *a, **k: Result("Logged in using an API key")
    )
    assert codex_logged_in_with_chatgpt() is False
    monkeypatch.setattr(
        backends.subprocess, "run", lambda *a, **k: Result("Not logged in", rc=1)
    )
    assert codex_logged_in_with_chatgpt() is False


def test_codex_backend_requires_cli(monkeypatch):
    monkeypatch.setattr(backends.shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="npm install -g @openai/codex"):
        CodexBackend()


def test_codex_backend_rejects_missing_ref(monkeypatch, tmp_path):
    monkeypatch.setattr(backends.shutil, "which", lambda name: "/bin/codex")
    with pytest.raises(ValueError, match="reference image not found"):
        CodexBackend(refs=(tmp_path / "nope.png",))


def test_codex_backend_generate_collects_image(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(backends.shutil, "which", lambda name: "/bin/codex")
    calls = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(command, **kwargs):
        calls.append(command)
        _png(tmp_path / "generated_images" / "t9" / "exec-1.png")
        return Result("\n".join(_events({"type": "thread.started", "thread_id": "t9"})))

    monkeypatch.setattr(backends.subprocess, "run", fake_run)
    image = get_backend("codex", model="m", base_model="schnell").generate(
        "a boat", 1440, 800, 1, 4
    )
    assert image.size == (8, 8) and image.mode == "RGB"
    assert calls[0][-1].endswith("a boat")


def test_codex_backend_surfaces_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setattr(backends.shutil, "which", lambda name: "/bin/codex")

    class Result:
        returncode = 1
        stderr = "boom"
        stdout = "\n".join(_events({"type": "error", "message": "401 auth expired"}))

    monkeypatch.setattr(backends.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(ValueError, match="codex login"):
        CodexBackend().generate("x", 64, 64, 1, 4)
