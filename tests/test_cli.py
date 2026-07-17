from pathlib import Path

import generate


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
