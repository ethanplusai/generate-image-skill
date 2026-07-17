# agentimagegen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public GitHub repo that is both an installable Agent Skill (SKILL.md) and a self-contained uv/PEP 723 Python CLI that generates production-ready web/app images locally via mflux + FLUX.1-schnell 4-bit on Apple Silicon.

**Architecture:** Two Python files under `scripts/`: `imagegen_core.py` holds all pure logic (size mapping, style config, manifest parsing, output handling) and is unit-testable without mflux; `generate.py` is the PEP 723 CLI entry that parses args, supports `--dry-run` without importing mflux, and lazily loads Flux1 for real generation. SKILL.md + `reference/prompting.md` are the agent-facing taste layer.

**Tech Stack:** Python ≥3.11 (tomllib), uv (PEP 723 inline deps), mflux 0.18.0 (MLX), Pillow, pytest, GitHub Actions (macOS arm64 runner).

## Global Constraints

- Platform v1: Apple Silicon macOS only (`sys.platform == "darwin"` and `platform.machine() == "arm64"`); exit with an actionable message elsewhere.
- Dependency pin: `mflux==0.18.0`; `requires-python = ">=3.11"` in the PEP 723 block.
- Default model: `dhairyashil/FLUX.1-schnell-mflux-4bit` with `base_model="schnell"`; default `--steps 4`.
- Native generation cap: 1,310,720 pixels (1.25 MP — the spec's "~1 MP", raised so common 1440×800 heroes generate natively); generation dimensions are multiples of 16; larger requests are generated at the aspect-matching size under the cap then Lanczos-upscaled with a printed warning.
- Output formats: `.webp` (quality 82), `.jpg`/`.jpeg` (quality 88, RGB), `.png`; any other extension is a `ValueError`.
- `--dry-run` must never import mflux.
- Unit tests must run without mflux: `uvx --with pillow pytest tests/ -v`.
- Verified mflux 0.18.0 API (do not deviate):
  `from mflux.models.flux.variants.txt2img.flux import Flux1, ModelConfig`;
  `ModelConfig.from_name(model_name, base_model="schnell")`;
  `Flux1(model_config=cfg)`;
  `flux.generate_image(seed=int, prompt=str, num_inference_steps=int, width=int, height=int)` returns an object whose `.image` attribute is a `PIL.Image.Image` .
- Every commit message ends with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Reference-hardware baseline (M4 Pro, 48 GB): ~7 GB one-time model download, ~40 s per 1024×768 image at 4 steps, 16 GB peak MLX memory. Use these numbers in docs.

---

### Task 1: Sizing logic (`parse_size`, `plan_generation_size`)

**Files:**
- Create: `scripts/imagegen_core.py`
- Create: `tests/conftest.py`
- Test: `tests/test_sizing.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `parse_size(value: str) -> tuple[int, int]` (raises `ValueError` on bad input); `plan_generation_size(w: int, h: int, max_pixels: int = 1_310_720, multiple: int = 16) -> tuple[int, int, bool]` returning `(gen_w, gen_h, needs_upscale)`. Constants `MAX_PIXELS`, `MULTIPLE`.

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
```

Create `tests/test_sizing.py`:

```python
import pytest

from imagegen_core import parse_size, plan_generation_size


def test_parse_size_valid():
    assert parse_size("1440x800") == (1440, 800)


def test_parse_size_strips_and_lowercases():
    assert parse_size(" 1200X630 ") == (1200, 630)


def test_parse_size_rejects_garbage():
    with pytest.raises(ValueError):
        parse_size("1440by800")


def test_parse_size_rejects_tiny():
    with pytest.raises(ValueError):
        parse_size("8x8")


def test_small_request_rounds_up_to_multiple_of_16():
    assert plan_generation_size(1000, 700) == (1008, 704, False)


def test_exact_multiple_untouched():
    assert plan_generation_size(1024, 768) == (1024, 768, False)


def test_common_hero_size_generates_natively():
    assert plan_generation_size(1440, 800) == (1440, 800, False)


def test_oversized_request_scales_to_cap_and_flags_upscale():
    assert plan_generation_size(2880, 1600) == (1536, 848, True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx --with pillow pytest tests/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'imagegen_core'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/imagegen_core.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx --with pillow pytest tests/ -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/imagegen_core.py tests/conftest.py tests/test_sizing.py
git commit -m "feat: size parsing and native-resolution planning

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Image finalization and saving (`finalize_image`, `save_image`)

**Files:**
- Modify: `scripts/imagegen_core.py` (append)
- Test: `tests/test_output.py`

**Interfaces:**
- Consumes: nothing from other tasks (pure Pillow).
- Produces: `finalize_image(img: PIL.Image.Image, width: int, height: int) -> PIL.Image.Image` (cover-crop/upscale to exact size); `save_image(img: PIL.Image.Image, path: pathlib.Path) -> None` (format from extension, creates parent dirs, raises `ValueError` on unknown extension); `numbered_outputs(out: Path, count: int) -> list[Path]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_output.py`:

```python
from pathlib import Path

import pytest
from PIL import Image

from imagegen_core import finalize_image, numbered_outputs, save_image


def test_finalize_center_crops_to_exact_size():
    img = Image.new("RGB", (1024, 768), "red")
    assert finalize_image(img, 1000, 700).size == (1000, 700)


def test_finalize_upscales_when_source_smaller():
    img = Image.new("RGB", (1376, 768), "blue")
    assert finalize_image(img, 2880, 1600).size == (2880, 1600)


def test_save_webp_creates_parents(tmp_path):
    path = tmp_path / "sub" / "img.webp"
    save_image(Image.new("RGB", (32, 32), "green"), path)
    assert Image.open(path).format == "WEBP"


def test_save_jpg_converts_to_rgb(tmp_path):
    path = tmp_path / "img.jpg"
    save_image(Image.new("RGBA", (32, 32)), path)
    assert Image.open(path).format == "JPEG"


def test_save_png(tmp_path):
    path = tmp_path / "img.png"
    save_image(Image.new("RGB", (32, 32)), path)
    assert Image.open(path).format == "PNG"


def test_save_rejects_unknown_extension(tmp_path):
    with pytest.raises(ValueError):
        save_image(Image.new("RGB", (32, 32)), tmp_path / "img.gif")


def test_numbered_outputs_single():
    assert numbered_outputs(Path("a/hero.webp"), 1) == [Path("a/hero.webp")]


def test_numbered_outputs_multiple():
    assert numbered_outputs(Path("a/hero.webp"), 3) == [
        Path("a/hero-1.webp"),
        Path("a/hero-2.webp"),
        Path("a/hero-3.webp"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx --with pillow pytest tests/test_output.py -v`
Expected: FAIL — `ImportError: cannot import name 'finalize_image'`

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/imagegen_core.py` (and add the new imports at the top of the file):

```python
from pathlib import Path

from PIL import Image, ImageOps

WEBP_QUALITY = 82
JPEG_QUALITY = 88


def finalize_image(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize + center-crop (cover semantics) to the exact requested pixels."""
    return ImageOps.fit(img, (width, height), Image.LANCZOS)


def save_image(img: Image.Image, path: Path) -> None:
    ext = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".webp":
        img.save(path, quality=WEBP_QUALITY)
    elif ext in (".jpg", ".jpeg"):
        img.convert("RGB").save(path, quality=JPEG_QUALITY)
    elif ext == ".png":
        img.save(path)
    else:
        raise ValueError(
            f"unsupported output format {ext!r}: use .webp, .png, or .jpg"
        )


def numbered_outputs(out: Path, count: int) -> list[Path]:
    if count <= 1:
        return [out]
    return [out.with_name(f"{out.stem}-{i}{out.suffix}") for i in range(1, count + 1)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx --with pillow pytest tests/ -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/imagegen_core.py tests/test_output.py
git commit -m "feat: exact-size finalization, format-aware saving, numbered outputs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Style config (`discover_style_config`, `apply_style`) + example file

**Files:**
- Modify: `scripts/imagegen_core.py` (append)
- Create: `imagegen.example.toml`
- Test: `tests/test_style.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `discover_style_config(start: Path) -> dict | None` (walks `start` and its parents for `imagegen.toml`, returns its `[style]` table); `apply_style(prompt: str, style: dict | None) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_style.py`:

```python
from imagegen_core import apply_style, discover_style_config


def test_discovers_config_in_parent(tmp_path):
    (tmp_path / "imagegen.toml").write_text(
        '[style]\nprefix = "editorial photo"\nsuffix = "muted palette"\n'
    )
    nested = tmp_path / "src" / "components"
    nested.mkdir(parents=True)
    assert discover_style_config(nested) == {
        "prefix": "editorial photo",
        "suffix": "muted palette",
    }


def test_returns_none_when_absent(tmp_path):
    assert discover_style_config(tmp_path) is None


def test_apply_style_wraps_prompt():
    style = {"prefix": "editorial photo", "suffix": "muted palette"}
    assert (
        apply_style("a pottery studio", style)
        == "editorial photo, a pottery studio, muted palette"
    )


def test_apply_style_none_passthrough():
    assert apply_style("a pottery studio", None) == "a pottery studio"


def test_apply_style_partial():
    assert apply_style("x", {"suffix": "warm light"}) == "x, warm light"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx --with pillow pytest tests/test_style.py -v`
Expected: FAIL — `ImportError: cannot import name 'apply_style'`

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/imagegen_core.py` (add `import tomllib` at the top):

```python
import tomllib

STYLE_FILENAME = "imagegen.toml"


def discover_style_config(start: Path) -> dict | None:
    """Walk start and its parents for imagegen.toml; return its [style] table."""
    for directory in [start, *start.parents]:
        candidate = directory / STYLE_FILENAME
        if candidate.is_file():
            with open(candidate, "rb") as f:
                return tomllib.load(f).get("style", {})
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
```

Create `imagegen.example.toml`:

```toml
# Copy to your project root as `imagegen.toml`. Every generated image in the
# project gets prefix/suffix wrapped around its prompt so assets share one
# art direction. Delete the file (or pass --no-style) to opt out.

[style]
prefix = "warm editorial photography"
suffix = "muted earthy palette, soft natural light, film grain"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx --with pillow pytest tests/ -v`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/imagegen_core.py tests/test_style.py imagegen.example.toml
git commit -m "feat: project style config discovery and prompt wrapping

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Batch manifest and seed resolution (`Job`, `parse_manifest`, `resolve_seeds`)

**Files:**
- Modify: `scripts/imagegen_core.py` (append)
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `parse_size` from Task 1.
- Produces: `@dataclass Job(prompt: str, out: Path, width: int, height: int, seed: int | None = None, count: int = 1)`; `parse_manifest(path: Path) -> list[Job]` (raises `ValueError` with item index on bad entries); `resolve_seeds(seed: int | None, count: int) -> list[int]` (fixed seed → sequential `seed+i`; None → random 32-bit).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_manifest.py`:

```python
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


def test_seeds_sequential_from_fixed():
    assert resolve_seeds(42, 3) == [42, 43, 44]


def test_seeds_random_when_none():
    seeds = resolve_seeds(None, 2)
    assert len(seeds) == 2
    assert all(0 <= s < 2**32 for s in seeds)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx --with pillow pytest tests/test_manifest.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_manifest'`

- [ ] **Step 3: Write minimal implementation**

Append to `scripts/imagegen_core.py` (add `import json`, `import random`, and `from dataclasses import dataclass` at the top):

```python
import json
import random
from dataclasses import dataclass


@dataclass
class Job:
    prompt: str
    out: Path
    width: int
    height: int
    seed: int | None = None
    count: int = 1


def parse_manifest(path: Path) -> list[Job]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise ValueError("manifest must be a non-empty JSON array of jobs")
    jobs = []
    for index, item in enumerate(data):
        missing = [key for key in ("prompt", "out", "size") if key not in item]
        if missing:
            raise ValueError(
                f"manifest item {index} missing keys: {', '.join(missing)}"
            )
        width, height = parse_size(item["size"])
        jobs.append(
            Job(
                prompt=item["prompt"],
                out=Path(item["out"]),
                width=width,
                height=height,
                seed=item.get("seed"),
                count=item.get("count", 1),
            )
        )
    return jobs


def resolve_seeds(seed: int | None, count: int) -> list[int]:
    if seed is None:
        return [random.randrange(2**32) for _ in range(count)]
    return [seed + i for i in range(count)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx --with pillow pytest tests/ -v`
Expected: 26 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/imagegen_core.py tests/test_manifest.py
git commit -m "feat: batch manifest parsing and seed resolution

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: CLI entry point with `--dry-run` (`scripts/generate.py`)

**Files:**
- Create: `scripts/generate.py`

**Interfaces:**
- Consumes: everything `imagegen_core` produced in Tasks 1–4 (exact names in the import block below).
- Produces: the complete CLI. `main()` builds plans as tuples `(job, gen_w, gen_h, needs_upscale, outs, seeds)`; `run_plans(plans, model: str, steps: int)` does mflux generation (implemented here, verified live in Task 6).

- [ ] **Step 1: Write the full CLI**

Create `scripts/generate.py`:

```python
#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["mflux==0.18.0"]
# ///
"""Generate images locally with FLUX.1-schnell for website/app assets.

Single image:
    uv run scripts/generate.py "warm photo of a pottery studio" \
        --out public/hero.webp --size 1440x800

Batch (loads the model once for all jobs):
    uv run scripts/generate.py --batch manifest.json
"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from imagegen_core import (
    Job,
    apply_style,
    discover_style_config,
    finalize_image,
    numbered_outputs,
    parse_manifest,
    parse_size,
    plan_generation_size,
    resolve_seeds,
    save_image,
)

DEFAULT_MODEL = "dhairyashil/FLUX.1-schnell-mflux-4bit"
BASE_MODEL = "schnell"


def check_environment() -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        sys.exit(
            "agentimagegen v1 requires an Apple Silicon Mac (macOS arm64).\n"
            "Linux/CUDA support is on the roadmap:\n"
            "https://github.com/ethanrogers/agentimagegen#roadmap"
        )
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        )
        if int(result.stdout.strip()) < 16 * 1024**3:
            print(
                "warning: under 16 GB RAM; generation may be very slow (swapping).",
                file=sys.stderr,
            )
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass  # RAM check is best-effort only


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images locally with FLUX.1-schnell."
    )
    parser.add_argument("prompt", nargs="?", help="image description")
    parser.add_argument("--out", help="output path (.webp, .png, or .jpg)")
    parser.add_argument("--size", help="exact output size, e.g. 1440x800")
    parser.add_argument("--seed", type=int, help="fixed seed for reproducibility")
    parser.add_argument(
        "--count", type=int, default=1, help="number of candidates (hero-1.webp, ...)"
    )
    parser.add_argument("--steps", type=int, default=4, help="inference steps")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model repo")
    parser.add_argument(
        "--batch", help="JSON manifest: [{prompt, out, size, seed?, count?}, ...]"
    )
    parser.add_argument(
        "--no-style", action="store_true", help="ignore project imagegen.toml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the generation plan without loading the model",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.batch:
        jobs = parse_manifest(Path(args.batch))
    elif args.prompt:
        if not args.out or not args.size:
            sys.exit("error: --out and --size are required with a prompt")
        width, height = parse_size(args.size)
        jobs = [
            Job(
                prompt=args.prompt,
                out=Path(args.out),
                width=width,
                height=height,
                seed=args.seed,
                count=args.count,
            )
        ]
    else:
        sys.exit("error: provide a prompt or --batch manifest.json")

    style = None if args.no_style else discover_style_config(Path.cwd())
    plans = []
    for job in jobs:
        job.prompt = apply_style(job.prompt, style)
        gen_w, gen_h, needs_upscale = plan_generation_size(job.width, job.height)
        outs = numbered_outputs(job.out, job.count)
        seeds = resolve_seeds(job.seed, job.count)
        plans.append((job, gen_w, gen_h, needs_upscale, outs, seeds))

    if args.dry_run:
        for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
            note = " (will be Lanczos-upscaled)" if needs_upscale else ""
            for out, seed in zip(outs, seeds):
                print(
                    f"[dry-run] {out}  {job.width}x{job.height}  "
                    f"gen@{gen_w}x{gen_h}{note}  seed={seed}"
                )
                print(f"          prompt: {job.prompt}")
        return

    check_environment()
    run_plans(plans, model=args.model, steps=args.steps)


def run_plans(plans, model: str, steps: int) -> None:
    print(f"loading {model} (first run downloads ~7 GB)...", flush=True)
    from mflux.models.flux.variants.txt2img.flux import Flux1, ModelConfig

    flux = Flux1(model_config=ModelConfig.from_name(model, base_model=BASE_MODEL))
    for job, gen_w, gen_h, needs_upscale, outs, seeds in plans:
        for out, seed in zip(outs, seeds):
            generated = flux.generate_image(
                seed=seed,
                prompt=job.prompt,
                num_inference_steps=steps,
                width=gen_w,
                height=gen_h,
            )
            image = finalize_image(generated.image, job.width, job.height)
            if needs_upscale:
                print(
                    f"warning: {out} exceeds the native generation ceiling; "
                    f"upscaled from {gen_w}x{gen_h}.",
                    file=sys.stderr,
                )
            save_image(image, out)
            print(f"wrote {out} ({job.width}x{job.height}, seed={seed})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify dry-run (single image, oversized size)**

Run: `uv run scripts/generate.py "test prompt" --out /tmp/x.webp --size 2880x1600 --seed 1 --dry-run`
Expected output (exact):

```
[dry-run] /tmp/x.webp  2880x1600  gen@1536x848 (will be Lanczos-upscaled)  seed=1
          prompt: test prompt
```

- [ ] **Step 3: Verify dry-run (batch + count + style)**

```bash
cd /tmp && mkdir -p igtest && cd igtest
printf '[style]\nprefix = "editorial photo"\n' > imagegen.toml
printf '[{"prompt": "hero", "out": "public/hero.webp", "size": "1440x800", "seed": 7, "count": 2}]' > m.json
uv run /Users/ethanrogers/Projects/agentimagegen/scripts/generate.py --batch m.json --dry-run
```

Expected output (exact):

```
[dry-run] public/hero-1.webp  1440x800  gen@1440x800  seed=7
          prompt: editorial photo, hero
[dry-run] public/hero-2.webp  1440x800  gen@1440x800  seed=8
          prompt: editorial photo, hero
```

- [ ] **Step 4: Verify error paths**

Run: `uv run scripts/generate.py --dry-run` — Expected: exit 1, `error: provide a prompt or --batch manifest.json`
Run: `uv run scripts/generate.py "x" --out /tmp/x.webp --dry-run` — Expected: exit 1, `error: --out and --size are required with a prompt`

- [ ] **Step 5: Run full test suite, then commit**

Run: `uvx --with pillow pytest tests/ -v` — Expected: 26 passed

```bash
git add scripts/generate.py
git commit -m "feat: PEP 723 CLI with dry-run, batch, style, and env checks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Live generation smoke test (model is already cached locally)

**Files:**
- No new files; verifies `run_plans` end-to-end.

**Interfaces:**
- Consumes: the full CLI from Task 5.
- Produces: confirmed working generation on reference hardware.

- [ ] **Step 1: Generate a real image**

Run (allow 10 minutes):

```bash
uv run scripts/generate.py \
    "minimalist abstract gradient background, soft blue and sand tones" \
    --out /tmp/igtest/smoke.webp --size 800x500 --seed 7
```

Expected: `wrote /tmp/igtest/smoke.webp (800x500, seed=7)` in ~60 s (model cached).

- [ ] **Step 2: Verify dimensions and format programmatically**

Run: `uvx --with pillow python -c "from PIL import Image; i = Image.open('/tmp/igtest/smoke.webp'); print(i.format, i.size)"`
Expected: `WEBP (800, 500)`

- [ ] **Step 3: View the image**

Read `/tmp/igtest/smoke.webp` and confirm it is a plausible abstract gradient (not noise, not black).

- [ ] **Step 4: Verify seed reproducibility**

Re-run the Step 1 command with `--out /tmp/igtest/smoke2.webp`, then:

```bash
uvx --with pillow python -c "
from PIL import Image, ImageChops
a = Image.open('/tmp/igtest/smoke.webp')
b = Image.open('/tmp/igtest/smoke2.webp')
print('identical:', ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is None)
"
```

Expected: `identical: True`

- [ ] **Step 5: Commit (no code changes — record the verification)**

```bash
git commit --allow-empty -m "test: live generation smoke verified (800x500 webp, seed-reproducible)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: SKILL.md and reference/prompting.md (the taste layer)

**Files:**
- Create: `SKILL.md`
- Create: `reference/prompting.md`

**Interfaces:**
- Consumes: CLI flags exactly as defined in Task 5.
- Produces: agent-facing docs; the skill's trigger description.

- [ ] **Step 1: Write SKILL.md**

Create `SKILL.md`:

````markdown
---
name: agentimagegen
description: Generate original images locally (free, offline, no API keys) for websites and apps — hero images, backgrounds, textures, spot illustrations, og:images, placeholder photography — using FLUX.1-schnell on Apple Silicon. Use when a project needs real imagery instead of stock photos, gray boxes, or placeholder URLs. Not for logos, icons, or UI screenshots.
---

# agentimagegen — local image generation for coding agents

Generate production-ready imagery while you build, on the user's own machine.
Free, offline, Apache-2.0-licensed model, no API keys.

## When to use — and when NOT to

**Generate:** hero images, section backgrounds, textures, spot illustrations,
og:images (1200x630), placeholder/editorial photography, empty-state art.

**Do NOT generate:** logos, icons, UI screenshots, or text-heavy graphics.
Diffusion models render text and precise geometry badly. Use SVG for
logos/icons and real screenshots for UI. If an image needs more than 1–2
words of legible text, build it in HTML/CSS instead.

## How to run

The script lives in THIS skill's directory (the directory containing this
SKILL.md), not in the user's project. Use the skill's base directory for the
path:

```bash
uv run <SKILL_DIR>/scripts/generate.py "warm photo of a pottery studio" \
    --out public/hero.webp --size 1440x800
```

**TIMEOUTS — important:** each image takes ~40–90 s; the FIRST EVER run also
downloads ~7 GB (several minutes). Set your command timeout to at least 10
minutes, or run in the background and poll. Do not let a default 2-minute
timeout kill a working generation.

Requirements: Apple Silicon Mac, `uv` installed (`brew install uv`). The
script exits with a clear message on unsupported platforms.

## Flags

| Flag | Meaning |
|---|---|
| `--out PATH` | Output file; format from extension: `.webp` (best for web), `.png`, `.jpg` |
| `--size WxH` | Exact output pixels, e.g. `1440x800`. Oversized requests are upscaled with a warning |
| `--seed N` | Reproducible output; same seed + prompt = same image |
| `--count N` | N candidates as `name-1.webp`, `name-2.webp`, … with sequential seeds |
| `--batch FILE` | JSON array of `{prompt, out, size, seed?, count?}` — loads the model once for all jobs |
| `--no-style` | Ignore the project's `imagegen.toml` |
| `--dry-run` | Print the plan (styled prompts, sizes, seeds) without loading the model |

## Workflow rules

1. **Plan all assets first, generate in one `--batch`** — the model loads
   once (~20 s) per invocation; batching amortizes it.
2. **Generate 1–2 candidates, not 10.** Use `--count 2` when unsure.
3. **ALWAYS view the output** (read the image file) before wiring it into
   the page. If it's bad, regenerate with a different seed or a more
   concrete prompt — don't ship unseen images.
4. **Record the seed** you shipped (e.g. in the asset's git commit message)
   so the image can be regenerated or varied later.
5. **Set up style once:** if the project has no `imagegen.toml`, consider
   creating one (copy `imagegen.example.toml` from this skill's directory)
   so all assets share an art direction.

## Prompting

Flux responds best to natural-language scene descriptions, not tag soup.
Describe subject, setting, lighting, and mood in a full sentence. See
`reference/prompting.md` in this skill's directory for per-asset-type
recipes (hero, texture, illustration, og:image, photography).
````

- [ ] **Step 2: Write reference/prompting.md**

Create `reference/prompting.md`:

````markdown
# Prompt recipes by asset type

Flux.1-schnell wants natural-language captions: subject, setting, lighting,
mood, style — as a sentence, not comma-spam tags. Concrete nouns beat
adjectives. Never ask for legible text beyond 1–2 words.

## Hero images (1440x800, 1440x600, 2880x1600 for retina)

Pattern: `[style] photo of [concrete scene], [lighting], [mood]`

> warm, natural-light photograph of a sunlit pottery studio, shelves of
> handmade ceramic bowls, soft morning atmosphere

Leave negative space for headline overlay by putting the subject to one
side: "subject on the right third, soft out-of-focus background on the left".

## Section backgrounds & textures (1440x600, or square tiles 1024x1024)

Pattern: `abstract [material/texture], [palette], [energy]`

> abstract close-up of handmade paper texture, warm ivory tones, subtle
> fibers, soft even lighting, minimalist

Keep contrast LOW so foreground text stays readable: add "muted, low
contrast, soft" and avoid "vibrant, dramatic".

## Spot illustrations (600x600 – 800x800)

Pattern: `flat [style] illustration of [single subject], [palette], simple shapes, clean background`

> flat minimalist illustration of a paper airplane looping upward, two-tone
> terracotta and cream, simple geometric shapes, solid off-white background

One subject per image. Diffusion gets crowded compositions wrong.

## og:images / social cards (1200x630)

Design for NO text (your page title gets overlaid by the platform or by
HTML). Aim for a bold, simple, high-recognition composition:

> bold minimal composition of a single terracotta ceramic bowl centered on
> a warm cream background, soft studio lighting, generous negative space

## Placeholder & editorial photography (varies)

Pattern: `[shot type] photograph of [subject], [setting], [lighting]`

> candid medium-shot photograph of two people reviewing sketches at a
> workshop table, natural window light, shallow depth of field

Avoid celebrity names and brand logos. For diverse team/people sets,
generate separate images with consistent lighting via a shared style suffix
rather than one group shot.

## What consistently fails — redirect instead

| Ask | Do this instead |
|---|---|
| Logo | SVG, hand-written |
| Icon set | SVG library or hand-drawn SVG |
| UI screenshot | Build the UI, screenshot it |
| Chart/diagram | HTML/SVG/Mermaid |
| Legible paragraph text in image | HTML/CSS overlay |
````

- [ ] **Step 3: Sanity-check the paths the docs promise**

Verify `scripts/generate.py`, `imagegen.example.toml`, and `reference/prompting.md` all exist where SKILL.md says they are: `ls scripts/generate.py imagegen.example.toml reference/prompting.md`
Expected: all three listed, no error.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md reference/prompting.md
git commit -m "docs: agent-facing SKILL.md and prompting recipes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: README.md and LICENSE

**Files:**
- Create: `README.md`
- Create: `LICENSE`

**Interfaces:**
- Consumes: measured numbers from Global Constraints; CLI flags from Task 5.
- Produces: the public-facing repo front page.

- [ ] **Step 1: Write README.md**

Create `README.md`:

````markdown
# agentimagegen

Give your coding agent the ability to generate its own imagery — locally,
free, no API keys. A portable [Agent Skill](https://agentskills.io) plus a
self-contained CLI that runs FLUX.1-schnell on Apple Silicon via
[mflux](https://github.com/filipstrand/mflux).

Your agent is building a site and needs a hero image, background texture, or
og:image? Instead of shipping gray boxes or hotlinking stock photos, it
generates the asset on your machine in ~40 seconds.

## Requirements

- Apple Silicon Mac (M1 or later). 24 GB+ RAM recommended; 16 GB works but
  swaps (peak usage is ~16 GB).
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- ~8 GB free disk for the one-time model download

Measured on an M4 Pro (48 GB): ~40 s per 1024×768 image, ~2 min one-time
model download.

## Install

**Claude Code** — global:

```bash
git clone https://github.com/ethanrogers/agentimagegen ~/.claude/skills/agentimagegen
```

or per-project: clone into `.claude/skills/agentimagegen` inside your repo.

**Codex and other agents:** clone anywhere and point the agent at
`SKILL.md` (e.g. reference it from `AGENTS.md`). The CLI works standalone —
the skill file is instructions, not a dependency.

## Use it yourself (without an agent)

```bash
uv run scripts/generate.py "warm photo of a pottery studio" \
    --out hero.webp --size 1440x800
```

First run downloads the quantized model (~7 GB) from Hugging Face — no
account needed. See `SKILL.md` for all flags (`--batch`, `--count`,
`--seed`, `--dry-run`) and `reference/prompting.md` for prompt recipes.

## Consistent art direction

Copy `imagegen.example.toml` to your project root as `imagegen.toml`. Its
style prefix/suffix wraps every prompt so all of a project's images share
one look.

## Licensing

- This repo: MIT.
- Model weights: [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
  is **Apache 2.0** — commercial use of the model and its outputs is fine.
  (FLUX.1-dev is NOT — it's non-commercial. This project deliberately uses
  schnell.)

## Uninstall / reclaim disk

Model weights live in the Hugging Face cache. Remove them with:

```bash
rm -rf ~/.cache/huggingface/hub/models--dhairyashil--FLUX.1-schnell-mflux-4bit
```

## Roadmap

- Background removal (transparent PNGs)
- CUDA/Linux backend behind the same CLI
- Warm daemon mode (skip the ~20 s model load per invocation)
- img2img / style-reference images
- Evaluate FLUX.2-klein-4B as an alternative default model

PRs welcome.
````

- [ ] **Step 2: Write LICENSE**

Create `LICENSE` with the standard MIT text:

```text
MIT License

Copyright (c) 2026 Ethan Rogers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Commit**

```bash
git add README.md LICENSE
git commit -m "docs: public README and MIT license

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: test command from Global Constraints; dry-run CLI from Task 5.
- Produces: CI that runs on every push/PR without downloading the model.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: macos-15 # Apple Silicon runner
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Unit tests (no model)
        run: uvx --with pillow pytest tests/ -v
      - name: CLI dry-run (no model)
        run: uv run scripts/generate.py "ci smoke" --out /tmp/ci.webp --size 640x400 --dry-run
```

- [ ] **Step 2: Verify both commands locally exactly as CI runs them**

```bash
uvx --with pillow pytest tests/ -v
uv run scripts/generate.py "ci smoke" --out /tmp/ci.webp --size 640x400 --dry-run
```

Expected: 26 passed; one `[dry-run]` line for `/tmp/ci.webp 640x400 gen@640x400`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: unit tests and CLI dry-run on macOS arm64

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: End-to-end acceptance test (real multi-asset batch)

**Files:**
- No new files. Final verification of the whole product as an agent would use it.

**Interfaces:**
- Consumes: everything.
- Produces: shipped v1, ready to publish.

- [ ] **Step 1: Simulate an agent workflow with a real batch**

```bash
cd /tmp/igtest
printf '[
  {"prompt": "sunlit pottery studio with shelves of ceramic bowls", "out": "site/hero.webp", "size": "1440x800", "seed": 11},
  {"prompt": "abstract close-up of handmade paper texture, low contrast", "out": "site/bg.webp", "size": "1440x600", "seed": 12},
  {"prompt": "bold minimal composition of a single terracotta bowl centered, generous negative space", "out": "site/og.jpg", "size": "1200x630", "seed": 13}
]' > site.json
uv run /Users/ethanrogers/Projects/agentimagegen/scripts/generate.py --batch site.json
```

Expected: three `wrote ...` lines; total time ~3 minutes (one model load).
Note: `/tmp/igtest/imagegen.toml` from Task 5 still exists, so prompts should
show the `editorial photo` prefix — that's the style system working.

- [ ] **Step 2: Verify all three outputs**

Run: `uvx --with pillow python -c "
from PIL import Image
for name, want in [('site/hero.webp', (1440, 800)), ('site/bg.webp', (1440, 600)), ('site/og.jpg', (1200, 630))]:
    img = Image.open(f'/tmp/igtest/{name}')
    assert img.size == want, (name, img.size)
    print(name, img.format, img.size, 'ok')
"`
Expected: three `ok` lines (WEBP, WEBP, JPEG).

- [ ] **Step 3: View all three images**

Read each file and confirm each is plausible, on-brief, and shares the
editorial-photo art direction. If any is bad, that's a prompting-recipe
problem — fix `reference/prompting.md`, not the code.

- [ ] **Step 4: Final review and cleanup**

Run: `git status` — Expected: clean tree, nothing untracked (test artifacts all live in `/tmp/igtest`).
Run: `uvx --with pillow pytest tests/ -v` — Expected: 26 passed.

- [ ] **Step 5: Commit (record acceptance)**

```bash
git commit --allow-empty -m "test: end-to-end multi-asset batch acceptance verified

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Publishing the repo to GitHub (`gh repo create ethanrogers/agentimagegen --public`) happens with the user after acceptance — it's outward-facing.
