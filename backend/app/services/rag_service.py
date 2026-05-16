"""RAG (Retrieval Augmented Generation) service for PDF documents.

Handles PDF upload, text extraction, embedding, and retrieval from ChromaDB.
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.chroma_client import get_chroma_client, get_user_collection_name
from app.core.config import settings
from app.models.document import Document
from app.schemas.rag import DocumentMetadata

logger = logging.getLogger(__name__)

# Configuration for text splitting
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
RETRIEVAL_K = 5  # Number of chunks to retrieve
SIMILARITY_THRESHOLD = 0.4  # Filter out chunks with similarity distance > threshold (cosine distance, strict filtering)


def _get_embeddings() -> OpenAIEmbeddings:
    """Get OpenAI embeddings client."""
    return OpenAIEmbeddings(
        model=settings.LITELLM_EMBEDDING_MODEL,
        base_url=settings.LITELLM_PROXY_URL,
        api_key=settings.LITELLM_API_KEY,
    )


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text from PDF
        
    Raises:
        ValueError: If PDF cannot be read
    """
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
        raise ValueError(f"Failed to extract text from PDF: {e}")


def _chunk_text(text: str) -> list[str]:
    """Split text into chunks using RecursiveCharacterTextSplitter.
    
    Args:
        text: Text to chunk
        
    Returns:
        List of text chunks
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_text(text)
    logger.info(f"Split document into {len(chunks)} chunks")
    return chunks


async def ingest_pdf(
    pdf_path: Path,
    user_id: str,
    user_email: str,
    document_name: str,
) -> str:
    """Ingest a PDF document into ChromaDB.
    
    Args:
        pdf_path: Path to PDF file
        user_id: User UUID
        user_email: User email for tracking
        document_name: Name of the document for reference
        
    Returns:
        Document ID
        
    Raises:
        ValueError: If PDF processing fails
    """
    # Extract text from PDF
    logger.info(f"Extracting text from PDF: {document_name}")
    text = _extract_text_from_pdf(pdf_path)
    
    if not text.strip():
        raise ValueError("PDF contains no extractable text")
    
    # Chunk text
    logger.info(f"Chunking text from {document_name}")
    chunks = _chunk_text(text)
    
    # Get embeddings client
    embeddings = _get_embeddings()
    
    # Get or create collection for user
    client = get_chroma_client()
    collection_name = get_user_collection_name(user_id)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    
    # Generate document ID
    document_id = str(uuid4())
    
    # Add chunks to collection
    logger.info(f"Adding {len(chunks)} chunks to ChromaDB collection {collection_name}")
    
    ids = []
    metadatas = []
    documents = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{document_id}#{i}"
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "document_id": document_id,
            "document_name": document_name,
            "user_email": user_email,
            "chunk_index": i,
            "total_chunks": len(chunks),
        })
    
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )
    
    logger.info(f"Successfully ingested PDF {document_name} with ID {document_id}")
    return document_id


async def retrieve_relevant_chunks(
    query: str,
    user_id: str,
    k: int = RETRIEVAL_K,
) -> list[dict]:
    """Retrieve relevant chunks from ChromaDB based on query.
    
    Args:
        query: Query string
        user_id: User UUID
        k: Number of chunks to retrieve
        
    Returns:
        List of relevant chunks with metadata
    """
    try:
        client = get_chroma_client()
        collection_name = get_user_collection_name(user_id)
        
        # Check if collection exists
        collections = client.list_collections()
        if not any(c.name == collection_name for c in collections):
            logger.info(f"No documents found for user {user_id}")
            return []
        
        collection = client.get_collection(name=collection_name)
        
        # Query the collection
        results = collection.query(
            query_texts=[query],
            n_results=k,
        )
        
        # Format results
        retrieved_chunks = []
        if results["documents"] and len(results["documents"]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else None
                # Filter by similarity threshold - exclude low-relevance chunks
                if distance is not None and distance > SIMILARITY_THRESHOLD:
                    logger.info(f"Skipping chunk {i} with distance {distance} (above threshold {SIMILARITY_THRESHOLD})")
                    continue
                retrieved_chunks.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": distance,
                })
        
        logger.info(f"Retrieved {len(retrieved_chunks)} relevant chunks (similarity > {1-SIMILARITY_THRESHOLD:.2f}) for query: {query[:50]}...")
        return retrieved_chunks
        
    except Exception as e:
        logger.error(f"Failed to retrieve chunks: {e}")
        return []


async def get_user_documents(
    user_id: str,
) -> list[DocumentMetadata]:
    """Get list of documents uploaded by user.
    
    Args:
        user_id: User UUID
        
    Returns:
        List of document metadata
    """
    try:
        client = get_chroma_client()
        collection_name = get_user_collection_name(user_id)
        
        # Check if collection exists
        collections = client.list_collections()
        if not any(c.name == collection_name for c in collections):
            return []
        
        collection = client.get_collection(name=collection_name)
        
        # Get all documents in the collection
        all_data = collection.get()
        
        # Extract unique documents
        documents_dict = {}
        if all_data["metadatas"]:
            for metadata in all_data["metadatas"]:
                doc_id = metadata.get("document_id")
                doc_name = metadata.get("document_name")
                if doc_id and doc_name:
                    if doc_id not in documents_dict:
                        documents_dict[doc_id] = DocumentMetadata(
                            document_id=doc_id,
                            document_name=doc_name,
                            chunk_count=0,
                        )
                    documents_dict[doc_id].chunk_count += 1
        
        return list(documents_dict.values())
        
    except Exception as e:
        logger.error(f"Failed to get user documents: {e}")
        return []


async def delete_document(
    user_id: str,
    document_id: str,
) -> bool:
    """Delete a document from ChromaDB.
    
    Args:
        user_id: User UUID
        document_id: Document ID to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_chroma_client()
        collection_name = get_user_collection_name(user_id)
        
        # Check if collection exists
        collections = client.list_collections()
        if not any(c.name == collection_name for c in collections):
            return False
        
        collection = client.get_collection(name=collection_name)
        
        # Delete all chunks for this document
        # ChromaDB's delete operation uses where filters
        collection.delete(
            where={"document_id": document_id}
        )
        
        logger.info(f"Deleted document {document_id} from user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        return False


def format_retrieved_chunks_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context string for the LLM prompt.
    
    Args:
        chunks: List of retrieved chunks
        
    Returns:
        Formatted context string with NO preamble headers that trigger LLM preambles
    """
    if not chunks:
        return ""

    # Format chunks minimally - no headers that trigger preambles
    context_parts = []
    for chunk in chunks:
        content = chunk.get("content", "")
        context_parts.append(content)

    return "\n\n---\n\n".join(context_parts)
