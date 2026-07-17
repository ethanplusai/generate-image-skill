import base64

import pytest

from backends import (
    GeminiBackend,
    LocalBackend,
    OpenAIBackend,
    ReplicateBackend,
    gemini_payload,
    get_backend,
    nearest_aspect_ratio,
    nearest_gemini_aspect_ratio,
    nearest_openai_size,
    openai_payload,
    parse_gemini_output,
    parse_openai_output,
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


def test_nearest_openai_size_landscape():
    assert nearest_openai_size(1440, 800) == "1536x1024"


def test_nearest_openai_size_square():
    assert nearest_openai_size(800, 800) == "1024x1024"


def test_nearest_openai_size_portrait():
    assert nearest_openai_size(800, 1200) == "1024x1536"


def test_openai_payload_shape():
    payload = openai_payload("a cat", 1440, 800)
    assert payload["model"] == "gpt-image-1"
    assert payload["prompt"] == "a cat"
    assert payload["size"] == "1536x1024"
    assert payload["n"] == 1


def test_parse_openai_output_decodes_b64():
    encoded = base64.b64encode(b"PNGDATA").decode()
    assert parse_openai_output({"data": [{"b64_json": encoded}]}) == b"PNGDATA"


def test_parse_openai_output_empty_raises():
    with pytest.raises(ValueError):
        parse_openai_output({"data": []})


def test_parse_openai_output_missing_b64_raises():
    with pytest.raises(ValueError):
        parse_openai_output({"data": [{}]})


def test_get_backend_local():
    backend = get_backend("local", model="m", base_model="schnell")
    assert isinstance(backend, LocalBackend) and backend.name == "local"


def test_get_backend_replicate_requires_key():
    with pytest.raises(ValueError, match="--set-key replicate"):
        get_backend("replicate", model="m", base_model="schnell", api_key=None)


def test_get_backend_replicate_with_key():
    backend = get_backend("replicate", model="m", base_model="schnell", api_key="sk-1")
    assert isinstance(backend, ReplicateBackend) and backend.name == "replicate"


def test_get_backend_openai_requires_key():
    with pytest.raises(ValueError, match="--set-key openai"):
        get_backend("openai", model="m", base_model="schnell", api_key=None)


def test_get_backend_openai_with_key():
    backend = get_backend("openai", model="m", base_model="schnell", api_key="sk-1")
    assert isinstance(backend, OpenAIBackend) and backend.name == "openai"


def test_nearest_gemini_aspect_ratio_landscape():
    assert nearest_gemini_aspect_ratio(1920, 1080) == "16:9"


def test_nearest_gemini_aspect_ratio_square():
    assert nearest_gemini_aspect_ratio(800, 800) == "1:1"


def test_nearest_gemini_aspect_ratio_portrait():
    assert nearest_gemini_aspect_ratio(800, 1200) == "2:3"


def test_gemini_payload_shape():
    payload = gemini_payload("a cat", 1440, 800)
    assert payload["contents"][0]["parts"][0]["text"] == "a cat"
    assert payload["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert payload["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"


def test_parse_gemini_output_decodes_inline_data():
    encoded = base64.b64encode(b"PNGDATA").decode()
    response = {"candidates": [{"content": {"parts": [{"inlineData": {"data": encoded}}]}}]}
    assert parse_gemini_output(response) == b"PNGDATA"


def test_parse_gemini_output_accepts_snake_case():
    encoded = base64.b64encode(b"X").decode()
    response = {"candidates": [{"content": {"parts": [{"inline_data": {"data": encoded}}]}}]}
    assert parse_gemini_output(response) == b"X"


def test_parse_gemini_output_skips_text_parts():
    encoded = base64.b64encode(b"IMG").decode()
    response = {
        "candidates": [
            {"content": {"parts": [{"text": "here you go"}, {"inlineData": {"data": encoded}}]}}
        ]
    }
    assert parse_gemini_output(response) == b"IMG"


def test_parse_gemini_output_no_candidates_raises():
    with pytest.raises(ValueError):
        parse_gemini_output({"promptFeedback": {"blockReason": "SAFETY"}})


def test_parse_gemini_output_no_image_raises():
    response = {"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}
    with pytest.raises(ValueError):
        parse_gemini_output(response)


def test_get_backend_gemini_requires_key():
    with pytest.raises(ValueError, match="--set-key gemini"):
        get_backend("gemini", model="m", base_model="schnell", api_key=None)


def test_get_backend_gemini_with_key():
    backend = get_backend("gemini", model="m", base_model="schnell", api_key="sk-1")
    assert isinstance(backend, GeminiBackend) and backend.name == "gemini"


def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match="unknown backend"):
        get_backend("midjourney", model="m", base_model="schnell")
