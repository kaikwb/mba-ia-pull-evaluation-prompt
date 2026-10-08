"""
Script para fazer push de prompts otimizados ao LangSmith Prompt Hub.

Este script:
1. Lê os prompts otimizados de prompts/bug_to_user_story_v2.yml
2. Valida os prompts
3. Faz push PÚBLICO para o LangSmith Hub
4. Adiciona metadados (tags, descrição, técnicas utilizadas)

DICAS DE IMPLEMENTAÇÃO:

- O push é feito pelo cliente do LangSmith:

      from langsmith import Client
      from langchain_core.prompts import ChatPromptTemplate

      client = Client()
      prompt = ChatPromptTemplate.from_messages([
          ("system", system_prompt),
          ("user", user_prompt),
      ])
      url = client.push_prompt(
          f"{username}/bug_to_user_story_v2",
          object=prompt,
          is_public=True,
          description="...",
          tags=[...],
      )

- `username` vem de USERNAME_LANGSMITH_HUB no .env e precisa ser o seu handle
  do Hub. Se você ainda não tem um handle, veja as instruções no .env.example.

- A variável do template precisa ser {bug_report}, que é a chave de entrada
  usada no dataset de avaliação.

- Use `load_yaml` de utils.py para ler o arquivo .yml.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.utils import LangSmithError

from utils import (
    check_env_vars,
    load_yaml,
    print_section_header,
    validate_prompt_structure,
)

load_dotenv()

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "bug_to_user_story_v2.yml"
)


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """
    Faz push do prompt otimizado para o LangSmith Hub (PÚBLICO).

    Args:
        prompt_name: Nome do prompt
        prompt_data: Dados do prompt

    Returns:
        True se sucesso, False caso contrário
    """
    is_valid, errors = validate_prompt(prompt_data)
    if not is_valid:
        print("❌ Prompt validation failed: " + "; ".join(errors))
        return False
    username = os.getenv("USERNAME_LANGSMITH_HUB")
    if not username:
        print(
            "❌ Set USERNAME_LANGSMITH_HUB after creating your public LangSmith Hub handle."
        )
        return False

    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_data["system_prompt"]),
                ("human", prompt_data["user_prompt"]),
            ]
        )
        prompt.metadata = {
            "techniques_applied": prompt_data["techniques_applied"],
            "version": prompt_data["version"],
        }
        Client().push_prompt(
            f"{username}/{prompt_name}",
            object=prompt,
            is_public=True,
            description=prompt_data["description"],
            tags=prompt_data["tags"] + prompt_data["techniques_applied"],
        )
        print(f"✅ Prompt published: {username}/{prompt_name}")
        return True
    except (LangSmithError, OSError, ValueError):
        print("❌ Unable to publish the prompt to LangSmith.")
        return False


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """
    Valida estrutura básica de um prompt (versão simplificada).

    Args:
        prompt_data: Dados do prompt

    Returns:
        (is_valid, errors) - Tupla com status e lista de erros
    """
    errors = []
    if not isinstance(prompt_data, dict):
        return False, ["Prompt data must be a mapping"]

    required_text = ("description", "system_prompt", "user_prompt", "version")
    for field in required_text:
        if (
            not isinstance(prompt_data.get(field), str)
            or not prompt_data[field].strip()
        ):
            errors.append(f"{field} must be a non-empty string")
    if prompt_data.get("version") != "v2":
        errors.append("version must be v2")

    for field in ("tags", "techniques_applied"):
        values = prompt_data.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            errors.append(f"{field} must be a non-empty list of strings")

    if errors:
        return False, errors
    structure_valid, structure_errors = validate_prompt_structure(prompt_data)
    if not structure_valid:
        return False, structure_errors

    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_data["system_prompt"]),
                ("human", prompt_data["user_prompt"]),
            ]
        )
    except (TypeError, ValueError):
        return False, ["Prompt messages could not be parsed"]

    system_variables = prompt.messages[0].prompt.input_variables
    user_variables = prompt.messages[1].prompt.input_variables
    if prompt.input_variables != ["bug_report"]:
        errors.append("Template must use exactly the bug_report input variable")
    if "bug_report" not in user_variables or "bug_report" in system_variables:
        errors.append(
            "bug_report must appear in the user message, not the system message"
        )
    return not errors, errors


def main():
    """Função principal"""
    print_section_header("PUSH OPTIMIZED PROMPT TO LANGSMITH")
    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        print("Create your public LangSmith Hub handle before running this script.")
        return 1

    data = load_yaml(str(PROMPT_PATH))
    prompt_data = data.get("bug_to_user_story_v2") if isinstance(data, dict) else None
    if prompt_data is None:
        print("❌ Prompt file must contain a bug_to_user_story_v2 mapping.")
        return 1
    return 0 if push_prompt_to_langsmith("bug_to_user_story_v2", prompt_data) else 1


if __name__ == "__main__":
    sys.exit(main())
