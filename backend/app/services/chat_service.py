from collections.abc import AsyncIterator
import base64
from dataclasses import dataclass
import mimetypes
import logging
from pathlib import Path
import re
from typing import Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.chains.chat_chain import build_chat_chain, STATEMENT_INSTRUCTION, QUESTION_INSTRUCTION, IMAGE_GENERATION_INSTRUCTION
from app.ai.llm import get_chat_llm
from app.core.config import settings
from app.ai.memory.sliding_window import (
    DEFAULT_WINDOW_SIZE,
    fetch_recent_user_messages,
)
from app.models.message import Message
from app.services import thread_service

logger = logging.getLogger(__name__)


MAX_ATTACHMENT_CHARS = 2000
MEMORY_FACT_SCAN_LIMIT = 50


_FACT_QUERY_ALIASES: dict[str, str] = {
    "favorite": "favorite",
    "name": "name",
    "age": "age",
    "hobby": "hobby",
    "sport": "sport",
    "snack": "snack",
    "color": "color",
    "animal": "animal",
    "city": "city",
    "laptop": "laptop",
    "activity": "activity",
}


def _tokenize_for_relevance(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def _select_relevant_snippets(
    content: str,
    query: str,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
    max_chars: int = MAX_ATTACHMENT_CHARS,
) -> str:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_text(content)
    if not chunks:
        return content[:max_chars]

    query_terms = _tokenize_for_relevance(query)
    scored: list[tuple[int, int, str]] = []
    for idx, chunk in enumerate(chunks):
        chunk_terms = _tokenize_for_relevance(chunk)
        score = len(query_terms & chunk_terms)
        scored.append((score, -idx, chunk))

    scored.sort(reverse=True)

    selected: list[str] = []
    total = 0
    for score, _neg_idx, chunk in scored:
        if not selected and score == 0:
            selected.append(chunk)
            break

        if total + len(chunk) > max_chars and selected:
            continue

        if total + len(chunk) > max_chars:
            selected.append(chunk[: max_chars - total])
            break

        selected.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break

    return "\n\n...\n\n".join(selected)[:max_chars]


async def _summarize_attachment_for_prompt(
    content: str,
    query: str,
    attachment_type: Literal["code", "table", "formula"],
    user_email: str,
) -> str:
    llm = get_chat_llm()

    summary_prompt = (
        "Summarize the attached file content for chat context. "
        "Prioritize parts most relevant to the user request. "
        f"Attachment type: {attachment_type}. "
        "Return concise bullet points and preserve critical identifiers (function names, columns, constants).\n\n"
        f"User request: {query}\n\n"
        f"File content:\n{content}"
    )
    result = await llm.ainvoke(
        [HumanMessage(content=summary_prompt)],
        config={"metadata": {"user_email": user_email, "purpose": "attachment_summary"}},
    )
    return str(getattr(result, "content", "")).strip()


async def prepare_attachment_content_for_memory(
    content: str,
    *,
    query: str,
    attachment_type: Literal["code", "table", "formula"],
    user_email: str,
    strategy: Literal["snippets", "summary", "auto"] = "auto",
    max_chars: int = MAX_ATTACHMENT_CHARS,
) -> str:
    """Reduce oversized code/table attachment content before adding to prompt memory.

    Behavior:
    - If content is short (<= max_chars), returns as-is.
    - `snippets`: uses RecursiveCharacterTextSplitter and keeps relevant chunks.
    - `summary`: asks the LLM to summarize the file content.
    - `auto`: for very large files, summarize; otherwise keep relevant snippets.
    """
    if len(content) <= max_chars:
        return content

    effective_strategy = strategy
    if strategy == "auto":
        effective_strategy = "summary" if len(content) > (max_chars * 3) else "snippets"

    if effective_strategy == "summary":
        try:
            summarized = await _summarize_attachment_for_prompt(
                content,
                query,
                attachment_type,
                user_email,
            )
            if summarized:
                return summarized[:max_chars]
        except Exception:
            logger.warning("Falling back to snippet extraction for oversized attachment", exc_info=True)

    return _select_relevant_snippets(content, query, max_chars=max_chars)


@dataclass
class IncomingUpload:
    original_name: str
    content_type: str | None
    content: bytes


@dataclass
class StoredUpload:
    original_name: str
    stored_name: str
    content_type: str | None
    size_bytes: int
    category: str


_ALLOWED_EXTENSIONS: dict[str, tuple[str, set[str]]] = {
    ".png": ("image", {"image/png"}),
    ".jpg": ("image", {"image/jpeg"}),
    ".jpeg": ("image", {"image/jpeg"}),
    ".pdf": ("document", {"application/pdf"}),
    ".csv": (
        "document",
        {
            "text/csv",
            "application/csv",
            "application/vnd.ms-excel",
            "text/plain",
        },
    ),
    ".py": ("code", {"text/plain", "text/x-python", "application/x-python-code"}),
    ".js": (
        "code",
        {
            "text/plain",
            "text/javascript",
            "application/javascript",
            "application/x-javascript",
        },
    ),
    ".tex": (
        "formula",
        {
            "text/plain",
            "text/x-tex",
            "application/x-tex",
        },
    ),
}


def _safe_user_segment(user_email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", user_email)


def _safe_file_name(name: str) -> str:
    cleaned = Path(name).name.strip()
    if not cleaned:
        return "file"
    return re.sub(r"[^a-zA-Z0-9._-]", "_", cleaned)


def _attachment_root_for_user(user_email: str) -> Path:
    return Path(settings.UPLOAD_DIR).resolve() / "attachments" / _safe_user_segment(user_email)


def _resolve_attachment_path(user_email: str, stored_name: str) -> Path:
    root = _attachment_root_for_user(user_email)
    candidate = (root / Path(stored_name).name).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise ValueError(f"Invalid attachment path: {stored_name}")
    if not candidate.exists() or not candidate.is_file():
        raise ValueError(f"Attachment not found: {stored_name}")
    return candidate


def _guess_image_mime(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("image/"):
        return guessed
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "image/png"


async def _extract_images_from_recent_messages(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
    limit: int = 10,
) -> list[str]:
    """Extract image URLs from recent messages in the conversation.
    
    This allows follow-up questions to reference images from previous messages
    without re-uploading them.
    
    Args:
        db: Database session
        thread_id: Current thread ID
        user_email: User email
        limit: Number of recent messages to scan
    
    Returns:
        List of image URLs found in recent messages
    """
    from sqlalchemy import select, desc
    
    # Get recent messages from the thread
    stmt = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .where(Message.user_email == user_email)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    messages = result.scalars().all()

    image_urls: list[str] = []

    for msg in messages:
        # Extract from attachments JSON
        if msg.attachments and isinstance(msg.attachments, dict):
            if "images" in msg.attachments and isinstance(msg.attachments["images"], list):
                image_urls.extend(msg.attachments["images"])

        # Extract from markdown in content
        if msg.content:
            markdown_urls = _extract_image_urls(msg.content)
            image_urls.extend(markdown_urls)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in image_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


async def _build_human_content_blocks(
    message: str,
    user_email: str,
    attachment_names: list[str],
    db: AsyncSession | None = None,
    thread_id: str | None = None,
    user_id: str | None = None,
) -> tuple[list[dict[str, str | dict[str, str]]], bool]:
    content_blocks: list[dict[str, str | dict[str, str]]] = [{"type": "text", "text": message}]
    attached_text_parts: list[str] = []
    rag_context_added = False  # Initialize flag for RAG context tracking

    for stored_name in attachment_names:
        file_path = _resolve_attachment_path(user_email, stored_name)
        ext = file_path.suffix.lower()

        if ext in {".png", ".jpg", ".jpeg"}:
            encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
            mime_type = _guess_image_mime(file_path)
            content_blocks.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
            continue

        if ext in {".py", ".js", ".csv", ".tex"}:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            attachment_type: Literal["code", "table", "formula"] = (
                "table" if ext == ".csv" else "formula" if ext == ".tex" else "code"
            )
            prepared = await prepare_attachment_content_for_memory(
                content,
                query=message,
                attachment_type=attachment_type,
                user_email=user_email,
                strategy="auto",
                max_chars=MAX_ATTACHMENT_CHARS,
            )
            attached_text_parts.append(
                f"Attached Code/Data: [{prepared}]"
            )
            continue

        if ext == ".pdf":
            attached_text_parts.append(
                f"Attached Code/Data: [PDF attached: {file_path.name}]"
            )

    if attached_text_parts:
        content_blocks.append(
            {
                "type": "text",
                "text": "\n\n".join(attached_text_parts),
            }
        )

    # Also include images from recent messages to support follow-up questions on previously shared images
    if db is not None and thread_id is not None:
        try:
            recent_image_urls = await _extract_images_from_recent_messages(
                db, thread_id, user_email, limit=10
            )

            # Add images that aren't already in content_blocks
            existing_urls = set()
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    if "image_url" in block and "url" in block["image_url"]:
                        existing_urls.add(block["image_url"]["url"])

            for image_url in recent_image_urls:
                if image_url not in existing_urls:
                    # Determine MIME type based on URL
                    if image_url.startswith("data:"):
                        content_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                        )
                    elif image_url.startswith("http"):
                        content_blocks.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                        )
        except Exception as e:
            logger.warning(f"Failed to extract images from recent messages: {e}", exc_info=True)

    # Retrieve RAG context from uploaded PDF documents
    rag_context_added = False
    if user_id:
        try:
            from app.services import rag_service
            retrieved_chunks = await rag_service.retrieve_relevant_chunks(
                query=message,
                user_id=user_id,
                k=5,  # Retrieve top 5 relevant chunks
            )
            
            if retrieved_chunks:
                rag_context = rag_service.format_retrieved_chunks_for_prompt(retrieved_chunks)
                # Add RAG context directly without headers that trigger LLM preambles
                content_blocks.append({
                    "type": "text",
                    "text": f"\n\nDocument Context:\n{rag_context}\n\nAnswer the question using ONLY the above content. Do NOT add preambles or explanations.",
                })
                rag_context_added = True
                logger.info(f"Added RAG context with {len(retrieved_chunks)} chunks to the prompt")
        except Exception as e:
            logger.warning(f"Failed to retrieve RAG context: {e}", exc_info=True)

    return content_blocks, rag_context_added


async def store_uploads(files: list[IncomingUpload], user_email: str) -> list[StoredUpload]:
    if not files:
        raise ValueError("At least one file is required")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    upload_root = Path(settings.UPLOAD_DIR).resolve() / "attachments" / _safe_user_segment(user_email)
    upload_root.mkdir(parents=True, exist_ok=True)

    stored: list[StoredUpload] = []
    for file in files:
        safe_original_name = _safe_file_name(file.original_name)
        extension = Path(safe_original_name).suffix.lower()
        allowed = _ALLOWED_EXTENSIONS.get(extension)
        if not allowed:
            raise ValueError(f"Unsupported file type: {safe_original_name}")

        category, accepted_mime_types = allowed
        normalized_content_type = (file.content_type or "").lower()
        if normalized_content_type and normalized_content_type not in accepted_mime_types:
            raise ValueError(
                f"Invalid content type for {safe_original_name}: {file.content_type}"
            )

        size_bytes = len(file.content)
        if size_bytes == 0:
            raise ValueError(f"File is empty: {safe_original_name}")
        if size_bytes > max_bytes:
            raise ValueError(
                f"File exceeds {settings.MAX_UPLOAD_MB} MB limit: {safe_original_name}"
            )

        stored_name = f"{uuid4().hex}_{safe_original_name}"
        destination = upload_root / stored_name
        destination.write_bytes(file.content)

        stored.append(
            StoredUpload(
                original_name=safe_original_name,
                stored_name=stored_name,
                content_type=file.content_type,
                size_bytes=size_bytes,
                category=category,
            )
        )

    return stored


def _is_personal_fact_statement(message: str) -> bool:
    """Detect if message is a personal fact (not a question)."""
    # Check if it's a question
    if message.strip().endswith("?"):
        return False
    # Check if it's a statement about personal facts
    patterns = [
        r"^(?:I|my|my )",  # Starts with I, my, or My
        r"my (favorite|name|age|hobby|sport|snack|color|animal|city|laptop|activity)",
    ]
    return any(re.search(p, message.strip(), re.IGNORECASE) for p in patterns)


def _is_memory_list_request(message: str) -> bool:
    """Detect list-style memory recall prompts, including imperative phrasing."""
    msg = message.strip().lower()
    patterns = [
        r"list\s+all\s+facts",
        r"list\s+everything\s+you\s+remember",
        r"what\s+do\s+you\s+remember\s+about\s+me",
        r"tell\s+me\s+what\s+you\s+remember\s+about\s+me",
        r"all\s+facts\s+you\s+remember\s+about\s+me",
    ]
    return any(re.search(p, msg, re.IGNORECASE) for p in patterns)


def _is_memory_related_query(message: str) -> bool:
    """Detect whether the user is explicitly asking about profile memory."""
    msg = message.strip().lower()
    if not msg:
        return False

    patterns = [
        r"what\s+(?:is|'s)\s+my\s+",
        r"tell\s+me\s+my\s+",
        r"remember\s+about\s+me",
        r"facts\s+about\s+me",
        r"my\s+profile",
        r"who\s+am\s+i",
    ]
    return any(re.search(p, msg, re.IGNORECASE) for p in patterns) or _is_memory_list_request(msg)


def _extract_fact_query_key(message: str) -> str | None:
    """Extract the requested fact key from prompts like "What is my laptop?"."""
    msg = message.strip().lower()
    key_pattern = "|".join(_FACT_QUERY_ALIASES.keys())
    patterns = [
        rf"what\s+(?:is|'s)\s+my\s+({key_pattern})",
        rf"tell\s+me\s+my\s+({key_pattern})",
        rf"do\s+you\s+remember\s+my\s+({key_pattern})",
    ]
    for pattern in patterns:
        match = re.search(pattern, msg, re.IGNORECASE)
        if match:
            return _FACT_QUERY_ALIASES.get(match.group(1).lower())
    return None


def _extract_personal_fact(message: str) -> tuple[str, str] | None:
    """Extract canonical fact key + normalized sentence from a user statement."""
    raw = message.strip()
    msg = raw.rstrip(".! ")

    direct_patterns: list[tuple[str, str]] = [
        ("favorite", r"my\s+favorite\s+.+?\s+is\s+(.+)"),
        ("name", r"my\s+name\s+is\s+(.+)"),
        ("age", r"my\s+age\s+is\s+(.+)"),
        ("hobby", r"my\s+hobby\s+is\s+(.+)"),
        ("sport", r"my\s+sport\s+is\s+(.+)"),
        ("snack", r"my\s+snack\s+is\s+(.+)"),
        ("color", r"my\s+color\s+is\s+(.+)"),
        ("animal", r"my\s+animal\s+is\s+(.+)"),
        ("city", r"my\s+city\s+is\s+(.+)"),
        ("laptop", r"my\s+laptop\s+is\s+(.+)"),
        ("activity", r"my\s+activity\s+is\s+(.+)"),
    ]
    for key, pattern in direct_patterns:
        match = re.search(pattern, msg, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return key, f"Your {key} is {value}."

    love_watch = re.search(r"i\s+love\s+watching\s+(.+)", msg, re.IGNORECASE)
    if love_watch:
        value = love_watch.group(1).strip()
        return "sport", f"You love watching {value}."

    i_play = re.search(r"i\s+play\s+(.+)", msg, re.IGNORECASE)
    if i_play:
        value = i_play.group(1).strip()
        return "activity", f"You play {value}."

    return None


async def _build_memory_list_answer(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
) -> str:
    rows = await fetch_recent_user_messages(
        db,
        thread_id,
        user_email,
        limit=MEMORY_FACT_SCAN_LIMIT,
    )
    # Collect the latest DEFAULT_WINDOW_SIZE fact statements, ignoring non-fact turns.
    # This keeps output stable at "last 5 facts" even if recent user turns include questions.
    recent_facts: list[str] = []
    for row in reversed(rows):
        extracted = _extract_personal_fact(row.content)
        if extracted:
            _key, sentence = extracted
            recent_facts.append(sentence)
            if len(recent_facts) >= DEFAULT_WINDOW_SIZE:
                break

    if not recent_facts:
        return "I do not remember any personal facts yet. Share one and I will remember it."

    lines = [f"- {sentence}" for sentence in reversed(recent_facts)]
    return "I remember the following facts about you:\n" + "\n".join(lines)


async def _build_specific_fact_answer(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
    fact_key: str,
) -> str | None:
    rows = await fetch_recent_user_messages(
        db,
        thread_id,
        user_email,
        limit=DEFAULT_WINDOW_SIZE,
    )
    for row in reversed(rows):
        extracted = _extract_personal_fact(row.content)
        if not extracted:
            continue
        key, sentence = extracted
        if key == fact_key:
            return sentence
    return None


def _detect_image_generation_intent(message: str) -> bool:
    """Detect if user wants to generate, create, or draw an image.
    
    Returns True if message contains intent keywords like:
    - "generate an image", "create an image", "draw", "visualize", etc.
    """
    msg_lower = message.lower().strip()

    # Require explicit image nouns plus generation verbs to avoid false positives
    # on general prompts like "can you create..." or "draw a conclusion".
    explicit_patterns = [
        r"\b(generate|create|make|draw|paint|design|render|produce)\b\s+(?:an?\s+)?\b(image|picture|photo|illustration|artwork|graphic|portrait|logo|icon)\b",
        r"\b(image|picture|photo|illustration|artwork|graphic|portrait|logo|icon)\b\s+\b(of|for)\b",
        r"\bturn\b.+\binto\b.+\b(image|picture|photo|illustration)\b",
    ]

    return any(re.search(pattern, msg_lower, re.IGNORECASE) for pattern in explicit_patterns)


def _detect_image_modification_intent(message: str) -> bool:
    """Detect if user wants to modify an existing image.
    
    Returns True if message contains modification keywords like:
    - "change", "modify", "update", "make it", "turn it", "convert it", etc.
    
    These are typically follow-up requests to previously generated images.
    """
    msg_lower = message.lower().strip()
    
    modification_patterns = [
        r"\b(change|modify|update|alter|replace|adjust|edit|make)\b",
        r"\b(turn\s+it|convert\s+it|make\s+it|swap|change\s+the)\b",
    ]
    
    return any(re.search(pattern, msg_lower, re.IGNORECASE) for pattern in modification_patterns)


async def _extract_last_image_prompt_from_history(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
) -> str | None:
    """Extract the last image generation prompt from conversation history.
    
    Scans recent messages to find the last user message that was about generating/creating an image.
    Returns the message text if found, None otherwise.
    """
    from sqlalchemy import select, desc
    
    # Get last 20 messages from this thread
    stmt = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .where(Message.user_email == user_email)
        .where(Message.role == "user")
        .order_by(desc(Message.created_at))
        .limit(20)
    )
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    # Find the last message that looks like an image generation request
    for msg in messages:
        if msg.content and _detect_image_generation_intent(msg.content):
            return msg.content
    
    return None


def _extract_image_urls(text: str) -> list[str]:
    """Extract image URLs from Markdown image syntax: ![alt](url)
    
    Args:
        text: Response text potentially containing Markdown image syntax.
    
    Returns:
        List of image URLs found in the text.
    """
    # Regex pattern for Markdown image syntax: ![...](url)
    pattern = r'!\[.*?\]\(((?:https?://|data:)[^\)]+)\)'
    urls = re.findall(pattern, text)
    return urls


def _build_message_attachments(image_urls: list[str]) -> dict | None:
    """Build attachments dict for message JSONB column.
    
    Args:
        image_urls: List of image URLs to store.
    
    Returns:
        Dict with 'images' key containing list of URLs, or None if empty.
    """
    if not image_urls:
        return None
    
    return {
        "images": image_urls
    }


def get_message_image_urls(message_attachments: dict | None) -> list[str]:
    """Extract image URLs from message attachments JSONB.
    
    Args:
        message_attachments: The attachments dict from a Message object.
    
    Returns:
        List of image URLs, or empty list if none found.
    """
    if not message_attachments:
        return []
    
    return message_attachments.get("images", [])


def _should_truncate_response(message: str) -> bool:
    """Determine if response should be truncated to first sentence.
    
    Returns True for:
    - Personal fact statements (e.g., "My snack is popcorn")
    - Specific information questions (e.g., "What is my snack?", "What is my laptop?")
    
    Returns False for:
    - General/conversational questions (e.g., "How are you?", "Tell me about yourself")
    """
    msg = message.strip()

    if _is_personal_fact_statement(msg):
        return True

    if _extract_fact_query_key(msg) is not None:
        return True

    return False


def _truncate_to_first_sentence(text: str) -> str:
    """Extract and return only the first sentence, but keep meaningful content.
    
    For acknowledgments like "Noted. Your X is Y.", return the full meaningful response,
    not just "Noted."
    """
    text = text.strip()
    
    # Split by period, exclamation, or question mark
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    if not sentences:
        return text
    
    # For acknowledgment patterns like "Noted. Your X is Y.", 
    # if first part is just "Noted", combine with next sentence
    if len(sentences) > 1 and sentences[0].lower().strip() in ["noted", "acknowledged"]:
        # Return first two sentences for acknowledgment style
        return (sentences[0] + ". " + sentences[1]).rstrip(".")  + "."
    
    return sentences[0]


def _to_lc_messages(rows):
    """Convert ORM Message rows to LangChain BaseMessage instances."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    out = []
    for r in rows:
        if r.role == "user":
            out.append(HumanMessage(content=r.content))
        elif r.role == "assistant":
            out.append(AIMessage(content=r.content))
        else:
            out.append(SystemMessage(content=r.content))
    return out


async def stream_response(
    message: str,
    history: list,
    user_email: str,
    db: AsyncSession,
    thread_id: str | None = None,
    attachment_names: list[str] | None = None,
    user_id: str | None = None,
) -> AsyncIterator[str]:
    if not user_id:
        try:
            from sqlalchemy import select
            from app.models.user import User

            user_row = await db.scalar(select(User.id).where(User.email == user_email))
            if user_row is not None:
                user_id = str(user_row)
        except Exception:
            logger.warning("Unable to resolve user_id for RAG retrieval", exc_info=True)

    # Resolve / create thread for this user.
    if thread_id:
        thread = await thread_service.get_thread(db, user_email, thread_id)
    else:
        thread = await thread_service.create_thread(db, user_email)

    # Surface the thread id to the client first so the UI can attach to it
    # when the message was sent without a thread_id.
    yield f"__THREAD__{thread.id}\n"

    # Sliding-window memory: fetch BEFORE saving the current message so that
    # chat_history contains only previous messages, not the current one.
    # Always fetch at most the latest N rows and apply a final in-memory cap
    # to guarantee prompt injection never exceeds N.
    # The system prompt remains outside this list and is always first in the
    # ChatPromptTemplate.
    rows = await fetch_recent_user_messages(
        db, str(thread.id), user_email, limit=DEFAULT_WINDOW_SIZE
    )
    chat_history = _to_lc_messages(rows)[-DEFAULT_WINDOW_SIZE:]
    
    logger.info(f"DEBUG: User message: '{message}'")
    logger.info(f"DEBUG: Chat history count: {len(chat_history)}")
    for i, msg in enumerate(chat_history):
        logger.info(f"DEBUG: History[{i}] {msg.type}: {msg.content[:100]}")

    # For personal fact statements ONLY, use empty history to avoid LLM
    # getting confused and mixing up facts from previous messages.
    # For questions, keep history so LLM can recall previously stated facts.
    fact_query_key = _extract_fact_query_key(message)
    is_memory_list = _is_memory_list_request(message)
    is_memory_related = (
        fact_query_key is not None
        or is_memory_list
        or _is_memory_related_query(message)
    )
    is_question_like = message.strip().endswith("?") or fact_query_key is not None or is_memory_list
    is_statement = _is_personal_fact_statement(message) and not is_question_like

    # Keep memory/profile prompts isolated: for non-memory tasks (e.g., image or file analysis),
    # remove memory-related and personal-fact turns from history so answers stay on-task.
    if not is_memory_related:
        filtered_history = []
        for history_msg in chat_history:
            content = str(getattr(history_msg, "content", ""))
            if _extract_personal_fact(content):
                continue
            if _is_memory_related_query(content):
                continue
            filtered_history.append(history_msg)
        chat_history = filtered_history

    if is_statement and _should_truncate_response(message):
        logger.info("DEBUG: Clearing history for personal fact statement")
        chat_history = []
    
    # Build attachments for the user message based on uploaded files
    # This allows follow-up questions to reference these images
    user_attachments = None
    if attachment_names:
        try:
            user_image_urls = []
            for stored_name in attachment_names:
                file_path = _resolve_attachment_path(user_email, stored_name)
                ext = file_path.suffix.lower()
                # Only capture images as attachments for follow-up reference
                if ext in {".png", ".jpg", ".jpeg"}:
                    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
                    mime_type = _guess_image_mime(file_path)
                    image_url = f"data:{mime_type};base64,{encoded}"
                    user_image_urls.append(image_url)
            
            if user_image_urls:
                user_attachments = {"images": user_image_urls}
                logger.info(f"DEBUG: Saving user message with {len(user_image_urls)} image attachments")
        except Exception as e:
            logger.warning(f"Failed to create image attachments for user message: {e}")
    
    # Save user message to database after fetching history.
    user_msg_obj = Message(
        thread_id=str(thread.id),
        user_email=user_email,
        role="user",
        content=message,
        attachments=user_attachments,
    )
    db.add(user_msg_obj)
    await db.commit()
    
    # Echo back the user message so the frontend can display it.
    yield f"__USER_MESSAGE__{message}\n"
    logger.info(
        "sliding_window thread=%s sent_to_llm=%d roles=%s",
        thread.id,
        len(chat_history),
        [m.type for m in chat_history],
    )

    # Check for RAG context FIRST before handling fact queries
    # This ensures RAG answers take priority over cached memory
    chain = build_chat_chain()
    human_content, rag_context_added = await _build_human_content_blocks(
        message,
        user_email,
        attachment_names or [],
        db=db,
        thread_id=str(thread.id),
        user_id=user_id,
    )

    # If RAG context is available, use it even for fact queries
    # (documents take priority over chat memory)
    if rag_context_added:
        logger.info("DEBUG: RAG context found, using LLM to answer with document context")
    else:
        # Only use memory fact lookups if NO RAG context is available
        if fact_query_key is not None:
            specific_answer = await _build_specific_fact_answer(
                db,
                str(thread.id),
                user_email,
                fact_query_key,
            )
            answer = specific_answer or f"I do not remember your {fact_query_key} yet. Please tell me and I will remember it."
            yield answer
            db.add(
                Message(
                    thread_id=str(thread.id),
                    user_email=user_email,
                    role="assistant",
                    content=answer,
                    attachments=None,
                )
            )
            await db.commit()
            return

        if is_memory_list:
            answer = await _build_memory_list_answer(db, str(thread.id), user_email)
            yield answer
            db.add(
                Message(
                    thread_id=str(thread.id),
                    user_email=user_email,
                    role="assistant",
                    content=answer,
                    attachments=None,
                )
            )
            await db.commit()
            return
    
    # When RAG context is available, clear chat history to ensure LLM uses ONLY the document context
    if rag_context_added:
        logger.info("DEBUG: RAG context added, clearing chat history to use only document context")
        chat_history = []

    human_messages = [HumanMessage(content=human_content)]
    assistant_parts: list[str] = []
    should_truncate = _should_truncate_response(message)
    is_statement = _is_personal_fact_statement(message) and not is_question_like
    
    # Check if this is an image generation or modification request
    is_image_generation = _detect_image_generation_intent(message)
    is_image_modification = _detect_image_modification_intent(message) and not is_image_generation
    
    # If it's a modification, try to get the previous image prompt
    previous_image_prompt = None
    if is_image_modification:
        logger.info("DEBUG: Image modification intent detected, extracting previous image prompt")
        previous_image_prompt = await _extract_last_image_prompt_from_history(db, str(thread.id), user_email)
        if previous_image_prompt:
            logger.info(f"DEBUG: Found previous image prompt: {previous_image_prompt[:100]}")
        else:
            logger.info("DEBUG: No previous image prompt found in history")
    
    # Determine mode instruction
    mode_instruction = IMAGE_GENERATION_INSTRUCTION if is_image_generation else (
        STATEMENT_INSTRUCTION if is_statement else QUESTION_INSTRUCTION
    )

    try:
        logger.info(f"DEBUG: Image generation intent: {is_image_generation}, Image modification intent: {is_image_modification}")
        logger.info("DEBUG: Beginning async iteration over chain.astream()")
        
        # If image generation or modification is requested, handle it directly
        if is_image_generation or (is_image_modification and previous_image_prompt):
            try:
                from app.services.image_service import generate_chat_image, download_and_upload_image
                
                # Combine previous prompt with modification request for modifications
                if is_image_modification and previous_image_prompt:
                    combined_prompt = f"Take this image concept: '{previous_image_prompt}' and {message}"
                    logger.info(f"DEBUG: Generating modified image with combined prompt: {combined_prompt[:100]}")
                else:
                    combined_prompt = message
                    logger.info(f"DEBUG: Generating new image for prompt: {combined_prompt[:100]}")
                
                # Generate image from the request
                temp_url = await generate_chat_image(combined_prompt, user_email)
                logger.info(f"DEBUG: Got temporary image URL, downloading and uploading...")
                
                # Download and upload to storage
                permanent_url = await download_and_upload_image(temp_url, user_email)
                logger.info(f"DEBUG: Image uploaded: {permanent_url}")
                
                # Build response with image
                image_markdown = f"![generated image]({permanent_url})"
                
                # Stream the image to the client
                yield image_markdown
                answer = image_markdown
                
            except Exception as e:
                error_msg = f"[Image Generation Error] {type(e).__name__}: {str(e)}"
                logger.error(f"DEBUG: Image generation failed: {error_msg}", exc_info=True)
                yield error_msg
                answer = error_msg
        elif is_image_modification:
            # Modification requested but no previous image found
            error_msg = "I don't see a previous image to modify. Please generate an image first, then I can help you modify it."
            logger.info(f"DEBUG: Modification requested but no previous image found")
            yield error_msg
            answer = error_msg
        elif is_statement and should_truncate:
            # For personal fact statements, provide an engaging response with helpful suggestions
            logger.info(f"DEBUG: Personal fact statement detected, generating helpful response")
            token_count = 0
            # Use a special instruction to generate a structured response with emoji, acknowledgment, and suggestions
            fact_instruction = (
                "The user shared a personal fact about something they love or enjoy (e.g., 'I love playing tennis'). "
                "Respond with: "
                "1. An enthusiastic acknowledgment with a relevant emoji (e.g., 'Nice! 🎾')\n"
                "2. One brief sentence about why this activity is great\n"
                "3. A bulleted list (4-6 items) of specific ways you can help them with this topic. "
                "Format as markdown bullets with helpful suggestions like improving skills, fitness routines, equipment advice, "
                "following professionals, finding local communities, etc. Keep suggestions relevant to their interest.\n"
                "Be encouraging and actionable!"
            )
            async for chunk in chain.astream(
                {
                    "human_messages": human_messages,
                    "chat_history": chat_history,
                    "mode_instruction": fact_instruction,
                },
                config={"metadata": {"user_email": user_email}},
            ):
                token_count += 1
                text = str(chunk)
                logger.info(f"DEBUG: Chunk {token_count}: {repr(text[:100])}")
                assistant_parts.append(text)
                yield text
            
            logger.info(f"DEBUG: Fact info generation completed with {token_count} tokens")
            answer = "".join(assistant_parts)
        else:
            # Regular text response
            token_count = 0
            async for chunk in chain.astream(
                {
                    "human_messages": human_messages,
                    "chat_history": chat_history,
                    "mode_instruction": mode_instruction,
                },
                config={"metadata": {"user_email": user_email}},
            ):
                token_count += 1
                text = str(chunk)
                logger.info(f"DEBUG: Chunk {token_count}: {repr(text[:100])}")
                assistant_parts.append(text)
                
                # If not truncating, stream chunks as they arrive
                if not should_truncate:
                    yield text
                    
            logger.info(f"DEBUG: Chain invocation completed with {token_count} tokens")
            
            answer = "".join(assistant_parts)
            
            logger.info(f"DEBUG: LLM raw response: {answer[:200]}")
            logger.info(f"DEBUG: Should truncate? {should_truncate}")
            
            # If user shared a personal fact or asked a specific information question,
            # truncate response to first sentence
            if should_truncate:
                truncated_answer = _truncate_to_first_sentence(answer)
                logger.info(f"DEBUG: Truncating response: '{answer[:150]}' → '{truncated_answer[:150]}'")
                answer = truncated_answer
                # Stream the truncated version to client
                yield answer
                
    except Exception as e:
        logger.error(f"DEBUG: Exception during response generation", exc_info=True)
        error_msg = f"[LLM Error] {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        yield error_msg
        answer = ""
        return

    # Extract any generated image URLs from the response
    image_urls = _extract_image_urls(answer)
    attachments = _build_message_attachments(image_urls)
    if image_urls:
        logger.info(f"DEBUG: Extracted {len(image_urls)} image URL(s) from response")
    
    db.add(
        Message(
            thread_id=str(thread.id),
            user_email=user_email,
            role="assistant",
            content=answer,
            attachments=attachments,
        )
    )
    await db.commit()

    # Auto-title the thread after the first exchange.
    if thread.title == thread_service.DEFAULT_TITLE:
        title = await thread_service.generate_title(message, answer, user_email)
        if title:
            await thread_service.update_thread_title(
                db, user_email, thread.id, title
            )
