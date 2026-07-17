import pytest

from backends import (
    LocalBackend,
    ReplicateBackend,
    get_backend,
    nearest_aspect_ratio,
    parse_replicate_output,
    replicate_payload,
)


def test_nearest_aspect_ratio_landscape():
    assert nearest_aspect_ratio(1920, 1080) == "16:9"


def test_nearest_aspect_ratio_square():
    assert nearest_aspect_ratio(800, 800) == "1:1"


def test_nearest_aspect_ratio_portrait():
    assert nearest_aspect_ratio(800, 1200) == "2:3"


def test_replicate_payload_caps_steps_and_carries_fields():
    payload = replicate_payload("a cat", 1440, 800, 7, 8)["input"]
    assert payload["num_inference_steps"] == 4  # schnell caps at 4
    assert payload["seed"] == 7
    assert payload["prompt"] == "a cat"
    assert payload["aspect_ratio"] == "16:9"


def test_parse_output_list_returns_first_url():
    response = {"status": "succeeded", "output": ["https://img/1.png", "https://img/2.png"]}
    assert parse_replicate_output(response) == "https://img/1.png"


def test_parse_output_string_url():
    assert parse_replicate_output({"output": "https://img/x.png"}) == "https://img/x.png"


def test_parse_output_empty_list_raises():
    with pytest.raises(ValueError):
        parse_replicate_output({"output": []})


def test_parse_output_failed_status_raises():
    with pytest.raises(ValueError, match="failed"):
        parse_replicate_output({"status": "failed", "error": "boom", "output": None})


def test_parse_output_still_processing_raises_timeout():
    with pytest.raises(ValueError, match="wait window"):
        parse_replicate_output({"status": "processing", "output": None})


def test_get_backend_local():
    backend = get_backend("local", model="m", base_model="schnell")
    assert isinstance(backend, LocalBackend) and backend.name == "local"


def test_get_backend_replicate_requires_key():
    with pytest.raises(ValueError, match="--set-key"):
        get_backend("replicate", model="m", base_model="schnell", api_key=None)


def test_get_backend_replicate_with_key():
    backend = get_backend("replicate", model="m", base_model="schnell", api_key="sk-1")
    assert isinstance(backend, ReplicateBackend) and backend.name == "replicate"


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("dalle", model="m", base_model="schnell")
