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
