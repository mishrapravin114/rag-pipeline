from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, distinct
from database.database import FDAExtractionResults, ChatHistory, SourceFiles, EntitySections, SearchHistory, Collection, collection_document_association
from utils.qdrant_util import QdrantUtil
from utils.llm_util import get_embeddings_model
from api.services.analytics_service import AnalyticsService
import collections
import re
import json
import ast
import logging
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)

class FDAChatManagementService:
    
    @staticmethod
    async def search_fda_documents(
        search_query: str,
        user_id: int,
        entity_name: Optional[str] = None,
        collection_id: Optional[int] = None,
        source_file_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        db: Session = None
    ) -> Dict[str, Any]:
        """Search for FDA documents using SourceFiles table with SQL first, then vector search fallback."""
        logger.info(f"Searching FDA documents with query: {search_query}, entity_name filter: {entity_name}, collection_id: {collection_id}, source_file_id: {source_file_id}")
        
        start_time = datetime.now()
        
        try:
            # Get collection name for vector database operations
            vector_db_collection_name = "fda_documents"  # Default fallback
            if collection_id:
                collection = db.query(Collection).filter(Collection.id == collection_id).first()
                if collection and collection.vector_db_collection_name:
                    vector_db_collection_name = collection.vector_db_collection_name
                    logger.info(f"Using vector database collection: {vector_db_collection_name}")
                else:
                    logger.warning(f"Collection {collection_id} not found or has no vector_db_collection_name, using default")
            
            # Prepare filters for analytics tracking
            filters = {}
            if entity_name:
                filters["entity_name"] = entity_name
            if collection_id:
                filters["collection_id"] = collection_id
            if source_file_id:
                filters["source_file_id"] = source_file_id
            
            # If source_file_id and query are provided, search within that specific document
            if source_file_id and search_query.strip():
                logger.info(f"Source file ID and query provided - searching within specific document")
                
                # Get the file details
                source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
                
                if not source_file:
                    logger.info(f"No file found with ID: {source_file_id}")
                    # Track search with no results
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    await AnalyticsService.track_search(
                        db=db,
                        username=str(user_id),
                        search_query=search_query,
                        search_type="Vector",
                        filters=filters,
                        results_count=0,
                        execution_time_ms=int(execution_time)
                    )
                    
                    return {
                        "success": True,
                        "results": [],
                        "search_type": "Vector",
                        "total_results": 0,
                        "message": f"No document found with ID {source_file_id}"
                    }
                
                # Use search_with_grading with specific file filter
                # For vector search, we get more results initially then paginate
                vector_results = FDAChatManagementService.search_with_grading(
                    query=search_query,
                    collection_name=vector_db_collection_name,
                    n_results=max(100, limit + offset),  # Get enough results for pagination
                    db=db,
                    metadata_filter={"source": source_file.file_name}
                )
                
                # Transform vector results to match our standard format
                results = []
                for result in vector_results:
                    # Ensure the result is from our target file
                    if result.get("file_name") == source_file.file_name:
                        # Ensure relevance score is between 0 and 100
                        raw_score = result.get("relevance_score", 0)
                        if raw_score > 1:  # Already in percentage
                            relevance_score = min(raw_score, 100)
                        else:  # Convert from decimal to percentage
                            relevance_score = min(raw_score * 100, 100)
                        
                        results.append({
                            "source_file_id": source_file.id,
                            "file_name": source_file.file_name,
                            "file_url": source_file.file_url,
                            "entity_name": source_file.entity_name,
                            "us_ma_date": source_file.us_ma_date,
                            "relevance_score": round(relevance_score, 1),
                            "relevance_comments": result.get("relevance_comments", "Content match within specific document"),
                            "grade_weight": result.get('grade_weight', 0),
                            "search_type": "Vector"
                        })
                
                # Track search results
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                await AnalyticsService.track_search(
                    db=db,
                    username=str(user_id),
                    search_query=search_query,
                    search_type="Vector",
                    filters=filters,
                    results_count=len(results),
                    execution_time_ms=int(execution_time)
                )
                
                logger.info(f"Document-specific search returned {len(results)} results")
                
                # Sort by relevance score (highest first)
                results.sort(key=lambda x: x['relevance_score'], reverse=True)
                
                # Store total before pagination
                total_results = len(results)
                
                # Apply pagination to results
                results = results[offset:offset + limit]
                
                return {
                    "success": True,
                    "results": results,
                    "search_type": "Vector",
                    "total_results": total_results
                }
            
            # If both entity_name and query are provided, go directly to vector search with metadata filter
            elif entity_name and search_query.strip():
                logger.info(f"Both entity_name and query provided - using vector search with metadata filter")
                
                # Get file names for the specific entity to use as metadata filter
                entitie_files_query = db.query(SourceFiles).filter(
                    SourceFiles.entity_name == entity_name
                )
                
                # Add collection filter if provided
                if collection_id:
                    entitie_files_query = entitie_files_query.join(
                        collection_document_association,
                        SourceFiles.id == collection_document_association.c.document_id
                    ).filter(
                        collection_document_association.c.collection_id == collection_id
                    ).distinct()
                
                entitie_files = entitie_files_query.all()
                
                if not entitie_files:
                    logger.info(f"No files found for entity: {entity_name}")
                    # Track search with no results
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    await AnalyticsService.track_search(
                        db=db,
                        username=str(user_id),
                        search_query=search_query,
                        search_type="Vector",
                        filters=filters,
                        results_count=0,
                        execution_time_ms=int(execution_time)
                    )
                    
                    return {
                        "success": True,
                        "results": [],
                        "search_type": "Vector",
                        "total_results": 0
                    }
                
                # Use search_with_grading with entity filter
                file_names = [f.file_name for f in entitie_files]
                vector_results = FDAChatManagementService.search_with_grading(
                    query=search_query,
                    collection_name=vector_db_collection_name,
                    n_results=max(100, limit + offset),  # Get enough results for pagination
                    db=db,
                    metadata_filter={"source": {"$in": file_names}}
                )
                
                # Transform vector results to match our standard format
                results = []
                for result in vector_results:
                    # Get source file details from SourceFiles table
                    source_file = db.query(SourceFiles).filter(
                        SourceFiles.file_name == result.get("file_name")
                    ).first()
                    
                    if source_file:
                        # If collection filter is applied, verify file is in collection and indexed
                        if collection_id:
                            file_in_collection = db.query(collection_document_association).filter(
                                collection_document_association.c.document_id == source_file.id,
                                collection_document_association.c.collection_id == collection_id,
                                collection_document_association.c.indexing_status == 'indexed'
                            ).first()
                            
                            if not file_in_collection:
                                continue  # Skip files not in the collection or not indexed
                        
                        # Ensure relevance score is between 0 and 100
                        raw_score = result.get("relevance_score", 0)
                        if raw_score > 1:  # Already in percentage
                            relevance_score = min(raw_score, 100)
                        else:  # Convert from decimal to percentage
                            relevance_score = min(raw_score * 100, 100)
                        
                        results.append({
                            "source_file_id": source_file.id,
                            "file_name": source_file.file_name,
                            "file_url": source_file.file_url,
                            "entity_name": source_file.entity_name,
                            "us_ma_date": source_file.us_ma_date,
                            "relevance_score": round(relevance_score, 1),
                            "relevance_comments": result.get("relevance_comments", "Content match with entity filter"),
                            "grade_weight": result.get('grade_weight', 0),
                            "search_type": "Vector"
                        })
                
                # Track search results
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                await AnalyticsService.track_search(
                    db=db,
                    username=str(user_id),
                    search_query=search_query,
                    search_type="Vector",
                    filters=filters,
                    results_count=len(results),
                    execution_time_ms=int(execution_time)
                )
                
                logger.info(f"Vector search with entity filter returned {len(results)} results")
                
                # Sort by relevance score (highest first)
                results.sort(key=lambda x: x['relevance_score'], reverse=True)
                
                # Store total before pagination
                total_results = len(results)
                
                # Apply pagination to results
                results = results[offset:offset + limit]
                
                return {
                    "success": True,
                    "results": results,
                    "search_type": "Vector",
                    "total_results": total_results
                }
            
            # Original SQL search logic for other cases
            logger.info(f"Executing SQL search - entity_name: {entity_name}, collection_id: {collection_id}, query empty: {not search_query.strip()}")
            sql_query = db.query(SourceFiles)
            
            # Add collection filter if provided
            if collection_id:
                logger.info(f"Adding collection filter for collection_id: {collection_id}")
                sql_query = sql_query.join(
                    collection_document_association,
                    SourceFiles.id == collection_document_association.c.document_id
                ).filter(
                    collection_document_association.c.collection_id == collection_id,
                    collection_document_association.c.indexing_status == 'indexed'
                ).distinct()
            
            if entity_name and not search_query.strip():
                # Entity name filter (with or without collection), no search query
                logger.info(f"Adding entity name filter: {entity_name}")
                sql_query = sql_query.filter(SourceFiles.entity_name == entity_name)
            elif search_query.strip() and not entity_name:
                # Only search query, no entity filter - search entity names
                sql_query = sql_query.filter(SourceFiles.entity_name.ilike(f"%{search_query}%"))
            elif not search_query.strip() and not entity_name and collection_id:
                # Only collection filter - this is allowed
                pass
            else:
                # No entity filter, no search query, and no collection - this shouldn't happen due to frontend validation
                logger.warning("Search called with no query, no entity filter, and no collection")
                return {
                    "success": True,
                    "results": [],
                    "search_type": "SQL",
                    "total_results": 0
                }
            
            # Get total count before applying pagination
            total_count = sql_query.count()
            
            # Apply pagination to SQL query
            sql_results = sql_query.offset(offset).limit(limit).all()
            logger.info(f"SQL query returned {len(sql_results)} results out of {total_count} total")
            
            if sql_results:
                # Found results via SQL search
                results = []
                for file in sql_results:
                    # Determine relevance comment based on filters
                    if collection_id and entity_name and not search_query.strip():
                        relevance_comment = f"Document from collection matching entity name: {entity_name}"
                    elif entity_name and not search_query.strip():
                        relevance_comment = f"Exact match on entity name: {entity_name}"
                    elif collection_id and not entity_name and not search_query.strip():
                        relevance_comment = "Document from selected collection"
                    else:
                        relevance_comment = "Entity name contains search term"
                    
                    results.append({
                        "source_file_id": file.id,
                        "file_name": file.file_name,
                        "file_url": file.file_url,
                        "entity_name": file.entity_name,
                        "us_ma_date": file.us_ma_date,
                        "relevance_score": 100,
                        "relevance_comments": relevance_comment,
                        "grade_weight": 1,
                        "search_type": "SQL"
                    })
                
                # Track SQL search results
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                await AnalyticsService.track_search(
                    db=db,
                    username=str(user_id),
                    search_query=search_query,
                    search_type="SQL",
                    filters=filters,
                    results_count=len(results),
                    execution_time_ms=int(execution_time)
                )
                
                logger.info(f"SQL search returned {len(results)} results")
                
                return {
                    "success": True,
                    "results": results,
                    "search_type": "SQL",
                    "total_results": total_count
                }
            
            # Check if we should skip vector search fallback
            if collection_id and entity_name and not search_query.strip():
                # No fallback to vector search when looking for exact entity matches in a collection
                logger.info(f"No documents found with entity_name '{entity_name}' in collection {collection_id}")
                
                # Track SQL search with no results
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                await AnalyticsService.track_search(
                    db=db,
                    username=str(user_id),
                    search_query=search_query,
                    search_type="SQL",
                    filters=filters,
                    results_count=0,
                    execution_time_ms=int(execution_time)
                )
                
                return {
                    "success": True,
                    "results": [],
                    "search_type": "SQL",
                    "total_results": 0,
                    "message": f"No documents found with entity name '{entity_name}' in the selected collection"
                }
            
            # Step 2: Vector search fallback (only for cases with actual search queries)
            logger.info("No SQL results found, falling back to vector search")
            
            # Build metadata filter for vector search if collection is specified
            metadata_filter = None
            if collection_id:
                # Get file names from the collection
                collection_files = db.query(SourceFiles).join(
                    collection_document_association,
                    SourceFiles.id == collection_document_association.c.document_id
                ).filter(
                    collection_document_association.c.collection_id == collection_id,
                    collection_document_association.c.indexing_status == 'indexed'
                ).distinct().all()
                
                if collection_files:
                    file_names = [f.file_name for f in collection_files]
                    metadata_filter = {"source": {"$in": file_names}}
                else:
                    # No files in collection, return empty results
                    logger.info(f"No files found in collection: {collection_id}")
                    return {
                        "success": True,
                        "results": [],
                        "search_type": "Vector",
                        "total_results": 0
                    }
            
            # Use the existing search_with_grading method
            vector_results = FDAChatManagementService.search_with_grading(
                query=search_query,
                collection_name=chromadb_collection_name,
                n_results=max(100, limit + offset),  # Get enough results for pagination
                db=db,
                metadata_filter=metadata_filter
            )
            
            # Transform vector results to match our standard format
            results = []
            for result in vector_results:
                # Get source file details from SourceFiles table
                source_file = db.query(SourceFiles).filter(
                    SourceFiles.file_name == result.get("file_name")
                ).first()
                
                if source_file:
                    # If collection filter is applied, verify file is in collection and indexed
                    if collection_id:
                        file_in_collection = db.query(collection_document_association).filter(
                            collection_document_association.c.document_id == source_file.id,
                            collection_document_association.c.collection_id == collection_id,
                            collection_document_association.c.indexing_status == 'indexed'
                        ).first()
                        
                        if not file_in_collection:
                            continue  # Skip files not in the collection or not indexed
                    
                    # Ensure relevance score is between 0 and 100
                    raw_score = result.get("relevance_score", 0)
                    if raw_score > 1:  # Already in percentage
                        relevance_score = min(raw_score, 100)
                    else:  # Convert from decimal to percentage
                        relevance_score = min(raw_score * 100, 100)
                    
                    results.append({
                        "source_file_id": source_file.id,
                        "file_name": source_file.file_name,
                        "file_url": source_file.file_url,
                        "entity_name": source_file.entity_name,
                        "us_ma_date": source_file.us_ma_date,
                        "relevance_score": round(relevance_score, 1),
                        "relevance_comments": result.get("relevance_comments", "Content similarity match"),
                        "grade_weight": result.get('grade_weight', 0),
                        "search_type": "Vector"
                    })
            
            # Track vector search results
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            await AnalyticsService.track_search(
                db=db,
                username=str(user_id),
                search_query=search_query,
                search_type="Vector",
                filters=filters,
                results_count=len(results),
                execution_time_ms=int(execution_time)
            )
            
            logger.info(f"Vector search returned {len(results)} results")
            
            return {
                "success": True,
                "results": results,
                "search_type": "Vector",
                "total_results": len(results)
            }
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            # Still try to track failed search
            try:
                await AnalyticsService.track_search(
                    db=db,
                    username=str(user_id),
                    search_query=search_query,
                    search_type="Failed",
                    filters=filters if 'filters' in locals() else {},
                    results_count=0,
                    execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                )
            except:
                pass
            
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "search_type": "Failed",
                "total_results": 0
            }
    
    @staticmethod
    def get_unique_entitie_names(db: Session, collection_id: Optional[int] = None) -> List[str]:
        """Get all unique entity names from SourceFiles for filter dropdown."""
        try:
            if collection_id:
                # Import necessary models
                from database.database import Collection, collection_document_association
                
                # Get entity names only from documents in the specified collection
                entity_names = db.query(SourceFiles.entity_name)\
                    .join(collection_document_association, SourceFiles.id == collection_document_association.c.document_id)\
                    .filter(
                        collection_document_association.c.collection_id == collection_id,
                        SourceFiles.entity_name.isnot(None)
                    )\
                    .distinct()\
                    .order_by(SourceFiles.entity_name)\
                    .all()
            else:
                # Get all entity names
                entity_names = db.query(SourceFiles.entity_name)\
                    .filter(
                        SourceFiles.entity_name.isnot(None)
                    )\
                    .distinct()\
                    .order_by(SourceFiles.entity_name)\
                    .all()
            
            return [name[0] for name in entity_names if name[0]]
        except Exception as e:
            logger.error(f"Error getting unique entity names: {str(e)}")
            return []
    
    @staticmethod
    def get_chat_history(
        session_id: str, 
        user_id: int, 
        source_file_id: int, 
        db: Session
    ) -> Optional[List[Tuple[str, str]]]:
        """Get chat history for a specific session and file."""
        chat_history = []
        
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
                    
                    if isinstance(response_details, dict) and response_details.get("source_file_id") == source_file_id:
                        chat_history.append(("human", response_details.get("user_query", "")))
                        chat_history.append(("ai", response_details.get("response", "")))
                except (ValueError, json.JSONDecodeError):
                    logger.error(f"Invalid format in response_details: {chat.response_details}")
        
        # Return last 5 exchanges (10 total messages) for conversational context
        # Each exchange = user message + assistant response = 2 messages
        return chat_history[-10:] if chat_history else None
    
    @staticmethod
    async def query_fda_document(
        source_file_id: int,
        query_string: str,
        session_id: str,
        user_id: int,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Query a specific FDA document using vector database."""
        logger.info(f"Querying FDA document with source_file_id: {source_file_id}")
        
        # Get document details
        fda_doc = db.query(SourceFiles).filter(
            SourceFiles.id == source_file_id
        ).first()
        
        if not fda_doc:
            logger.warning(f"No FDA document found for source_file_id: {source_file_id}")
            return None
        
        # Get the collection name from the document's collections
        vector_db_collection_name = "fda_documents"  # Default fallback
        if fda_doc.collections:
            # Use the first collection's vector database name
            collection = fda_doc.collections[0]
            if collection.vector_db_collection_name:
                vector_db_collection_name = collection.vector_db_collection_name
                logger.info(f"Using vector database collection: {vector_db_collection_name} for document {source_file_id}")
        
        # Get chat history
        chat_history = FDAChatManagementService.get_chat_history(
            session_id, user_id, source_file_id, db
        )
        
        # Query vector database
        vector_db_util = QdrantUtil.get_instance()
        
        # Build metadata filter for vector database - it expects exact match on source
        metadata_filter = {
            "source": fda_doc.file_name
        }
        
        response = vector_db_util.query_with_llm(
            query=query_string,
            collection_name=chromadb_collection_name,
            n_results=5,
            filter_dict=metadata_filter,
            chat_history=chat_history
        )
        
        if response:
            # fda_doc is already the source file, no need to query again
            
            query_response = {
                "source_file_id": source_file_id,
                "file_name": fda_doc.file_name,
                "file_url": fda_doc.file_url if fda_doc else None,
                "entity_name": fda_doc.entity_name,
                "user_query": query_string,
                "response": response
            }
            return query_response
        
        return None
    
    @staticmethod
    async def query_fda_documents(
        source_file_ids: List[int],
        query_string: str,
        session_id: str,
        user_id: int,
        db: Session,
        file_name_filter: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Query multiple FDA documents using vector database."""
        logger.info(f"Querying FDA documents with source_file_ids: {source_file_ids}")
        
        # Get document details for all source_file_ids
        fda_docs = db.query(SourceFiles).filter(
            SourceFiles.id.in_(source_file_ids)
        ).all()
        
        if not fda_docs:
            logger.warning(f"No FDA documents found for source_file_ids: {source_file_ids}")
            return None
        
        # Get chat history (using the first source_file_id for consistency)
        chat_history = FDAChatManagementService.get_chat_history(
            session_id, user_id, source_file_ids[0], db
        )
        
        # Get the collection name from the documents' collections
        vector_db_collection_name = "fda_documents"  # Default fallback
        if fda_docs:
            # Check the first document's collections
            first_doc = fda_docs[0]
            if first_doc.collections:
                collection = first_doc.collections[0]
                if collection.vector_db_collection_name:
                    vector_db_collection_name = collection.vector_db_collection_name
                    logger.info(f"Using vector database collection: {vector_db_collection_name} for multiple documents")
        
        # Query vector database with multiple source filters
        vector_db_util = QdrantUtil.get_instance()
        
        # Build metadata filter for vector database
        if file_name_filter:
            # Use the LLM-filtered file names if provided
            logger.info(f"Using LLM-filtered file names: {file_name_filter}")
            # Filter the fda_docs to only include those in the filter
            filtered_docs = [doc for doc in fda_docs if doc.file_name in file_name_filter]
            if filtered_docs:
                file_names = [doc.file_name for doc in filtered_docs]
            else:
                # If no docs match the filter, use all docs as fallback
                logger.warning("No documents matched the file filter, using all documents")
                file_names = [doc.file_name for doc in fda_docs]
        else:
            # Use all file names from the provided documents
            file_names = [doc.file_name for doc in fda_docs]
        
        # Note: The metadata field is "source" not "file_name" in vector database
        metadata_filter = {
            "source": {"$in": file_names}
        }
        
        # Increase n_results for multiple documents to ensure we get content from all
        # For specific topics like side effects, we need more chunks
        if any(keyword in query_string.lower() for keyword in ['side effect', 'adverse', 'safety', 'comparison', 'compare']):
            n_results_per_doc = 10  # More chunks for detailed comparisons
        else:
            n_results_per_doc = 7  # Standard retrieval
        
        logger.info(f"Using {n_results_per_doc} chunks per document for query: {query_string}")
        
        try:
            response = vector_db_util.query_with_llm_multi_doc(
                query=query_string,
                collection_name=chromadb_collection_name,
                n_results_per_doc=n_results_per_doc,
                filter_dict=metadata_filter,
                chat_history=chat_history,
                expected_sources=file_names
            )
        except Exception as e:
            logger.error(f"Error in multi-doc query: {str(e)}")
            # Fallback to general response
            return {
                "response": "I apologize, but I encountered an issue while processing your multi-document query. Please try rephrasing your question or contact support if the issue persists.",
                "status": "error", 
                "error_details": str(e)
            }
        
        if response:
            # fda_docs already contains the source files, no need to query again
            
            # Build response with all entity information
            entities_info = []
            for doc in fda_docs:
                entities_info.append({
                    "source_file_id": doc.id,  # Use doc.id instead of doc.source_file_id
                    "file_name": doc.file_name,
                    "file_url": doc.file_url,
                    "entity_name": doc.entity_name
                })
            
            query_response = {
                "source_file_ids": source_file_ids,
                "entities_info": entities_info,
                "user_query": query_string,
                "response": response,
                "comparison_mode": True
            }
            return query_response
        
        return None
    
    @staticmethod
    def save_chat_request(
        user_id: int,
        user_query: str,
        session_id: str,
        request_details: Dict[str, Any],
        db: Session
    ) -> int:
        """Save chat request to database."""
        chat = ChatHistory(
            user_id=user_id,
            user_query=user_query,
            session_id=session_id,
            request_details=json.dumps(request_details)
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat.id
    
    @staticmethod
    def update_chat_response(
        chat_id: int,
        response_details: Dict[str, Any],
        db: Session
    ) -> None:
        """Update chat response in database."""
        chat = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
        if chat:
            chat.response_details = json.dumps(response_details)
            db.commit()
    
    @staticmethod
    def retrieve_chat_history(
        user_id: int,
        db: Session,
        docx_chat_filter: Optional[bool] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve chat history for a user with optional docXChat filtering."""
        # Get all chat entries for the user, ordered by most recent first
        query = db.query(ChatHistory).filter(ChatHistory.user_id == user_id)
        
        # Apply docXChat filter if specified
        if docx_chat_filter is not None:
            if docx_chat_filter:
                # Filter for chats where request_details contains "docXChat": true
                query = query.filter(
                    func.json_extract(ChatHistory.request_details, '$.docXChat') == True
                )
            else:
                # Filter for chats where request_details contains "docXChat": false or doesn't have the field
                query = query.filter(
                    or_(
                        func.json_extract(ChatHistory.request_details, '$.docXChat') == False,
                        func.json_extract(ChatHistory.request_details, '$.docXChat').is_(None)
                    )
                )
        
        chats = query.order_by(desc(ChatHistory.created_at)).limit(50).all()  # Limit to last 50 chats
        
        history = []
        for chat in chats:
            try:
                # Parse response details to get response content
                response_details = json.loads(chat.response_details) if chat.response_details else {}
                response_content = response_details.get("response", "")
            except (json.JSONDecodeError, TypeError):
                response_content = ""
            
            # Parse request details to check docXChat
            try:
                request_details = json.loads(chat.request_details) if chat.request_details else {}
                is_docx_chat = request_details.get("docXChat", False)
            except (json.JSONDecodeError, TypeError):
                request_details = {}
                is_docx_chat = False
            
            # Extract source information from response details
            source_info = response_details.get("source_info", {})
            used_documents = response_details.get("used_documents", False)
            search_results = response_details.get("search_results", [])
            
            history.append({
                'id': chat.id,
                'session_id': chat.session_id,
                'query': chat.user_query,
                'response': response_content,
                'source_file_id': None,  # For compatibility
                'source_file_ids': None,  # For compatibility
                'created_at': chat.created_at.isoformat(),
                'is_favorite': chat.is_favorite,
                'source_info': source_info,
                'used_documents': used_documents,
                'search_results': search_results[:3] if search_results else [],  # Limit to 3 for UI
                'is_docx_chat': is_docx_chat  # Include docXChat status
            })
        
        return {'history': history}
    
    @staticmethod
    def retrieve_chat_sessions(
        user_id: int,
        db: Session,
        docx_chat_filter: Optional[bool] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve chat sessions grouped by session_id for a user with optional docXChat filtering."""
        from sqlalchemy import func
        
        # Build base query for ChatHistory
        base_query = db.query(ChatHistory).filter(ChatHistory.user_id == user_id)
        
        # Apply docXChat filter if specified
        if docx_chat_filter is not None:
            if docx_chat_filter:
                # Filter for chats where request_details contains "docXChat": true
                base_query = base_query.filter(
                    func.json_extract(ChatHistory.request_details, '$.docXChat') == 'true'
                )
            else:
                # Filter for chats where request_details contains "docXChat": false or doesn't have the field
                base_query = base_query.filter(
                    or_(
                        func.json_extract(ChatHistory.request_details, '$.docXChat') == False,
                        func.json_extract(ChatHistory.request_details, '$.docXChat').is_(None)
                    )
                )
        
        # Get the first chat of each session with session info
        session_subquery = (
            base_query.with_entities(
                ChatHistory.session_id,
                func.min(ChatHistory.created_at).label('first_chat_time'),
                func.max(ChatHistory.created_at).label('last_chat_time'),
                func.count(ChatHistory.id).label('message_count')
            )
            .group_by(ChatHistory.session_id)
            .subquery()
        )
        
        # Get the first chat details for each session
        first_chats_query = (
            db.query(ChatHistory, session_subquery.c.message_count, session_subquery.c.last_chat_time)
            .join(
                session_subquery,
                and_(
                    ChatHistory.session_id == session_subquery.c.session_id,
                    ChatHistory.created_at == session_subquery.c.first_chat_time
                )
            )
            .filter(ChatHistory.user_id == user_id)
        )
        
        # Apply the same docXChat filter to the main query
        if docx_chat_filter is not None:
            if docx_chat_filter:
                first_chats_query = first_chats_query.filter(
                    func.json_extract(ChatHistory.request_details, '$.docXChat') == 'true'
                )
            else:
                first_chats_query = first_chats_query.filter(
                    or_(
                        func.json_extract(ChatHistory.request_details, '$.docXChat') == False,
                        func.json_extract(ChatHistory.request_details, '$.docXChat').is_(None)
                    )
                )
        
        first_chats = (
            first_chats_query
            .order_by(desc(session_subquery.c.last_chat_time))
            .limit(30)  # Limit to last 30 sessions
            .all()
        )
        
        sessions = []
        for chat, message_count, last_chat_time in first_chats:
            # Check if any message in this session is favorite (respecting the filter)
            favorite_query = db.query(ChatHistory).filter(
                ChatHistory.session_id == chat.session_id,
                ChatHistory.user_id == user_id,
                ChatHistory.is_favorite == True
            )
            
            # Apply docXChat filter to favorite check
            if docx_chat_filter is not None:
                if docx_chat_filter:
                    favorite_query = favorite_query.filter(
                        func.json_extract(ChatHistory.request_details, '$.docXChat') == 'true'
                    )
                else:
                    favorite_query = favorite_query.filter(
                        or_(
                            func.json_extract(ChatHistory.request_details, '$.docXChat') == False,
                            func.json_extract(ChatHistory.request_details, '$.docXChat').is_(None)
                        )
                    )
            
            has_favorite = favorite_query.first() is not None
            
            # Parse request details to check docXChat
            try:
                request_details = json.loads(chat.request_details) if chat.request_details else {}
                is_docx_chat = request_details.get("docXChat", False)
            except (json.JSONDecodeError, TypeError):
                request_details = {}
                is_docx_chat = False
            
            sessions.append({
                'id': chat.id,  # ID of the first message
                'session_id': chat.session_id,
                'query': chat.user_query,  # First query as session title
                'created_at': chat.created_at.isoformat(),
                'last_activity': last_chat_time.isoformat(),
                'message_count': message_count,
                'is_favorite': has_favorite,
                'timestamp': chat.created_at.isoformat(),  # For compatibility
                'is_docx_chat': is_docx_chat  # Include docXChat status
            })
        
        return {'sessions': sessions}
    
    @staticmethod
    def retrieve_chat_details_by_session(
        session_id: str,
        user_id: int,
        db: Session
    ) -> List[Dict[str, Any]]:
        """Retrieve all chat details for a session."""
        chats = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == user_id,
                ChatHistory.session_id == session_id
            )
            .order_by(ChatHistory.created_at.asc())
            .all()
        )
        
        chat_details = []
        for chat in chats:
            try:
                request_details = json.loads(chat.request_details) if chat.request_details else {}
                response_details = json.loads(chat.response_details) if chat.response_details else {}
            except json.JSONDecodeError:
                request_details = {}
                response_details = {}
            
            chat_details.append({
                'chat_id': chat.id,
                'user_query': chat.user_query,
                'request_details': request_details,
                'response_details': response_details,
                'is_favorite': chat.is_favorite,
                'created_at': chat.created_at.isoformat()
            })
        
        return chat_details
    
    @staticmethod
    def mark_chat_as_favorite(
        chat_id: int,
        user_id: int,
        db: Session
    ) -> bool:
        """Mark a chat as favorite."""
        chat = db.query(ChatHistory).filter(
            ChatHistory.id == chat_id,
            ChatHistory.user_id == user_id
        ).first()
        
        if chat:
            chat.is_favorite = True
            db.commit()
            return True
        return False
    
    @staticmethod
    def remove_chat_from_favorites(
        chat_id: int,
        user_id: int,
        db: Session
    ) -> bool:
        """Remove a chat from favorites."""
        chat = db.query(ChatHistory).filter(
            ChatHistory.id == chat_id,
            ChatHistory.user_id == user_id
        ).first()
        
        if chat:
            chat.is_favorite = False
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_favorite_chats(
        user_id: int,
        db: Session,
        docx_chat_filter: Optional[bool] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get favorite chats for a user with optional docXChat filtering."""
        query = db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.is_favorite == True
        )
        
        # Apply docXChat filter if specified
        if docx_chat_filter is not None:
            if docx_chat_filter:
                # Filter for chats where request_details contains "docXChat": true
                query = query.filter(
                    func.json_extract(ChatHistory.request_details, '$.docXChat') == True
                )
            else:
                # Filter for chats where request_details contains "docXChat": false or doesn't have the field
                query = query.filter(
                    or_(
                        func.json_extract(ChatHistory.request_details, '$.docXChat') == False,
                        func.json_extract(ChatHistory.request_details, '$.docXChat').is_(None)
                    )
                )
        
        chats = query.order_by(desc(ChatHistory.created_at)).all()
        
        favorites = []
        for chat in chats:
            try:
                # Parse response details to get response content
                response_details = json.loads(chat.response_details) if chat.response_details else {}
                response_content = response_details.get("response", "")
            except (json.JSONDecodeError, TypeError):
                response_content = ""
            
            # Parse request details to check docXChat
            try:
                request_details = json.loads(chat.request_details) if chat.request_details else {}
                is_docx_chat = request_details.get("docXChat", False)
            except (json.JSONDecodeError, TypeError):
                request_details = {}
                is_docx_chat = False
            
            # Extract source information from response details
            try:
                response_details = json.loads(chat.response_details) if chat.response_details else {}
                source_info = response_details.get("source_info", {})
                used_documents = response_details.get("used_documents", False)
                search_results = response_details.get("search_results", [])
            except (json.JSONDecodeError, TypeError):
                source_info = {}
                used_documents = False
                search_results = []
            
            favorites.append({
                'id': chat.id,
                'session_id': chat.session_id,
                'query': chat.user_query,
                'response': response_content,
                'source_file_id': None,  # For compatibility
                'source_file_ids': None,  # For compatibility
                'created_at': chat.created_at.isoformat(),
                'is_favorite': chat.is_favorite,
                'source_info': source_info,
                'used_documents': used_documents,
                'search_results': search_results[:3] if search_results else [],  # Limit to 3 for UI
                'is_docx_chat': is_docx_chat  # Include docXChat status
            })
        
        return {'favorites': favorites}
    
    @staticmethod
    def delete_chat(
        chat_id: int,
        user_id: int,
        db: Session
    ) -> bool:
        """Delete a chat."""
        chat = db.query(ChatHistory).filter(
            ChatHistory.id == chat_id,
            ChatHistory.user_id == user_id
        ).first()
        
        if chat:
            db.delete(chat)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_filter_options(db: Session) -> Dict[str, List[str]]:
        """Get available filter options from source files."""
        # Get unique entity names from SourceFiles
        entity_names = db.query(distinct(SourceFiles.entity_name)).filter(
            SourceFiles.entity_name.isnot(None)
        ).all()
        
        return {
            "entity_names": ["ALL"] + [name[0] for name in entity_names if name[0]],
            "manufacturers": ["ALL"],  # Not available in SourceFiles
            "document_types": ["ALL"]  # Not available in SourceFiles
        }
    
    @staticmethod
    def search_with_grading(
        query: str,
        collection_name: str = "fda_documents",
        n_results: int = 15,
        db: Session = None,
        metadata_filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents using vector database and grade them for relevance.
        This is useful when no filters are applied and we want the best matches.
        
        Args:
            query: Search query
            collection_name: Vector database collection name
            n_results: Number of initial results to retrieve for grading
            db: Database session (optional)
            metadata_filter: Metadata filter for vector database query (optional)
            
        Returns:
            List of graded and ranked documents
        """
        try:
            vector_db_util = QdrantUtil.get_instance()
            
            # Search documents
            search_results = vector_db_util.search_documents(
                query=query,
                collection_name=collection_name,
                n_results=n_results,
                filter_dict=metadata_filter
            )
            
            if not search_results:
                logger.warning("No search results found")
                return []
            
            # Grade documents
            grading_results = vector_db_util.grade_documents(
                search_results=search_results,
                query=query
            )
            
            if not grading_results['file_paths']:
                logger.warning("No relevant documents after grading")
                return []
            
            # Get unique file names from grading results
            relevant_files = grading_results['file_paths']
            
            # If database session provided, fetch full document details
            if db:
                # Get source files for relevant file names
                source_files = db.query(SourceFiles).filter(
                    SourceFiles.file_name.in_(relevant_files)
                ).all()
                
                # Create mapping of file names to source files
                file_to_source = {sf.file_name: sf for sf in source_files}
                
                # Prepare results with grading information
                results = []
                max_weight = max(grading_results['weights']) if grading_results['weights'] else 1
                
                for file_path, weight, comment in zip(
                    grading_results['file_paths'],
                    grading_results['weights'],
                    grading_results['comments']
                ):
                    if file_path in file_to_source:
                        source_file = file_to_source[file_path]
                        
                        # Calculate relevance score as percentage based on max weight
                        # Weight represents how many relevant chunks were found
                        relevance_score = (weight / max_weight) * 100 if max_weight > 0 else 0.0
                        
                        results.append({
                            "id": source_file.id,
                            "source_file_id": source_file.id,
                            "file_name": source_file.file_name,
                            "file_url": source_file.file_url,
                            "entity_name": source_file.entity_name,
                            "relevance_score": round(min(relevance_score, 100), 1),  # Cap at 100%
                            "relevance_comments": comment,
                            "grade_weight": weight  # Just the number, formatting will be done in frontend
                        })
                
                # Sort by relevance score (highest first)
                results.sort(key=lambda x: x['relevance_score'], reverse=True)
                return results
            else:
                # Return grading results without database info
                total_weight = sum(grading_results['weights'])
                results = []
                
                for file_path, weight, comment in zip(
                    grading_results['file_paths'],
                    grading_results['weights'],
                    grading_results['comments']
                ):
                    results.append({
                        "file_name": file_path,
                        "relevance_score": (weight / total_weight) if total_weight > 0 else 0.0,
                        "relevance_comments": comment,
                        "grade_weight": weight
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error in search_with_grading: {str(e)}")
            return []
    
    
    @staticmethod
    def get_chat_suggestions(
        user_id: int,
        db: Session
    ) -> List[str]:
        """Generate chat suggestions based on user history."""
        recent_queries = (
            db.query(ChatHistory.user_query)
            .filter(ChatHistory.user_id == user_id)
            .order_by(desc(ChatHistory.created_at))
            .limit(20)
            .all()
        )
        
        if not recent_queries:
            # Default suggestions
            return [
                "What are the side effects?",
                "What is the recommended dosage?",
                "What are the contraindications?",
                "What are the entity interactions?",
                "What is the mechanism of action?"
            ]
        
        # Extract common keywords
        all_words = []
        for query in recent_queries:
            words = re.findall(r'\b\w+\b', query[0].lower())
            all_words.extend(words)
        
        # Count word frequency
        word_counts = collections.Counter(all_words)
        
        # Filter out common words
        common_words = {'what', 'is', 'the', 'are', 'of', 'a', 'an', 'and', 'or', 'for', 'in', 'to'}
        filtered_counts = {word: count for word, count in word_counts.items() 
                          if word not in common_words and len(word) > 3}
        
        # Get top keywords
        top_keywords = [word for word, _ in collections.Counter(filtered_counts).most_common(5)]
        
        # Generate suggestions
        suggestions = []
        for keyword in top_keywords:
            if keyword in ['effect', 'effects', 'side']:
                suggestions.append("What are the side effects?")
            elif keyword in ['dose', 'dosage', 'dosing']:
                suggestions.append("What is the recommended dosage?")
            elif keyword in ['interaction', 'interactions']:
                suggestions.append("What are the entity interactions?")
            elif keyword in ['contraindication', 'contraindications']:
                suggestions.append("What are the contraindications?")
            elif keyword in ['mechanism', 'action']:
                suggestions.append("What is the mechanism of action?")
        
        # Remove duplicates and limit to 5
        return list(dict.fromkeys(suggestions))[:5] or [
            "What are the side effects?",
            "What is the recommended dosage?",
            "What are the contraindications?",
            "What are the entity interactions?",
            "What is the mechanism of action?"
        ]
    
    @staticmethod
    def generate_smart_suggestions(
        chat_history: List[Dict[str, Any]],
        selected_entities: List[Dict[str, Any]],
        last_response: str,
        db: Session
    ) -> List[str]:
        """Generate intelligent suggestions based on conversation context using LLM."""
        from utils.llm_util_gemini import get_llm
        
        suggestions = []
        
        # If no chat history, return initial suggestions
        if not chat_history or len(chat_history) <= 1:
            if len(selected_entities) > 5:
                # For many entities, use generic terms
                return [
                    "Compare the indications of entities in this collection",
                    "What are the safety differences among these medications?",
                    "Which entities have similar mechanisms of action?",
                    "Show the most commonly prescribed entities here",
                    "What are the newest entities in this collection?"
                ]
            elif len(selected_entities) > 1:
                entity_names = [entity.get("entity_name", "Entity") for entity in selected_entities[:3]]  # Limit to 3
                suffix = f" and {len(selected_entities) - 3} others" if len(selected_entities) > 3 else ""
                return [
                    f"Compare the indications of {' and '.join(entity_names)}{suffix}",
                    f"What are the safety differences between these entities?",
                    f"How do dosing regimens differ among them?",
                    f"Which is most effective for common conditions?"
                ]
            elif len(selected_entities) == 1:
                entity_name = selected_entities[0].get("entity_name", "this entity")
                return [
                    f"What is the indication for {entity_name}?",
                    f"What are the most common side effects of {entity_name}?",
                    f"What is the recommended dosage for {entity_name}?",
                    f"Are there any contraindications for {entity_name}?"
                ]
            else:
                return [
                    "Search for entities by indication",
                    "Compare multiple entities",
                    "Show recent FDA approvals",
                    "Explain entity safety monitoring"
                ]
        
        # Analyze the last response for context
        last_response_lower = last_response.lower()
        
        # Get entity names for personalized suggestions (limit for readability)
        all_entitie_names = [entity.get("entity_name", "Entity") for entity in selected_entities] if selected_entities else []
        entity_names = all_entitie_names[:3] if len(all_entitie_names) > 3 else all_entitie_names
        has_many_entities = len(all_entitie_names) > 5
        
        # Topic-specific suggestions
        if any(term in last_response_lower for term in ["indication", "treat", "therapy", "condition"]):
            if has_many_entities:
                suggestions.extend([
                    "What clinical trials support these indications?",
                    "Are there off-label uses in this collection?",
                    "Which entities are most effective for this condition?",
                    "Compare mechanisms of action by entity class"
                ])
            elif len(entity_names) > 1:
                suggestions.extend([
                    f"What clinical trials support these indications?",
                    f"Are there off-label uses for these entities?",
                    f"How does efficacy compare between them?",
                    f"Compare mechanisms of action"
                ])
            elif len(entity_names) == 1:
                suggestions.extend([
                    f"What clinical trials support {entity_names[0]}'s indication?",
                    f"Are there any off-label uses for {entity_names[0]}?",
                    f"How does {entity_names[0]} compare to standard of care?",
                    f"What is the mechanism of action for {entity_names[0]}?"
                ])
            else:
                suggestions.extend([
                    "What clinical trials support this indication?",
                    "Are there any off-label uses?",
                    "How does efficacy compare to standard of care?",
                    "What is the mechanism of action for this indication?"
                ])
        
        if any(term in last_response_lower for term in ["side effect", "adverse", "safety", "toxicity"]):
            if len(entity_names) > 1:
                suggestions.extend([
                    f"What are the contraindications for {' vs '.join(entity_names)}?",
                    f"Do any of these entities have black box warnings: {', '.join(entity_names)}?",
                    f"Which requires more monitoring: {' or '.join(entity_names)}?",
                    f"Compare adverse events between {' and '.join(entity_names)}",
                    f"Compare entity interactions for {' vs '.join(entity_names)}"
                ])
            elif len(entity_names) == 1:
                suggestions.extend([
                    f"What are the contraindications for {entity_names[0]}?",
                    f"Does {entity_names[0]} have any black box warnings?",
                    f"What monitoring is required for {entity_names[0]}?",
                    f"How common are adverse events with {entity_names[0]}?",
                    f"What entity interactions does {entity_names[0]} have?"
                ])
            else:
                suggestions.extend([
                    "What are the contraindications?",
                    "Are there any black box warnings?",
                    "What monitoring is required during treatment?",
                    "How do adverse events compare between entities?",
                    "What are the entity-entity interactions?"
                ])
        
        if any(term in last_response_lower for term in ["dose", "dosing", "administration", "frequency"]):
            suggestions.extend([
                "Are there dose adjustments for renal/hepatic impairment?",
                "What about pediatric or geriatric dosing?",
                "Can doses be split or crushed?",
                "What is the pharmacokinetic profile?",
                "How should missed doses be handled?"
            ])
        
        if any(term in last_response_lower for term in ["efficacy", "effective", "clinical trial", "study", "endpoint"]):
            suggestions.extend([
                "What were the primary and secondary endpoints?",
                "What was the study population size?",
                "What was the duration of the trials?",
                "Were there any subgroup analyses?",
                "What about long-term efficacy data?"
            ])
        
        if any(term in last_response_lower for term in ["pregnan", "nursing", "breastfeed", "pediatric", "geriatric"]):
            suggestions.extend([
                "What are the reproductive toxicity findings?",
                "Is there data on use during lactation?",
                "What about use in pediatric populations?",
                "Are there special considerations for elderly patients?"
            ])
        
        # Comparison-specific suggestions if multiple entities
        if len(selected_entities) > 1:
            if any(term in last_response_lower for term in ["compar", "differ", "versus", "vs"]):
                suggestions.extend([
                    "Which entity has fewer entity interactions?",
                    "Compare the onset of action",
                    "Which is more cost-effective?",
                    "Compare patient adherence rates",
                    "Which has better quality of life outcomes?"
                ])
        
        # Remove duplicates and limit to 5 suggestions
        unique_suggestions = list(dict.fromkeys(suggestions))[:5]
        
        # If we don't have enough specific suggestions, add general ones
        if len(unique_suggestions) < 3:
            general_suggestions = [
                "Tell me more about the clinical development",
                "What are the storage requirements?",
                "Is there a REMS program?",
                "What patient counseling is recommended?",
                "Show the prescribing information highlights"
            ]
            unique_suggestions.extend(general_suggestions[:5-len(unique_suggestions)])
        
        return unique_suggestions
    
    @staticmethod
    def generate_llm_suggestions(
        chat_history: List[Dict[str, Any]],
        selected_entities: List[Dict[str, Any]],
        db: Session
    ) -> List[str]:
        """Generate intelligent suggestions using LLM based on full conversation context."""
        try:
            # Check if we have a valid API key
            if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY.strip() == "":
                logger.warning("Google API key not configured, falling back to rule-based suggestions")
                # Extract last response safely
                last_response = ""
                if chat_history:
                    last_item = chat_history[-1]
                    if isinstance(last_item, dict):
                        last_response = last_item.get("content", "")
                    elif isinstance(last_item, str):
                        last_response = last_item
                
                return FDAChatManagementService.generate_smart_suggestions(
                    chat_history, selected_entities, last_response, db
                )
                
            from utils.llm_util_gemini import get_llm
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            
            # If no meaningful chat history, return empty list
            if not chat_history or len(chat_history) <= 1:
                return FDAChatManagementService.generate_smart_suggestions(
                    chat_history, selected_entities, "", db
                )
            
            # Build conversation context
            messages = [
                SystemMessage(content="""You are an FDA entity information expert. Based on the conversation history, 
                generate 4-5 highly relevant follow-up questions that the user might want to ask next.
                
                Guidelines:
                1. Questions should be specific to the topic being discussed
                2. Build upon information already provided in the conversation
                3. Explore aspects not yet covered in detail
                4. Keep questions concise - max 10-12 words each
                5. Focus on practical, clinically relevant information
                6. If comparing multiple entities, use general terms like "these entities" instead of listing all names
                7. NEVER list all entity names in a single question
                8. For collections with many entities, use phrases like "in this collection" or "among these medications"
                
                Return ONLY the questions as a JSON array of strings, nothing else.""")
            ]
            
            # Add conversation history
            for msg in chat_history:
                if isinstance(msg, dict):
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg.get("content", "")))
                elif isinstance(msg, str):
                    # If it's a string, assume it's user content
                    messages.append(HumanMessage(content=msg))
            
            # Add context about selected entities (limit to avoid overly long suggestions)
            if selected_entities:
                entity_names = [entity.get("entity_name", "Unknown") for entity in selected_entities]
                # Limit to first 5 entities to avoid extremely long suggestions
                if len(entity_names) > 5:
                    context = f"\nEntitys being discussed: {', '.join(entity_names[:5])} and {len(entity_names) - 5} others"
                else:
                    context = f"\nEntitys being discussed: {', '.join(entity_names)}"
                messages.append(SystemMessage(content=context))
            
            # Add prompt for suggestions
            messages.append(HumanMessage(content="Generate 4-5 relevant follow-up questions based on this conversation."))
            
            # Get LLM response with timeout
            logger.info("Attempting to generate LLM-based suggestions")
            llm = get_llm()
            response = llm.invoke(messages)
            
            # Parse response
            import json
            import re
            
            # Extract JSON array from response
            content = response.content.strip()
            
            # Try to find JSON array in response
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                try:
                    suggestions = json.loads(json_match.group())
                    # Ensure we have strings and limit to 5
                    valid_suggestions = [str(s) for s in suggestions[:5] if isinstance(s, str) and s.strip()]
                    if valid_suggestions:
                        logger.info(f"Successfully generated {len(valid_suggestions)} LLM suggestions")
                        return valid_suggestions
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON from LLM response: {e}")
            
            # Fallback: try to parse lines as questions
            lines = content.split('\n')
            questions = []
            for line in lines:
                line = line.strip()
                # Remove numbering, bullets, quotes
                line = re.sub(r'^[\d\.\-\*\"\'\`]+\s*', '', line)
                line = re.sub(r'[\"\'\`]+$', '', line)
                
                # Check if it looks like a question
                if line and '?' in line and len(line) > 10:
                    questions.append(line)
            
            if questions:
                logger.info(f"Generated {len(questions[:5])} LLM suggestions from parsed lines")
                return questions[:5]
            
            # Final fallback to rule-based suggestions
            logger.warning("LLM response parsing failed, falling back to rule-based suggestions")
            # Extract last response safely
            last_response = ""
            if chat_history:
                last_item = chat_history[-1]
                if isinstance(last_item, dict):
                    last_response = last_item.get("content", "")
                elif isinstance(last_item, str):
                    last_response = last_item
            
            return FDAChatManagementService.generate_smart_suggestions(
                chat_history, selected_entities, last_response, db
            )
            
        except ImportError as e:
            logger.error(f"Failed to import LLM utilities: {e}")
            # Extract last response safely
            last_response = ""
            if chat_history:
                last_item = chat_history[-1]
                if isinstance(last_item, dict):
                    last_response = last_item.get("content", "")
                elif isinstance(last_item, str):
                    last_response = last_item
            
            return FDAChatManagementService.generate_smart_suggestions(
                chat_history, selected_entities, last_response, db
            )
        except Exception as e:
            logger.error(f"Error generating LLM suggestions: {e}")
            # Extract last response safely
            last_response = ""
            if chat_history:
                last_item = chat_history[-1]
                if isinstance(last_item, dict):
                    last_response = last_item.get("content", "")
                elif isinstance(last_item, str):
                    last_response = last_item
            
            # Fallback to rule-based suggestions
            return FDAChatManagementService.generate_smart_suggestions(
                chat_history, selected_entities, last_response, db
            )