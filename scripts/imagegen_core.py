"""Pure logic for agentimagegen: no mflux imports, fully unit-testable."""

import math
import re

MAX_PIXELS = 1_310_720  # 1.25 MP: schnell stays reliable here, and 1440x800 heroes fit natively
MULTIPLE = 16


def parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value.strip().lower())
    if not match:
        raise ValueError(f"size must look like 1440x800, got: {value!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 16 or height < 16:
        raise ValueError(f"size must be at least 16x16, got: {value!r}")
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
    return gen_w, gen_h, True
