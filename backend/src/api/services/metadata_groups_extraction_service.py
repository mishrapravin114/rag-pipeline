"""
Metadata Groups Extraction Service - Handles background processing of metadata extraction jobs for collections
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import json
import traceback
import time

# Agno imports for agent-based approach
from agno.agent import Agent
from agno.models.google import Gemini
from agno.vectordb.qdrant import Qdrant
from agno.embedder.google import GeminiEmbedder
from qdrant_client import QdrantClient
from agno.knowledge.agent import AgentKnowledge

# Local imports
from database.database import get_db_session
from utils.llm_util import get_llm, get_embeddings_function
from utils.qdrant_util import QdrantUtil
from utils.filtered_agent_knowledge_qdrant import FilteredAgentKnowledge
# WebSocket removed - using polling instead
from langchain_core.messages import HumanMessage
from config.settings import settings

logger = logging.getLogger(__name__)


def get_agentic_rag_agent(   
    session_id: Optional[str] = None,
    collection_name: Optional[str] = None,
    debug_mode: bool = False,
    n_results: int = 30,
    filters: Optional[Dict[str, Any]] = None
) -> Agent:
    """
    Get an Agentic RAG Agent with Knowledge Base for metadata extraction.
    Based on the pattern from multi_chat.py
    
    Args:       
        session_id: Session identifier for persistent conversations
        collection_name: Qdrant collection name for knowledge base
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
            # Configure vector database with Qdrant
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
            # Continue without knowledge base
    
    # Configure the agent with specific instructions for metadata extraction
    agent = Agent(
        name="metadata-extraction-agent",
        model=Gemini(id="gemini-2.5-flash"),
        instructions=[
            "You are a metadata extraction specialist for FDA entity label documents.",
            "Your task is to extract specific information when asked.",
            "IMPORTANT: You have access to a knowledge base that will automatically search for relevant information.",
            "When you receive a question, search the knowledge base and extract the requested information.",
            "Guidelines:",
            "- If the information is found, provide ONLY the extracted value",
            "- Do not add explanations, context, or additional text",
            "- If the information is not found in the search results, respond with exactly 'Not Found'",
            "- Be precise and extract the exact information requested",
            "- For dates, use the format found in the document",
            "- For entity names, use the brand name or generic name as requested"
        ],
        knowledge=knowledge_base,
        search_knowledge=True,
        markdown=False,  # Disable markdown for cleaner extraction
        debug_mode=debug_mode,
        show_tool_calls=debug_mode
    )
    
    return agent


# Note: Removed obsolete functions - now using agent-based approach
# The following functions were removed:
# - get_qdrant_collection() - no longer needed as agent handles Qdrant
# - search_relevant_chunks() - agent performs the search internally
# - extract_metadata_with_agent() - agent handles extraction directly


def extract_agent_response(agent_response) -> str:
    """
    Extract the actual content from agent response.
    Based on the pattern from multi_chat.py
    
    Args:
        agent_response: Response from agent.arun()
        
    Returns:
        Extracted content as string
    """
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
    
    logger.info(f"Extracted response length: {len(result)} characters")
    return result.strip()


async def enhance_query_for_metadata(query: str, metadata_name: str, llm) -> str:
    """
    Enhance the query for better vector search results.
    
    Args:
        query: Original extraction prompt
        metadata_name: Name of the metadata field
        llm: Language model instance
        
    Returns:
        Enhanced query for vector search
    """
    try:
        logger.info(f"Enhancing query for metadata: {metadata_name}")
        logger.debug(f"Original query: {query}")
        
        # For metadata extraction, create a single cohesive query
        enhancement_prompt = f"""
        You need to create ONE single search query to find information about "{metadata_name}" in an FDA entity label document.
        
        Original extraction instruction: {query}
        
        IMPORTANT: 
        - Create ONE complete sentence or question, not a list of terms
        - Do not use quotes or separate terms with commas
        - Make it a natural query that covers all aspects mentioned in the extraction instruction
        - The query should read like a single question or statement
        
        Examples of good queries:
        - "What is the entity's name, manufacturer, approval date and active ingredients?"
        - "What are the clinical efficacy results and trial outcomes for this medication?"
        - "What safety warnings and contraindications are listed for this entity?"
        
        Examples of bad queries (DO NOT DO THIS):
        - "Entity name" "Manufacturer" "Approval date"
        - Entity name, manufacturer, approval date
        - Name. Manufacturer. Date.
        
        Output only the single query sentence, nothing else.
        """
        
        logger.debug("Calling LLM for query enhancement...")
        response = await llm.ainvoke([HumanMessage(content=enhancement_prompt)])
        enhanced = response.content.strip() if response.content else query
        
        # Ensure it's a proper question
        if enhanced and not enhanced.endswith('?'):
            enhanced += '?'
        
        logger.info(f"Enhanced query for {metadata_name}: {enhanced}")
        return enhanced
        
    except Exception as e:
        logger.error(f"Error enhancing query: {str(e)}")
        logger.exception("Full traceback:")
        # Create a simple fallback question
        fallback = f"What is the {metadata_name} of this entity?"
        logger.warning(f"Using fallback query: {fallback}")
        return fallback


async def process_metadata_extraction(
    extraction_job_id: int,
    collection_id: int,
    group_id: int,
    document_ids: List[int],
    user_id: int
):
    """
    Process metadata extraction job in background.
    
    Args:
        extraction_job_id: ID of the extraction job record
        collection_id: ID of the collection
        group_id: ID of the metadata group
        document_ids: List of document IDs to process
        user_id: ID of the user who initiated the job
    """
    db = None
    try:
        # Get database session
        db = get_db_session()
        
        # Update job status to processing
        update_job = text("""
            UPDATE collection_extraction_jobs 
            SET status = 'processing', started_at = CURRENT_TIMESTAMP
            WHERE id = :job_id
        """)
        db.execute(update_job, {"job_id": extraction_job_id})
        db.commit()
        
        # Get collection vector database name
        collection_query = text("""
            SELECT vector_db_collection_name
            FROM collections
            WHERE id = :collection_id
        """)
        collection_result = db.execute(collection_query, {"collection_id": collection_id}).fetchone()
        
        if not collection_result or not collection_result.vector_db_collection_name:
            raise Exception(f"Collection {collection_id} not found or has no vector database collection")
        
        qdrant_collection_name = collection_result.vector_db_collection_name
        logger.info(f"Using Qdrant collection: {qdrant_collection_name}")
        
        # Note: We'll create agents per document with filters, so we don't need to check collection here
        logger.info(f"Will use agent-based approach with vector database collection: {qdrant_collection_name}")
        
        # Get metadata configurations for the group
        metadata_configs_query = text("""
            SELECT 
                mc.id,
                mc.metadata_name,
                mc.description,
                mc.extraction_prompt,
                mc.data_type,
                mc.validation_rules,
                mgc.display_order
            FROM metadata_group_configs mgc
            JOIN MetadataConfiguration mc ON mgc.config_id = mc.id
            WHERE mgc.group_id = :group_id
            ORDER BY mgc.display_order, mc.metadata_name
        """)
        
        metadata_configs = db.execute(metadata_configs_query, {"group_id": group_id}).fetchall()
        
        if not metadata_configs:
            raise Exception("No metadata configurations found in group")
        
        # Initialize LLM
        llm = get_llm()
        
        # Process each document
        processed_count = 0
        failed_count = 0
        
        for doc_index, doc_id in enumerate(document_ids):
            try:
                logger.info(f"Processing document {doc_index + 1}/{len(document_ids)}: ID={doc_id}")
                
                # Get document content
                doc_query = text("""
                    SELECT id, file_name, entity_name, extracted_content
                    FROM SourceFiles
                    WHERE id = :doc_id
                """)
                document = db.execute(doc_query, {"doc_id": doc_id}).fetchone()
                
                if not document:
                    logger.warning(f"Document {doc_id} not found")
                    failed_count += 1
                    continue
                
                logger.info(f"Document found: {document.file_name} (entity: {document.entity_name})")
                
                # Progress is now tracked via database polling instead of WebSocket
                logger.info(f"Processing document {doc_index + 1}/{len(document_ids)}: {document.file_name}")
                
                # Create ONE agent for this document that will be reused for all metadata fields
                # Note: Qdrant uses 'source' as the metadata field for file names
                file_name_filter = {"source": {"$eq": document.file_name}}
                logger.info(f"Creating single agent for document with file filter: {file_name_filter}")
                
                try:
                    document_agent = get_agentic_rag_agent(
                        collection_name=qdrant_collection_name,
                        n_results=25,  # Use 25 chunks as requested
                        filters=file_name_filter,
                        debug_mode=False
                    )
                    logger.info("Document agent created successfully")
                except Exception as agent_creation_error:
                    logger.error(f"Failed to create agent for document {doc_id}: {str(agent_creation_error)}")
                    failed_count += 1
                    continue
                
                # Extract metadata for each configuration using the same agent
                for config in metadata_configs:
                    try:
                        logger.info(f"Extracting metadata: {config.metadata_name}")
                        logger.debug(f"Extraction prompt: {config.extraction_prompt}")
                        
                        # Enhance query for better search results
                        enhanced_query = await enhance_query_for_metadata(
                            config.extraction_prompt,
                            config.metadata_name,
                            llm
                        )
                        
                        logger.info(f"Enhanced query for {config.metadata_name}: {enhanced_query}")
                        
                        logger.info(f"Running agent with query: {enhanced_query[:100]}...")
                        
                        # Run the document agent to extract metadata with retry logic
                        max_retries = 3
                        retry_delay = 2.0  # Start with 2 seconds
                        agent_response = None
                        
                        for attempt in range(max_retries):
                            try:
                                logger.info(f"Attempt {attempt + 1}/{max_retries} for {config.metadata_name}")
                                agent_response = await document_agent.arun(
                                    enhanced_query,
                                    stream=False
                                )
                                logger.info("Agent response received successfully")
                                break  # Success, exit retry loop
                                
                            except Exception as retry_error:
                                error_str = str(retry_error)
                                if "503" in error_str or "Service Unavailable" in error_str:
                                    if attempt < max_retries - 1:
                                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                        logger.warning(f"Got 503 error, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                                        await asyncio.sleep(wait_time)
                                    else:
                                        logger.error(f"Failed after {max_retries} attempts: {error_str}")
                                        raise
                                else:
                                    # Non-503 error, don't retry
                                    logger.error(f"Non-retryable error: {error_str}")
                                    raise
                        
                        if agent_response is None:
                            raise Exception("Failed to get agent response after all retries")
                        
                        # Extract the actual content from agent response
                        extracted_value = extract_agent_response(agent_response)
                        
                        # Clean up the extracted value
                        extracted_value = extracted_value.strip()
                        
                        # Handle multi-line "Not Found" responses
                        if "Not Found" in extracted_value:
                            extracted_value = "Not Found"
                        
                        # Remove any extra whitespace and newlines
                        extracted_value = ' '.join(extracted_value.split())
                        
                        logger.info(f"extracted_value: {extracted_value[:100]}...")

                        # If empty or very short response, treat as not found
                        if not extracted_value or len(extracted_value) < 2:
                            extracted_value = "Not Found"
                        
                        logger.info(f"Preparing to save {config.metadata_name}: {extracted_value[:100]}...")
                        
                        # Validate if validation rules provided (JSON format expected)
                        if config.validation_rules and extracted_value != "Not Found":
                            try:
                                import re
                                import json
                                rules = json.loads(config.validation_rules) if isinstance(config.validation_rules, str) else config.validation_rules
                                if 'regex' in rules:
                                    if not re.match(rules['regex'], extracted_value):
                                        extracted_value = rules.get('default', "Invalid Format")
                            except Exception as e:
                                logger.warning(f"Failed to parse validation rules: {e}")
                        
                        # Store extracted metadata - will update if already exists
                        # First try to update existing record
                        update_metadata = text("""
                            UPDATE collection_extracted_metadata
                            SET extracted_value = :value,
                                extraction_job_id = :job_id,
                                extracted_by = :user_id,
                                extracted_at = CURRENT_TIMESTAMP
                            WHERE collection_id = :collection_id
                            AND document_id = :doc_id
                            AND group_id = :group_id
                            AND metadata_name = :metadata_name
                        """)
                        
                        result = db.execute(update_metadata, {
                            "collection_id": collection_id,
                            "doc_id": doc_id,
                            "group_id": group_id,
                            "job_id": extraction_job_id,
                            "metadata_name": config.metadata_name,
                            "value": extracted_value,
                            "user_id": user_id
                        })
                        
                        # If no rows were updated, insert new record
                        if result.rowcount == 0:
                            insert_metadata = text("""
                                INSERT INTO collection_extracted_metadata
                                (collection_id, document_id, group_id, extraction_job_id, 
                                 metadata_name, extracted_value, extracted_by)
                                VALUES (:collection_id, :doc_id, :group_id, :job_id,
                                        :metadata_name, :value, :user_id)
                            """)
                            
                            db.execute(insert_metadata, {
                                "collection_id": collection_id,
                                "doc_id": doc_id,
                                "group_id": group_id,
                                "job_id": extraction_job_id,
                                "metadata_name": config.metadata_name,
                                "value": extracted_value,
                                "user_id": user_id
                            })
                            logger.info(f"Inserted new metadata: {config.metadata_name} for document {doc_id}")
                        else:
                            logger.info(f"Updated existing metadata: {config.metadata_name} for document {doc_id}")
                        
                        # Commit after each successful metadata save to ensure data is persisted
                        db.commit()
                        logger.info(f"Committed {config.metadata_name} to database")
                        
                        # Add a delay to avoid rate limiting (increased from 0.5 to 1.0)
                        await asyncio.sleep(1.0)
                        
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Error extracting {config.metadata_name} for doc {doc_id}: {error_msg}")
                        
                        # If it's a 503 error after retries, mark as "Service Unavailable"
                        if "503" in error_msg or "Service Unavailable" in error_msg:
                            extracted_value = "Service Unavailable"
                            # Store the error status
                            try:
                                # First try to update
                                update_result = db.execute(text("""
                                    UPDATE collection_extracted_metadata
                                    SET extracted_value = :value,
                                        extraction_job_id = :job_id,
                                        extracted_by = :user_id,
                                        extracted_at = CURRENT_TIMESTAMP
                                    WHERE collection_id = :collection_id
                                    AND document_id = :doc_id
                                    AND group_id = :group_id
                                    AND metadata_name = :metadata_name
                                """), {
                                    "collection_id": collection_id,
                                    "doc_id": doc_id,
                                    "group_id": group_id,
                                    "job_id": extraction_job_id,
                                    "metadata_name": config.metadata_name,
                                    "value": extracted_value,
                                    "user_id": user_id
                                })
                                
                                # If no update, insert
                                if update_result.rowcount == 0:
                                    db.execute(text("""
                                        INSERT INTO collection_extracted_metadata
                                        (collection_id, document_id, group_id, extraction_job_id, 
                                         metadata_name, extracted_value, extracted_by)
                                        VALUES (:collection_id, :doc_id, :group_id, :job_id,
                                                :metadata_name, :value, :user_id)
                                    """), {
                                        "collection_id": collection_id,
                                        "doc_id": doc_id,
                                        "group_id": group_id,
                                        "job_id": extraction_job_id,
                                        "metadata_name": config.metadata_name,
                                        "value": extracted_value,
                                        "user_id": user_id
                                    })
                                
                                db.commit()
                                logger.info(f"Saved 'Service Unavailable' status for {config.metadata_name}")
                            except Exception as db_error:
                                logger.error(f"Failed to store error status: {str(db_error)}")
                        
                        # Add longer delay on error to avoid rate limiting
                        await asyncio.sleep(2.0)
                        # Continue with next metadata field
                
                # Note: We're committing after each field, so no need for a final commit here
                processed_count += 1
                
                # Update job progress
                update_progress = text("""
                    UPDATE collection_extraction_jobs
                    SET processed_documents = :processed
                    WHERE id = :job_id
                """)
                db.execute(update_progress, {
                    "processed": processed_count,
                    "job_id": extraction_job_id
                })
                db.commit()
                
            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {str(e)}")
                failed_count += 1
                continue
        
        # Update job as completed
        # Use 'failed' status if there were any failures, otherwise 'completed'
        final_status = "completed" if failed_count == 0 else "failed"
        complete_job = text("""
            UPDATE collection_extraction_jobs
            SET status = :status,
                completed_at = CURRENT_TIMESTAMP,
                processed_documents = :processed,
                failed_documents = :failed
            WHERE id = :job_id
        """)
        
        db.execute(complete_job, {
            "status": final_status,
            "processed": processed_count,
            "failed": failed_count,
            "job_id": extraction_job_id
        })
        db.commit()
        
        # Job completion is tracked in database
        logger.info(f"Extraction job {extraction_job_id} completed with status: {final_status}")
        
        logger.info(f"Extraction job {extraction_job_id} completed. Processed: {processed_count}, Failed: {failed_count}")
        
    except Exception as e:
        logger.error(f"Error in metadata extraction job {extraction_job_id}: {str(e)}")
        
        # Update job as failed
        if db:
            try:
                fail_job = text("""
                    UPDATE collection_extraction_jobs
                    SET status = 'failed',
                        completed_at = CURRENT_TIMESTAMP,
                        error_details = :error
                    WHERE id = :job_id
                """)
                db.execute(fail_job, {
                    "error": str(e)[:500],
                    "job_id": extraction_job_id
                })
                db.commit()
            except:
                pass
        
        # Error status is tracked in database
        logger.error(f"Extraction job {extraction_job_id} failed")
            
    finally:
        if db:
            db.close()

# Extraction status check function
async def get_extraction_job_status(job_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """Get the status of an extraction job."""
    try:
        query = text("""
            SELECT 
                cej.id,
                cej.collection_id,
                cej.group_id,
                cej.status,
                cej.total_documents,
                cej.processed_documents,
                cej.failed_documents,
                cej.created_at,
                cej.started_at,
                cej.completed_at,
                cej.error_details,
                mg.name as group_name
            FROM collection_extraction_jobs cej
            JOIN metadata_groups mg ON cej.group_id = mg.id
            WHERE cej.id = :job_id
        """)
        
        result = db.execute(query, {"job_id": job_id}).fetchone()
        
        if not result:
            return None
        
        progress_percentage = 0
        if result.total_documents > 0:
            progress_percentage = round(
                (result.processed_documents / result.total_documents) * 100, 2
            )
        
        return {
            "job_id": result.id,
            "collection_id": result.collection_id,
            "group_id": result.group_id,
            "group_name": result.group_name,
            "status": result.status,
            "total_documents": result.total_documents,
            "processed_documents": result.processed_documents,
            "failed_documents": result.failed_documents or 0,
            "progress_percentage": progress_percentage,
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_details": result.error_details
        }
        
    except Exception as e:
        logger.error(f"Error getting extraction job status: {str(e)}")
        return None