"""Simple chat endpoints for FDA drug information."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime

from database.database import get_db_session, FDAExtractionResults
from api.routers.simple_auth import get_current_user
from utils.qdrant_util import QdrantUtil

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simple_chat"])

class ChatRequest(BaseModel):
    message: str
    drugId: Optional[int] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    timestamp: datetime

def get_db():
    """Dependency to get database session."""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

@router.post("/api/chat")
async def simple_chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Simple chat endpoint for FDA drug queries."""
    try:
        # If drugId is provided, get context from that drug
        context = ""
        if request.drugId:
            drug = db.query(FDAExtractionResults).filter(
                FDAExtractionResults.id == request.drugId
            ).first()
            
            if drug:
                context = f"Context: Drug {drug.drug_name} by {drug.manufacturer}. "
        
        # Initialize ChromaDB
        vector_db = QdrantUtil.get_instance(use_persistent_client=True)
        
        # Search for relevant information
        try:
            results = vector_db.query_with_llm(
                query=request.message,
                collection_name="fda_documents",
                n_results=3
            )
            
            response_content = results if results else f"I couldn't find specific information about '{request.message}'."
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            response_content = f"{context}Based on the FDA database, {request.message}. Please check the drug details section for more specific information."
        
        return ChatResponse(
            id=str(datetime.now().timestamp()),
            content=response_content,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            id=str(datetime.now().timestamp()),
            content="I'm having trouble accessing the information right now. Please try again.",
            timestamp=datetime.now()
        )