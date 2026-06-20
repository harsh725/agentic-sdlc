"""Risk classifier is deterministic and fails closed (plan §7.1)."""

from __future__ import annotations

from agentic_sdlc.contracts import RiskLevel
from agentic_sdlc.risk_classifier import RiskClassifier


def make() -> RiskClassifier:
    return RiskClassifier(
        high_path_globs={"auth": ["**/auth/**"], "infra": ["**/*.tf"]},
        high_content_patterns={"secrets": [r"api[_-]?key\s*[:=]"]},
        ambiguous_path_globs=["**/*secret*"],
    )


def test_low_risk_path() -> None:
    v = make().classify(["src/widgets/button.py"])
    assert v.level is RiskLevel.LOW
    assert not v.is_high


def test_high_risk_auth_path() -> None:
    v = make().classify(["src/auth/session.py"])
    assert v.level is RiskLevel.HIGH
    assert "auth" in v.flags


def test_high_risk_infra_path() -> None:
    assert make().classify(["infra/main.tf"]).is_high


def test_high_risk_content_in_innocuous_path() -> None:
    v = make().classify(["src/util/helper.py"], diff_text="api_key = load()")
    assert v.is_high
    assert "secrets" in v.flags


def test_ambiguous_path_fails_closed() -> None:
    v = make().classify(["config/secret_store.py"])
    assert v.is_high
    assert "ambiguous" in v.flags


def test_unreadable_rules_fail_closed() -> None:
    clf = RiskClassifier.from_yaml("/nonexistent/path/rules.yaml")
    v = clf.classify(["src/anything.py"])
    assert v.is_high
    assert "fail_closed" in v.flags


def test_from_yaml_defaults_load() -> None:
    clf = RiskClassifier.from_yaml()
    assert clf.classify(["src/auth/login.py"]).is_high
    assert not clf.classify(["src/widgets/button.py"]).is_high
    assert clf.classify([".github/workflows/ci.yml"]).is_high
