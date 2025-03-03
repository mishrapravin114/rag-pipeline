"""
Generic entity file matcher - matches user queries with relevant entity files using LLM
Replaces entity_file_matcher.py with domain-agnostic implementation
"""
from typing import List, Dict, Optional, Union, Set
from sqlalchemy.orm import Session
from database.database import SourceFiles, collection_document_association
from utils.llm_util import get_llm
from utils.domain_mapper import DomainMapper
from config.domain_config import DomainConfig, Domain
import json
import logging

logger = logging.getLogger(__name__)

# Configuration constants for chunking
ENTITY_CHUNK_SIZE = 100  # Max entities per LLM chunk
USE_TWO_STAGE_THRESHOLD = 100  # Use two-stage approach if more than this many entities

class EntityFileMatcher:
    """Generic utility class for matching user queries with relevant entity files using LLM"""
    
    def __init__(self, domain: str = "pharmaceutical"):
        self.domain = domain
        self.domain_config = DomainConfig(Domain[domain.upper()] if hasattr(Domain, domain.upper()) else Domain.PHARMACEUTICAL)
        self.mapper = DomainMapper()
    
    async def _process_entity_chunk(self, query: str, entity_names: List[str], llm, domain: str = "pharmaceutical") -> List[str]:
        """
        Process a single chunk of entity names to identify relevant ones.
        
        Args:
            query: User query
            entity_names: List of entity names to check
            llm: LLM instance
            domain: Domain context (pharmaceutical, legal, corporate, etc.)
            
        Returns:
            List of relevant entity names from this chunk
        """
        entity_label = self.mapper.get_entity_label(domain)
        
        prompt = f"""You are an intelligent {domain} information matcher. Given a user query and a list of {entity_label} names,
identify which {entity_label}s are relevant to answer the query.

USER QUERY: {query}

AVAILABLE {entity_label.upper()} NAMES:
{json.dumps(entity_names, indent=2)}

TASK: Return ONLY a JSON array of {entity_label} names that are relevant to the query.

IMPORTANT RULES:
1. ONLY include {entity_label}s if the query contains:
   - Explicit {entity_label} names (exact or partial match)
   - Generic/brand name variations that match
   - Specific conditions/topics AND asks about {entity_label}s for those conditions
   - Requests to compare specific {entity_label}s

2. DO NOT include {entity_label}s if the query:
   - Only asks for general information (dates, processes, requirements) without {entity_label} references.
   - Does not mention any specific {entity_label}s or related topics.
   - Is asking about regulatory/informational content without {entity_label} references.

3. For queries about dates, processes, or regulatory information WITHOUT specific {entity_label} names, return []

Return empty array [] if no {entity_label}s are explicitly or implicitly referenced.
Return ONLY the JSON array, no explanations.

Example responses:
Query: "Compare Entity1 and Entity2" → ["Entity1", "Entity2"]
Query: "Provide me the approval date details alone" → []
Query: "What are the requirements?" → []

Response:"""
        
        try:
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Handle markdown formatting
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Parse and validate
            entity_list = json.loads(content)
            if isinstance(entity_list, list):
                # Only return entities that were in the input list
                valid_entities = [e for e in entity_list if e in entity_names]
                return valid_entities
            return []
            
        except Exception as e:
            logger.error(f"Error processing entity chunk: {e}")
            return []
    
    async def get_relevant_entities_from_query(
        self, 
        query: str, 
        all_entity_names: List[str], 
        llm,
        domain: str = "pharmaceutical"
    ) -> List[str]:
        """
        Identify which entities from a large list are relevant to the query.
        Handles large lists by processing in chunks.
        
        Args:
            query: User query
            all_entity_names: Complete list of entity names
            llm: LLM instance
            domain: Domain context
            
        Returns:
            List of relevant entity names
        """
        if len(all_entity_names) <= ENTITY_CHUNK_SIZE:
            # Small enough to process in one go
            return await self._process_entity_chunk(query, all_entity_names, llm, domain)
        
        # Process in chunks
        relevant_entities: Set[str] = set()
        total_chunks = (len(all_entity_names) - 1) // ENTITY_CHUNK_SIZE + 1
        
        logger.info(f"Processing {len(all_entity_names)} entities in {total_chunks} chunks")
        
        for i in range(0, len(all_entity_names), ENTITY_CHUNK_SIZE):
            chunk = all_entity_names[i:i + ENTITY_CHUNK_SIZE]
            chunk_num = i // ENTITY_CHUNK_SIZE + 1
            
            logger.info(f"Processing chunk {chunk_num}/{total_chunks} with {len(chunk)} entities")
            
            chunk_results = await self._process_entity_chunk(query, chunk, llm, domain)
            relevant_entities.update(chunk_results)
            
            logger.info(f"Chunk {chunk_num} identified {len(chunk_results)} relevant entities")
        
        logger.info(f"Total relevant entities identified: {len(relevant_entities)}")
        return list(relevant_entities)
    
    async def extract_relevant_files_for_query(
        self,
        query: str,
        collection_id: Optional[int] = None,
        source_file_ids: Optional[List[int]] = None,
        db: Session = None,
        domain: str = "pharmaceutical"
    ) -> Optional[List[str]]:
        """
        Use LLM to match query with relevant entity files.
        Now uses two-stage approach for large collections.
        
        Args:
            query: User query
            collection_id: Optional collection ID for collection-based queries
            source_file_ids: Optional list of document IDs for document-based queries
            db: Database session
            domain: Domain context
            
        Returns:
            List of relevant file names or None if no specific files identified
        """
        
        if source_file_ids is not None and len(source_file_ids) > 0:
            entity_file_mapping = self.get_documents_entity_files(source_file_ids, db)
            context = f"{len(source_file_ids)} specific documents"
        elif collection_id:
            entity_file_mapping = self.get_collection_entity_files(collection_id, db)
            context = f"collection {collection_id}"
        else:
            logger.error("Neither collection_id nor source_file_ids provided")
            return None
        
        if not entity_file_mapping:
            logger.info(f"No entity files found in {context}")
            return None
        
        # Get LLM instance
        llm = get_llm()
        entity_label = self.mapper.get_entity_label(domain)
        
        # Check if we need two-stage approach
        if len(entity_file_mapping) > USE_TWO_STAGE_THRESHOLD:
            logger.info(f"Using two-stage approach for {len(entity_file_mapping)} entities")
            
            # Stage 1: Get relevant entities
            all_entity_names = list(entity_file_mapping.keys())
            relevant_entities = await self.get_relevant_entities_from_query(
                query, all_entity_names, llm, domain
            )
            
            if not relevant_entities:
                logger.info("No relevant entities identified in stage 1")
                return None
            
            # Stage 2: Filter mapping to relevant entities only
            filtered_mapping = {
                entity: files 
                for entity, files in entity_file_mapping.items() 
                if entity in relevant_entities
            }
            
            logger.info(f"Filtered from {len(entity_file_mapping)} to {len(filtered_mapping)} entities")
            
            # Use filtered mapping for file selection
            entity_file_mapping = filtered_mapping
        
        prompt = f"""You are an intelligent {domain} file matcher. Given a user query and a list of {entity_label} names with their associated file names, 
identify which files would be most relevant to answer the query.

USER QUERY: {query}

AVAILABLE {entity_label.upper()}S AND FILES IN {context.upper()}:
{json.dumps(entity_file_mapping, indent=2)}

TASK: Return ONLY a JSON array of file names that are relevant to the query. 
- Include files for {entity_label}s explicitly mentioned in the query
- Include files for {entity_label}s related to the topic/condition mentioned
- If the query asks for comparison, include all relevant {entity_label} files
- If the query is general or doesn't mention specific {entity_label}s, return an empty array []
- Return ONLY the JSON array, no explanations

Example responses:
["entity1_document.pdf", "entity2_info.pdf"]
[]

Response:"""
        
        try:
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Handle potential markdown formatting
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            logger.info(f"response: {response}")
            # Parse the JSON response
            file_names = json.loads(content)
            
            if isinstance(file_names, list) and len(file_names) > 0:
                # Validate that returned files exist in our mapping
                all_files = set()
                for files in entity_file_mapping.values():
                    all_files.update(files)
                
                valid_files = [f for f in file_names if f in all_files]
                
                if valid_files:
                    logger.info(f"LLM identified {len(valid_files)} relevant files for query in {context}")
                    return valid_files
                else:
                    logger.warning("LLM returned files not found in the mapping")
                    return None
            else:
                logger.info(f"LLM did not identify any specific files for filtering in {context}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response as JSON: {e}, Response: {content}")
            return None
        except Exception as e:
            logger.error(f"Error in LLM file matching: {e}")
            return None
    
    @staticmethod
    def get_collection_entity_files(collection_id: int, db: Session, use_entity_name: bool = True) -> Dict[str, List[str]]:
        """
        Get mapping of entity names to file names in a collection.
        Only includes documents that are indexed in the collection.
        
        Args:
            collection_id: Collection ID
            db: Database session
            use_entity_name: If True, use entity_name; if False, use entity_name for backward compatibility
            
        Returns:
            Dictionary mapping entity names to list of file names (only indexed files)
        """
        try:
            # Try entity_name first, fallback to entity_name for backward compatibility
            name_column = SourceFiles.entity_name if use_entity_name else SourceFiles.entity_name
            
            results = db.query(
                name_column,
                SourceFiles.file_name
            ).join(
                collection_document_association,
                SourceFiles.id == collection_document_association.c.document_id
            ).filter(
                collection_document_association.c.collection_id == collection_id,
                collection_document_association.c.indexing_status == 'indexed',
                name_column.isnot(None)
            ).distinct().all()
            
            # Group by entity name
            entity_files = {}
            for entity_name, file_name in results:
                if entity_name and file_name:
                    if entity_name not in entity_files:
                        entity_files[entity_name] = []
                    if file_name not in entity_files[entity_name]:
                        entity_files[entity_name].append(file_name)
            
            logger.info(f"Found {len(entity_files)} entities with indexed files in collection {collection_id}")
            return entity_files
            
        except Exception as e:
            logger.error(f"Error getting collection entity files: {e}")
            return {}
    
    @staticmethod
    def get_documents_entity_files(source_file_ids: List[int], db: Session, use_entity_name: bool = True) -> Dict[str, List[str]]:
        """
        Get mapping of entity names to file names for specific documents.
        
        Args:
            source_file_ids: List of source file IDs
            db: Database session
            use_entity_name: If True, use entity_name; if False, use entity_name for backward compatibility
            
        Returns:
            Dictionary mapping entity names to list of file names
        """
        try:
            # Try entity_name first, fallback to entity_name for backward compatibility
            name_column = SourceFiles.entity_name if use_entity_name else SourceFiles.entity_name
            
            results = db.query(
                name_column,
                SourceFiles.file_name
            ).filter(
                SourceFiles.id.in_(source_file_ids),
                name_column.isnot(None)
            ).distinct().all()
            
            # Group by entity name
            entity_files = {}
            for entity_name, file_name in results:
                if entity_name and file_name:
                    if entity_name not in entity_files:
                        entity_files[entity_name] = []
                    if file_name not in entity_files[entity_name]:
                        entity_files[entity_name].append(file_name)
            
            logger.info(f"Found {len(entity_files)} entities with files for {len(source_file_ids)} documents")
            return entity_files
            
        except Exception as e:
            logger.error(f"Error getting documents entity files: {e}")
            return {}

# Backward compatibility alias
EntityFileMatcher = EntityFileMatcher

