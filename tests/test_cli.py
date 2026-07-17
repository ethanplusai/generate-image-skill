from pathlib import Path

import pytest
from PIL import Image

import generate


class FakeBackend:
    def __init__(self, image):
        self._image = image
        self.calls = []

    def generate(self, prompt, width, height, seed, steps):
        self.calls.append((prompt, width, height, seed, steps))
        return self._image


def _one_plan(out, width, height, seed=1, gen=None):
    gen_w, gen_h = gen or (width, height)
    job = generate.Job(prompt="p", out=out, width=width, height=height)
    return [(job, gen_w, gen_h, False, [out], [seed])]


def test_run_plans_generates_and_saves(tmp_path):
    out = tmp_path / "o.webp"
    backend = FakeBackend(Image.new("RGB", (64, 64), "red"))
    generate.run_plans(_one_plan(out, 64, 64, seed=7), backend=backend, steps=4)
    assert out.exists()
    assert backend.calls == [("p", 64, 64, 7, 4)]


def test_run_plans_warns_when_source_smaller(tmp_path, capsys):
    out = tmp_path / "o.webp"
    backend = FakeBackend(Image.new("RGB", (64, 64), "red"))
    generate.run_plans(_one_plan(out, 128, 128), backend=backend, steps=4)
    assert "upscaled from 64x64" in capsys.readouterr().err


def test_run_plans_generation_error_exits_cleanly(tmp_path):
    class Boom:
        def generate(self, *args):
            raise OSError("network down")

    with pytest.raises(SystemExit):
        generate.run_plans(_one_plan(tmp_path / "o.webp", 64, 64), backend=Boom(), steps=4)


def test_list_keys_uses_presence_check(monkeypatch, capsys):
    monkeypatch.setattr(generate.keychain, "key_exists", lambda p: p == "replicate")
    args = generate.build_parser().parse_args(["--list-keys"])
    assert generate.handle_key_commands(args) is True
    assert "replicate: stored" in capsys.readouterr().out


def test_check_environment_hosted_allows_non_apple_silicon(monkeypatch):
    monkeypatch.setattr(generate.platform, "machine", lambda: "x86_64")
    generate.check_environment("replicate")  # must not exit


def test_check_environment_local_requires_apple_silicon(monkeypatch):
    monkeypatch.setattr(generate.platform, "machine", lambda: "x86_64")
    with pytest.raises(SystemExit):
        generate.check_environment("local")


def test_parser_has_open_flag_default_false():
    args = generate.build_parser().parse_args(["p", "--out", "o.webp", "--size", "10x10"])
    assert args.open is False


def test_open_flag_parses_true():
    args = generate.build_parser().parse_args(
        ["p", "--out", "o.webp", "--size", "10x10", "--open"]
    )
    assert args.open is True


def test_open_in_viewer_invokes_open(monkeypatch):
    calls = []
    monkeypatch.setattr(generate.subprocess, "run", lambda *a, **k: calls.append(a))
    generate.open_in_viewer(Path("/tmp/x.webp"))
    assert calls and calls[0][0] == ["open", "/tmp/x.webp"]


def test_open_in_viewer_swallows_oserror(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no open binary")

    monkeypatch.setattr(generate.subprocess, "run", boom)
    generate.open_in_viewer(Path("/tmp/x.webp"))  # must not raise
