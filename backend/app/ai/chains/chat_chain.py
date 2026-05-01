from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.ai.llm import get_chat_llm

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_chat_chain() -> Runnable:
    system_prompt = _load_prompt("chat_system.txt")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("placeholder", "{history}"),
            ("human", "{human_input}"),
        ]
    )
    return prompt | get_chat_llm() | StrOutputParser()
