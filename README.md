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
