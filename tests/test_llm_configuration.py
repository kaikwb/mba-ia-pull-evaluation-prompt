import sys
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from google.genai.types import GenerateContentConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import (
    _uses_fixed_sampling_and_disallows_prefill,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from utils import get_eval_llm, get_llm


@pytest.mark.parametrize(
    "model_name",
    [
        "gemini-3.5-flash-lite",
        "models/gemini-3.5-flash-lite-001",
        "gemini-3.6-flash",
    ],
)
def test_fixed_sampling_models_omit_temperature_and_emit_no_sdk_warning(
    model_name, monkeypatch
):
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")
    assert _uses_fixed_sampling_and_disallows_prefill(model_name)

    with patch.dict("os.environ", {"LLM_MODEL": model_name}):
        model = get_llm(temperature=0.25)

    assert isinstance(model, ChatGoogleGenerativeAI)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        config = model._build_request_config(
            formatted_tools=None,
            formatted_tool_config=None,
            formatted_safety_settings=[],
            params=model._prepare_params(stop=None),
            cached_content=None,
            system_instruction=None,
        )

    assert not any("fixed sampling" in str(warning.message) for warning in captured)
    assert isinstance(config, GenerateContentConfig)
    assert "temperature" not in config.model_fields_set


def test_regular_google_model_preserves_temperature(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")

    model = get_llm(temperature=0.25)
    assert isinstance(model, ChatGoogleGenerativeAI)
    config = model._build_request_config(
        formatted_tools=None,
        formatted_tool_config=None,
        formatted_safety_settings=[],
        params=model._prepare_params(stop=None),
        cached_content=None,
        system_instruction=None,
    )

    assert config.temperature == 0.25
    assert "temperature" in config.model_fields_set


def test_evaluation_factory_uses_fixed_sampling_model_without_temperature(
    monkeypatch,
):
    monkeypatch.setenv("LLM_PROVIDER", "google")
    monkeypatch.setenv("EVAL_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key")

    model = get_eval_llm(temperature=0.25)

    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemini-3.5-flash-lite"
    config = model._build_request_config(
        formatted_tools=None,
        formatted_tool_config=None,
        formatted_safety_settings=[],
        params=model._prepare_params(stop=None),
        cached_content=None,
        system_instruction=None,
    )
    assert "temperature" not in config.model_fields_set


def test_openai_model_preserves_temperature(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")

    with patch("langchain_openai.ChatOpenAI") as chat_openai:
        get_llm(temperature=0.25)

    chat_openai.assert_called_once_with(
        model="gpt-test", temperature=0.25, api_key="test-api-key"
    )
