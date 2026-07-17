"""Image-generation backends.

Two ways to turn a prompt into pixels, behind one interface:

- ``LocalBackend`` — FLUX.1-schnell via mflux on this machine (the default;
  free, offline). mflux is imported lazily so nothing hosted-only pays for it.
- Hosted backends — offload compute to an API when you want a different model
  or aren't on a capable machine. Bring your own key (stored in the Keychain;
  see ``keychain.py``). Two ship built in: ``ReplicateBackend`` (the same
  flux-schnell model) and ``OpenAIBackend`` (gpt-image-1). Adding another is a
  small class plus one entry in ``HOSTED_BACKENDS``.

Each backend exposes ``generate(prompt, width, height, seed, steps) ->
PIL.Image``. The caller crops/resizes the result to the exact requested size,
so a backend only has to return an image of roughly the right shape.
"""

from __future__ import annotations

import io
import json
import urllib.request

from PIL import Image

# Aspect ratios the hosted flux-schnell model accepts, mapped to width/height.
REPLICATE_ASPECT_RATIOS = {
    "1:1": 1 / 1,
    "16:9": 16 / 9,
    "21:9": 21 / 9,
    "3:2": 3 / 2,
    "2:3": 2 / 3,
    "4:5": 4 / 5,
    "5:4": 5 / 4,
    "9:16": 9 / 16,
    "9:21": 9 / 21,
    "3:4": 3 / 4,
    "4:3": 4 / 3,
}


def nearest_aspect_ratio(width: int, height: int) -> str:
    """Pick the supported aspect-ratio string closest to width/height."""
    target = width / height
    return min(
        REPLICATE_ASPECT_RATIOS,
        key=lambda ratio: abs(REPLICATE_ASPECT_RATIOS[ratio] - target),
    )


def replicate_payload(prompt: str, width: int, height: int, seed: int, steps: int) -> dict:
    """Build the request body for a hosted flux-schnell prediction.

    The hosted model chooses exact pixels from an aspect ratio, so we send the
    nearest ratio and cover-crop the result locally to the requested size.
    """
    return {
        "input": {
            "prompt": prompt,
            "aspect_ratio": nearest_aspect_ratio(width, height),
            "num_inference_steps": min(steps, 4),  # schnell tops out at 4
            "seed": seed,
            "num_outputs": 1,
            "output_format": "png",
        }
    }


def parse_replicate_output(response: dict) -> str:
    """Extract the image URL from a completed Replicate prediction response."""
    status = response.get("status")
    if status in ("starting", "processing"):
        raise ValueError(
            "Replicate did not finish within the wait window; try again"
        )
    if status and status not in ("succeeded", None):
        raise ValueError(
            f"Replicate prediction {status}: {response.get('error') or 'no detail'}"
        )
    output = response.get("output")
    if isinstance(output, list):
        if not output:
            raise ValueError("Replicate returned an empty output list")
        return output[0]
    if isinstance(output, str) and output:
        return output
    raise ValueError("unexpected Replicate response shape (no image URL)")


class LocalBackend:
    name = "local"

    def __init__(self, model: str, base_model: str):
        self._model = model
        self._base_model = base_model
        self._flux = None

    def _ensure_loaded(self) -> None:
        if self._flux is None:
            print(
                f"loading {self._model} (first run downloads ~7 GB)...", flush=True
            )
            from mflux.models.flux.variants.txt2img.flux import Flux1, ModelConfig

            self._flux = Flux1(
                model_config=ModelConfig.from_name(
                    self._model, base_model=self._base_model
                )
            )

    def generate(
        self, prompt: str, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        self._ensure_loaded()
        generated = self._flux.generate_image(
            seed=seed,
            prompt=prompt,
            num_inference_steps=steps,
            width=width,
            height=height,
        )
        return generated.image


class ReplicateBackend:
    name = "replicate"
    MODEL = "black-forest-labs/flux-schnell"

    def __init__(self, api_key: str):
        self._key = api_key

    def _post_prediction(self, payload: dict) -> dict:
        request = urllib.request.Request(
            f"https://api.replicate.com/v1/models/{self.MODEL}/predictions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
                "Prefer": "wait",  # block until the prediction finishes (~seconds)
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def _download(self, url: str) -> Image.Image:
        with urllib.request.urlopen(url, timeout=180) as response:
            return Image.open(io.BytesIO(response.read())).convert("RGB")

    def generate(
        self, prompt: str, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        import sys

        if steps > 4:
            print(
                f"note: schnell caps at 4 steps; using 4 instead of {steps} (hosted).",
                file=sys.stderr,
            )
        print("generating via Replicate...", flush=True)
        prediction = self._post_prediction(
            replicate_payload(prompt, width, height, seed, steps)
        )
        return self._download(parse_replicate_output(prediction))


# Sizes gpt-image-1 accepts, mapped to width/height. It has no arbitrary-size
# or seed option, so we request the nearest shape and cover-crop locally.
OPENAI_SIZES = {
    "1024x1024": 1.0,
    "1536x1024": 1536 / 1024,
    "1024x1536": 1024 / 1536,
}


def nearest_openai_size(width: int, height: int) -> str:
    target = width / height
    return min(OPENAI_SIZES, key=lambda size: abs(OPENAI_SIZES[size] - target))


def openai_payload(prompt: str, width: int, height: int) -> dict:
    return {
        "model": "gpt-image-1",
        "prompt": prompt,
        "size": nearest_openai_size(width, height),
        "n": 1,
    }


def parse_openai_output(response: dict) -> bytes:
    """Return the raw image bytes from an OpenAI images response."""
    import base64

    data = response.get("data")
    if not data:
        raise ValueError(f"OpenAI returned no image: {response.get('error') or response}")
    encoded = data[0].get("b64_json")
    if not encoded:
        raise ValueError("OpenAI response had no b64_json image data")
    return base64.b64decode(encoded)


class OpenAIBackend:
    name = "openai"
    ENDPOINT = "https://api.openai.com/v1/images/generations"

    def __init__(self, api_key: str):
        self._key = api_key

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read())

    def generate(
        self, prompt: str, width: int, height: int, seed: int, steps: int
    ) -> Image.Image:
        print("generating via OpenAI (gpt-image-1)...", flush=True)
        response = self._post(openai_payload(prompt, width, height))
        raw = parse_openai_output(response)
        return Image.open(io.BytesIO(raw)).convert("RGB")


# Each hosted provider maps to its backend class and the env-style help shown
# when its key is missing. Add a provider by adding a class above and an entry
# here — nothing else in the CLI needs to change.
HOSTED_BACKENDS = {
    "replicate": ReplicateBackend,
    "openai": OpenAIBackend,
}
HOSTED_PROVIDERS = tuple(HOSTED_BACKENDS)


def get_backend(
    name: str, *, model: str, base_model: str, api_key: str | None = None
):
    if name == "local":
        return LocalBackend(model, base_model)
    if name in HOSTED_BACKENDS:
        if not api_key:
            raise ValueError(
                f"no {name} API key is stored. Add one first:\n"
                f"    uv run scripts/generate.py --set-key {name}"
            )
        return HOSTED_BACKENDS[name](api_key)
    options = "', '".join(("local", *HOSTED_PROVIDERS))
    raise ValueError(f"unknown backend {name!r}: use one of '{options}'")
