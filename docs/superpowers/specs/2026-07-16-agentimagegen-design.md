# agentimagegen — Design Spec

**Date:** 2026-07-16
**Status:** Validated by smoke test on reference hardware (M4 Pro, 48 GB)

## What it is

A public GitHub repo that is simultaneously:

1. **An installable Agent Skill** following the open SKILL.md standard, usable by
   Claude Code, Codex, and any agent that reads skills or can be pointed at a
   markdown file.
2. **A self-contained Python CLI** that generates images locally with
   FLUX.1-schnell (Apache 2.0) via mflux on Apple Silicon.

Agents read `SKILL.md` for *when and how* to generate imagery while building
websites/apps; the CLI does the generating. No API keys, no cloud, no
per-image cost.

## Validated feasibility (measured 2026-07-16, M4 Pro / 48 GB)

- Model: `dhairyashil/FLUX.1-schnell-mflux-4bit` (pre-quantized, ~7 GB)
- Download: ~2 minutes, unauthenticated (no HF account needed)
- Generation: ~40 s for 1024×768 at 4 steps (~10 s/step)
- Peak MLX memory: 16.01 GB
- Invocation that worked end-to-end:
  `uvx --from mflux mflux-generate --model dhairyashil/FLUX.1-schnell-mflux-4bit --base-model schnell --prompt "..." --steps 4 --width 1024 --height 768 --output out.png`

**Hardware guidance derived from this:** 48 GB comfortable; 24 GB recommended
minimum; 16 GB "works but will swap."

## Decisions made (with rationale)

| Decision | Choice | Why |
|---|---|---|
| Hardware target (v1) | Apple Silicon only, via mflux/MLX | Dogfoodable on reference machine; CUDA is a fast-follow behind the same CLI interface |
| Invocation model | Plain one-shot CLI | Simplest; no daemon lifecycle. Model-load tax amortized via `--batch` |
| Model | FLUX.1-schnell 4-bit quantized | Apache 2.0 (commercial OK), ungated download, fast (4 steps). FLUX.1-dev rejected: non-commercial license |
| Distribution | Self-contained via uv, PEP 723 inline deps | Users install nothing but uv; no PyPI account; versions in lockstep with skill |
| Dependency pinning | Pin `mflux` (and pillow) to exact known-good versions in the PEP 723 block | A public repo where `uv run` floats to latest breaks unreproducibly for strangers; bumps happen via PRs with a smoke test |
| v1 scope | Exact-size output, web formats, style config | Background removal, CUDA, daemon, img2img deferred to roadmap |

Candidate to evaluate during implementation: `Runpod/FLUX.2-klein-4B-mflux-4bit`
(newer, smaller base model) as an alternative default.

## Repo layout

```
agentimagegen/
├── SKILL.md              # agent-facing: triggers, workflow, taste rules
├── scripts/
│   └── generate.py       # one-shot CLI, PEP 723 inline deps (mflux, pillow)
├── reference/
│   └── prompting.md      # per-asset-type prompt recipes (loaded on demand)
├── imagegen.example.toml # style config template
├── README.md             # human install guide per agent + hardware reqs
└── LICENSE               # MIT for repo code; notes on model weight licenses
```

## CLI interface

```
uv run scripts/generate.py "warm photo of a pottery studio" \
    --out public/hero.webp --size 1440x800 [--seed 42] [--count 2] \
    [--steps 4] [--no-style] [--dry-run]
uv run scripts/generate.py --batch manifest.json
```

Behavior:

- **Size mapping:** map requested size to nearest Flux-friendly resolution
  (~1 MP, dimensions multiple of 16), generate, then resize + center-crop to
  the exact requested pixels.
- **Oversized requests:** if the requested size exceeds native generation
  (~1 MP), generate at the largest aspect-matching native resolution, then
  Lanczos-upscale to the target and print a warning that the result is
  upscaled. Never error, never silently degrade.
- **Multiple candidates:** `--count N` writes numbered siblings
  (`hero-1.webp`, `hero-2.webp`, …) with distinct seeds, printed to stdout so
  the agent can view and pick.
- **Format from extension:** `.webp` (recommended default, quality ~82),
  `.png`, `.jpg`.
- **Batch:** `--batch manifest.json` takes a list of
  `{prompt, out, size, seed?}` objects so multi-asset jobs pay the model-load
  tax once.
- **Style config:** walk up from cwd looking for `imagegen.toml`
  (style prefix/suffix, palette keywords); auto-apply to every prompt so a
  project's images share art direction. `--no-style` opts out. Fixed `--seed`
  for reproducibility.
- **First run:** clear message about the one-time ~7 GB download.
- **Errors:** actionable messages for non-Apple-Silicon, missing uv,
  <16 GB RAM, interrupted downloads (HF hub resume handles partials).
- **`--dry-run`:** validate args, config discovery, and size mapping without
  loading the model.

## SKILL.md — the taste layer

Half the product. Contents:

- **When NOT to generate:** logos, icons, UI screenshots, text-heavy graphics
  → direct the agent to SVG / real screenshots instead.
- **Asset-class recipes:** hero image, background texture, spot illustration,
  og:image, placeholder photography — each with a prompt pattern and
  recommended size/format.
- **Flux prompting:** natural-language captions beat tag soup; concrete nouns,
  lighting, and mood words.
- **Workflow rules:** generate 1–2 candidates (not 10); *view the output*
  (agents can read images) to judge quality before wiring it in; expect
  ~40–90 s per image and plan batching accordingly.
- **Timeout handling:** agents' default shell timeouts (~2 min) are shorter
  than a multi-image batch. SKILL.md must explicitly instruct agents to raise
  the command timeout or run generation in the background and poll.
- **Path resolution:** the skill installs outside the project cwd. SKILL.md
  must reference `scripts/generate.py` via the skill's own base directory
  (provided to the agent when the skill loads), never a cwd-relative path.

`reference/prompting.md` holds the longer per-asset recipes so SKILL.md stays
small and is loaded cheaply.

## Testing

- Unit tests for pure logic (size mapping, config discovery, manifest
  parsing, format selection) — run without the model.
- `--dry-run` exercises everything up to inference.
- Manual smoke tests on the reference M4 Pro; the measured numbers above are
  the baseline.
- **CI:** GitHub Actions on a macOS (Apple Silicon) runner runs the unit
  tests and a `--dry-run` invocation on every PR. No model download in CI.

## Install story (README)

- **Claude Code:** clone into `~/.claude/skills/` (global) or
  `.claude/skills/` (per-project).
- **Codex / others:** document their current skills directories; fall back to
  "clone anywhere and point the agent at SKILL.md."
- Exact per-agent paths to be verified against current docs during
  implementation, not from memory.
- Prereqs: Apple Silicon Mac, 24 GB+ RAM recommended, `uv`
  (`brew install uv`), ~8 GB free disk.
- Uninstall note: model weights live in the Hugging Face cache
  (`~/.cache/huggingface`); document how to reclaim the ~7 GB.

## Out of scope for v1 (roadmap section in README)

- Background removal (transparent PNGs)
- CUDA/Linux/Windows backend
- Warm daemon mode
- img2img / style reference images
