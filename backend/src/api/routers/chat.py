from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, ConfigDict, validator
from database.database import get_db, ChatHistory, ShareChat
from api.services.chat_management_service import FDAChatManagementService
from api.routers.auth import get_current_user
from utils.llm_util import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document
import uuid
import logging
import json
import asyncio
from datetime import datetime, timedelta
from dataclasses import asdict
from config.settings import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Simple SourceDocument class for document metadata
class SourceDocument:
    def __init__(self, id, filename, snippet, citation_number, relevance_score, 
                 page_number=None, drug_name=None, used_in_response=True, metadata=None):
        self.id = id
        self.filename = filename
        self.snippet = snippet
        self.citation_number = citation_number
        self.relevance_score = relevance_score
        self.page_number = page_number
        self.drug_name = drug_name
        self.used_in_response = used_in_response
        self.metadata = metadata or {}

# Helper function for HTML conversion in unified endpoint
def _is_no_info_response(response: str) -> bool:
    """Check if response indicates no relevant information was found"""
    response_lower = response.lower()
    return (
        "sorry" in response_lower or
        "no relevant information found" in response_lower or
        "couldn't find any relevant information" in response_lower or
        "i am unable to provide" in response_lower or
        "i cannot provide" in response_lower or
        "unable to find" in response_lower or
        "no information available" in response_lower or
        "not available in the provided documents" in response_lower or
        "not found in the" in response_lower or
        "no documents found" in response_lower or
        "no results found" in response_lower or
        "this information is not available" in response_lower
    )

async def _ensure_english_response_with_llm(response: str, original_query: str) -> str:
    """Ensure response is in English by detecting language and translating if needed"""
    if not response:
        return response
    
    try:
        from utils.llm_util import get_llm
        llm = get_llm()
        
        # First, check if the response is in English
        language_check_prompt = f"""Analyze the language of this text and respond with ONLY the language name (e.g., "English", "French", "Spanish", etc.):

Text: {response}

Language:"""
        
        language_result = llm.invoke(language_check_prompt)
        detected_language = language_result.content.strip() if hasattr(language_result, 'content') else str(language_result).strip()
        
        logger.info(f"Detected language: {detected_language} for response: {response}")
        
        # If not English, translate it
        if detected_language.lower() not in ['english', 'en']:
            logger.info(f"Response is in {detected_language}, translating to English...")
            
            translation_prompt = f"""Translate the following {detected_language} text to English. 
Maintain the same tone, structure, and meaning. 
If the text mentions that information is not available or cannot be provided, ensure this is clearly stated in English.

Original text in {detected_language}:
{response}

English translation:"""
            
            translation_result = await llm.ainvoke(translation_prompt)
            translated_response = translation_result.content if hasattr(translation_result, 'content') else str(translation_result)
            
            logger.info(f"Translated response from {detected_language} to English")
            return translated_response.strip()
        
        return response
        
    except Exception as e:
        logger.error(f"Error in language detection/translation: {str(e)}")
        # Fallback: if detection/translation fails, return original
        return response

async def _convert_response_to_html_unified(text: str, query: str) -> str:
    """Convert LLM response to clean HTML for unified endpoint."""
    if not text:
        return text
    
    try:
        llm = get_llm()
        
        conversion_prompt = f"""
        You are a professional HTML converter for a Tailwind-based chat UI.

        Your job is to:
        1. Convert the provided text into clean, semantic HTML.
        2. Do not modify, shorten, or omit any content — preserve it exactly as given.
        3. Ensure the HTML is style-safe and does not interfere with the existing chat UI layout.
        4. Make sure the response is in English only.

        TEXT TO CONVERT:
        {text}

        RULES:
        - Output must be valid semantic HTML only.
        - Wrap all content in:
        <div class="prose max-w-none text-gray-800 text-base leading-relaxed"> ... </div>
        - Use semantic tags (<p>, <ul>, <li>, <table>, <h2>, <h3>, etc.) as appropriate.
        - Tables must use Tailwind-safe minimal classes:
        <table class="min-w-full border-collapse border border-gray-300">
            <thead class="bg-gray-50">
            <tr><th class="border border-gray-300 px-4 py-2">Header</th></tr>
            </thead>
            <tbody>
            <tr><td class="border border-gray-300 px-4 py-2">Content</td></tr>
            </tbody>
        </table>
        - Do not inject inline styles, global CSS, or extra classes that could affect the chat UI.
        - Do not add explanations, notes, or metadata — return only the HTML.
        """





        response = llm.invoke(conversion_prompt)
        html_content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up any markdown code block markers that might be included
        html_content = html_content.replace('```html', '').replace('```', '').strip()
        
        # Remove any unwanted wrapper tags that might interfere with ReactMarkdown
        html_content = html_content.replace('<!DOCTYPE html>', '')
        html_content = html_content.replace('<html>', '').replace('</html>', '')
        html_content = html_content.replace('<head>', '').replace('</head>', '')
        html_content = html_content.replace('<body>', '').replace('</body>', '')
        html_content = html_content.replace('<title>Indications and Usage</title>', '')
        
        return html_content.strip()
        
    except Exception as e:
        logger.error(f"Error in unified HTML conversion: {str(e)}")
        # Fallback to original text if LLM conversion fails
        return text

# Pydantic models for request/response
class SearchDocumentsRequest(BaseModel):
    query: str
    drug_name: Optional[str] = None
    collection_id: Optional[int] = None
    source_file_id: Optional[int] = None  # For document-specific search

class QueryDocumentRequest(BaseModel):
    source_file_id: int
    query: str
    session_id: str
    user_id: int

class QueryMultipleDocumentsRequest(BaseModel):
    source_file_ids: Optional[List[int]] = None
    collection_id: Optional[int] = None
    query: str
    session_id: str
    user_id: int
    
    @validator('session_id')
    def validate_session_id(cls, v):
        if not v or not v.strip():
            raise ValueError("session_id is required for conversational context")
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or v < 1:
            raise ValueError("valid user_id is required for conversational context")
        return v

class ChatRequest(BaseModel):
    chat_id: int

class FavoriteRequest(BaseModel):
    chat_id: int
    user_id: int

class AdvancedSearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None

class SuggestionsRequest(BaseModel):
    chat_history: List[Dict[str, Any]] = []
    selected_drugs: List[Any] = []  # Can be list of strings or list of dicts
    last_response: str = ""

class EnhancedSourceDocumentResponse(BaseModel):
    """Enhanced source document with citation details"""
    id: str
    filename: str
    snippet: str
    citation_number: int
    relevance_score: float
    page_number: Optional[int] = None
    drug_name: Optional[str] = None

class QueryMultipleEnhancedResponse(BaseModel):
    """Enhanced response model with citations and metadata"""
    # Original fields
    user_query: str
    response: str
    query_type: str
    chat_id: int
    
    # Enhanced fields
    cited_response: str  # Response with inline citations [1], [2], etc.
    source_documents: List[EnhancedSourceDocumentResponse]  # With snippets
    intent: str  # Classified intent (new_topic, follow_up, etc.)
    conversation_summary: str  # Brief summary of conversation context
    enhanced_query: str  # The enhanced query used for retrieval
    confidence_scores: Dict[str, float]  # Confidence metrics
    
    # Optional fields
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
    content_type: str = "html"  # For backward compatibility

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    source_file_id: int
    file_name: str
    file_url: Optional[str] = None
    drug_name: Optional[str] = None
    manufacturer: Optional[str] = None
    document_type: Optional[str] = None
    approval_date: Optional[str] = None
    indication: Optional[str] = None
    efficacy_details: Optional[str] = None
    relevance_score: float
    relevance_comments: Optional[str] = ""

class QueryResponse(BaseModel):
    source_file_id: int
    file_name: str
    file_url: Optional[str]
    drug_name: Optional[str]
    user_query: str
    response: str
    chat_id: int


@router.post("/search")
async def search_documents(
    request: SearchDocumentsRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search FDA documents by drug name with SQL first, then vector search fallback."""
    try:
        # Perform search with user_id for history tracking
        result = await FDAChatManagementService.search_fda_documents(
            search_query=request.query,
            user_id=current_user.id,
            drug_name=request.drug_name,
            collection_id=request.collection_id,
            source_file_id=request.source_file_id,
            db=db
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in search endpoint: {str(e)}")
        
        # Determine user-friendly error message based on error type
        if "embedding" in str(e).lower() or "404" in str(e):
            error_message = "I'm currently experiencing issues with the search system. Please try again in a few moments."
        elif "api" in str(e).lower() or "key" in str(e).lower():
            error_message = "I'm having trouble connecting to the AI service. Please try again later."
        elif "timeout" in str(e).lower():
            error_message = "The request took too long to process. Please try with a shorter query or try again later."
        elif "database" in str(e).lower() or "connection" in str(e).lower():
            error_message = "I'm experiencing database connectivity issues. Please try again later."
        else:
            error_message = "I'm experiencing a technical issue right now. Please try again later or contact support if this continues."
        
        raise HTTPException(status_code=500, detail=error_message)

@router.post("/query", response_model=QueryResponse)
async def query_document(
    request: QueryDocumentRequest,
    db: Session = Depends(get_db)
):
    """Query a specific FDA document."""
    try:
        # Save chat request
        request_details = {
            "source_file_id": request.source_file_id,
            "query": request.query
        }
        
        chat_id = FDAChatManagementService.save_chat_request(
            user_id=request.user_id,
            user_query=request.query,
            session_id=request.session_id,
            request_details=request_details,
            db=db
        )
        
        # Get recent chat history for conversation context
        chat_history = _get_recent_chat_history(request.session_id, request.user_id, db, limit=3)
        logger.info(f"Retrieved {len(chat_history)} conversation pairs for context")
        
        # Enhance query with conversation context if available
        enhanced_query = request.query
        if chat_history:
            enhanced_query = await _enhance_query_with_context(request.query, chat_history)
            logger.info(f"Enhanced query from '{request.query}' to '{enhanced_query}'")
        
        # Query document with enhanced query
        result = await FDAChatManagementService.query_fda_document(
            source_file_id=request.source_file_id,
            query_string=enhanced_query,
            session_id=request.session_id,
            user_id=request.user_id,
            db=db
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Document not found or query failed")
        
        # Convert response to HTML for frontend rendering
        if result.get("response"):
            logger.info(f"Converting response to HTML for query endpoint")
            html_response = await _convert_response_to_html_unified(result["response"],request.query)
            result["response"] = html_response
            result["content_type"] = "html"  # Indicate HTML content
        
        # Update chat response with HTML-converted content
        FDAChatManagementService.update_chat_response(
            chat_id=chat_id,
            response_details=result,
            db=db
        )
        
        result["chat_id"] = chat_id
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {str(e)}")
        
        # Determine user-friendly error message based on error type
        if "embedding" in str(e).lower() or "404" in str(e):
            error_message = "I'm currently experiencing issues with the search system. Please try again in a few moments."
        elif "api" in str(e).lower() or "key" in str(e).lower():
            error_message = "I'm having trouble connecting to the AI service. Please try again later."
        elif "timeout" in str(e).lower():
            error_message = "The request took too long to process. Please try with a shorter query or try again later."
        elif "database" in str(e).lower() or "connection" in str(e).lower():
            error_message = "I'm experiencing database connectivity issues. Please try again later."
        else:
            error_message = "I'm experiencing a technical issue right now. Please try again later or contact support if this continues."
        
        raise HTTPException(status_code=500, detail=error_message)

# Modular helper methods for query-multiple endpoint
async def _initialize_chat_and_validate(
    request: QueryMultipleDocumentsRequest,
    user_id: int,
    db: Session
) -> Tuple[int, List[Tuple[str, str]], Optional[Dict], Optional[Dict], Any]:
    """Initialize chat and validate collection access"""
    # Validate that collection_id is provided
    if not request.collection_id:
        raise HTTPException(status_code=400, detail="collection_id must be provided")
    
    # Import necessary models
    from database.database import Collection, collection_document_association
    
    # Handle finding collection when collection_id is -1
    if request.collection_id == -1:
        # Find collection_id using source_file_ids if provided
        if request.source_file_ids:
            # Query to find the collection that contains these documents
            collection_result = db.query(Collection).join(
                collection_document_association,
                Collection.id == collection_document_association.c.collection_id
            ).filter(
                collection_document_association.c.document_id.in_(request.source_file_ids)
            ).first()
            
            if collection_result:
                collection = collection_result
                logger.info(f"Found collection '{collection.name}' (id={collection.id}) for source_file_ids: {request.source_file_ids}")
            else:
                # Fallback to default fda_document collection if no collection found
                collection = db.query(Collection).filter(Collection.name == "fda_document").first()
                if not collection:
                    # Create a placeholder collection object for default collection
                    class DefaultCollection:
                        id = -1
                        name = "fda_document"
                        vector_db_collection_name = "fda_documents"
                    collection = DefaultCollection()
                logger.warning(f"No collection found for source_file_ids: {request.source_file_ids}, using default fda_document collection")
        else:
            # No source_file_ids provided, use default fda_document collection
            collection = db.query(Collection).filter(Collection.name == "fda_document").first()
            if not collection:
                # Create a placeholder collection object for default collection
                class DefaultCollection:
                    id = -1
                    name = "fda_document"
                    vector_db_collection_name = "fda_documents"
                    user_id = user_id
                collection = DefaultCollection()
            logger.info("No source_file_ids provided, using default fda_document collection")
    else:
        # Verify collection exists
        collection = db.query(Collection).filter(Collection.id == request.collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection with id {request.collection_id} not found")
        
        #request.source_file_ids = None
            
        # Note: Collections don't have user ownership in this system
        # All authenticated users can access all collections
    
    # Ensure collection has proper vector database name
    if not hasattr(collection, 'vector_db_collection_name') or not collection.vector_db_collection_name:
        import re
        sanitized_name = re.sub(r'[^\w\-_]', '_', collection.name)
        collection.vector_db_collection_name = f"collection_{collection.id}_{sanitized_name}"
    
    logger.info(f"Using collection: '{collection.name}' (ID: {collection.id})")
    logger.info(f"Vector database collection name: {collection.vector_db_collection_name}")
    
    # Save chat request with collection info
    request_details = {
        "collection_id": request.collection_id,
        "collection_name": collection.name,
        "vector_db_collection": collection.vector_db_collection_name,
        "query": request.query,
        "comparison_mode": True,
        "query_type": "collection"
    }
    
    chat_id = FDAChatManagementService.save_chat_request(
        user_id=user_id,
        user_query=request.query,
        session_id=request.session_id,
        request_details=request_details,
        db=db
    )
    
    # Get recent chat history for conversation context
    chat_history = _get_recent_chat_history(request.session_id, user_id, db, limit=3)
    logger.info(f"Retrieved {len(chat_history)} conversation pairs for context")
    
    # Get last response and follow-up status
    # Note: These methods don't exist in FDAChatManagementService yet
    # For now, we'll use the chat history to get the last response
    last_response = None
    if chat_history and len(chat_history) > 0:
        _, last_response = chat_history[-1]
    
    follow_up_status = None  # Not implemented yet
    
    return chat_id, chat_history, last_response, follow_up_status, collection

async def _classify_intent(
    query: str,
    chat_history: List[Tuple[str, str]]
) -> Tuple[Any, float]:
    """Classify query intent"""
    from utils.enhanced_intent_classifier import EnhancedIntentClassifier
    classifier = EnhancedIntentClassifier()
    
    # Get last response from chat history if available
    last_response = None
    if chat_history and len(chat_history) > 0:
        _, last_response = chat_history[-1]
    
    intent, confidence, reasoning = await classifier.classify_intent_with_context(
        current_query=query,
        chat_history=chat_history,
        last_response=last_response
    )
    
    logger.info(f"Classified query intent as: {intent} (confidence: {confidence:.2f})")
    logger.info(f"Classification reasoning: {reasoning}")
    return intent, confidence

async def _generate_conversation_summary(
    chat_history: List[Tuple[str, str]]
) -> str:
    """Generate conversation summary if needed"""
    if len(chat_history) <= 3:
        return " ".join([q for q, _ in chat_history])
    
    # Generate summary for longer conversations
    history_text = "\n".join([f"User: {q}\nAssistant: {a}" for q, a in chat_history])
    summary_prompt = f"""Summarize this conversation concisely in 2-3 sentences:
{history_text}

Summary:"""
    
    llm = get_llm()
    summary_response = await llm.ainvoke(summary_prompt)
    return summary_response.content if hasattr(summary_response, 'content') else str(summary_response)

async def _enhance_query(
    query: str    
) -> str:
    """Enhance query with context"""
    return await _enhance_query_with_context_v3(query)

async def _retrieve_documents(
    enhanced_query: str,
    collection_name: str,
    collection_id: int,
    vector_db_util,
    file_name_filter: Optional[Dict] = None
) -> List[Document]:
    """Retrieve and grade documents"""
    from utils.llm_util import get_embeddings_model
    # Retrieve documents
    logger.info("Using standard document search")
    search_results = vector_db_util.search_documents(
        query=enhanced_query,
        collection_name=collection_name,
        n_results=30,
        filter_dict=file_name_filter
    )
    documents = [Document(page_content=doc['content'], metadata=doc['metadata']) for doc in search_results]
    
    logger.info(f"Retrieved {len(documents)} candidate documents")
    
    # Apply relevance grading if needed
    if documents and len(documents) > 15:
        logger.info("Applying relevance grading to select top documents")
        documents = await _grade_documents_by_relevance(enhanced_query, documents)
        logger.info(f"Relevance grading selected {len(documents)} final documents")
    
    return documents

async def _generate_response_from_documents(
    documents: List[Document],    
    original_query: str,
    vector_db_util
) -> Tuple[str, str]:
    """Generate response from retrieved documents"""
    if not documents:
        response = "No relevant documents found for your query."
        return response, response
    
       
    prompt = vector_db_util._create_enhanced_generation_prompt(        
        documents=documents[:20],            
        original_query=original_query
    )
    
    # Get response from LLM
    llm = get_llm()
    llm_response_obj = await llm.ainvoke(prompt)
    response = llm_response_obj.content if hasattr(llm_response_obj, 'content') else str(llm_response_obj)
    
    # Ensure response is in English
    response = await _ensure_english_response_with_llm(response, original_query)
    
    
    # For now, cited_response is same as response (fact checking removed)
    cited_response = response
    
    return response, cited_response

async def _format_response(
    response: str,
    cited_response: str,
    documents: List[Document],
    request: QueryMultipleDocumentsRequest,
    collection_name: str,
    collection_id: int
) -> Dict[str, Any]:
    """Format the final response"""
    # Convert to HTML
    html_response = await _convert_response_to_html_unified(response, request.query)
    html_cited = await _convert_response_to_html_unified(cited_response, request.query)
    
    # Create enhanced sources
    enhanced_sources = []
    for i, doc in enumerate(documents[:20], 1):
        enhanced_sources.append(SourceDocument(
            id=doc.metadata.get('id', f'doc_{i}'),
            filename=doc.metadata.get('source_file_name', doc.metadata.get('source', 'Unknown')),
            snippet=doc.metadata.get('original_content', '')[:300] + '...' if len(doc.metadata.get('original_content', '')) > 300 else doc.metadata.get('original_content', ''),
            citation_number=i,
            relevance_score=doc.metadata.get('relevance_score', 0.0),
            page_number=doc.metadata.get('page_number'),
            drug_name=doc.metadata.get('drug_name'),
            used_in_response=True,
            metadata={
                'original_content': doc.metadata.get('original_content'),
                'file_url': doc.metadata.get('file_url', '')
            }
        ))
    
    # Check if response indicates no relevant information
    is_no_info_response = _is_no_info_response(response)
    
    return {
        "response": html_response,
        "cited_response": html_response if is_no_info_response else html_cited,
        "query_type": "collection",
        "collection_id": collection_id,
        "collection_name": collection_name,
        "source_documents": [] if is_no_info_response else [
            {
                'id': doc.id,
                'filename': doc.filename,
                'snippet': doc.snippet,
                'citation_number': doc.citation_number,
                'relevance_score': doc.relevance_score,
                'page_number': doc.page_number,
                'drug_name': doc.drug_name,
                'used_in_response': doc.used_in_response,
                'metadata': doc.metadata
            }
            for doc in enhanced_sources
        ],
        "content_type": "html"
    }

async def _handle_follow_up_query(
    request: QueryMultipleDocumentsRequest,
    chat_history: List[Tuple[str, str]],
    chat_id: int,
    collection: Any,
    db: Session
) -> Dict[str, Any]:
    """Handle follow-up queries without document search"""
    # Build comprehensive context from chat history
    history_context = "\n\n".join([
        f"User: {q}\nAssistant: {r}"
        for q, r in chat_history
    ])
    
    # Generate follow-up response using LLM with history
    follow_up_prompt = f"""Based on the conversation history:

{history_context}

Current Query: {request.query}

Please provide a comprehensive response to the current query based on the previous conversation context. 

CRITICAL REQUIREMENTS:
1. You MUST respond in English only, regardless of any language used in the conversation history
2. If the conversation history contains text in other languages, translate relevant information to English
3. Your entire response must be in English - do not include any text in other languages
4. Do not search for new documents - use only the information from the conversation history

Response (in English):"""
    
    llm = get_llm()
    follow_up_response_obj = await llm.ainvoke(follow_up_prompt)
    follow_up_response = follow_up_response_obj.content if hasattr(follow_up_response_obj, 'content') else str(follow_up_response_obj)
    
    # Ensure response is in English
    follow_up_response = await _ensure_english_response_with_llm(follow_up_response, request.query)
    
    # Convert to HTML
    html_response = await _convert_response_to_html_unified(follow_up_response, request.query)
    
    result = {
        "user_query": request.query,
        "response": html_response,
        "cited_response": html_response,
        "query_type": "collection_follow_up",
        "collection_id": request.collection_id,
        "collection_name": collection.name,
        "source_documents": [],  # No new documents searched
        "content_type": "html"
    }
    
    # Update chat response
    FDAChatManagementService.update_chat_response(
        chat_id=chat_id,
        response_details=result,
        db=db
    )
    
    result["chat_id"] = chat_id
    return result

async def _build_file_filter(
    request: QueryMultipleDocumentsRequest,
    collection: Any,
    db: Session
) -> Optional[Dict[str, Any]]:
    """Build file filter for document retrieval"""
    file_name_filter = None
    
    # Build file filter if source_file_ids provided
    if request.source_file_ids:
        from database.database import SourceFiles
        
        # Get file names from source_file_ids
        source_files = db.query(SourceFiles).filter(
            SourceFiles.id.in_(request.source_file_ids)
        ).all()
        
        if source_files:
            relevant_files = [f.file_name for f in source_files]
            logger.info(f"Collection query: Using {len(relevant_files)} files from source_file_ids: {relevant_files[:3]}...")
            file_name_filter = {"file_name": {"$in": relevant_files}}
        else:
            logger.warning(f"No source files found for ids: {request.source_file_ids}")
    
    return file_name_filter

@router.post("/query-multiple2")
async def query_multiple_documents(
    request: QueryMultipleDocumentsRequest,
    db: Session = Depends(get_db)
):
    """Query FDA documents from a collection - modularized version."""
    try:
        chat_id, chat_history, last_response, follow_up_status, collection = await _initialize_chat_and_validate(
            request, request.user_id, db
        )
        
        from utils.qdrant_util import QdrantUtil
        vector_db_util = QdrantUtil.get_instance(use_persistent_client=True)

        enhanced_query = await _enhance_query(request.query)
        logger.info(f"Enhanced query from '{request.query}' to '{enhanced_query}'")

        from utils.drug_file_matcher import DrugFileMatcher
        relevant_files = await DrugFileMatcher.extract_relevant_files_for_query(
            enhanced_query,
            source_file_ids=request.source_file_ids,    
            db=db
        )

        file_name_filter = None
        if relevant_files:
            logger.info(f"Document query: Applying file filter for {len(relevant_files)} files: {relevant_files[:3]}...")
            # Convert list of filenames to proper metadata filter for Qdrant
            file_name_filter = {"source": {"$in": relevant_files}}
        
        # Step 9: Retrieve documents
        documents = await _retrieve_documents(
            enhanced_query,
            collection.vector_db_collection_name,
            collection.id,
            vector_db_util,
            file_name_filter
        )
        
        # Step 10: Generate response
        response, cited_response = await _generate_response_from_documents(
            documents,           
            request.query,            
            vector_db_util
        )
        
        # Step 11: Format response
        result = await _format_response(
            response,
            cited_response,
            documents,
            request,
            collection.name,
            collection.id
        )
        
        # Step 13: Update chat response
        FDAChatManagementService.update_chat_response(
            chat_id=chat_id,
            response_details=result,
            db=db
        )
        
        result["chat_id"] = chat_id
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query-multiple endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/query-multiple-v2")
async def query_multiple_documents_v2(
    request: QueryMultipleDocumentsRequest, 
    db: Session = Depends(get_db)
):
    """
    Handle multi-document queries with source_file_ids.
    This endpoint supports document-specific queries with advanced features:
    - Intent classification
    - Conversation context
    - Follow-up query handling
    - Multi-query retrieval
    - Hybrid retrieval with reranking
    - Semantic caching
    - Enhanced fact checking
    """
    try:
        # Import necessary utilities
        from utils.feature_flags import FeatureFlags
        from utils.llm_util import get_llm
        from services.chat_management_service import FDAChatManagementService
        
        # Validate that source_file_ids are provided
        if not request.source_file_ids:
            raise HTTPException(status_code=400, detail="source_file_ids must be provided for document-based queries")
        
        # Original source_file_ids based query
        logger.info(f"Processing document-based query for {len(request.source_file_ids)} documents")
        
        # Save chat request
        request_details = {
            "source_file_ids": request.source_file_ids,
            "query": request.query,
            "comparison_mode": True,
            "query_type": "documents"
        }
        
        chat_id = FDAChatManagementService.save_chat_request(
            user_id=request.user_id,
            user_query=request.query,
            session_id=request.session_id,
            request_details=request_details,
            db=db
        )
        
        # Get recent chat history for conversation context
        chat_history = _get_recent_chat_history(request.session_id, request.user_id, db, limit=3)
        logger.info(f"Retrieved {len(chat_history)} conversation pairs for context")
        
        # NEW: Classify intent for document-based queries too
        from utils.enhanced_intent_classifier import EnhancedIntentClassifier, EnhancedIntent
        enhanced_classifier = EnhancedIntentClassifier()
        
        # Get last response for context
        last_response = None
        if chat_history:
            _, last_response = chat_history[-1]
        
        intent, confidence, reasoning = await enhanced_classifier.classify_intent_with_context(
            request.query, chat_history, last_response
        )
        logger.info(f"Classified query intent as: {intent.value} (confidence: {confidence:.2f})")
        
        # NEW: Generate conversation summary
        conversation_summary = await _generate_conversation_summary(chat_history)
        logger.info(f"Generated conversation summary: {conversation_summary[:100]}...")
        
        # NEW: Handle follow-up queries using previous response context
        from utils.response_context_handler import ResponseContextHandler
        response_handler = ResponseContextHandler()
        
        # Check if we should process using previous response
        if response_handler.should_use_previous_response(intent) and last_response:
            logger.info("Processing follow-up using previous response context")
            
            # Get the original query from last chat
            last_original_query = None
            if chat_history:
                last_original_query, _ = chat_history[-1]
            
            # Process the follow-up - always use history without document search
            logger.info("Processing follow-up query using conversation history")
            
            # Build comprehensive context from chat history
            history_context = "\n\n".join([
                f"User: {q}\nAssistant: {r}"
                for q, r in chat_history
            ])
            
            # Generate follow-up response using LLM with history
            follow_up_prompt = f"""Based on the conversation history:

{history_context}

Current Query: {request.query}

Please provide a comprehensive response to the current query based on the previous conversation context. 

CRITICAL REQUIREMENTS:
1. You MUST respond in English only, regardless of any language used in the conversation history
2. If the conversation history contains text in other languages, translate relevant information to English
3. Your entire response must be in English - do not include any text in other languages
4. Do not search for new documents - use only the information from the conversation history

Response (in English):"""
            
            llm = get_llm()
            follow_up_response_obj = await llm.ainvoke(follow_up_prompt)
            follow_up_response = follow_up_response_obj.content if hasattr(follow_up_response_obj, 'content') else str(follow_up_response_obj)
            
            # Ensure response is in English
            follow_up_response = await _ensure_english_response_with_llm(follow_up_response, request.query)
            
            logger.info("Follow-up processed without document search")
            
            # Convert to HTML
            html_response = await _convert_response_to_html_unified(
                follow_up_response, 
                request.query
            )
            
            result = {
                "user_query": request.query,
                "response": html_response,
                "cited_response": html_response,
                "query_type": "documents_follow_up",
                "source_file_ids": request.source_file_ids,
                "source_documents": [],  # No new documents searched
                "content_type": "html",
                "metadata": {}
            }
            
            # Update chat response
            FDAChatManagementService.update_chat_response(
                chat_id=chat_id,
                response_details=result,
                db=db
            )
            
            result["chat_id"] = chat_id
            return result
        else:
            # Enhanced query enhancement logic using v2
            enhanced_query = request.query
            if chat_history or intent != EnhancedIntent.NEW_TOPIC:
                # Map EnhancedIntent to QueryIntent for compatibility
                from utils.intent_classifier import QueryIntent
                mapped_intent = QueryIntent.NEW_TOPIC
                if intent in [EnhancedIntent.FOLLOW_UP_DETAIL, EnhancedIntent.FOLLOW_UP_COMPARISON]:
                    mapped_intent = QueryIntent.FOLLOW_UP
                elif intent == EnhancedIntent.CLARIFICATION:
                    mapped_intent = QueryIntent.CLARIFICATION
                
                enhanced_query = await _enhance_query_with_context_v2(
                    request.query, 
                    chat_history,
                    mapped_intent,
                    conversation_summary
                )
                logger.info(f"Enhanced query from '{request.query}' to '{enhanced_query}'")
        
        # Import the drug file matcher
        from utils.drug_file_matcher import DrugFileMatcher
        
        # Extract relevant file names using LLM for document-based query
        doc_file_name_filter = None
        try:
            relevant_files = await DrugFileMatcher.extract_relevant_files_for_query(
                enhanced_query,
                source_file_ids=request.source_file_ids,
                db=db
            )
            
            if relevant_files:
                logger.info(f"Document query: Applying file filter for {len(relevant_files)} files: {relevant_files[:3]}...")
                # For document-based queries, we'll pass this to the query service
                doc_file_name_filter = relevant_files
            else:
                logger.info("Document query: No specific file filter applied, using all provided documents")
        except Exception as e:
            logger.error(f"Error in document file filtering: {e}")
            # Continue without filter on error
        
        # Instead of using query_fda_documents, implement the same advanced logic as collection query
        
        # Get document file names for Qdrant filtering
        from database.database import SourceFiles, collection_document_association, Collection
        source_docs = db.query(SourceFiles).filter(
            SourceFiles.id.in_(request.source_file_ids)
        ).all()
        
        if not source_docs:
            raise HTTPException(status_code=404, detail="Documents not found")
        
        # Build file name filter for Qdrant
        source_file_names = [doc.file_name for doc in source_docs if doc.file_name]
        logger.info(f"Source document file names: {source_file_names}")
        
        # If we have LLM-filtered files, use those instead
        if doc_file_name_filter:
            file_name_filter = {"file_name": {"$in": doc_file_name_filter}}
            logger.info(f"Using LLM-filtered files: {doc_file_name_filter}")
        else:
            file_name_filter = {"file_name": {"$in": source_file_names}}
            logger.info(f"Using all source files: {source_file_names}")
        
        # Find which collection these documents belong to
        # Query to find the collection that contains these documents
        collection_result = db.query(Collection).join(
            collection_document_association,
            Collection.id == collection_document_association.c.collection_id
        ).filter(
            collection_document_association.c.document_id.in_(request.source_file_ids)
        ).first()
        
        if collection_result and collection_result.vector_db_collection_name:
            collection_name = collection_result.vector_db_collection_name
            logger.info(f"Found collection for documents: {collection_name}")
        else:
            # Fallback to main collection if documents aren't in a specific collection
            collection_name = "fda_documents"
            logger.info(f"No specific collection found, using main collection: {collection_name}")
        
        logger.info(f"Using collection: {collection_name} with filter: {file_name_filter}")
        
        # Initialize Qdrant and other utilities
        from utils.qdrant_util import QdrantUtil
        vector_db_util = QdrantUtil.get_instance(use_persistent_client=True)
        
        # Import feature flags
        from utils.feature_flags import FeatureFlags
        
        # Initialize semantic cache
        from utils.semantic_cache import SemanticCache
        semantic_cache = SemanticCache(
            chroma_client=vector_db_util.chroma_client,
            similarity_threshold=FeatureFlags.get("SEMANTIC_CACHE_SIMILARITY_THRESHOLD", 0.95),
            ttl_seconds=FeatureFlags.get("SEMANTIC_CACHE_TTL_SECONDS", 3600)
        )
        
        # Check cache first
        # Note: semantic cache doesn't have source_file_ids parameter, so we use metadata
        cached_result = await semantic_cache.get(
            query=enhanced_query,
            context=chat_history
        )
        
        if cached_result:
            logger.info(f"Cache hit! Returning cached response")
            
            # Get enhanced sources from cache metadata if available
            cache_metadata = cached_result.get('cache_metadata', {})
            enhanced_sources = cache_metadata.get('enhanced_sources', [])
            
            # If not in cache_metadata, check the main result
            if not enhanced_sources and 'enhanced_sources' in cached_result:
                enhanced_sources = cached_result['enhanced_sources']
            
            result = {
                "user_query": request.query,
                "response": cached_result.get('html_response', cached_result['response']),
                "cited_response": cached_result.get('html_response', cached_result['response']),
                "query_type": "documents",
                "source_file_ids": request.source_file_ids,
                "source_documents": enhanced_sources or cached_result.get('documents_used', []),
                "content_type": "html"
            }
        else:
            # Continue with document retrieval
            logger.info("Cache miss, proceeding with document retrieval")
            
            # Use single enhanced query to retrieve documents
            logger.info("Using enhanced single query retrieval")
            source_docs = await vector_db_util.retrieve_single_query(
                query=enhanced_query,
                collection_name=collection_name,
                n_results=30,  # Get 30 results
                metadata_filter=file_name_filter  # Apply file filter
            )
            logger.info(f"Retrieved {len(source_docs)} candidate documents")
            
            # Debug: Check what documents we got
            if source_docs:
                logger.info(f"Sample document metadata: {source_docs[0].metadata if source_docs else 'No docs'}")
                unique_files = set(doc.metadata.get('file_name', 'Unknown') for doc in source_docs)
                logger.info(f"Unique files in retrieval results: {unique_files}")
            
            # Apply relevance grading to get top documents
            if source_docs:
                logger.info("Applying relevance grading to select top documents")
                source_docs = _grade_documents_by_relevance(enhanced_query, source_docs)
                logger.info(f"Relevance grading selected {len(source_docs)} final documents")
            else:
                # No documents found
                source_docs = []
            
            # Check if we found any documents
            if not source_docs:
                logger.warning(f"No relevant documents found for query: {enhanced_query}")
                logger.warning(f"File filter used: {file_name_filter}")
                logger.warning(f"Collection searched: {collection_name}")
                
                # Provide error message
                error_msg = f"No relevant information found for '{request.query}' in the searched documents: {', '.join(source_file_names)}"
                
                result = {
                    "user_query": request.query,
                    "response": error_msg,
                    "cited_response": error_msg,
                    "query_type": "documents",
                    "source_file_ids": request.source_file_ids,
                    "source_documents": [],
                    "content_type": "html"
                }
            else:
                # Generate response with enhanced prompt (same as collection query)
                # Map intent for generation prompt
                intent_str = intent.value if hasattr(intent, 'value') else str(intent)
                prompt = vector_db_util._create_enhanced_generation_prompt(
                    query=enhanced_query,
                    documents=source_docs,
                    conversation_summary=conversation_summary,
                    intent=intent_str,
                    original_query=request.query
                )
                
                # Get response from LLM
                llm = get_llm()
                llm_response_obj = await llm.ainvoke(prompt)
                llm_response = llm_response_obj.content if hasattr(llm_response_obj, 'content') else str(llm_response_obj)
                
                # Ensure response is in English
                llm_response = await _ensure_english_response_with_llm(llm_response, request.query)
                
                
                # Skip fact-checking - removed from pipeline
                cited_response = llm_response
                enhanced_sources = []
                used_indices = []
                
                response = llm_response  # Keep original for compatibility
                
                # Convert to HTML
                html_response = await _convert_response_to_html_unified(response, request.query)
                html_cited = await _convert_response_to_html_unified(cited_response, request.query)
                
                # Cache the result with enhanced sources
                cache_enhanced_sources = []
                if enhanced_sources:
                    # Convert enhanced sources to dict for caching
                    cache_enhanced_sources = [
                        {
                            'id': src.id,
                            'filename': src.filename,
                            'snippet': src.snippet,
                            'citation_number': src.citation_number,
                            'relevance_score': src.relevance_score,
                            'page_number': src.page_number,
                            'drug_name': src.drug_name,
                            'used_in_response': src.used_in_response,
                            'metadata': src.metadata
                        }
                        for src in enhanced_sources[:20]  # Limit to top 20
                    ]
                
                # Store metadata including source_file_ids
                cache_metadata = {
                    'source_file_ids': request.source_file_ids,
                    'enhanced_sources': cache_enhanced_sources
                }
                
                await semantic_cache.set(
                    query=enhanced_query,
                    response=response,
                    html_response=html_response,
                    context=chat_history,
                    documents_used=cache_enhanced_sources if enhanced_sources else None,
                    metadata=cache_metadata
                )
                
                # Create properly structured source documents for fallback
                source_docs_fallback = []
                for i, doc in enumerate(source_docs[:20], 1):
                    source_docs_fallback.append({
                        'id': doc.metadata.get('id', f'doc_{i}'),
                        'filename': doc.metadata.get('source_file_name', doc.metadata.get('source', doc.metadata.get('file_name', 'Unknown'))),
                        'snippet': doc.metadata.get('original_content', '')[:300] + '...' if len(doc.metadata.get('original_content', '')) > 300 else doc.metadata.get('original_content', ''),
                        'citation_number': i,
                        'relevance_score': doc.metadata.get('relevance_score', 0.0),
                        'page_number': doc.metadata.get('page_number'),
                        'drug_name': doc.metadata.get('drug_name'),
                        'used_in_response': True,
                        'metadata': {
                            'original_content': doc.metadata.get('original_content'),
                            'file_url': doc.metadata.get('file_url', '')
                        }
                    })
                
                # Calculate confidence scores
                confidence_scores = {
                    "retrieval_confidence": calculate_retrieval_confidence(source_docs),
                    "citation_coverage": calculate_citation_coverage(cited_response, response),
                    "intent_confidence": confidence
                }
                
                # Check if response indicates no relevant information
                is_no_info_response = _is_no_info_response(llm_response)
                
                result = {
                    "user_query": request.query,
                    "response": html_response,
                    "cited_response": html_cited,
                    "query_type": "documents",
                    "source_file_ids": request.source_file_ids,
                    "source_documents": [] if is_no_info_response else (enhanced_sources if enhanced_sources else source_docs_fallback),
                    "content_type": "html",
                    "intent": intent.value if hasattr(intent, 'value') else str(intent),
                    "conversation_summary": conversation_summary,
                    "enhanced_query": enhanced_query,
                    "confidence_scores": confidence_scores
                }
        
        # Convert response to HTML for frontend rendering
        if result.get("response"):
            logger.info(f"Converting response to HTML for query-multiple-v2 endpoint")
            html_response = await _convert_response_to_html_unified(result["response"], request.query)
            result["response"] = html_response
            result["content_type"] = "html"  # Indicate HTML content
        
        # Update chat response with HTML-converted content
        FDAChatManagementService.update_chat_response(
            chat_id=chat_id,
            response_details=result,
            db=db
        )
        
        result["chat_id"] = chat_id
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query-multiple-v2 endpoint: {str(e)}")
        
        # Determine user-friendly error message based on error type
        if "embedding" in str(e).lower() or "404" in str(e):
            error_message = "I'm currently experiencing issues with the search system. Please try again in a few moments."
        elif "api" in str(e).lower() or "key" in str(e).lower():
            error_message = "I'm having trouble connecting to the AI service. Please try again later."
        elif "timeout" in str(e).lower():
            error_message = "The request took too long to process. Please try with a shorter query or try again later."
        elif "database" in str(e).lower() or "connection" in str(e).lower():
            error_message = "I'm experiencing database connectivity issues. Please try again later."
        else:
            error_message = "I'm experiencing a technical issue right now. Please try again later or contact support if this continues."
        
        raise HTTPException(status_code=500, detail=error_message)

@router.get("/history/{user_id}")
async def get_chat_history(
    user_id: int,
    docx_chat_filter: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get chat history for a user with optional docXChat filtering."""
    try:
        history = FDAChatManagementService.retrieve_chat_history(user_id, db, docx_chat_filter)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{user_id}")
async def get_chat_sessions(
    user_id: int,
    docx_chat_filter: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get chat sessions grouped by session_id for a user with optional docXChat filtering."""
    try:
        sessions = FDAChatManagementService.retrieve_chat_sessions(user_id, db, docx_chat_filter)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session_details(
    session_id: str,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Get all chat details for a session."""
    try:
        details = FDAChatManagementService.retrieve_chat_details_by_session(
            session_id=session_id,
            user_id=user_id,
            db=db
        )
        
        # Transform the response to match frontend expectations
        chats = []
        for detail in details:
            # Extract response from response_details
            response = detail.get('response_details', {}).get('response', '')
            source_documents = detail.get('response_details', {}).get('source_documents', [])
            source_info = detail.get('response_details', {}).get('source_info', None)
            
            chats.append({
                'id': detail['chat_id'],
                'query': detail['user_query'],
                'response': response,
                'source_documents': source_documents,
                'source_info': source_info,
                'source_file_id': detail.get('request_details', {}).get('source_file_id'),
                'source_file_ids': detail.get('request_details', {}).get('source_file_ids'),
                'created_at': detail['created_at'],
                'is_favorite': detail['is_favorite']
            })
        
        return {
            'session_id': session_id,
            'chats': chats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/favorite")
async def mark_as_favorite(
    request: FavoriteRequest,
    db: Session = Depends(get_db)
):
    """Mark a chat as favorite."""
    try:
        success = FDAChatManagementService.mark_chat_as_favorite(
            chat_id=request.chat_id,
            user_id=request.user_id,
            db=db
        )
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/favorite")
async def remove_from_favorites(
    request: FavoriteRequest,
    db: Session = Depends(get_db)
):
    """Remove a chat from favorites."""
    try:
        success = FDAChatManagementService.remove_chat_from_favorites(
            chat_id=request.chat_id,
            user_id=request.user_id,
            db=db
        )
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/favorites/{user_id}")
async def get_favorite_chats(
    user_id: int,
    docx_chat_filter: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get favorite chats for a user with optional docXChat filtering."""
    try:
        favorites = FDAChatManagementService.get_favorite_chats(user_id, db, docx_chat_filter)
        return favorites
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/{chat_id}")
async def delete_chat(
    chat_id: int,
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """Delete a chat."""
    try:
        success = FDAChatManagementService.delete_chat(
            chat_id=chat_id,
            user_id=user_id,
            db=db
        )
        if not success:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters")
async def get_filter_options(db: Session = Depends(get_db)):
    """Get available filter options."""
    try:
        filters = FDAChatManagementService.get_filter_options(db)
        return filters
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/drug-names")
async def get_unique_drug_names(
    collection_id: Optional[int] = Query(None, description="Filter drug names by collection"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all unique drug names from SourceFiles for filter dropdown."""
    try:
        drug_names = FDAChatManagementService.get_unique_drug_names(db, collection_id)
        return {
            "success": True,
            "drug_names": drug_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggestions/{user_id}")
async def get_chat_suggestions(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get chat suggestions for a user."""
    try:
        suggestions = FDAChatManagementService.get_chat_suggestions(user_id, db)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/new-session")
async def create_new_session():
    """Create a new chat session."""
    return {"session_id": str(uuid.uuid4())}

@router.post("/suggestions")
async def generate_suggestions(
    request: SuggestionsRequest,
    db: Session = Depends(get_db)
):
    """Generate context-aware suggestions based on chat history."""
    try:
        chat_history = request.chat_history
        selected_drugs = request.selected_drugs
        last_response = request.last_response
        
        # Validate input
        if not isinstance(chat_history, list):
            chat_history = []
        if not isinstance(selected_drugs, list):
            selected_drugs = []
        
        # Normalize selected_drugs format
        # Handle both string array and dict array formats
        normalized_drugs = []
        for drug in selected_drugs:
            if isinstance(drug, str):
                # If it's a string, convert to dict format
                normalized_drugs.append({"drug_name": drug})
            elif isinstance(drug, dict) and "drug_name" in drug:
                # If it's already a dict with drug_name, use as is
                normalized_drugs.append(drug)
            # Skip invalid formats
        
        selected_drugs = normalized_drugs
        
        logger.info(f"Generating suggestions for chat history length: {len(chat_history)}, drugs: {len(selected_drugs)}")
        
        suggestions = []
        suggestion_type = "rule-based"
        
        try:
            # Use LLM-based suggestions if we have chat history
            if chat_history and len(chat_history) > 1:
                logger.info("Attempting LLM-based suggestions")
                suggestions = FDAChatManagementService.generate_llm_suggestions(
                    chat_history=chat_history,
                    selected_drugs=selected_drugs,
                    db=db
                )
                if suggestions:
                    suggestion_type = "contextual"
        except Exception as llm_error:
            logger.warning(f"LLM suggestions failed: {llm_error}")
        
        # Fallback to rule-based suggestions if LLM failed or no suggestions generated
        if not suggestions:
            logger.info("Using rule-based suggestions")
            try:
                suggestions = FDAChatManagementService.generate_smart_suggestions(
                    chat_history=chat_history,
                    selected_drugs=selected_drugs,
                    last_response=last_response,
                    db=db
                )
            except Exception as rule_error:
                logger.error(f"Rule-based suggestions also failed: {rule_error}")
                # Ultimate fallback - provide default suggestions
                suggestions = [
                    "What are the main side effects?",
                    "What is the recommended dosage?",
                    "What are the contraindications?",
                    "What are the drug interactions?",
                    "Tell me more about this drug"
                ]
        
        # Ensure we always have suggestions
        if not suggestions:
            suggestions = [
                "What are the main side effects?",
                "What is the recommended dosage?",
                "What are the contraindications?",
                "What are the drug interactions?",
                "Tell me more about this drug"
            ]
        
        logger.info(f"Returning {len(suggestions)} suggestions of type: {suggestion_type}")
        return {
            "suggestions": suggestions,
            "type": suggestion_type
        }
        
    except Exception as e:
        logger.error(f"Suggestions endpoint error: {e}")
        # Even if everything fails, return basic suggestions
        return {
            "suggestions": [
                "What are the main side effects?",
                "What is the recommended dosage?",
                "What are the contraindications?",
                "What are the drug interactions?",
                "Tell me more about this drug"
            ],
            "type": "fallback"
        }

@router.post("/search/advanced")
async def advanced_search(
    request: AdvancedSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Advanced search with document grading.
    This endpoint performs a more thorough search by grading documents for relevance.
    Best used when you want high-quality results without specific filters.
    """
    try:
        # Perform advanced search first
        results = FDAChatManagementService.search_with_grading(
            query=request.query,
            collection_name="fda_documents",
            n_results=30,
            db=db
        )
        
        # Only save to chat history if user_id and session_id are provided
        if request.user_id and request.session_id:
            # Save chat request
            request_details = {
                "search_type": "advanced",
                "query": request.query
            }
            
            chat_id = FDAChatManagementService.save_chat_request(
                user_id=request.user_id,
                user_query=f"Advanced search: {request.query}",
                session_id=request.session_id,
                request_details=request_details,
                db=db
            )
            
            # Update chat with response details
            response_details = {
                "results_count": len(results),
                "results": results[:10] if results else []  # Store first 10 results
            }
            
            FDAChatManagementService.update_chat_response(
                chat_id=chat_id,
                response_details=response_details,
                db=db
            )
        
        return jsonable_encoder(results)
    except Exception as e:
        logger.error(f"Error in advanced search endpoint: {str(e)}")
        
        # Determine user-friendly error message based on error type
        if "embedding" in str(e).lower() or "404" in str(e):
            error_message = "I'm currently experiencing issues with the search system. Please try again in a few moments."
        elif "api" in str(e).lower() or "key" in str(e).lower():
            error_message = "I'm having trouble connecting to the AI service. Please try again later."
        elif "timeout" in str(e).lower():
            error_message = "The request took too long to process. Please try with a shorter query or try again later."
        elif "database" in str(e).lower() or "connection" in str(e).lower():
            error_message = "I'm experiencing database connectivity issues. Please try again later."
        else:
            error_message = "I'm experiencing a technical issue right now. Please try again later or contact support if this continues."
        
        raise HTTPException(status_code=500, detail=error_message)

# New unified chat endpoint
class UnifiedChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None

class UnifiedChatResponse(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    timestamp: str
    chat_id: int
    search_results: Optional[List[Dict[str, Any]]] = None
    used_documents: bool = False
    source_info: Dict[str, Any] = {}

@router.post("/unified", response_model=UnifiedChatResponse)
async def unified_chat(
    request: UnifiedChatRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enhanced unified chat endpoint with conversational context:
    1. Get recent 5 request/response pairs for conversation context
    2. Use LLM to enhance current query with conversation context
    3. Search vector DB with enhanced query, grade results, keep relevant ones
    4. If matches found: use documents with conversation context for response
    5. If no matches: use general LLM with conversation context
    6. Save request/response and format as HTML for frontend
    """
    try:
        # Setup
        session_id = request.session_id or str(uuid.uuid4())
        user_id = request.user_id or current_user.id
        
        logger.info("="*80)
        logger.info("🚀 UNIFIED CHAT ENDPOINT - ENHANCED WITH CONVERSATION CONTEXT")
        logger.info(f"📋 User ID: {user_id}, Session ID: {session_id}")
        logger.info(f"📝 Original Query: '{request.message}'")
        
        # STEP 1: Get recent 3 chat history for conversation context (prioritizing recency)
        chat_history = _get_recent_chat_history(session_id, user_id, db, limit=3)
        logger.info(f"📜 Retrieved Chat History: {len(chat_history)} conversation pairs (last 3 with recency priority)")
        
        if chat_history:
            logger.info("📜 CHAT HISTORY DETAILS (ordered by recency):")
            # Show in reverse order for recency priority (most recent first)
            for i, (user_msg, assistant_msg) in enumerate(reversed(chat_history), 1):
                priority_label = ["MOST RECENT", "RECENT", "EARLIER"][i-1] if i <= 3 else "EARLIER"
                logger.info(f"   {i}. [{priority_label}] User: '{user_msg[:60]}...'")
                logger.info(f"      [{priority_label}] Assistant: '{assistant_msg[:60]}...'")
        else:
            logger.info("📜 No previous chat history found - first message in session")
        
        # STEP 2: Use LLM to enhance query with conversation context
        enhanced_query = await _enhance_query_with_context(request.message, chat_history)
        logger.info(f"🔍 Enhanced Query: '{enhanced_query}'")
        logger.info(f"🔄 Query Enhancement: {'Applied' if enhanced_query != request.message else 'None (first message or no relevant context)'}")
        
        # STEP 3: Search vector DB with enhanced query
        logger.info("🔍 VECTOR DATABASE SEARCH:")
        logger.info(f"   Search Query: '{enhanced_query}'")
        logger.info(f"   Target Results: 30")
        logger.info(f"   Relevance Threshold: 70")
        
        search_results = FDAChatManagementService.search_with_grading(
            query=enhanced_query,
            collection_name="fda_documents",
            n_results=30,
            db=db
        )
        
        # Keep only relevant results (score > 70)
        relevant_docs = [doc for doc in search_results if doc.get("relevance_score", 0) > 70]
        
        logger.info(f"📊 SEARCH RESULTS:")
        logger.info(f"   Total Results: {len(search_results)}")
        logger.info(f"   Relevant Results (>70): {len(relevant_docs)}")
        
        if relevant_docs:
            logger.info("📄 TOP RELEVANT DOCUMENTS:")
            for i, doc in enumerate(relevant_docs[:3], 1):
                logger.info(f"   {i}. {doc.get('drug_name', 'Unknown')} - Score: {doc.get('relevance_score', 0):.1f}%")
                logger.info(f"      File: {doc.get('file_name', 'Unknown')}")
        
        # STEP 4: Generate response based on relevance
        if relevant_docs:
            # CASE 1: Document-based response with conversation history
            logger.info("🎯 USING DOCUMENT-BASED RESPONSE")
            logger.info(f"   Selected Documents: {len(relevant_docs[:3])}")
            logger.info(f"   Conversation Context: {len(chat_history)} pairs")
            
            # Get top 3 most relevant documents
            top_docs = relevant_docs[:3]
            source_file_ids = [doc["source_file_id"] for doc in top_docs]
            
            # Generate response using documents with enhanced query (already contains context)
            doc_response = await FDAChatManagementService.query_fda_documents(
                source_file_ids=source_file_ids,
                query_string=enhanced_query,  # Use enhanced query which already contains conversation context
                session_id=session_id,
                user_id=user_id,
                db=db
            )
            
            if doc_response and doc_response.get("response"):
                logger.info("✅ Document-based response generated successfully")
                response_content = await _convert_response_to_html_unified(doc_response["response"])
                used_documents = True
                search_results = top_docs
                source_info = {
                    "type": "document_based",
                    "source": "Knowledge Base",
                    "documents_used": len(top_docs)
                }
            else:
                # Fallback to LLM if document query fails
                logger.warning("⚠️ Document query failed, falling back to LLM")
                response_content = await _generate_enhanced_llm_response(enhanced_query)
                used_documents = False
                search_results = []
                from config.settings import settings
                source_info = {"type": "llm_based", "source": f"Gemini ({settings.LLM_GEMINI_MODEL})", "model": settings.LLM_GEMINI_MODEL}
        else:
            # CASE 2: General LLM response with conversation history
            logger.info("🧠 USING GENERAL LLM RESPONSE")
            logger.info(f"   Reason: No relevant documents found (threshold: 70)")
            logger.info(f"   Using Enhanced Query: '{enhanced_query}' (context already included)")
            
            response_content = await _generate_enhanced_llm_response(enhanced_query)
            used_documents = False
            search_results = []
            from config.settings import settings
            source_info = {"type": "llm_based", "source": f"Gemini ({settings.LLM_GEMINI_MODEL})", "model": settings.LLM_GEMINI_MODEL}
        
        # STEP 5: Save request and response for future conversation support
        logger.info("💾 SAVING CHAT TO DATABASE:")
        
        request_details = {
            "search_type": "unified",
            "original_query": request.message,
            "enhanced_query": enhanced_query,
            "session_id": session_id,
            "used_documents": used_documents,
            "documents_found": len(relevant_docs),
            "chat_history_used": len(chat_history)
        }
        
        chat_id = FDAChatManagementService.save_chat_request(
            user_id=user_id,
            user_query=request.message,
            session_id=session_id,
            request_details=request_details,
            db=db
        )
        
        logger.info(f"   Chat ID: {chat_id}")
        logger.info(f"   Session: {session_id}")
        logger.info(f"   Used Documents: {used_documents}")
        
        # Generate response metadata
        response_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Save the response to database
        response_details = {
            "user_query": request.message,
            "enhanced_query": enhanced_query,
            "response": response_content,
            "search_results": search_results if used_documents else [],
            "used_documents": used_documents,
            "source_info": source_info,
            "response_id": response_id,
            "timestamp": timestamp,
            "content_type": "html",
            "conversation_context_used": len(chat_history)
        }
        
        FDAChatManagementService.update_chat_response(
            chat_id=chat_id,
            response_details=response_details,
            db=db
        )
        
        logger.info("✅ RESPONSE COMPLETED:")
        logger.info(f"   Response ID: {response_id}")
        logger.info(f"   Content Length: {len(response_content)} characters")
        logger.info(f"   Source Type: {source_info['type']}")
        logger.info(f"   Source: {source_info['source']}")
        logger.info("="*80)
        
        # STEP 6: Return response with source information
        return UnifiedChatResponse(
            id=response_id,
            content=response_content,
            role="assistant",
            timestamp=timestamp,
            chat_id=chat_id,
            search_results=search_results if used_documents else None,
            used_documents=used_documents,
            source_info=source_info
        )
        
    except Exception as e:
        logger.error(f"Error in unified chat endpoint: {str(e)}")
        
        # Provide user-friendly error messages instead of raising HTTPException
        try:
            # Generate a graceful error response that matches the expected format
            error_id = str(uuid.uuid4())
            error_timestamp = datetime.now().isoformat()
            
            # Determine user-friendly error message based on error type
            if "embedding" in str(e).lower() or "404" in str(e):
                error_message = "I'm currently experiencing issues with the search system. Please try again in a few moments."
            elif "api" in str(e).lower() or "key" in str(e).lower():
                error_message = "I'm having trouble connecting to the AI service. Please try again later."
            elif "timeout" in str(e).lower():
                error_message = "The request took too long to process. Please try with a shorter query or try again later."
            else:
                error_message = "I'm experiencing a technical issue right now. Please try again later or contact support if this continues."
            
            # Create a proper response even during errors
            return UnifiedChatResponse(
                id=error_id,
                content=error_message,
                role="assistant",
                timestamp=error_timestamp,
                chat_id=0,  # Use 0 to indicate no chat was saved
                search_results=None,
                used_documents=False,
                source_info={"type": "error", "source": "System"}
            )
        except Exception as response_error:
            logger.error(f"Failed to create error response: {str(response_error)}")
            raise HTTPException(status_code=500, detail="I'm experiencing technical difficulties. Please try again later.")

def _get_all_chat_history_with_timestamps(
    session_id: str, 
    user_id: int, 
    db: Session
) -> List[Tuple[str, str, float]]:
    """Get all chat history with timestamps for dynamic context selection"""
    try:
        result = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        
        chat_history = []
        for chat in result:
            if chat.user_query and chat.response_details:
                try:
                    response_details = json.loads(chat.response_details)
                    response_content = response_details.get("response", "")
                    
                    # Clean HTML tags for context
                    import re
                    clean_response = re.sub(r'<[^>]+>', '', response_content)
                    
                    # Get timestamp as float (seconds since epoch)
                    timestamp = chat.created_at.timestamp()
                    
                    chat_history.append((
                        chat.user_query,
                        clean_response[:500],  # Limit response length
                        timestamp
                    ))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse response_details for chat {chat.id}")
                    continue
        
        logger.info(f"Retrieved {len(chat_history)} total conversations with timestamps")
        return chat_history
        
    except Exception as e:
        logger.error(f"Error retrieving chat history with timestamps: {str(e)}")
        return []

def _get_recent_chat_history(session_id: str, user_id: int, db: Session, limit: int = 3) -> List[Tuple[str, str]]:
    """Get recent chat history using the working logic from _get_general_chat_history"""
    try:
        # Get recent chat history from the session - same logic as query endpoint
        result = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            )
            .order_by(ChatHistory.created_at.asc())  # ASC for chronological order
            .all()  # Get all records, then filter the most recent
        )
        
        chat_pairs = []
        for chat in result:
            if chat.user_query and chat.response_details:
                try:
                    response_details = json.loads(chat.response_details)
                    response_content = response_details.get("response", "")
                    
                    # Add as (query, response) pair for conversation context
                    if response_content:
                        chat_pairs.append((chat.user_query, response_content))
                        
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Error parsing response_details for chat {chat.id}: {str(e)}")
                    continue
        
        # Return only the specified number of most recent conversation pairs
        return chat_pairs[-limit:] if len(chat_pairs) > limit else chat_pairs
        
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return []

async def _generate_conversation_summary(
    chat_history: List[Tuple[str, str]],
    max_length: int = 200
) -> str:
    """
    Generate a concise summary of the conversation context
    
    Args:
        chat_history: List of (user_query, assistant_response) tuples
        max_length: Maximum length of summary in words
        
    Returns:
        Concise conversation summary
    """
    if not chat_history:
        return ""
    
    llm = get_llm()
    
    # Format history for summary
    history_text = ""
    for i, (user_q, assistant_r) in enumerate(chat_history[-3:], 1):
        # Limit response length for summary
        response_preview = assistant_r[:300] if len(assistant_r) > 300 else assistant_r
        history_text += f"Exchange {i}:\nUser: {user_q}\nAssistant: {response_preview}...\n\n"
    
    prompt = f"""Create a concise summary of this pharmaceutical conversation in 1-2 sentences.
Focus on the main topics, drugs discussed, and key questions asked.

Conversation:
{history_text}

Summary (max {max_length} words):"""
    
    try:
        response = await llm.ainvoke(prompt)
        summary = response.content.strip()
        
        # Ensure summary isn't too long
        words = summary.split()
        if len(words) > max_length:
            summary = ' '.join(words[:max_length]) + "..."
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating conversation summary: {e}")
        return ""

async def _enhance_query_with_context_v2(
    current_query: str,
    chat_history: List[Tuple[str, str]],
    intent: 'QueryIntent',  # QueryIntent from utils.intent_classifier
    conversation_summary: str
) -> str:
    """
    Enhanced query construction using summary and intent
    
    Args:
        current_query: The user's current query
        chat_history: Recent conversation history
        intent: Classified query intent
        conversation_summary: Concise summary of conversation
        
    Returns:
        Enhanced query optimized for retrieval
    """
    from utils.intent_classifier import QueryIntent
    
    llm = get_llm()
    
    # Build intent-specific instructions
    intent_instructions = {
        QueryIntent.NEW_TOPIC: "Focus ONLY on the new query. DO NOT replace drug names, medical terms, or specific entities from the current query with those from previous conversations. The user is asking about something NEW.",
        QueryIntent.FOLLOW_UP: "Strongly incorporate the previous topic and expand the query with context.",
        QueryIntent.CLARIFICATION: "Reference the specific aspect from the previous response that needs clarification.",
        QueryIntent.OFF_TOPIC: "Treat as a new query but maintain pharmaceutical/medical focus if possible. DO NOT replace entities from the current query."
    }
    
    instruction = intent_instructions.get(intent, intent_instructions[QueryIntent.NEW_TOPIC])
    
    # Build the enhancement prompt
    prompt = f"""Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is.

CONVERSATION SUMMARY: {conversation_summary if conversation_summary else "No previous conversation"}

USER INTENT: {intent.value}

CURRENT QUERY: {current_query}

RULES:
1. If the query references "it", "this", "that", etc., replace with the specific entity from the conversation
2. If the query is already clear and standalone, return it as is
3. Do not add extra information or keywords
4. Do not answer the question
5. Keep the reformulated query concise and natural

EXAMPLES:
- Current: "What are its side effects?" + Context: discussing Aspirin → Output: "What are the side effects of Aspirin?"
- Current: "Tell me about Lipitor" + No relevant context → Output: "Tell me about Lipitor"
- Current: "How does it work?" + Context: discussing Metformin → Output: "How does Metformin work?"

Reformulated Query:"""

    try:
        response = await llm.ainvoke(prompt)
        enhanced = response.content.strip()
        
        # Validate enhancement
        if len(enhanced.split()) > 50:
            # If reformulation is too long, use original
            enhanced = current_query
        
        logger.info(f"Query reformulated from '{current_query}' to '{enhanced}' (intent: {intent.value})")
        return enhanced
        
    except Exception as e:
        logger.error(f"Error enhancing query: {e}")
        return current_query  # Fallback to original

async def _enhance_query_with_context_v3(
    current_query: str    
) -> str:
    """
    Enhanced query construction using summary and intent
    
    Args:
        current_query: The user's current query
        chat_history: Recent conversation history
        intent: Classified query intent
        conversation_summary: Concise summary of conversation
        
    Returns:
        Enhanced query optimized for retrieval
    """
    from utils.intent_classifier import QueryIntent
    
    llm = get_llm()   
    
    
    # Build the enhancement prompt
    prompt = f"""You are an expert in semantic search and information retrieval.  
            Your task is to take a raw user query and expand it into a more detailed, context-aware query that will produce the best results when used with vector similarity search.  

            Guidelines:
            1. Preserve the original intent of the query.  
            2. Add relevant domain-specific terms, synonyms, and related keywords.  
            3. Convert incomplete, vague, or shorthand queries into clear, full sentences.  
            4. If the query is a question, rephrase it into a neutral search-style statement.  
            5. Avoid hallucinations – do not add details that were not implied by the query.  
            6. Output the enhanced query only, nothing else.  

            Example Transformations:
            - Input: "side effects"  
            Output: "Information about the adverse effects, safety profile, and common side effects of the drug."  

            - Input: "FDA approval process"  
            Output: "Detailed information on the FDA regulatory approval process for drugs, including phases, requirements, and guidelines."  

            - Input: "compare ibrutinib and acalabrutinib"  
            Output: "Comparison between ibrutinib and acalabrutinib including mechanism of action, clinical efficacy, safety profile, and FDA-approved indications."  

            Now, enhance the following user query for optimized vector similarity search:  
            [USER QUERY]: {current_query}
            """

    try:
        response = await llm.ainvoke(prompt)
        enhanced = response.content.strip()
        
        # Validate enhancement
        if len(enhanced.split()) > 150:
            # If reformulation is too long, use original
            enhanced = current_query
        
        logger.info(f"Query reformulated from '{current_query}' to '{enhanced}'")
        return enhanced
        
    except Exception as e:
        logger.error(f"Error enhancing query: {e}")
        return current_query  # Fallback to original

async def _enhance_query_with_context(
    current_query: str,
    chat_history: List[Tuple[str, str]]
) -> str:
    """Use LLM to enhance current query with conversation context for better vector search"""
    if not chat_history:
        # No conversation history, return original query
        return current_query
    
    try:
        llm = get_llm()
        
        # Build conversation context with recency priority (most recent first)
        conversation_context = ""
        
        # Process in reverse order so most recent conversation appears first
        for i, (user_msg, assistant_msg) in enumerate(reversed(chat_history)):
            priority_label = ["MOST RECENT", "RECENT", "EARLIER"][i] if i < 3 else "EARLIER"
            conversation_context += f"[{priority_label}] User: {user_msg}\n[{priority_label}] Assistant: {assistant_msg[:150]}...\n\n"
        
        enhancement_prompt = f"""You are helping enhance a search query by adding relevant context from conversation history.

CONVERSATION HISTORY (prioritized by recency):
{conversation_context}

CURRENT USER QUERY: {current_query}

TASK: Create an enhanced search query that combines the current query with relevant context from the conversation history. The enhanced query should be optimal for searching pharmaceutical documents.

PRIORITY RULES:
1. PRIORITIZE MOST RECENT context over older conversations
2. If the current query refers to "it", "this drug", "that medication", etc., replace with the specific drug name from the MOST RECENT conversation
3. If the current query is a follow-up question, use context from the MOST RECENT relevant conversation
4. Only use EARLIER context if the MOST RECENT context is not relevant
5. If the current query is completely new topic, keep it mostly unchanged
6. Keep the enhanced query concise and focused on pharmaceutical/medical terms
7. The enhanced query should be optimized for vector database search

EXAMPLES:
- Current: "What are the side effects?" + MOST RECENT: "Keytruda" → Enhanced: "Keytruda pembrolizumab side effects adverse reactions"
- Current: "How does it work?" + MOST RECENT: "Lisinopril" → Enhanced: "Lisinopril mechanism of action how does it work"
- Current: "What about dosage?" + MOST RECENT: "paracetamol" → Enhanced: "paracetamol acetaminophen dosage information"

Enhanced Query (return only the enhanced query, no explanations):"""

        response = llm.invoke(enhancement_prompt)
        enhanced_query = response.content if hasattr(response, 'content') else str(response)
        enhanced_query = enhanced_query.strip()
        
        # If enhancement seems invalid or too long, fallback to original
        if len(enhanced_query) > 200 or not enhanced_query:
            return current_query
            
        return enhanced_query
        
    except Exception as e:
        logger.error(f"Error enhancing query with context: {str(e)}")
        return current_query

async def _generate_enhanced_llm_response(enhanced_query: str) -> str:
    """Generate LLM response using enhanced query (context already included)"""
    try:
        llm = get_llm()
        
        # Simple prompt since enhanced_query already contains conversation context
        prompt = f"""You are a pharmaceutical AI assistant specializing in FDA-approved drugs and medical information.

RESPONSE STYLE - CRITICAL RULES:
- NEVER use phrases like "I can help you", "I can provide information", "Let me help", "I'll provide", "I can assist"
- NEVER start with "Okay", "Sure", "Certainly", "Of course", "I'd be happy to"
- START IMMEDIATELY with facts and details
- Use direct statements: "Here are the details about...", "The following covers...", "Key information includes..."
- Be authoritative and factual from the first word
- NO conversational pleasantries or helper language

GUIDELINES:
- Provide accurate, evidence-based pharmaceutical information
- Focus on FDA-approved drugs, clinical data, and medical guidelines
- Use professional, clear language suitable for healthcare contexts
- Format responses with proper structure (headers, lists, tables when appropriate)
- If you don't have specific information, clearly state limitations

USER QUERY (already enhanced with conversation context): {enhanced_query}

Provide a comprehensive response about the pharmaceutical topic requested."""

        response = llm.invoke(prompt)
        response_content = response.content if hasattr(response, 'content') else str(response)
        return await _convert_response_to_html_unified(response_content)
        
    except Exception as e:
        logger.error(f"Error generating enhanced LLM response: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now. Please try again later."

async def _generate_llm_response_with_history(
    message: str, 
    chat_history: List[Tuple[str, str]], 
    session_id: str, 
    user_id: int, 
    db: Session
) -> str:
    """Generate LLM response using chat history for conversation context"""
    try:
        llm = get_llm()
        
        # Build conversation context
        context_messages = []
        
        # Add chat history
        for user_msg, assistant_msg in chat_history:
            context_messages.append(HumanMessage(content=user_msg))
            context_messages.append(AIMessage(content=assistant_msg))
        
        # Create prompt with conversation history
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are a pharmaceutical AI assistant specializing in FDA-approved drugs and medical information.

RESPONSE STYLE - CRITICAL RULES:
- NEVER use phrases like "I can help you", "I can provide information", "Let me help", "I'll provide", "I can assist"
- NEVER start with "Okay", "Sure", "Certainly", "Of course", "I'd be happy to"
- START IMMEDIATELY with facts and details
- Use direct statements: "Here are the details about...", "The following covers...", "Key information includes..."
- Be authoritative and factual from the first word
- NO conversational pleasantries or helper language

CONVERSATION GUIDELINES:
- Maintain conversation context and refer to previous exchanges when relevant
- Provide accurate, evidence-based pharmaceutical information
- Focus on FDA-approved drugs, clinical data, and medical guidelines
- Use professional, clear language suitable for healthcare contexts
- Format responses with proper structure (headers, lists, tables when appropriate)
- If you don't have specific information, clearly state limitations

RESPONSE FORMAT:
- Use clear headings and bullet points
- Include relevant medical terminology
- Provide structured, easy-to-read information
- When appropriate, suggest consulting healthcare professionals"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])
        
        # Create the chain
        chain = prompt_template | llm
        
        # Execute with conversation context
        response = chain.invoke({
            "input": message,
            "chat_history": context_messages
        })
        
        response_content = response.content if hasattr(response, 'content') else str(response)
        return await _convert_response_to_html_unified(response_content)
        
    except Exception as e:
        logger.error(f"Error generating LLM response with history: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now. Please try again later."

async def _ensure_english_response(response: str, original_query: str) -> str:
    """Ensure the response is in English only"""
    # Extended list of non-English indicators
    swedish_indicators = ['å', 'ä', 'ö', 'Å', 'Ä', 'Ö', 'är', 'och', 'för', 'att', 'med', 'som', 'eller', 'från', 
                         'bedömning', 'läkemedel', 'behandling', 'följande', 'gäller', 'enligt']
    german_indicators = ['ü', 'ö', 'ä', 'ß', 'der', 'die', 'das', 'und', 'mit', 'für']
    french_indicators = ['à', 'é', 'è', 'ê', 'ç', 'œ', 'et', 'pour', 'avec', 'dans']
    spanish_indicators = ['ñ', 'á', 'é', 'í', 'ó', 'ú', 'por', 'para', 'con']
    
    # Simple check for non-ASCII characters that might indicate non-English text
    non_ascii_ratio = sum(1 for c in response if ord(c) > 127) / len(response) if response else 0
    
    # Check if response contains any non-English indicators
    contains_non_english = (
        any(indicator in response.lower() for indicator in swedish_indicators) or
        any(indicator in response.lower() for indicator in german_indicators) or
        any(indicator in response.lower() for indicator in french_indicators) or
        any(indicator in response.lower() for indicator in spanish_indicators)
    )
    
    # More aggressive check - if more than 5% non-ASCII or any non-English indicators
    if non_ascii_ratio > 0.05 or contains_non_english:
        logger.warning(f"Response appears to contain non-English text (non-ASCII ratio: {non_ascii_ratio:.2f})")
        
        # Use LLM to translate to English
        translation_prompt = f"""URGENT: The following response is NOT in English and MUST be translated.

TRANSLATE EVERYTHING TO ENGLISH. NO EXCEPTIONS.

Original Response (NOT IN ENGLISH):
{response}

User's Question (for context):
{original_query}

REQUIREMENTS:
1. Translate EVERY SINGLE WORD to English
2. Keep all numbers, percentages, and citations
3. Translate organization names but keep acronyms in parentheses
4. Example: "TLV (Tandvårds- och läkemedelsförmånsverket)" becomes "TLV (The Dental and Pharmaceutical Benefits Agency)"

PROVIDE THE COMPLETE RESPONSE IN ENGLISH ONLY:"""
        
        llm = get_llm()
        translated_response = await llm.ainvoke(translation_prompt)
        return translated_response.content if hasattr(translated_response, 'content') else str(translated_response)
    
    # ALWAYS do a final validation pass to ensure English
    # This catches cases where the initial detection might miss some non-English content
    validation_prompt = f"""Review this response and ensure it is 100% in English.

Response to validate:
{response}

If the response is already completely in English, return it as-is.
If you find ANY non-English text, translate it to English.

IMPORTANT: Organization names should be translated but keep original acronyms in parentheses.
Example: "TLV" should be "TLV (The Dental and Pharmaceutical Benefits Agency)"

Return the response (must be 100% in English):"""
    
    llm = get_llm()
    validated_response = await llm.ainvoke(validation_prompt)
    final_response = validated_response.content if hasattr(validated_response, 'content') else str(validated_response)
    
    # Log if translation was needed
    if final_response != response:
        logger.info("Response was translated/validated to ensure English-only content")
    
    return final_response

async def _grade_documents_by_relevance(query: str, documents: List[Document]) -> List[Document]:
    """Grade documents by relevance using batch processing and return top 20"""
    
    # Skip grading if we have 15 or fewer documents
    if len(documents) <= 15:
        logger.info(f"Skipping relevance grading - only {len(documents)} documents")
        return documents[:20]  # Still ensure max 20 returned
    
    batch_grading_prompt = """You are a document relevance grader. Rate each document's relevance to the query.

Query: {query}

Documents to grade:
{documents_text}

For each document, provide ONLY a numeric score from 0-10:
- 0-3: Not relevant
- 4-6: Somewhat relevant  
- 7-8: Relevant
- 9-10: Highly relevant

Return your response as a JSON array of scores in the same order as the documents.
Example: [8, 3, 9, 5, 7, 10, 2, 8, 9, 6]

IMPORTANT: Return ONLY the JSON array, no explanations."""
    
    # Prepare documents for batch grading
    documents_text = ""
    valid_docs = []
    
    for i, doc in enumerate(documents):
        content = doc.metadata.get('original_content', '')
        if not content:
            logger.warning(f"Document {i} missing original_content in metadata, skipping")
            continue
        # Limit content for grading
        content = content[:500]  # Reduced from 1000 to fit more in batch
        documents_text += f"\n---Document {i+1}---\n{content}\n"
        valid_docs.append((i, doc))
    
    if not valid_docs:
        logger.error("No valid documents for grading")
        return []
    
    # Use zero-temperature LLM for consistent grading
    from utils.llm_util import get_llm_grading
    llm = get_llm_grading()
    
    try:
        # Grade all documents in one LLM call
        prompt = batch_grading_prompt.format(query=query, documents_text=documents_text)
        score_response = llm.invoke(prompt)
        score_text = score_response.content if hasattr(score_response, 'content') else str(score_response)
        
        # Parse JSON array of scores
        import json
        try:
            # Clean the response to get just the JSON array
            score_text = score_text.strip()
            if score_text.startswith('[') and score_text.endswith(']'):
                scores = json.loads(score_text)
            else:
                # Try to extract JSON array from the response
                import re
                json_match = re.search(r'\[[\d,\s\.]+\]', score_text)
                if json_match:
                    scores = json.loads(json_match.group())
                else:
                    raise ValueError("No JSON array found in response")
            
            # Validate we have the right number of scores
            if len(scores) != len(valid_docs):
                logger.warning(f"Score count mismatch: got {len(scores)}, expected {len(valid_docs)}")
                # Pad or truncate as needed
                if len(scores) < len(valid_docs):
                    scores.extend([5.0] * (len(valid_docs) - len(scores)))
                else:
                    scores = scores[:len(valid_docs)]
            
            # Pair scores with documents
            graded_docs = []
            for (orig_idx, doc), score in zip(valid_docs, scores):
                try:
                    score = float(score)
                    score = max(0, min(10, score))  # Clamp to 0-10
                except:
                    score = 5.0  # Default score
                graded_docs.append((doc, score))
                
        except Exception as e:
            logger.error(f"Error parsing batch grading response: {e}")
            logger.error(f"Response was: {score_text[:200]}...")
            # Fall back to giving all documents medium score
            graded_docs = [(doc, 5.0) for _, doc in valid_docs]
    
    except Exception as e:
        logger.error(f"Error in batch grading: {e}")
        # Fall back to returning all documents
        return documents[:20]
    
    # Sort by score and return top 20
    graded_docs.sort(key=lambda x: x[1], reverse=True)
    top_docs = [doc for doc, score in graded_docs[:20]]
    
    logger.info(f"Batch graded {len(documents)} documents in 1 LLM call, returning top {len(top_docs)} with scores: {[score for _, score in graded_docs[:20]]}")
    return top_docs

async def _convert_response_to_html(text: str) -> str:
    """Convert LLM response to clean HTML using another LLM call."""
    if not text:
        return text
    
    try:
        from utils.llm_util import get_llm
        
        llm = get_llm()
        
        conversion_prompt = f"""Convert this text to clean HTML format. Return ONLY the HTML, no explanations.

{text}"""

        response = llm.invoke(conversion_prompt)
        html_content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up any markdown code block markers that might be included
        html_content = html_content.replace('```html', '').replace('```', '').strip()
        
        return html_content
        
    except Exception as e:
        logger.error(f"Error in LLM HTML conversion: {str(e)}")
        # Fallback to original text if LLM conversion fails
        return text

def calculate_retrieval_confidence(documents: List) -> float:
    """Calculate confidence score based on retrieved documents"""
    if not documents:
        return 0.0
    
    # Average relevance scores if available
    scores = []
    for doc in documents[:5]:  # Top 5 documents
        if hasattr(doc, 'metadata') and doc.metadata.get('relevance_score'):
            scores.append(doc.metadata['relevance_score'])
    
    if scores:
        return sum(scores) / len(scores)
    else:
        # Default confidence based on document count
        return min(len(documents) * 0.1, 0.9)

def calculate_citation_coverage(cited_response: str, original_response: str) -> float:
    """Calculate what percentage of factual claims have citations"""
    import re
    
    # Count citations in response
    citation_pattern = r'\[\d+\]'
    citations = re.findall(citation_pattern, cited_response)
    
    if not citations:
        return 0.0
    
    # Estimate coverage based on citation density
    # Assume good coverage if at least 1 citation per 200 characters
    expected_citations = max(1, len(original_response) // 200)
    coverage = min(len(citations) / expected_citations, 1.0)
    
    return coverage

def _clean_markdown_formatting(text: str) -> str:
    """Clean and fix common markdown formatting issues."""
    import re
    
    if not text:
        return text
    
    # Fix headers without space after #, ##, ###, etc.
    text = re.sub(r'^(#{1,6})([^\s#])', r'\1 \2', text, flags=re.MULTILINE)
    
    # More comprehensive approach: find headers followed by asterisk-separated items
    # and convert them to proper bullet lists
    def process_header_with_bullets(match):
        header = match.group(1).strip()
        content = match.group(2).strip()
        
        # Split by asterisks and clean up
        items = [item.strip() for item in content.split('*') if item.strip()]
        
        if not items:
            return header
        
        # Create proper markdown structure
        result = header + '\n'
        for item in items:
            result += '- ' + item + '\n'
        
        return result.rstrip() + '\n'
    
    # Pattern to match header followed by asterisk-separated content
    # This handles both newline-separated and inline content
    pattern = r'(#{1,6}\s+[^*#]+?)\s*\*\s*([^#]+?)(?=\s#{1,6}|\n\s*#{1,6}|\n\s*\n|\n\s*$|$)'
    text = re.sub(pattern, process_header_with_bullets, text, flags=re.MULTILINE | re.DOTALL)
    
    # Clean up any remaining standalone asterisks at start of lines
    text = re.sub(r'^\s*\*\s+', '- ', text, flags=re.MULTILINE)
    text = re.sub(r'^•\s*', '- ', text, flags=re.MULTILINE)
    
    # Fix malformed bold formatting
    text = re.sub(r'\*\* ([^*]+?)(?=\s|$)', r'**\1**', text)
    text = re.sub(r'\*\* \* (.+)', r'- \1', text)
    text = re.sub(r'\* \*\*([^*]+)\*\*', r'**\1**', text)
    
    # Fix broken list formatting like "text\n•\nmore text"
    text = re.sub(r'(\w)\n•\n(\w)', r'\1\n- \2', text)
    
    # Clean up spacing
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

async def _generate_general_llm_response(
    message: str, 
    session_id: str = None, 
    user_id: int = None, 
    db: Session = None
) -> str:
    """Generate a response using general LLM without document context, limited to pharmaceutical scope."""
    try:
        llm = get_llm()
        
        # Get conversational history if session info provided
        chat_history = []
        if session_id and user_id and db:
            # Ensure any pending database changes are committed before retrieving history
            try:
                db.commit()
            except Exception as e:
                logger.warning(f"Database commit before history retrieval failed: {e}")
            
            chat_history = _get_general_chat_history(session_id, user_id, db)
            logger.info("=== UNIFIED ENDPOINT GENERAL LLM PROCESSING ===")
            logger.info(f"Original message: '{message}'")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Chat history retrieved: {len(chat_history)} exchanges")
            
            # Debug: Log actual chat history entries
            if chat_history:
                logger.info("📜 CHAT HISTORY DETAILS:")
                for i, (role, content) in enumerate(chat_history):
                    logger.info(f"  {i+1}. {role}: {content[:100]}...")
                    
                # Enhanced debugging for conversational context
                logger.info("🔄 CONVERSATIONAL CONTEXT ANALYSIS:")
                last_user_msg = None
                last_ai_msg = None
                for role, content in reversed(chat_history):
                    if role == "human" and not last_user_msg:
                        last_user_msg = content
                    elif role == "ai" and not last_ai_msg:
                        last_ai_msg = content
                    if last_user_msg and last_ai_msg:
                        break
                        
                if last_user_msg:
                    logger.info(f"   Last user question: '{last_user_msg[:100]}...'")
                if last_ai_msg:
                    logger.info(f"   Last AI response: '{last_ai_msg[:100]}...'")
                    
                # Check if current message seems like a follow-up
                current_msg_lower = message.lower()
                follow_up_indicators = ['this', 'that', 'it', 'they', 'these', 'those', 'what about', 'how about', 'also', 'too', 'compare', 'vs', 'versus']
                seems_follow_up = any(indicator in current_msg_lower for indicator in follow_up_indicators)
                logger.info(f"   Current message seems like follow-up: {seems_follow_up}")
                if seems_follow_up:
                    logger.info(f"   Follow-up indicators found: {[ind for ind in follow_up_indicators if ind in current_msg_lower]}")
            else:
                logger.warning("⚠️ NO CHAT HISTORY FOUND - checking database directly")
                # Debug database query
                debug_result = db.query(ChatHistory).filter(
                    ChatHistory.user_id == user_id,
                    ChatHistory.session_id == session_id
                ).count()
                logger.info(f"   Database has {debug_result} total records for user {user_id}, session {session_id}")
                
                # Show recent database entries for debugging
                recent_chats = db.query(ChatHistory).filter(
                    ChatHistory.user_id == user_id
                ).order_by(ChatHistory.created_at.desc()).limit(3).all()
                logger.info(f"   Recent 3 chat entries for user:")
                for i, chat in enumerate(recent_chats):
                    logger.info(f"     {i+1}. Session: {chat.session_id}, Query: '{chat.user_query[:50]}...'")
        else:
            logger.info("=== UNIFIED ENDPOINT GENERAL LLM (NO HISTORY) ===")
            logger.info(f"Message: '{message}'")
            logger.info("No session context provided - generating response without history")
        
        # First, check if the query is pharmaceutical/medical related
        classification_prompt = f"""You are an expert classifier. Analyze this user question and determine if it's related to pharmaceuticals, drugs, medicine, healthcare, or medical topics.

User question: {message}

Respond with only "PHARMACEUTICAL" if the question is about:
- Drugs, medications, pharmaceuticals
- Medical conditions, diseases, treatments
- Healthcare, clinical topics
- FDA, drug approvals, regulatory topics
- Drug interactions, side effects, dosing
- Medical research, clinical trials

Respond with only "NON_PHARMACEUTICAL" if the question is about:
- General knowledge, technology, science (non-medical)
- Personal questions, greetings
- Programming, business, entertainment
- Any topic not related to medicine or pharmaceuticals

Response:"""
        
        # Log the classification prompt details
        logger.info("📝 UNIFIED ENDPOINT CLASSIFICATION PROMPT:")
        logger.info(f"   Task: Binary classification (PHARMACEUTICAL vs NON_PHARMACEUTICAL)")
        logger.info(f"   User Question: '{message}'")
        logger.info(f"   Prompt Length: {len(classification_prompt)} characters")
        logger.info(f"   Expected Output: Single word classification")
        
        classification_response = llm.invoke(classification_prompt)
        classification = classification_response.content if hasattr(classification_response, 'content') else str(classification_response)
        
        logger.info(f"📋 Pharmaceutical classification result: '{classification.strip()}'")
        
        if "NON_PHARMACEUTICAL" in classification.upper():
            logger.info("❌ Query classified as NON_PHARMACEUTICAL - returning scope limitation message")
            return """I appreciate your question! I'm here to assist with pharmaceutical and medical-related topics. While I can't answer questions outside my area of expertise, I'd be happy to help with:

- **Drug Information**: Details about medications, their uses, and interactions
- **Medical Conditions**: Information about diseases, symptoms, and treatments
- **Regulatory Insights**: FDA approvals, guidelines, and compliance
- **Clinical Research**: Information about trials, studies, and medical research
- **Healthcare Topics**: General medical and pharmaceutical knowledge

Could you please rephrase your question to focus on one of these areas? I'm here to help with any pharmaceutical or medical information you need!"""
        
        # If pharmaceutical-related, provide a helpful response using LangChain chains
        logger.info("✅ Query classified as PHARMACEUTICAL - proceeding with LangChain response generation")
        # Convert chat history to LangChain messages
        messages = []
        if chat_history:
            for role, content in chat_history[-5:]:  # Last 5 exchanges
                if role == "human":
                    messages.append(HumanMessage(content=content))
                elif role == "ai":
                    messages.append(AIMessage(content=content))
        
        # Create enhanced prompt template with professional response guidelines and rich content support
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """# Role & Expertise
You are a highly knowledgeable pharmaceutical and medical AI assistant. Your responses should be professional, accurate, and helpful.

# Response Style - CRITICAL RULES
- NEVER use phrases like "I can help you", "I can provide information", "Let me help", "I'll provide", "I can assist"
- NEVER start with "Okay", "Sure", "Certainly", "Of course", "I'd be happy to"
- START IMMEDIATELY with facts and details
- Use direct statements: "Here are the details about...", "The following covers...", "Key information includes..."
- Be authoritative and factual from the first word
- NO conversational pleasantries or helper language

# Conversational Context
- Pay attention to previous messages in the conversation for context
- Reference earlier topics naturally when relevant (e.g., "As we discussed earlier about...", "Building on your previous question...")
- Maintain conversation continuity and remember what the user has asked about
- If the user asks follow-up questions, assume they relate to previous topics unless explicitly stated otherwise
- Use pronouns and references appropriately (e.g., "this drug", "that side effect" when referring to previously mentioned items)

# Critical Formatting Rules - FOLLOW EXACTLY
1. **Markdown Syntax**: Always use proper markdown syntax:
   - Headers: `## Header Name` (space after ##)
   - Bold: `**text**` (no spaces inside asterisks)
   - Italic: `*text*` (single asterisk, no spaces inside)
   - Lists: `- Item` or `* Item` (space after dash/asterisk)
   - Never mix formatting like `** *` or `* **`

2. **Table Format**: Use proper markdown tables:
   ```
   | Column 1 | Column 2 |
   |----------|----------|
   | Data 1   | Data 2   |
   ```

3. **List Format**: Use consistent bullet points:
   ```
   **Key Points:**
   - First point here
   - Second point here
   - Third point here
   ```

# Response Guidelines
1. **Professional Tone**: Maintain a warm, professional, and empathetic tone throughout all interactions.
2. **Structured Format**: Organize responses with clear sections, bullet points, and proper formatting.
3. **Rich Content Support**:
   - Tables: Use proper markdown table format with aligned columns
   - Lists: Use consistent bullet points (- or *) with proper spacing
   - Code Blocks: Use ```language for code blocks with dosages or formulas
   - **Bold** for important terms or warnings (proper syntax)
   - *Italics* for emphasis (proper syntax)
4. **No Results Response**: If information is unavailable, respond professionally:
   - Acknowledge the query
   - Explain the limitation clearly
   - Offer relevant alternatives if possible
   - Maintain a helpful tone

# Content Guidelines
- Provide comprehensive yet concise information
- Include relevant context and background
- Use medical terminology appropriately
- Include disclaimers for medical advice
- For drug information, include: class, mechanism, indications, dosing, side effects, contraindications, and important warnings

# Example Response Format
## Overview
[Main points in clear, structured format]

## Important Considerations
- Key point 1 with proper formatting
- Key point 2 with proper formatting
- Key point 3 with proper formatting

## Additional Information
[Tables or structured data if relevant using proper markdown syntax]

**Disclaimer**: *This information is for educational purposes only and not a substitute for professional medical advice.*"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}")
        ])
        
        # Log the unified endpoint prompt structure
        logger.info("📝 UNIFIED ENDPOINT MAIN RESPONSE PROMPT:")
        logger.info(f"   Brand Identity: Specialized pharmaceutical assistant")
        logger.info(f"   System Message: Comprehensive pharmaceutical guidance with medical disclaimers")
        logger.info(f"   System Message Length: ~475 characters")
        logger.info(f"   Chat History Variable: 'chat_history' (will insert {len(messages)} messages)")
        logger.info(f"   Human Input Variable: 'input' (value: '{message}')")
        logger.info(f"   Response Style: Informative, concise, professional pharmaceutical focus")
        
        # Create the chain
        chain = prompt_template | llm
        
        # Execute the chain
        logger.info("=== UNIFIED ENDPOINT CHAIN EXECUTION ===")
        logger.info(f"Executing LangChain with input: '{message}'")
        logger.info(f"Chat history messages passed to chain: {len(messages)}")
        for i, msg in enumerate(messages[:3]):  # Log first 3 messages
            msg_type = type(msg).__name__
            content_preview = msg.content[:80] if hasattr(msg, 'content') else str(msg)[:80]
            logger.info(f"  Message {i+1} ({msg_type}): {content_preview}...")
        
        # Log the exact data being passed to the unified chain
        chain_input = {
            "input": message,
            "chat_history": messages
        }
        logger.info("📤 EXACT INPUT TO UNIFIED CHAIN:")
        logger.info(f"   Input: '{chain_input['input']}'")
        logger.info(f"   Chat History: {len(chain_input['chat_history'])} LangChain messages")
        for i, msg in enumerate(chain_input['chat_history'][:3]):  # First 3 messages
            msg_type = type(msg).__name__
            content = msg.content[:60] if hasattr(msg, 'content') else str(msg)[:60]
            logger.info(f"     {i+1}. {msg_type}: {content}...")
        
        response = chain.invoke(chain_input)
        
        response_content = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"✅ Unified endpoint chain response received (length: {len(response_content)} chars)")
        logger.info(f"Response preview: {response_content[:100]}...")
        
        return response_content
        
    except Exception as e:
        logger.error(f"Error generating general LLM response: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now. Please try again later."

def _get_general_chat_history(session_id: str, user_id: int, db: Session) -> List[Tuple[str, str]]:
    """Get general chat history for a session, following same logic as query endpoint."""
    try:
        chat_history = []
        
        # Get recent chat history from the session - same logic as query endpoint
        result = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        
        for chat in result:
            if chat.response_details:
                try:
                    response_details = json.loads(chat.response_details)
                    response_content = response_details.get("response", "")
                    
                    # Add user query and assistant response - same format as query endpoint
                    if chat.user_query:
                        chat_history.append(("human", chat.user_query))
                    if response_content:
                        chat_history.append(("ai", response_content))
                        
                except (ValueError, json.JSONDecodeError):
                    logger.error(f"Invalid format in response_details: {chat.response_details}")
        
        # Return last 5 exchanges (10 total messages) for conversational context
        # Each exchange = user message + assistant response = 2 messages
        return chat_history[-10:] if chat_history else []
        
    except Exception as e:
        logger.error(f"Error retrieving general chat history: {str(e)}")
        return []


class ShareChatRequest(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    title: Optional[str] = None
    expiration_hours: Optional[int] = 24 * 7  # Default 7 days
    password: Optional[str] = None


class ShareChatResponse(BaseModel):
    share_id: str
    share_url: str
    expires_at: datetime
    password_protected: bool


@router.post("/share", response_model=ShareChatResponse)
async def create_share_link(
    request: ShareChatRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a shareable link for a chat conversation."""
    try:
        import hashlib
        import secrets
        
        # Generate unique share ID
        share_id = secrets.token_urlsafe(16)
        
        # Calculate expiration
        expires_at = datetime.now() + timedelta(hours=request.expiration_hours)
        
        # Hash password if provided
        password_hash = None
        if request.password:
            password_hash = hashlib.sha256(request.password.encode()).hexdigest()
        
        # Store share data in database
        share_data = {
            "share_id": share_id,
            "session_id": request.session_id,
            "user_id": current_user.id,
            "messages": request.messages,
            "title": request.title or "Shared Chat",
            "created_at": datetime.now(),
            "expires_at": expires_at,
            "password_hash": password_hash,
            "view_count": 0
        }
        
        # Store share data in database
        share_chat = ShareChat(
            share_id=share_id,
            session_id=request.session_id,
            user_id=current_user.id,
            title=request.title or "Shared Chat",
            messages=request.messages,
            password_hash=password_hash,
            expires_at=expires_at
        )
        db.add(share_chat)
        db.commit()
        
        # Generate share URL
        base_url = settings.FRONTEND_URL or "http://localhost:3000"
        share_url = f"{base_url}/share/{share_id}"
        
        return ShareChatResponse(
            share_id=share_id,
            share_url=share_url,
            expires_at=expires_at,
            password_protected=bool(password_hash)
        )
        
    except Exception as e:
        logger.error(f"Error creating share link: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create share link")


@router.get("/share/{share_id}")
async def get_shared_chat(
    share_id: str,
    password: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Retrieve a shared chat conversation."""
    try:
        # Retrieve from ShareChat table
        share_chat = db.query(ShareChat).filter(ShareChat.share_id == share_id).first()
        
        if not share_chat:
            raise HTTPException(status_code=404, detail="Share not found")
        
        # Check if expired
        if datetime.now() > share_chat.expires_at:
            raise HTTPException(status_code=404, detail="Share link has expired")
        
        # Verify password if required
        if share_chat.password_hash:
            if not password:
                raise HTTPException(status_code=401, detail="Password required")
            
            import hashlib
            provided_hash = hashlib.sha256(password.encode()).hexdigest()
            if provided_hash != share_chat.password_hash:
                raise HTTPException(status_code=401, detail="Invalid password")
        
        # Increment view count
        share_chat.view_count += 1
        db.commit()
        
        return {
            "share_id": share_chat.share_id,
            "title": share_chat.title,
            "messages": share_chat.messages,
            "created_at": share_chat.created_at,
            "view_count": share_chat.view_count
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is (for password errors, etc.)
        raise
    except Exception as e:
        logger.error(f"Error retrieving shared chat {share_id}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")