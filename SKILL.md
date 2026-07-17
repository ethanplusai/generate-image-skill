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
| `--out PATH` | Output file; format from extension: `.webp` (best for web), `.png`, `.jpg`/`.jpeg` (both work) |
| `--size WxH` | Exact output pixels, e.g. `1440x800`. Oversized requests are upscaled with a warning |
| `--seed N` | Reproducible output; same seed + prompt = same image |
| `--count N` | N candidates as `name-1.webp`, `name-2.webp`, … with sequential seeds |
| `--steps N` | Inference steps, default 4 — more steps is rarely worth it on schnell |
| `--model REPO` | Override the HF model repo (advanced; default is the pinned 4-bit schnell) |
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
