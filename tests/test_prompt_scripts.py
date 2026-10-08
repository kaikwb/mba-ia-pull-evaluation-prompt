import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
)
from langsmith.utils import LangSmithError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pull_prompts
import push_prompts


def valid_prompt_data():
    return {
        "description": "Convert bug reports into user stories",
        "system_prompt": "You are a product manager. Follow the requested format.",
        "user_prompt": "Analyze this report: {bug_report}",
        "version": "v2",
        "tags": ["bug-analysis", "user-story"],
        "techniques_applied": ["few-shot", "role-prompting"],
    }


def test_pull_saves_templates_and_dangerous_public_option():
    client = Mock()
    client.pull_prompt.return_value = ChatPromptTemplate.from_messages(
        [("system", "Analyze {bug_report}"), ("human", "Report: {bug_report}")]
    )

    with (
        patch.object(pull_prompts, "Client", return_value=client),
        patch.object(pull_prompts, "save_yaml", return_value=True) as save_yaml,
    ):
        assert pull_prompts.pull_prompts_from_langsmith()

    client.pull_prompt.assert_called_once_with(
        "leonanluppi/bug_to_user_story_v1", dangerously_pull_public_prompt=True
    )
    assert save_yaml.call_args.args[0] == {
        "bug_to_user_story_v1": {
            "description": "Prompt pulled from the LangSmith Prompt Hub",
            "system_prompt": "Analyze {bug_report}",
            "user_prompt": "Report: {bug_report}",
            "version": "v1",
        }
    }
    assert save_yaml.call_args.args[1] == str(pull_prompts.OUTPUT_PATH)


@pytest.mark.parametrize(
    "messages",
    [
        [("human", "Report: {bug_report}"), ("system", "Analyze {bug_report}")],
        [
            ("system", "Analyze {bug_report}"),
            ("human", "Report: {bug_report}"),
            ("ai", "Extra message"),
        ],
        [
            SystemMessagePromptTemplate(
                prompt=PromptTemplate.model_construct(
                    template="Analyze {bug_report}",
                    input_variables=["bug_report"],
                    template_format="jinja2",
                    partial_variables={},
                )
            ),
            ("human", "Report: {bug_report}"),
        ],
    ],
)
def test_pull_rejects_unsupported_messages_without_saving(messages):
    client = Mock()
    client.pull_prompt.return_value = ChatPromptTemplate.from_messages(messages)

    with (
        patch.object(pull_prompts, "Client", return_value=client),
        patch.object(pull_prompts, "save_yaml") as save_yaml,
    ):
        assert not pull_prompts.pull_prompts_from_langsmith()
    save_yaml.assert_not_called()


@pytest.mark.parametrize("failure", ["api", "save"])
def test_pull_api_or_save_failure_returns_false(failure):
    client = Mock()
    client.pull_prompt.return_value = ChatPromptTemplate.from_messages(
        [("system", "System"), ("human", "User")]
    )
    if failure == "api":
        client.pull_prompt.side_effect = LangSmithError("sensitive key")

    with (
        patch.object(pull_prompts, "Client", return_value=client),
        patch.object(pull_prompts, "save_yaml", return_value=False),
    ):
        assert not pull_prompts.pull_prompts_from_langsmith()


def test_push_sends_public_prompt_and_metadata(monkeypatch):
    monkeypatch.setenv("USERNAME_LANGSMITH_HUB", "public-handle")
    client = Mock()

    with patch.object(push_prompts, "Client", return_value=client):
        assert push_prompts.push_prompt_to_langsmith(
            "bug_to_user_story_v2", valid_prompt_data()
        )

    args, kwargs = client.push_prompt.call_args
    assert args == ("public-handle/bug_to_user_story_v2",)
    assert kwargs["is_public"] is True
    assert kwargs["description"] == valid_prompt_data()["description"]
    assert kwargs["tags"] == [
        "bug-analysis",
        "user-story",
        "few-shot",
        "role-prompting",
    ]
    assert kwargs["object"].metadata == {
        "techniques_applied": ["few-shot", "role-prompting"],
        "version": "v2",
    }


@pytest.mark.parametrize(
    "update",
    [
        {"description": ""},
        {"version": "v1"},
        {"tags": []},
        {"techniques_applied": ["few-shot"]},
        {"user_prompt": "No input variable"},
        {"system_prompt": "System {bug_report}"},
        {"user_prompt": "{bug_report} {other}"},
    ],
)
def test_invalid_prompt_is_not_sent(update):
    data = valid_prompt_data()
    data.update(update)
    client = Mock()

    with (
        patch.object(push_prompts, "Client", return_value=client),
        patch.dict("os.environ", {"USERNAME_LANGSMITH_HUB": "public-handle"}),
    ):
        assert not push_prompts.push_prompt_to_langsmith("bug_to_user_story_v2", data)

    client.push_prompt.assert_not_called()


def test_push_reports_api_failure_without_exception_details(monkeypatch, capsys):
    monkeypatch.setenv("USERNAME_LANGSMITH_HUB", "public-handle")
    client = Mock()
    client.push_prompt.side_effect = LangSmithError("secret-token")

    with patch.object(push_prompts, "Client", return_value=client):
        assert not push_prompts.push_prompt_to_langsmith(
            "bug_to_user_story_v2", valid_prompt_data()
        )
    assert "secret-token" not in capsys.readouterr().out


@pytest.mark.parametrize("module", [pull_prompts, push_prompts])
def test_main_rejects_missing_environment_without_client(module, monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    with patch.object(module, "Client") as client:
        assert module.main() == 1
    client.assert_not_called()


def test_push_main_exits_when_prompt_file_missing_handle(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.delenv("USERNAME_LANGSMITH_HUB", raising=False)
    with patch.object(push_prompts, "Client") as client:
        assert push_prompts.main() == 1
    client.assert_not_called()
