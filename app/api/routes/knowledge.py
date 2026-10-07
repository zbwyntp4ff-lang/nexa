"""Knowledge Base / RAG endpoints (Part 9).
Implements the Ingestion -> Retrieval surface described in the Part 9 spec.
The API only ever talks to :class:`app.knowledge.knowledge_base.KnowledgeBase`
- never to the vector store or document store directly.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Form, Query, UploadFile
from pydantic import BaseModel, Field
from app.knowledge.knowledge_base import KnowledgeBase, get_knowledge_base
from app.knowledge.models import Citation, KnowledgeDocument, RetrievedChunk
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
class NoteRequest(BaseModel):
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    project_id: str | None = None
    conversation_id: str | None = None
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    project_id: str | None = None
    conversation_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
class SearchResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunk]
    citations: list[Citation]
    insufficient: bool
@router.post("/documents", response_model=KnowledgeDocument)
async def upload_document(
    file: UploadFile,
    project_id: str | None = Form(default=None),
    conversation_id: str | None = Form(default=None),
    kb: KnowledgeBase = Depends(get_knowledge_base),
) -> KnowledgeDocument:
    raw = await file.read()
    return await kb.add_upload(
        file.filename or "file", raw, project_id=project_id, conversation_id=conversation_id
    )
@router.post("/notes", response_model=KnowledgeDocument)
async def add_note(request: NoteRequest, kb: KnowledgeBase = Depends(get_knowledge_base)) -> KnowledgeDocument:
    return await kb.add_note(
        request.title, request.text, project_id=request.project_id, conversation_id=request.conversation_id
    )
@router.get("/documents", response_model=list[KnowledgeDocument])
async def list_documents(
    project_id: str | None = Query(default=None), kb: KnowledgeBase = Depends(get_knowledge_base)
) -> list[KnowledgeDocument]:
    return kb.list_documents(project_id=project_id)
@router.get("/sources/{document_id}", response_model=KnowledgeDocument)
async def get_source(document_id: str, kb: KnowledgeBase = Depends(get_knowledge_base)) -> KnowledgeDocument:
    return kb.get_document(document_id)
@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, kb: KnowledgeBase = Depends(get_knowledge_base)) -> dict:
    kb.delete_document(document_id)
    return {"deleted": True, "id": document_id}
@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, kb: KnowledgeBase = Depends(get_knowledge_base)) -> SearchResponse:
    result = kb.search(
        request.query,
        project_id=request.project_id,
        conversation_id=request.conversation_id,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )
    return SearchResponse(
        query=request.query,
        chunks=result.chunks,
        citations=result.citations,
        insufficient=result.insufficient,
    )
