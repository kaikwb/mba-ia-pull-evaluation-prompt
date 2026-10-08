"""
Script para fazer pull de prompts do LangSmith Prompt Hub.

Este script:
1. Conecta ao LangSmith usando credenciais do .env
2. Faz pull do prompt semente do desafio
3. Salva localmente em prompts/bug_to_user_story_v1.yml

DICAS DE IMPLEMENTAÇÃO:

- O pull é feito pelo cliente do LangSmith:

      from langsmith import Client
      client = Client()
      prompt = client.pull_prompt(
          "leonanluppi/bug_to_user_story_v1",
          dangerously_pull_public_prompt=True,
      )

- O parâmetro `dangerously_pull_public_prompt=True` é obrigatório sempre que o
  identificador tem dono explícito ("owner/nome"). O LangSmith bloqueia esse pull
  por padrão porque um prompt do Hub é um objeto LangChain serializado, que pode
  vir de terceiros. Aqui o prompt é o do desafio, então o risco é conhecido.

- O retorno é um ChatPromptTemplate. Para extrair o conteúdo das mensagens,
  use a serialização nativa do LangChain (`prompt.messages`, e o atributo
  `.prompt.template` de cada mensagem).

- Use `save_yaml` de utils.py para gravar o resultado no arquivo .yml.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
)
from langsmith import Client
from langsmith.utils import LangSmithError

from utils import check_env_vars, print_section_header, save_yaml

load_dotenv()


PROMPT_NAME = "leonanluppi/bug_to_user_story_v1"
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "bug_to_user_story_v1.yml"
)


def pull_prompts_from_langsmith() -> bool:
    try:
        prompt = Client().pull_prompt(PROMPT_NAME, dangerously_pull_public_prompt=True)
        if not isinstance(prompt, ChatPromptTemplate) or len(prompt.messages) != 2:
            print("❌ Unsupported prompt message structure.")
            return False

        system_message = prompt.messages[0]
        user_message = prompt.messages[1]
        if not isinstance(
            system_message, SystemMessagePromptTemplate
        ) or not isinstance(user_message, HumanMessagePromptTemplate):
            print("❌ Unsupported prompt message structure.")
            return False

        system_template = system_message.prompt
        user_template = user_message.prompt
        if not isinstance(system_template, PromptTemplate) or not isinstance(
            user_template, PromptTemplate
        ):
            print("❌ Unsupported prompt message structure.")
            return False
        if any(
            template.template_format != "f-string"
            or template.partial_variables
            for template in (system_template, user_template)
        ):
            print("❌ Unsupported prompt message structure.")
            return False

        data = {
            "bug_to_user_story_v1": {
                "description": "Prompt pulled from the LangSmith Prompt Hub",
                "system_prompt": system_template.template,
                "user_prompt": user_template.template,
                "version": "v1",
            }
        }
        return save_yaml(data, str(OUTPUT_PATH))
    except (LangSmithError, OSError, ValueError):
        print("❌ Unable to pull the prompt from LangSmith or save it locally.")
        return False


def main():
    """Função principal"""
    print_section_header("PULL PROMPT FROM LANGSMITH")
    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return 1
    return 0 if pull_prompts_from_langsmith() else 1


if __name__ == "__main__":
    sys.exit(main())
