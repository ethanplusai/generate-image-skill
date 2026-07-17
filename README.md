<p align="center">
  <img src="assets/showcase/banner.webp" alt="generate-image-skill" width="100%">
</p>

<h1 align="center">generate-image-skill</h1>

<p align="center">
  <strong>Give your coding agent the power to generate its own images — locally, free, no API keys.</strong>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#is-it-really-free">Is it really free?</a> ·
  <a href="#setup--troubleshooting">Setup</a> ·
  <a href="SKILL.md">How agents use it</a> ·
  <a href="#roadmap">Roadmap</a>
</p>

---

Your agent is building a website or app and needs a hero image, a background
texture, an `og:image`, or a spot illustration. Instead of shipping gray
placeholder boxes or hotlinking stock photos, it generates the real asset on
your machine in about 40 seconds — using [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell)
running through [mflux](https://github.com/filipstrand/mflux) on Apple Silicon.

**generate-image-skill is two things in one repo:**

1. **An [Agent Skill](SKILL.md)** — Claude Code, Codex, and any agent that
   reads skills learn *when* to generate imagery (and, just as important, when
   **not** to — logos and icons should be SVG), plus the taste rules to make it
   look good.
2. **A self-contained CLI** — no install step beyond [`uv`](https://docs.astral.sh/uv/).
   Run it yourself, too.

## Made with generate-image-skill

Every image below was generated locally by this tool — no editing, no
cherry-picking across dozens of tries. Each took ~40 seconds on an M4 Pro.

<table>
  <tr>
    <td width="50%">
      <img src="assets/showcase/hero.webp" alt="Hero image example" width="100%"><br>
      <sub><b>Hero photography</b> — <i>"warm natural-light photograph of a sunlit pottery studio, shelves of handmade ceramic bowls, soft morning atmosphere"</i></sub>
    </td>
    <td width="50%">
      <img src="assets/showcase/product.webp" alt="og:image example" width="100%"><br>
      <sub><b>og:image / product</b> — <i>"bold minimal composition of a single terracotta ceramic bowl centered on a warm cream background, generous negative space"</i></sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="assets/showcase/illustration.webp" alt="Spot illustration example" width="100%"><br>
      <sub><b>Spot illustration</b> — <i>"flat minimalist illustration of a paper airplane looping upward, two-tone terracotta and cream, simple geometric shapes"</i></sub>
    </td>
    <td width="50%">
      <img src="assets/showcase/texture.webp" alt="Background texture example" width="100%"><br>
      <sub><b>Background texture</b> — <i>"abstract macro close-up of handmade paper texture, warm ivory tones, subtle fibers, low contrast"</i></sub>
    </td>
  </tr>
</table>

## Quickstart

```bash
# 1. Clone into your Claude Code skills directory
git clone https://github.com/ethanplusai/generate-image-skill ~/.claude/skills/generate-image-skill
cd ~/.claude/skills/generate-image-skill

# 2. Check your machine is ready (needs nothing but system python3)
python3 scripts/doctor.py

# 3. Generate an image
uv run scripts/generate.py \
    "warm natural-light photo of a sunlit pottery studio" \
    --out hero.webp --size 1440x800
```

The first run downloads the model (~7 GB, one time, no account needed). After
that, generation is fully offline. That's the whole setup — see
[Installing per agent](#installing-per-agent) for Codex and others.

## Is it really free?

Yes. Genuinely, entirely free — this trips people up, so to be concrete:

| | |
|---|---|
| **API keys / accounts** | None. Nothing to sign up for. |
| **Per-image cost** | $0. It runs on your GPU, not a cloud service. |
| **Model license** | [Apache 2.0](https://huggingface.co/black-forest-labs/FLUX.1-schnell) — commercial use of the model **and its output** is fine. |
| **The only costs** | ~7 GB of disk (one-time model download) and ~40 s of compute per image. |

> **Why schnell and not FLUX.1-dev?** `dev` produces slightly nicer images but
> its license is **non-commercial**. This project deliberately uses `schnell`
> so anything you generate is safe to ship in a real product.

## Setup & troubleshooting

**The only thing you need to install is [`uv`](https://docs.astral.sh/uv/).**
It bootstraps the right Python, installs mflux and Pillow automatically (pinned
versions, declared inline in the script), and the model self-downloads on first
run. You never manage a virtualenv or a `requirements.txt`.

**Start with the doctor.** It's pure standard library, so it runs on a stock
Mac with zero setup and tells you exactly what (if anything) to fix:

```text
$ python3 scripts/doctor.py
generate-image-skill — environment check

  ✓ platform: Apple Silicon Mac
  ✓ python: Python 3.11
  ✓ uv: uv (/opt/homebrew/bin/uv)
  ✓ disk: 181 GB free disk
  ✓ memory: 48 GB RAM
  ! model: model not downloaded yet
      The first generation downloads ~7 GB from Hugging Face (one time).

Ready to generate. The ! notes above are advisory, not blockers.
```

If you're using this as an agent skill, your agent runs the doctor for you and
walks you through any fix — that's built into [SKILL.md](SKILL.md).

<details>
<summary><b>Common issues</b></summary>

| Symptom | Cause & fix |
|---|---|
| `uv: command not found` | `uv` isn't installed. `brew install uv` — or, without Homebrew, `curl -LsSf https://astral.sh/uv/install.sh \| sh`. Then re-run the doctor. |
| `requires an Apple Silicon Mac` | v1 runs on M1+ Macs only. Intel Macs, Linux, and Windows aren't supported yet (see [Roadmap](#roadmap)). |
| First run "hangs" for minutes | It's downloading the ~7 GB model. Watch progress; it only happens once. Give any wrapping command a 10-minute timeout. |
| Generation is slow / machine swaps | Under ~24 GB of RAM, the model may swap. It still works, just slower. |
| Want the disk space back | See [Uninstall](#uninstall). |

</details>

## How agents use it

Point your agent at [`SKILL.md`](SKILL.md). It teaches the agent to:

- generate the right asset types (heroes, backgrounds, textures, spot
  illustrations, `og:image`s, editorial photography) and avoid the wrong ones
  (logos, icons, UI, anything text-heavy → those should be SVG or real screenshots);
- run the environment doctor first and help you fix any setup gap;
- batch a page's assets into one model load, view each result before shipping
  it, and keep a consistent art direction across a project.

Prompt recipes per asset type live in [`reference/prompting.md`](reference/prompting.md).

## CLI reference

```bash
uv run scripts/generate.py "PROMPT" --out PATH --size WxH [options]
uv run scripts/generate.py --batch manifest.json
```

| Flag | Meaning |
|---|---|
| `--out PATH` | Output file. Format from extension: `.webp` (best for web), `.png`, `.jpg`/`.jpeg`. |
| `--size WxH` | Exact output pixels, e.g. `1440x800`. Larger-than-native requests are upscaled with a warning. |
| `--seed N` | Reproducible output — same seed + prompt = same image. |
| `--count N` | Generate N candidates (`hero-1.webp`, `hero-2.webp`, …) with sequential seeds. |
| `--steps N` | Inference steps (default 4; rarely worth raising on schnell). |
| `--batch FILE` | JSON array of `{prompt, out, size, seed?, count?}` — loads the model **once** for all jobs. |
| `--no-style` | Ignore the project's `imagegen.toml`. |
| `--open` | Open each result in the Mac's default image viewer after saving. |
| `--dry-run` | Print the plan (styled prompts, sizes, seeds) without loading the model. |

## Consistent art direction

Drop an `imagegen.toml` at your project root and every generated image inherits
the same look — so a site's hero, background, and illustrations feel like one
design system:

```toml
[style]
prefix = "warm editorial photography"
suffix = "muted earthy palette, soft natural light, film grain"
```

Copy [`imagegen.example.toml`](imagegen.example.toml) to get started, or pass
`--no-style` to opt out for a single image.

## Hosted models (bring your own key)

Local generation is the default — free, offline, no key. If you'd rather offload
the compute (or you're not on a capable Mac), there's an optional hosted backend
that runs the **same** flux-schnell model on [Replicate](https://replicate.com).

Your API key is stored in the **macOS Keychain**, and — importantly — a coding
agent driving this tool never sees it: you store it once, and the CLI retrieves
it at run time. The secret never lands in a prompt, a transcript, or your shell
history.

```bash
# Store your key once (typed at a hidden prompt, never in shell history)
uv run scripts/generate.py --set-key replicate

# Generate against the hosted model
uv run scripts/generate.py "a sunlit pottery studio" \
    --out hero.webp --size 1440x800 --backend replicate

uv run scripts/generate.py --list-keys              # which providers have a key
uv run scripts/generate.py --delete-key replicate   # remove one
```

Hosted generation bills a small per-image fee to your provider account and needs
a network connection; the default local backend has neither cost.

## How it works

- **Model:** FLUX.1-schnell, 4-bit quantized ([`dhairyashil/FLUX.1-schnell-mflux-4bit`](https://huggingface.co/dhairyashil/FLUX.1-schnell-mflux-4bit)), ~7 GB.
- **Runtime:** [mflux](https://github.com/filipstrand/mflux) on Apple's MLX — native Apple Silicon acceleration.
- **Sizing:** images generate at up to ~1.25 MP (dimensions rounded to multiples of 16), then are cover-cropped or upscaled to the exact pixels you asked for.
- **Distribution:** the CLI declares its dependencies inline ([PEP 723](https://peps.python.org/pep-0723/)), so `uv run` sets up an isolated, version-pinned environment on the fly. Nothing to `pip install`.

**Measured on an M4 Pro (48 GB):** ~2 min one-time model download, then ~40 s
per 1024×768 image, ~16 GB peak memory.

## Requirements

- Apple Silicon Mac (M1 or newer). 24 GB+ RAM recommended; 16 GB works but may swap.
- [`uv`](https://docs.astral.sh/uv/) — `brew install uv`
- ~8 GB free disk for the one-time model download

## Installing per agent

- **Claude Code** — clone into `~/.claude/skills/generate-image-skill` (global) or
  `.claude/skills/generate-image-skill` inside a project.
- **Codex and others** — clone anywhere and point the agent at
  [`SKILL.md`](SKILL.md) (e.g. reference it from `AGENTS.md`). The CLI works
  standalone; the skill file is instructions, not a dependency.

## Uninstall

The model weights live in the Hugging Face cache. Reclaim the ~7 GB with:

```bash
rm -rf ~/.cache/huggingface/hub/models--dhairyashil--FLUX.1-schnell-mflux-4bit
```

## Roadmap

- Background removal (transparent PNGs)
- CUDA / Linux / Windows backend behind the same CLI
- Warm daemon mode (skip the ~20 s model load per invocation)
- img2img / style-reference images
- Evaluate FLUX.2-klein as an alternative default model

Contributions welcome.

## License

This repository's code is [MIT](LICENSE). The FLUX.1-schnell model weights are
Apache 2.0. See [Is it really free?](#is-it-really-free) for what that means
for shipping generated images.
