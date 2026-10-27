"""Guards for how skills.sh / `npx skills add` discover and install the skill."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "generate-image"


def _frontmatter() -> str:
    text = (SKILL_DIR / "SKILL.md").read_text()
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with YAML frontmatter"
    return match.group(1)


def test_no_root_skill_md():
    # A root SKILL.md shadows skills/ and makes the installer copy the whole repo.
    assert not (ROOT / "SKILL.md").exists()


def test_frontmatter_name_matches_directory():
    assert re.search(r"^name: generate-image$", _frontmatter(), re.M)


def test_description_is_quoted_single_line():
    # Unquoted colons in the description break the installer's YAML parse.
    line = next(l for l in _frontmatter().splitlines() if l.startswith("description:"))
    value = line.split(":", 1)[1].strip()
    assert value.startswith('"') and value.endswith('"') and '"' not in value[1:-1]


def test_skill_dir_has_only_runtime_files():
    allowed = {"SKILL.md", "scripts", "reference", "imagegen.example.toml"}
    present = {p.name for p in SKILL_DIR.iterdir() if p.name != "__pycache__"}
    assert present <= allowed, present - allowed
