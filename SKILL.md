---
name: generate-image-skill
description: Generate original images locally (free, offline, no API keys) for websites and apps — hero images, backgrounds, textures, spot illustrations, og:images, placeholder photography — using FLUX.1-schnell on Apple Silicon. Use when a project needs real imagery instead of stock photos, gray boxes, or placeholder URLs. Not for logos, icons, or UI screenshots.
---

# generate-image-skill — local image generation for coding agents

Generate production-ready imagery while you build, on the user's own machine.
Free, offline, Apache-2.0-licensed model, no API keys.

## When to use — and when NOT to

**Generate:** hero images, section backgrounds, textures, spot illustrations,
og:images (1200x630), placeholder/editorial photography, empty-state art.

**Do NOT generate:** logos, icons, UI screenshots, or text-heavy graphics.
Diffusion models render text and precise geometry badly. Use SVG for
logos/icons and real screenshots for UI. If an image needs more than 1–2
words of legible text, build it in HTML/CSS instead.

## Setup — DO THIS FIRST (before the first generation in a session)

Run the environment check. It is pure-stdlib and needs no dependencies — plain
`python3` works even on a fresh machine:

```bash
python3 <SKILL_DIR>/scripts/doctor.py
```

Read its output and act on it before generating — do not make the user
troubleshoot:

- **`✗ uv is not installed`** — `uv` is the only thing that must be installed;
  it runs the generator and manages Python + all dependencies automatically.
  Offer to install it for the user: run `brew install uv` (or, if Homebrew is
  absent, `curl -LsSf https://astral.sh/uv/install.sh | sh`), then re-run the
  doctor. If a `uv run …` command ever fails with `uv: command not found`,
  this is the cause.
- **`✗ unsupported platform`** — generate-image-skill v1 needs an Apple Silicon Mac.
  Tell the user plainly; do not attempt to generate.
- **`✗ only N GB free disk`** — the model needs ~7 GB; ask the user to free
  space first.
- **`! model not downloaded yet`** — normal on first use; just warn the user
  the first image will take a few extra minutes for the one-time ~7 GB
  download.

When the doctor reports "Ready to generate," proceed. You only need to run it
once per session (or whenever a `uv run` command fails unexpectedly).

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

Requirements: Apple Silicon Mac and `uv` — the `doctor.py` check above
verifies both and tells you exactly how to fix whatever is missing. The
generator also exits with a clear message on unsupported platforms.

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
| `--backend` | `local` (default, free/offline) or a hosted provider: `replicate`, `openai`, `gemini` |
| `--open` | Open each result in the Mac's default viewer after saving |
| `--dry-run` | Print the plan (styled prompts, sizes, seeds) without loading the model |

## Hosted models (optional — bring your own key)

Local generation is the default and needs no key. If the user wants to offload
compute to a hosted service (or isn't on a capable Mac), there are opt-in hosted
backends. Three ship built in: `replicate` (the same flux-schnell model),
`openai` (gpt-image-1), and `gemini` (gemini-2.5-flash-image). More can be added
in `scripts/backends.py`.

**The key is stored safely, and you (the agent) must never handle it:**

1. The **user** runs this once and types their key at a hidden prompt. Do NOT
   ask them to paste the key into the chat, and never run this with a key inline
   on the command line:
   ```bash
   uv run <SKILL_DIR>/scripts/generate.py --set-key replicate   # or: openai
   ```
   The key goes into the macOS Keychain (encrypted, access-controlled). This
   command must be run by the user in a real terminal — it refuses to run
   non-interactively, so you cannot (and must not) run it for them.
2. Then generate with `--backend replicate` (or `--backend openai`). The CLI
   reads the key from the Keychain itself, so the secret never enters your
   context, a log, or the shell history.

`--list-keys` shows which providers have a key stored; `--delete-key <provider>`
removes one. Hosted generation bills a small per-image fee to the user's account
and needs a network connection; local stays free and offline.

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

## Writing good prompts — be specific and detailed

Flux rewards detailed, natural-language scene descriptions and punishes terse
tag soup. A one-word prompt gives a generic, disappointing result. Every prompt
should name, in a full sentence or two:

- **Subject** — the concrete thing ("handmade ceramic bowls", not "something nice")
- **Setting / context** — where it is, what surrounds it
- **Lighting** — direction and quality ("soft morning light from the left", "hard studio spotlight")
- **Mood / palette** — the feeling and the colors ("calm, muted earthy tones")
- **Composition** — framing and negative space, *especially where text will
  overlay*: "subject on the right third, empty space on the left for a headline"

For photographic assets, add shot type and depth of field ("wide establishing
shot, shallow depth of field"). For illustrations, specify a flat style, simple
shapes, and a solid background.

**Weak → strong:**

> ❌ `a coffee shop`
> ✅ `warm natural-light photograph of a cozy independent coffee shop interior at golden hour, exposed brick walls, a barista blurred in the background, steam rising from a cup in the foreground, shallow depth of field, inviting mood`

Never ask for legible text beyond 1–2 words — diffusion renders it as gibberish.
Put real copy in HTML/CSS over the image.

## Choosing dimensions — always set `--size` deliberately

Pick the size from the asset's real role in the layout, never a default. Match
the aspect ratio to where the image will actually sit, so you aren't cropping
blind later.

| Asset | Size |
|---|---|
| Full-width hero | `1440x800` (or `2880x1600` for retina) |
| Wide banner strip | `1200x360` |
| Section background | `1440x600` |
| og:image / social card | `1200x630` |
| Square spot illustration | `800x800` |
| Portrait / mobile hero | `800x1200` |

## Showing the result to the user

After you generate and view an image yourself, surface it to the user — don't
leave a file path buried in tool output. Use whatever the current environment
supports, in order of preference:

1. **Orcha:** `open "orcha://file?path=<ABSOLUTE_PATH>"` opens the image in
   Orcha's in-app file viewer.
2. **`--open` flag:** pass `--open` to the generator and it opens each result in
   the Mac's default image viewer (Preview) right after saving.
3. **Image-capable terminals:** `imgcat <path>` (iTerm2) or `kitten icat <path>`
   (Kitty / Ghostty / WezTerm) render the image inline.
4. **Always** also print the path so the user can open it themselves.

## Reference

See `reference/prompting.md` in this skill's directory for per-asset-type prompt
recipes (hero, texture, illustration, og:image, photography).
