import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from langchain_google_genai.chat_models import (
    ChatGoogleGenerativeAIError,
    GoogleRateLimitError,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import metrics
from utils import load_yaml, save_yaml


def test_yaml_io_returns_failure_for_expected_file_errors(tmp_path):
    missing_path = tmp_path / "missing.yml"
    assert load_yaml(str(missing_path)) is None

    with patch("builtins.open", side_effect=PermissionError("denied")):
        assert load_yaml(str(tmp_path / "restricted.yml")) is None

    with patch("yaml.dump", side_effect=yaml.YAMLError("cannot serialize")):
        assert not save_yaml({"value": object()}, str(tmp_path / "output.yml"))


def test_yaml_io_does_not_swallow_unexpected_errors(tmp_path):
    with (
        patch("builtins.open", side_effect=RuntimeError("programming defect")),
        pytest.raises(RuntimeError, match="programming defect"),
    ):
        load_yaml(str(tmp_path / "unexpected.yml"))


@pytest.mark.parametrize(
    "failure",
    [
        ChatGoogleGenerativeAIError("provider request failed"),
        GoogleRateLimitError("rate limited"),
    ],
    ids=["provider-wrapper", "provider-rate-limit"],
)
def test_clarity_metric_handles_google_provider_errors(failure):
    llm = Mock()
    llm.invoke.side_effect = failure

    with patch.object(metrics, "get_evaluator_llm", return_value=llm):
        assert metrics.evaluate_clarity("question", "answer", "reference")[
            "score"
        ] == 0.0


def test_clarity_metric_does_not_swallow_unexpected_errors():
    llm = Mock()
    llm.invoke.side_effect = RuntimeError("programming defect")

    with (
        patch.object(metrics, "get_evaluator_llm", return_value=llm),
        pytest.raises(RuntimeError, match="programming defect"),
    ):
        metrics.evaluate_clarity("question", "answer", "reference")


def test_clarity_metric_handles_null_score_response():
    llm = Mock()
    llm.invoke.return_value.content = '{"score": null}'

    with patch.object(metrics, "get_evaluator_llm", return_value=llm):
        assert metrics.evaluate_clarity("question", "answer", "reference")[
            "score"
        ] == 0.0
