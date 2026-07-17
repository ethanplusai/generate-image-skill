import json
from pathlib import Path

import pytest

from imagegen_core import parse_manifest, resolve_seeds


def _write(tmp_path, data):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data))
    return path


def test_parses_jobs(tmp_path):
    path = _write(
        tmp_path,
        [
            {
                "prompt": "hero",
                "out": "public/hero.webp",
                "size": "1440x800",
                "seed": 7,
                "count": 2,
            },
            {"prompt": "texture", "out": "public/bg.png", "size": "512x512"},
        ],
    )
    jobs = parse_manifest(path)
    assert len(jobs) == 2
    assert jobs[0].out == Path("public/hero.webp")
    assert (jobs[0].width, jobs[0].height) == (1440, 800)
    assert jobs[0].seed == 7 and jobs[0].count == 2
    assert jobs[1].seed is None and jobs[1].count == 1


def test_missing_keys_error_names_item(tmp_path):
    path = _write(tmp_path, [{"prompt": "x"}])
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_empty_manifest_error(tmp_path):
    path = _write(tmp_path, [])
    with pytest.raises(ValueError):
        parse_manifest(path)


def test_non_dict_item_error(tmp_path):
    path = _write(tmp_path, [None])
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_wrong_typed_count_error(tmp_path):
    path = _write(
        tmp_path, [{"prompt": "x", "out": "a.webp", "size": "512x512", "count": "two"}]
    )
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_wrong_typed_seed_error(tmp_path):
    path = _write(
        tmp_path, [{"prompt": "x", "out": "a.webp", "size": "512x512", "seed": "seven"}]
    )
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_invalid_json_error_names_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("not json {")
    with pytest.raises(ValueError, match="invalid JSON in"):
        parse_manifest(path)


def test_boolean_seed_rejected(tmp_path):
    path = _write(
        tmp_path, [{"prompt": "x", "out": "a.webp", "size": "512x512", "seed": True}]
    )
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_negative_seed_rejected(tmp_path):
    path = _write(
        tmp_path, [{"prompt": "x", "out": "a.webp", "size": "512x512", "seed": -1}]
    )
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_boolean_count_rejected(tmp_path):
    path = _write(
        tmp_path, [{"prompt": "x", "out": "a.webp", "size": "512x512", "count": True}]
    )
    with pytest.raises(ValueError, match="item 0"):
        parse_manifest(path)


def test_seeds_sequential_from_fixed():
    assert resolve_seeds(42, 3) == [42, 43, 44]


def test_seeds_random_when_none():
    seeds = resolve_seeds(None, 2)
    assert len(seeds) == 2
    assert all(0 <= s < 2**32 for s in seeds)
