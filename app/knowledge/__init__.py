"""NEXA Knowledge Base + RAG (Part 9).
User -> NEXA -> KnowledgeBase -> Ingestion -> Chunking -> Embeddings -> VectorStore
                              -> Retriever -> Relevant Context -> NexaCore/ModelGateway
                              -> Answer + Sources
The UI and API never talk to the vector store directly - only through
:class:`app.knowledge.knowledge_base.KnowledgeBase`, so the embedding
provider or vector store can be swapped later without touching callers.
"""
from app.knowledge.knowledge_base import KnowledgeBase, build_knowledge_base, get_knowledge_base
__all__ = ["KnowledgeBase", "build_knowledge_base", "get_knowledge_base"]
