"""Pure logic for generate-image-skill: no mflux imports, fully unit-testable."""

import json
import math
import random
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

MAX_PIXELS = 1_310_720  # 1.25 MP: schnell stays reliable here, and 1440x800 heroes fit natively
MULTIPLE = 16

WEBP_QUALITY = 82
JPEG_QUALITY = 88

SUPPORTED_EXTENSIONS = (".webp", ".jpg", ".jpeg", ".png")


def parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value.strip().lower())
    if not match:
        raise ValueError(f"size must look like 1440x800, got: {value!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if width < MULTIPLE or height < MULTIPLE:
        raise ValueError(f"size must be at least {MULTIPLE}x{MULTIPLE}, got: {value!r}")
    return width, height


def plan_generation_size(
    width: int,
    height: int,
    max_pixels: int = MAX_PIXELS,
    multiple: int = MULTIPLE,
) -> tuple[int, int, bool]:
    """Pick native generation dimensions for a requested output size.

    Returns (gen_width, gen_height, needs_upscale). Requests at or under
    max_pixels generate at-or-above the requested size (rounded up to the
    dimension multiple) so we only ever crop down. Larger requests generate
    at the biggest aspect-matching size under max_pixels and are upscaled
    afterwards.
    """
    if width * height <= max_pixels:
        gen_w = math.ceil(width / multiple) * multiple
        gen_h = math.ceil(height / multiple) * multiple
        return gen_w, gen_h, False
    scale = (max_pixels / (width * height)) ** 0.5
    gen_w = max(multiple, round(width * scale / multiple) * multiple)
    gen_h = max(multiple, round(height * scale / multiple) * multiple)
    while gen_w * gen_h > max_pixels:
        if gen_w > multiple and gen_w / gen_h > width / height:
            gen_w -= multiple
        else:
            gen_h = max(multiple, gen_h - multiple)
    return gen_w, gen_h, True


def finalize_image(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize + center-crop (cover semantics) to the exact requested pixels."""
    return ImageOps.fit(img, (width, height), Image.LANCZOS)


def save_image(img: Image.Image, path: Path) -> None:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"unsupported output format {ext!r}: use .webp, .png, or .jpg"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".webp":
        img.save(path, quality=WEBP_QUALITY)
    elif ext in (".jpg", ".jpeg"):
        img.convert("RGB").save(path, quality=JPEG_QUALITY)
    elif ext == ".png":
        img.save(path)


def numbered_outputs(out: Path, count: int) -> list[Path]:
    if count <= 1:
        return [out]
    return [out.with_name(f"{out.stem}-{i}{out.suffix}") for i in range(1, count + 1)]


STYLE_FILENAME = "imagegen.toml"


def discover_style_config(start: Path) -> dict | None:
    """Walk start and its parents for imagegen.toml; return its [style] table."""
    for directory in [start, *start.parents]:
        candidate = directory / STYLE_FILENAME
        if candidate.is_file():
            with open(candidate, "rb") as f:
                try:
                    data = tomllib.load(f)
                except tomllib.TOMLDecodeError as exc:
                    raise ValueError(f"invalid TOML in {candidate}: {exc}") from exc
            style = data.get("style", {})
            for key, value in style.items():
                if not isinstance(value, str):
                    raise ValueError(
                        f"invalid {candidate}: style.{key} must be a string"
                    )
            return style
    return None


def apply_style(prompt: str, style: dict | None) -> str:
    if not style:
        return prompt
    parts = [
        style.get("prefix", "").strip(),
        prompt.strip(),
        style.get("suffix", "").strip(),
    ]
    return ", ".join(p for p in parts if p)


@dataclass
class Job:
    prompt: str
    out: Path
    width: int
    height: int
    seed: int | None = None
    count: int = 1


def parse_manifest(path: Path) -> list[Job]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("manifest must be a non-empty JSON array of jobs")
    jobs = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"manifest item {index} must be a JSON object")
        missing = [key for key in ("prompt", "out", "size") if key not in item]
        if missing:
            raise ValueError(
                f"manifest item {index} missing keys: {', '.join(missing)}"
            )
        seed = item.get("seed")
        if seed is not None and (
            isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
        ):
            raise ValueError(
                f"manifest item {index}: seed must be a non-negative integer"
            )
        count = item.get("count", 1)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(f"manifest item {index}: count must be a positive integer")
        width, height = parse_size(item["size"])
        jobs.append(
            Job(
                prompt=item["prompt"],
                out=Path(item["out"]),
                width=width,
                height=height,
                seed=seed,
                count=count,
            )
        )
    return jobs


def resolve_seeds(seed: int | None, count: int) -> list[int]:
    if seed is None:
        return [random.randrange(2**32) for _ in range(count)]
    return [seed + i for i in range(count)]
