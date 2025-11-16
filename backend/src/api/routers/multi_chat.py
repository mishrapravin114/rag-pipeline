import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from pydantic import BaseModel
from agno.agent import Agent
from agno.tools import tool
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from langchain_core.documents import Document
import json
import traceback
from agno.knowledge.agent import AgentKnowledge
from agno.vectordb.qdrant import Qdrant
from agno.embedder.google import GeminiEmbedder


# Database imports
from database.database import get_db, Collection, collection_document_association, SourceFiles

# Service imports
from api.services.chat_management_service import FDAChatManagementService

# Utility imports
from utils.qdrant_util import QdrantUtil
from utils.drug_file_matcher import DrugFileMatcher
from utils.llm_util import get_llm, get_llm_grading
from utils.intent_classifier import QueryIntent
from utils.filtered_agent_knowledge_qdrant import FilteredAgentKnowledge
from config.settings import settings

logger = logging.getLogger(__name__)

# ===========================
# Define Pydantic Models for Tool Inputs/Outputs
# ===========================
class QueryAndCollection(BaseModel):
    """Input model for tools that require a query and collection info."""
    query: str
    collection_name: str
    collection_id: int
    file_name_filter: Optional[Dict] = None

class RetrievalOutput(BaseModel):
    """Output model for the document retrieval tool."""
    documents: List[Document]

class GenerationInput(BaseModel):
    """Input model for the response generation tool."""
    query: str
    documents: List[Document]
    vector_db_util: Any # Cannot validate this, but must be passed


# ===========================
# Define Agno Tools
# ===========================

# Global variables to store current context
_current_collection_name = None  # Will be set dynamically per request
_current_original_query = ""

def _get_dynamic_doc_counts(query: str) -> Tuple[int, int]:
    """Returns (n_results, max_graded_docs) based on query length"""
    word_count = len(query.split())
    return (100, 60)
    if word_count < 10:
        return (50, 30)
    elif word_count < 25:
        return (60, 40)
    else:
        return (100, 60)

@tool
async def count_documents_in_collection(
    collection_name: Optional[str] = None,
    filter_by_source: Optional[str] = None,
    group_by_source: bool = False
) -> Dict[str, Any]:
    """
    Count documents in a collection with optional filtering.
    
    Arguments:
        collection_name (str, optional): The vector database collection name. If not provided, uses the current collection.
        filter_by_source (str, optional): Filter to count only documents from a specific source file
        group_by_source (bool): If True, returns counts grouped by source file
        
    Returns:
        Dict containing count information
        
    Usage Examples:
        # Count all documents in current collection
        count_documents_in_collection()
        
        # Count all documents in specific collection
        count_documents_in_collection("fda_documents")
        
        # Count documents from specific file
        count_documents_in_collection(filter_by_source="keytruda.pdf")
        
        # Get breakdown by source file
        count_documents_in_collection(group_by_source=True)
    """
    logger.info(f"=== count_documents_in_collection called ===")
    logger.info(f"Parameters: collection_name={collection_name}, filter_by_source={filter_by_source}, group_by_source={group_by_source}")
    
    try:
        global _current_collection_name
        
        # Use provided collection name or fall back to current collection
        if collection_name is None:
            collection_name = _current_collection_name
            logger.info(f"Using current collection: {collection_name}")
        
        logger.info(f"Counting documents in collection: {collection_name}")
        
        # Create a FilteredAgentKnowledge instance
        from agno.vectordb.qdrant import Qdrant
        from agno.embedder.google import GeminiEmbedder
        
        vector_db = Qdrant(
            collection=collection_name,
            embedder=GeminiEmbedder(id="models/text-embedding-004"),
            url=f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
        )
        
        # Create filters if needed
        filters = None
        if filter_by_source:
            filters = {"source": {"$in": [filter_by_source]}}  # FilteredAgentKnowledge will add meta_data prefix
        
        # Create knowledge base with filters
        knowledge_base = FilteredAgentKnowledge(
            vector_db=vector_db,
            filters=filters
        )
        
        result = {}
        
        if group_by_source:
            # Get counts grouped by source
            counts_by_source = await knowledge_base.async_get_document_count_by_metadata("source", collection_name=collection_name)
            # Convert numpy types to native Python types
            result["grouped_counts"] = {k: int(v) if hasattr(v, '__int__') else v for k, v in counts_by_source.items()}
            result["total_count"] = int(sum(counts_by_source.values()))
            result["unique_sources"] = len(counts_by_source)
        else:
            # Use optimized method for count-only queries (no document details needed)
            stats = await knowledge_base.async_get_collection_vector_stats(include_documents=False, collection_name=collection_name)
            result["count"] = stats.get("unique_documents", 0)
            result["total_vectors"] = stats.get("total_vectors", 0)
            result["average_chunks_per_document"] = stats.get("average_chunks_per_document", 0)
            if filter_by_source:
                result["filtered_by"] = filter_by_source
            if stats.get("is_estimate", False):
                result["is_estimate"] = True
        
        logger.info(f"Document count result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error counting documents: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e)}

def _convert_response_to_html_unified(text: str, query: str) -> str:
    """Convert LLM response to clean HTML for unified endpoint."""
    if not text:
        return text
    
    try:
        llm = get_llm()
        
        conversion_prompt = f"""
        You are a professional HTML converter for a Tailwind-based chat UI.

        Your job is to:
        1. Convert the provided text into clean, semantic HTML.
        2. Do not modify, shorten, or omit any content ? preserve it exactly as given.
        3. If any source URL's are found, make sure onclick of it opens in new page.
        4. Ensure same source details are not repeated, if there are duplicate sources, show the unique source details only and make sure sources are placed at the end of the responses.
        5. Ensure the HTML is style-safe and does not interfere with the existing chat UI layout.
        6. Make sure the response is in English only.

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
        - Do not add explanations, notes, or metadata ? return only the HTML.
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

def _validate_response_has_data(response: str) -> bool:
    """
    Uses LLM to validate if the response contains relevant data from the knowledge base.
    Returns False if the response indicates no relevant data was found.
    """
    try:
        llm = get_llm()
        
        validation_prompt = f"""
        Analyze the following response and determine if it contains data retrieved from a knowledge base or if it's just a general response.
        
        Response to analyze:
        {response}
        
        Decision Rules:
        1. Respond with NO_DATA if the response explicitly states:
           - "No relevant evidence found"
           - "No information found in the knowledge base"
           - "Unable to find relevant documents"
           - Similar phrases indicating absence of data
        
        2. Respond with HAS_DATA for all other cases, including:
           - General conversational responses (e.g., "I am a large language model")
           - Actual information or facts
           - Any response that doesn't explicitly state data was NOT found
        
        3. Respond with ERROR only if the response is clearly an error message or system failure
        
        IMPORTANT: Respond with ONLY one of these exact phrases: HAS_DATA, NO_DATA, or ERROR
        Do not include any other text, explanation, or formatting.
        """
        
        llm_response = llm.invoke(validation_prompt)
        result = llm_response.content.strip() if hasattr(llm_response, 'content') else str(llm_response).strip()
        
        logger.info(f"LLM validation result: {result}")
        
        # Return True if response has data, False if no data found
        if result == "HAS_DATA":
            return True
        elif result == "NO_DATA":
            return False
        else:
            # Default to True if we can't determine (ERROR or unexpected response)
            logger.warning(f"Unexpected LLM validation response: {result}")
            return True
            
    except Exception as e:
        logger.error(f"Error in LLM validation: {str(e)}")
        # Default to True if validation fails
        return True

async def _get_gemini_global_response(query: str, session_id: str) -> str:
    """
    Get response from Gemini LLM agent when no data is found in knowledge base.
    Uses agent-based approach with comprehensive pharmaceutical knowledge instructions.
    Formats the response with proper HTML structure and source citation.
    
    Args:
        query: The user's query
        session_id: Session ID for agent context
    
    Returns:
        Formatted HTML response with source citations
    """
    try:
        logger.info("Using agent for global response generation")
        
        # Build comprehensive instructions from the non-agent prompt
        agent_instructions = [
            "You are a highly knowledgeable AI assistant specializing in pharmaceutical, FDA, EMA, and regulatory documents.",
            "Your primary expertise is in pharmaceuticals, FDA, EMA, regulatory affairs, and you can also provide information about drug costs and pricing when asked.",
            "For topics outside your expertise, provide a helpful and polite response explaining what you can help with instead.",
            "Always be helpful and courteous, even when a query is outside your main domain.",
            "Please provide clear, comprehensive, and well-structured responses to all queries.",
            "",
            "Response Guidelines:",
            "1. Provide accurate, detailed information based on your training data",
            "2. Structure your response clearly with appropriate headings where needed",
            "3. Be factual and provide specific source citations where possible",
            "4. Format your response in valid semantic HTML",
            "5. Include relevant source URLs for the information you provide—preferably direct links to pages, PDFs, or articles, not just main website homepages",
            "6. For cost/pricing queries: Provide general information about drug pricing factors, typical price ranges if known, and suggest reliable sources for current pricing",
            "7. For off-topic queries: Politely acknowledge the question and offer to help with pharmaceutical or regulatory topics instead"
            "",
            "HTML Formatting Requirements:",
            "- Wrap ALL content inside: <div class=\"prose max-w-none text-gray-800 text-base leading-relaxed\"> ... </div>",
            "- Use semantic HTML tags (<p>, <ul>, <li>, <table>, <h2>, <h3>, etc.)",
            "- For tables use: <table class=\"min-w-full border-collapse border border-gray-300\">",
            "- At the END of your response, add a Sources section with relevant citations:",
            "  <h3>Sources</h3>",
            "  <ul>",
            "    <li><a href=\"[actual URL if citing specific source]\" target=\"_blank\" rel=\"noopener noreferrer\">[Source name/description]</a></li>",
            "  </ul>",
            "  <p class=\"text-sm text-gray-600 italic mt-2\">",
            "    <svg class=\"inline-block w-4 h-4 mr-1\" fill=\"currentColor\" viewBox=\"0 0 20 20\">",
            "      <path d=\"M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z\"/>",
            "    </svg>",
            "    This response is generated by Gemini AI from general knowledge.",
            "  </p>",
            "",
            "Note: If you reference specific facts, studies, or sources, include actual URLs where possible.",
            "For general knowledge, you can omit specific URLs but always include the Gemini AI attribution.",
            "Always indicate that your response is from general knowledge, not from the document knowledge base.",
            "",
            "Special Instructions:",
            "- For drug cost/pricing queries: Acknowledge that prices vary by location, brand, and other factors. Provide general guidance and suggest checking with local pharmacies or official pricing databases.",
            "- For off-topic queries: Use this format: 'I appreciate your question about [topic]. While my expertise is primarily in pharmaceutical and regulatory affairs, I'd be happy to help you with questions about drug information, FDA/EMA regulations, clinical trials, drug safety, or pharmaceutical pricing. Is there anything in these areas I can assist you with?'",
            "- Never say you 'cannot' help - instead, redirect politely to topics you can help with.",
            "- Maintain a helpful, professional, and friendly tone throughout."
        ]
        
        # Create a global knowledge agent without collection restrictions
        global_agent = Agent(
            name="Global Pharmaceutical Knowledge Agent",
            session_id=session_id,
            model=Gemini(id="gemini-2.5-flash"),
            markdown=False,  # Set to False since we're generating HTML
            instructions=agent_instructions
        )
        
        # Run the agent
        agent_response = await global_agent.arun(query)
        
        # Extract content from agent response
        if hasattr(agent_response, 'content'):
            content = agent_response.content
        elif hasattr(agent_response, 'messages') and agent_response.messages:
            content = agent_response.messages[-1].content if hasattr(agent_response.messages[-1], 'content') else str(agent_response.messages[-1])
        else:
            content = str(agent_response)
        
        # Clean up any markdown code block markers that might be included
        content = content.replace('```html', '').replace('```', '').strip()
        
        # Remove any unwanted wrapper tags
        content = content.replace('<!DOCTYPE html>', '')
        content = content.replace('<html>', '').replace('</html>', '')
        content = content.replace('<head>', '').replace('</head>', '')
        content = content.replace('<body>', '').replace('</body>', '')
        
        logger.info("Generated Gemini global response using agent")
        return content.strip()
        
    except Exception as e:
        logger.error(f"Error generating Gemini global response: {str(e)}")
        # Return a formatted error message
        return f"""
        <div class="prose max-w-none text-gray-800 text-base leading-relaxed">
            <p>I apologize, but I encountered an error while processing your request. Please try again.</p>
            <h3>Sources</h3>
            <ul>
                <li><a href="https://gemini.google.com" target="_blank" rel="noopener noreferrer">Gemini AI General Knowledge Base</a></li>
            </ul>
            <p class="text-sm text-gray-600 italic mt-2">
                <svg class="inline-block w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
                </svg>
                This response is generated by Gemini AI from general knowledge, not from your document knowledge base.
            </p>
        </div>
        """

def get_all_source_file_ids(collection_id: int, db: Session) -> List[int]:
    """
    Get all document IDs associated with a collection.
    
    Args:
        collection_id: The ID of the collection
        db: Database session
        
    Returns:
        List of document IDs
    """
    try:
        # Query the collection_document_association table to get all document IDs
        document_ids = db.query(collection_document_association.c.document_id).filter(
            collection_document_association.c.collection_id == collection_id
        ).all()
        
        # Extract IDs from the result
        return [doc_id[0] for doc_id in document_ids]
    except Exception as e:
        logger.error(f"Error fetching document IDs for collection {collection_id}: {str(e)}")
        return []

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
    prompt = f"""
            You are an expert in semantic search and information retrieval.  
            Your task is to take a raw user query and expand it into a more detailed, context-aware query that will produce the best results when used with vector similarity search.

            Guidelines:
            1. Preserve the exact intent of the query — do not interpret beyond what is stated or clearly implied.
            2. Add only relevant domain-specific terms, synonyms, or closely related keywords that align with the user's intent.
            3. Convert incomplete, vague, or shorthand queries into clear, full sentences without altering meaning.
            4. If the query is a question, rephrase it into a neutral, search-style statement.
            5. Do not introduce new topics, drugs, processes, or concepts that were not mentioned or implied.
            6. Output only the enhanced query itself. Do not include explanations, examples, or any other text.

            Example Transformations:
            - Input: "side effects"  
            Output: "Information about side effects of the drug."

            - Input: "FDA approval process"  
            Output: "Information on the FDA approval process for drugs."

            - Input: "compare ibrutinib and acalabrutinib"  
            Output: "Comparison between ibrutinib and acalabrutinib."

            - Input: "treatment for hypertension"  
            Output: "Information on treatments for hypertension."

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

# ===========================
# Define the Agent Factory Function
# ===========================

def get_agentic_rag_agent(   
    session_id: Optional[str] = None,
    collection_name: Optional[str] = None,
    debug_mode: bool = False,
    n_results:int=30,
    filters: Optional[Dict[str, Any]] = None
) -> Agent:
    """
    Get an Agentic RAG Agent with Memory and Knowledge Base.
    
    Args:       
        session_id: Session identifier for persistent conversations
        collection_name: Vector database collection name for knowledge base
        debug_mode: Enable debug mode for agent
        n_results: Number of documents to retrieve
        filters: Optional Qdrant filters to apply during search
    
    Returns:
        Configured Agent instance
    """
    
    # Create knowledge base if collection_name is provided
    knowledge_base = None
    if collection_name:
        try:
            # Configure vector database with standard Agno Qdrant
            vector_db = Qdrant(
                collection=collection_name,
                embedder=GeminiEmbedder(id="models/text-embedding-004"),
                url=f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
            )            
            # Create knowledge base with dynamic document count
            if filters:
                logger.info(f"Creating FilteredAgentKnowledge with filters: {filters}")
                knowledge_base = FilteredAgentKnowledge(
                    vector_db=vector_db,
                    num_documents=n_results,
                    filters=filters
                )
            else:
                logger.info("Creating standard AgentKnowledge without filters")
                knowledge_base = AgentKnowledge(
                    vector_db=vector_db,
                    num_documents=n_results,
                )
            logger.info(f"Knowledge base configured for collection: {collection_name}")            
                
        except Exception as e:
            logger.error(f"Failed to configure knowledge base: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Continue without knowledge base
    
    logger.info(f"Creating agent with knowledge_base: {knowledge_base is not None}, session_id: {session_id}")
    
    # Create and return the agent
    return Agent(
        name="FDA/EMA Document Agent",
        session_id=session_id,
        model=Gemini(id="gemini-2.5-flash"),
        add_references=True,
        add_history_to_messages=True,
        storage=SqliteAgentStorage(
            table_name='agent_sessions',
            db_file='storage/agent_storage.db'
        ),
        knowledge=knowledge_base,
        markdown=True,
        search_knowledge=True if knowledge_base else False,
        show_tool_calls=debug_mode,
        debug_mode=debug_mode,
        add_datetime_to_instructions=True,
        tools=[count_documents_in_collection],
        instructions=[
            "You are an advanced Retrieval-Augmented Generation (RAG) agent specializing in FDA and EMA regulatory documents.",
            "Your goals are: (1) understand the user query, (2) retrieve the most relevant evidence, and (3) synthesize a precise, regulatory-grade response.",
            "",
            "CRITICAL: For queries about document counts, collection size, or 'how many documents', you MUST use the count_documents_in_collection tool instead of searching.",
            "",
            "Document Counting Capabilities:",
            "   - IMPORTANT: When asked about document counts, collection size, or how many documents exist, ALWAYS use the count_documents_in_collection tool.",
            "   - DO NOT search for documents about counts - use the tool directly.",
            "   - The tool will automatically use the current collection unless specified otherwise.",
            "   - You can count all documents in a collection or filter by source file.",
            "   - You can provide breakdowns by source file when requested.",
            "   - Example queries that MUST use count_documents_in_collection:",
            "     • 'How many documents are in this collection?' → count_documents_in_collection()",
            "     • 'How many documents are there?' → count_documents_in_collection()",
            "     • 'What is the collection size?' → count_documents_in_collection()",
            "     • 'How many documents are from keytruda.pdf?' → count_documents_in_collection(filter_by_source='keytruda.pdf')",
            "     • 'Show me a breakdown of documents by source file' → count_documents_in_collection(group_by_source=True)",
            "",
            "Citation Rules:",
            "   - DO NOT use numeric inline citations like [1], [2], etc.",
            "   - At the END of every response, add a 'Sources' section.",
            "   - Each source must appear ONLY ONCE.",
            "   - Format the sources section in valid semantic HTML as follows:",
            "     <h3>Sources</h3>",
            "     <ul>",
            "       <li><a href=\"{{file_url}}\" target=\"_blank\" rel=\"noopener noreferrer\">{{source}}</a></li>",
            "     </ul>",
            "   - Use the human-readable filename from metadata ('source') as the link text.",
            "   - Ensure the link opens in a new tab.",
            "",
            "Response Quality:",
            "   - Base all answers solely on retrieved evidence; never hallucinate.",
            "   - If no evidence is found, state clearly: 'No relevant evidence found in the knowledge base.'",
            "   - Include short direct quotes from documents when useful.",
            "   - When query includes efficacy details, provide the efficaty details in table format for better readability.",
            "   - For counting queries, provide exact numbers from the count_documents_in_collection tool.",
            "   - When responding to document count queries:",
            "     • DO NOT include source citations or source details",
            "     • DO NOT perform document searches",
            "     • Simply report the count numbers directly",
            "     • Focus only on the numerical results",
            

            "",
            "Formatting Rules:",
            "   - Responses MUST be in valid semantic HTML only.",
            "   - Wrap ALL content inside:",
            "     <div class=\"prose max-w-none text-gray-800 text-base leading-relaxed\"> ... </div>",
            "   - Use semantic tags (<p>, <ul>, <li>, <table>, <h2>, <h3>, etc.).",
            "   - Prefer structured formats: bullet points, numbered lists, or tables.",
            "   - Tables must use Tailwind-safe minimal classes:",
            "     <table class=\"min-w-full border-collapse border border-gray-300\"> ... </table>",
            "   - Do NOT add inline styles, global CSS, or extra classes.",
            "   - Do NOT include raw URLs or localhost paths in the body; only show them properly formatted in 'Sources'.",
            "   - When presenting document counts, use clear formatting (tables or lists).",
            "",
            "Professional Standards:",
            "   - Never reveal internal tools or parameters.",
            "   - Ensure accuracy, regulatory clarity, and completeness.",
            "   - Structure your response clearly with appropriate headings where needed.",
            "   - Never leak raw URLs paths in the body (only in Sources).",
            "   - Ensure the respones are formatted with proper headings wherever required.",
            "   - Always respond in English with professional tone."
        ]
    )




# ===========================
# New FastAPI Endpoint using the Agent
# ===========================

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(tags=["agentic-rag"])

class QueryRequest(BaseModel):
    source_file_ids: Optional[List[int]] = None
    collection_id: Optional[int] = None
    query: str
    session_id: str
    user_id: int
    model_id: Optional[str] = "google:gemini-2.0-flash-exp"  # Default model
    global_search: bool = False  # Default to false for backward compatibility
    docXChat: bool = False

@router.post("/query-multiple")
async def query_agentic(
    request: QueryRequest,
    db: Session = Depends(get_db)
):
    """
    Queries documents using an Agno agent for a more dynamic and intelligent RAG process.
    """
    try:

        from database.database import Collection, collection_document_association    
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
        logger.info(f"Request flags - docXChat: {request.docXChat}, global_search: {request.global_search}")
        
        # Check collection document count
        #try:
        #    qdrant_util = QdrantUtil.get_instance()
        #    collection_stats = qdrant_util.get_collection_stats(collection.vector_db_collection_name)
        #    logger.info(f"Collection stats: {collection_stats}")
        #except Exception as e:
        #    logger.warning(f"Could not get collection stats: {e}")
        # Step 1: Initialize Chat and get collection details

        #enhanced_query = request.query
        enhanced_query = await _enhance_query_with_context_v3(request.query)
        logger.info(f"Enhanced query from '{request.query}' to '{enhanced_query}'")
        
        file_name_filter = None
        
        # Check if docXChat flag is set
        if request.docXChat and request.source_file_ids is not None and len(request.source_file_ids) > 0:
            # For docXChat with source_file_ids, get file names directly from the database
            logger.info(f"docXChat mode: Getting file names for source_file_ids: {request.source_file_ids}")
            
            #if len(request.source_file_ids) == 1 and request.source_file_ids[0] == 0:
            #    logger.info(f"Detected source_file_ids = [0], fetching all documents for collection {collection.id}")
            #    request.source_file_ids = get_all_source_file_ids(collection.id, db)
            #    logger.info(f"Retrieved {len(request.source_file_ids)} document IDs from collection")
            # Get the file names for the provided source_file_ids
            source_files = db.query(SourceFiles).filter(
                SourceFiles.id.in_(request.source_file_ids)
            ).all()
            
            if source_files:
                relevant_files = [sf.file_name for sf in source_files]
                logger.info(f"docXChat: Found {len(relevant_files)} files directly from source_file_ids")
                logger.info(f"docXChat: File names: {relevant_files}")
                file_name_filter = {"source": {"$in": relevant_files}}  # FilteredAgentKnowledge will add meta_data prefix
            else:
                logger.warning(f"docXChat: No files found for source_file_ids: {request.source_file_ids}")
        else:
            # Existing logic for non-docXChat requests
            logger.info("Using standard file matching logic")
            from utils.drug_file_matcher import DrugFileMatcher
            relevant_files = await DrugFileMatcher.extract_relevant_files_for_query(
                enhanced_query,
                collection_id=request.collection_id,
                source_file_ids=request.source_file_ids,    
                db=db
            )

            if relevant_files:
                logger.info(f"Document query: Applying file filter for {len(relevant_files)} files: {relevant_files[:3]}...")
                # Convert list of filenames to proper metadata filter for Qdrant
                file_name_filter = {"source": {"$in": relevant_files}}  # FilteredAgentKnowledge will add meta_data prefix


        # Step 2: Use the Agent to get the response
        # Store context in global variables for tools to access
        # (This is a workaround since agno doesn't support passing context to tools easily)
        global _current_collection_name, _current_original_query
        _current_collection_name = collection.vector_db_collection_name
        _current_original_query = request.query
        
        # Get dynamic document count based on query
        n_results, _ = _get_dynamic_doc_counts(request.query)
        
        # Create agent with dynamic configuration and filters
        rag_agent = get_agentic_rag_agent(           
            session_id=request.session_id,
            collection_name=collection.vector_db_collection_name,
            debug_mode=False,  # Enable debug mode to see tool calls
            n_results=n_results,
            filters=file_name_filter  # Pass filters to agent creation
        )

        logger.info("Agent created successfully")        

        # Log filter details for debugging
        #logger.info(f"file_name_filter type: {type(file_name_filter)}")
        logger.info(f"file_name_filter value: {file_name_filter}")
        
        # Try running the agent - no need to pass knowledge_filters anymore
        agent_response = None
        try:
            logger.info(f"Attempting to run agent with query: {enhanced_query[:100]}...")
            logger.info(f"Original query: {request.query}")
            logger.info(f"Full enhanced query: {enhanced_query}")
            
            # Run agent without knowledge_filters parameter since filters are now built into the knowledge base
            logger.info("Running agent with filters embedded in knowledge base")
            agent_response = await rag_agent.arun(
                enhanced_query,
                stream=False
            )
            
            logger.info(f"Agent response received successfully")
            logger.info(f"Agent response type: {type(agent_response)}")
            
            # Debug: Check if knowledge was used
            #if hasattr(agent_response, 'knowledge_used'):
            #    logger.info(f"Knowledge used: {agent_response.knowledge_used}")
            
            # Debug: Check tool calls
            #if hasattr(agent_response, 'tool_calls'):
            #    logger.info(f"Tool calls made: {len(agent_response.tool_calls) if agent_response.tool_calls else 0}")
            
            # Debug: Check messages
            #if hasattr(agent_response, 'messages'):
            #    for i, msg in enumerate(agent_response.messages):
            #        logger.debug(f"Message {i}: role={getattr(msg, 'role', 'unknown')}, content_length={len(str(getattr(msg, 'content', '')))}")
                    
        except Exception as e:
            logger.error(f"Error during agent.arun: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Extract the actual content from the RunResponse object
        result = ""
        try:
            if hasattr(agent_response, 'messages') and agent_response.messages:
                logger.info(f"Response has messages attribute with {len(agent_response.messages)} messages")
                # Get the last message content
                for i, message in enumerate(agent_response.messages):
                    logger.debug(f"Processing message {i}: type={type(message)}")
                    if hasattr(message, 'content') and message.content:
                        result = str(message.content)
                        logger.debug(f"Found content in message {i}: {result[:100]}...")
            elif hasattr(agent_response, 'content'):
                logger.info("Response has content attribute")
                result = str(agent_response.content)
            elif isinstance(agent_response, str):
                logger.info("Response is a string")
                result = agent_response
            else:
                # Log all attributes to understand the response structure
                logger.warning(f"Unable to extract content. Response attributes: {dir(agent_response)}")
                result = str(agent_response)
        except Exception as e:
            logger.error(f"Error extracting response content: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            result = "Error processing agent response"
            
        logger.info(f"Total response length: {len(result)} characters")

        # Validate response when global_search is enabled
        if request.global_search:
            logger.info("Global search enabled - validating response for relevant data")
            if not _validate_response_has_data(result):
                logger.warning("No data found in knowledgebase - falling back to Gemini global knowledge")
                # Get response from Gemini's general knowledge
                result = await _get_gemini_global_response(request.query, request.session_id)
                logger.info("Generated response from Gemini global knowledge")

        # Step 3: Log and format the final response
        chat_id = FDAChatManagementService.save_chat_request(
            user_id=request.user_id,
            user_query=request.query,
            session_id=request.session_id,
            request_details={
                "query_type": "agentic", 
                "collection_name": collection.name,
                "global_search": request.global_search,
                "docXChat": request.docXChat,
                "source_file_count": len(request.source_file_ids) if request.source_file_ids else 0
            },
            db=db
        )
        
        # Force commit after saving the chat request to ensure it's persisted
        db.commit()
        logger.info(f"Chat request saved successfully with ID: {chat_id}")

        result = result.replace("http://34.9.3.61/", "https://dxdemo.rxinsightx.com/")

        formatted_result = {
            "user_query": request.query,
            "response": result, # Agent's final response
            "cited_response": result, # For simplicity, citation logic is handled by the agent's prompt
            "query_type": "agentic",
            "collection_name": collection.name,
            "source_documents": [], # The agent's output does not provide raw docs, but could be part of the tool's return.
            "content_type": "text/markdown" # The LLM will provide text, which could be converted later
        }

        formatted_result["response"] = result
        formatted_result["content_type"] = "html"  # Indicate HTML content


        #if formatted_result.get("response"):
        #   logger.info(f"Converting response to HTML for query-multiple-v2 endpoint")
        #   html_response = _convert_response_to_html_unified(formatted_result["response"], request.query)
        #   formatted_result["response"] = html_response
        #   formatted_result["content_type"] = "html"  # Indicate HTML content

        FDAChatManagementService.update_chat_response(
            chat_id=chat_id,
            response_details=formatted_result,
            db=db
        )
        
        # Force commit after updating the chat response to ensure it's persisted
        db.commit()
        logger.info(f"Chat response updated successfully for ID: {chat_id}")
        
        formatted_result["chat_id"] = chat_id
        return formatted_result

    except Exception as e:
        logger.error(f"Error in agentic RAG endpoint: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Rollback the database session on error
        try:
            db.rollback()
            logger.info("Database session rolled back due to error")
        except Exception as rollback_error:
            logger.error(f"Error during rollback: {rollback_error}")
        
        # Provide more detailed error message
        error_detail = {
            "error": str(e),
            "type": type(e).__name__,
            "message": "An error occurred while processing your query. Please check the logs for details."
        }
        raise HTTPException(status_code=500, detail=error_detail)