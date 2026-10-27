import doctor
from doctor import (
    FAIL,
    OK,
    WARN,
    check_disk,
    check_model_cache,
    check_platform,
    check_python,
    check_ram,
    check_uv,
    format_report,
    overall_status,
)


def test_platform_apple_silicon_ok():
    status, _, fix = check_platform("Darwin", "arm64")
    assert status == OK and fix is None


def test_platform_intel_mac_fails():
    status, _, fix = check_platform("Darwin", "x86_64")
    assert status == FAIL and fix


def test_platform_linux_fails():
    status, _, fix = check_platform("Linux", "x86_64")
    assert status == FAIL and fix


def test_python_311_ok():
    assert check_python((3, 11))[0] == OK
    assert check_python((3, 13))[0] == OK


def test_python_310_warns():
    status, _, fix = check_python((3, 10))
    assert status == WARN and fix


def test_uv_present_ok():
    status, detail, fix = check_uv("/opt/homebrew/bin/uv")
    assert status == OK and fix is None and "uv" in detail


def test_uv_missing_fails_with_install_hint():
    status, _, fix = check_uv(None)
    assert status == FAIL
    assert "brew install uv" in fix


def test_disk_enough_ok():
    status, _, fix = check_disk(50 * 1024**3)
    assert status == OK and fix is None


def test_disk_low_fails():
    status, _, fix = check_disk(2 * 1024**3)
    assert status == FAIL and fix


def test_ram_high_ok():
    assert check_ram(48 * 1024**3)[0] == OK


def test_ram_16gb_warns_but_usable():
    status, _, fix = check_ram(16 * 1024**3)
    assert status == WARN and fix


def test_ram_low_warns():
    status, _, fix = check_ram(8 * 1024**3)
    assert status == WARN and fix


def test_model_cached_ok():
    assert check_model_cache(True)[0] == OK


def test_model_not_cached_warns():
    status, _, fix = check_model_cache(False)
    assert status == WARN and fix


def test_overall_status_precedence():
    assert overall_status([OK, WARN, FAIL]) == FAIL
    assert overall_status([OK, WARN]) == WARN
    assert overall_status([OK, OK]) == OK


def test_format_report_shows_fix_and_not_ready_on_fail():
    findings = [
        ("platform", OK, "Apple Silicon Mac", None),
        ("uv", FAIL, "uv is not installed", "brew install uv"),
    ]
    report = format_report(findings)
    assert "brew install uv" in report
    assert "Not ready yet" in report


def test_format_report_all_set_when_clean():
    findings = [("platform", OK, "Apple Silicon Mac", None)]
    report = format_report(findings)
    assert "All set" in report


def test_gather_findings_runs_on_this_machine():
    # Smoke test: real environment probing must not raise and must cover the
    # core checks (platform, uv, model) regardless of disk/ram availability.
    findings = doctor.gather_findings()
    labels = {label for label, _, _, _ in findings}
    assert {"platform", "python", "uv", "model"} <= labels


def test_check_codex_missing_is_advisory():
    status, detail, fix = doctor.check_codex(None, "", "")
    assert status == WARN and "npm install -g @openai/codex" in fix


def test_check_codex_needs_chatgpt_login():
    status, _, fix = doctor.check_codex("/bin/codex", "Logged in using an API key", "")
    assert status == WARN and "codex login" in fix


def test_check_codex_feature_disabled():
    features = "image_generation                         stable             false\n"
    status, _, fix = doctor.check_codex("/bin/codex", "Logged in using ChatGPT", features)
    assert status == WARN and "codex features enable image_generation" in fix


def test_check_codex_ready():
    features = "image_generation                         stable             true\n"
    status, _, _ = doctor.check_codex("/bin/codex", "Logged in using ChatGPT", features)
    assert status == OK


def test_local_blockers_become_advisory_when_codex_ready():
    finding = ("platform", FAIL, "unsupported platform (Linux/x86_64)", "need a Mac")
    label, status, detail, fix = doctor.advisory_when_codex_ready(finding, True)
    assert status == WARN and "--backend local" in detail and fix is None
    assert doctor.advisory_when_codex_ready(finding, False) == finding
