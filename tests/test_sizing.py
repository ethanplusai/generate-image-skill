import pytest

from imagegen_core import MAX_PIXELS, parse_size, plan_generation_size


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


def test_oversized_16_9_stays_under_cap():
    gen_w, gen_h, needs_upscale = plan_generation_size(3840, 2160)
    assert needs_upscale is True
    assert gen_w % 16 == 0 and gen_h % 16 == 0
    assert gen_w * gen_h <= MAX_PIXELS


def test_oversized_square_stays_under_cap():
    gen_w, gen_h, needs_upscale = plan_generation_size(2048, 2048)
    assert needs_upscale is True
    assert gen_w * gen_h <= MAX_PIXELS
