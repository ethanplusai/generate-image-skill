# Changelog

## 2.0.0 (2026-10-27)

Claude Code can now generate images with **Codex on your ChatGPT plan**.

### Added
- `codex` backend: runs `codex exec` headless, uses Codex's built-in image tool on
  your ChatGPT plan, and collects the result. No API key, no model download.
- `--backend auto` (the new default): `codex` when signed in with ChatGPT, else
  local FLUX.
- `--transparent` (real alpha) and `--ref IMAGE` (edits, restyles) on `codex`.
- `--json` result lines with absolute paths; `codex` batches run 3 at a time.
- The doctor checks the Codex install, the ChatGPT login and the image flag.
- The skill tells agents to run generation in the background, view each image,
  and show it inline in the chat.

### Changed
- **Install layout:** the skill now lives in `skills/generate-image/` and is
  named `generate-image`. Install with
  `npx skills add ethanplusai/generate-image-skill`. Manual installs: copy
  `skills/generate-image` (not the repo root) into your skills folder.
- mflux (torch + MLX, ~1 GB) installs only the first time you use the local
  backend.
- The OpenAI backend uses `gpt-image-2`.

### Fixed
- Pinned Pillow `<13`: Pillow 13.0 fails to import on Python 3.12, which broke
  the local backend.

## 1.1.0

- Hosted backends with Keychain-stored keys: Replicate, OpenAI, Gemini.

## 1.0.0

- Local image generation with FLUX.1-schnell via mflux on Apple Silicon:
  exact sizes, batches, `imagegen.toml` style config, and an environment doctor.
