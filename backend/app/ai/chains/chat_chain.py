from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from app.ai.llm import get_chat_llm

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
STATEMENT_INSTRUCTION = (
    "The user is sharing a personal fact. Acknowledge it briefly in ONE sentence only. "
    "Format: 'Noted. [restate the fact].' "
    "Do NOT list other facts. Do NOT add any extra commentary."
)

QUESTION_INSTRUCTION = (
    "The user is asking a question. Use the conversation history above to answer it. "
    "For specific recall questions (e.g. 'What is my snack?'), answer with ONE sentence only. "
    "For 'list everything' or 'what do you remember' questions, list all facts from the history."
)

IMAGE_GENERATION_INSTRUCTION = (
    "The user wants to create, draw, generate, or visualize an image. "
    "Generate the image based on the user's request and return the Markdown image syntax."
)


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def build_chat_chain(user_email: str | None = None) -> Runnable:
    system_prompt = _load_prompt("chat_system.txt")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("system", "---\n{mode_instruction}"),
            MessagesPlaceholder(variable_name="human_messages"),
        ]
    )
    llm = get_chat_llm()
    
    return prompt | llm | StrOutputParser()
