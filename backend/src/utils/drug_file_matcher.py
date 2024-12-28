from typing import List, Dict, Optional, Union, Set
from sqlalchemy.orm import Session
from database.database import SourceFiles, collection_document_association
from utils.llm_util import get_llm
import json
import logging

logger = logging.getLogger(__name__)

# Configuration constants for chunking
DRUG_CHUNK_SIZE = 100  # Max drugs per LLM chunk
USE_TWO_STAGE_THRESHOLD = 100  # Use two-stage approach if more than this many drugs

class DrugFileMatcher:
    """Utility class for matching user queries with relevant drug files using LLM"""
    
    @staticmethod
    async def _process_drug_chunk(query: str, drug_names: List[str], llm) -> List[str]:
        """
        Process a single chunk of drug names to identify relevant ones.
        
        Args:
            query: User query
            drug_names: List of drug names to check
            llm: LLM instance
            
        Returns:
            List of relevant drug names from this chunk
        """
        prompt = f"""You are a pharmaceutical drug matcher. Given a user query and a list of drug names,
identify which drugs are relevant to answer the query.

USER QUERY: {query}

AVAILABLE DRUG NAMES:
{json.dumps(drug_names, indent=2)}

TASK: Return ONLY a JSON array of drug names that are relevant to the query.

IMPORTANT RULES:
1. ONLY include drugs if the query contains:
   - Explicit drug names (exact or partial match)
   - Generic/brand name variations that match
   - Specific medical conditions AND asks about drugs for those conditions
   - Requests to compare specific drugs

2. DO NOT include drugs if the query:
   - Only asks for general information (dates, processes, requirements) without drug references.
   - Does not mention any specific drugs or medical conditions.
   - Is asking about regulatory information without drug references.

3. For queries about approval dates, clinical trials, or regulatory information WITHOUT specific drug names, return []

Return empty array [] if no drugs are explicitly or implicitly referenced.
Return ONLY the JSON array, no explanations.

Example responses:
Query: "Compare Keytruda and Opdivo" → ["Keytruda", "Opdivo"]
Query: "Provide me the approval date details alone" → []
Query: "What are the clinical trial requirements?" → []

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
            drug_list = json.loads(content)
            if isinstance(drug_list, list):
                # Only return drugs that were in the input list
                valid_drugs = [d for d in drug_list if d in drug_names]
                return valid_drugs
            return []
            
        except Exception as e:
            logger.error(f"Error processing drug chunk: {e}")
            return []
    
    @staticmethod
    async def get_relevant_drugs_from_query(
        query: str, 
        all_drug_names: List[str], 
        llm
    ) -> List[str]:
        """
        Identify which drugs from a large list are relevant to the query.
        Handles large lists by processing in chunks.
        
        Args:
            query: User query
            all_drug_names: Complete list of drug names
            llm: LLM instance
            
        Returns:
            List of relevant drug names
        """
        if len(all_drug_names) <= DRUG_CHUNK_SIZE:
            # Small enough to process in one go
            return await DrugFileMatcher._process_drug_chunk(query, all_drug_names, llm)
        
        # Process in chunks
        relevant_drugs: Set[str] = set()
        total_chunks = (len(all_drug_names) - 1) // DRUG_CHUNK_SIZE + 1
        
        logger.info(f"Processing {len(all_drug_names)} drugs in {total_chunks} chunks")
        
        for i in range(0, len(all_drug_names), DRUG_CHUNK_SIZE):
            chunk = all_drug_names[i:i + DRUG_CHUNK_SIZE]
            chunk_num = i // DRUG_CHUNK_SIZE + 1
            
            logger.info(f"Processing chunk {chunk_num}/{total_chunks} with {len(chunk)} drugs")
            
            chunk_results = await DrugFileMatcher._process_drug_chunk(query, chunk, llm)
            relevant_drugs.update(chunk_results)
            
            logger.info(f"Chunk {chunk_num} identified {len(chunk_results)} relevant drugs")
        
        logger.info(f"Total relevant drugs identified: {len(relevant_drugs)}")
        return list(relevant_drugs)
    
    @staticmethod
    async def extract_relevant_files_for_query(
        query: str,
        collection_id: Optional[int] = None,
        source_file_ids: Optional[List[int]] = None,
        db: Session = None
    ) -> Optional[List[str]]:
        """
        Use LLM to match query with relevant drug files.
        Now uses two-stage approach for large collections.
        
        Args:
            query: User query
            collection_id: Optional collection ID for collection-based queries
            source_file_ids: Optional list of document IDs for document-based queries
            db: Database session
            
        Returns:
            List of relevant file names or None if no specific files identified
        """
        
        if source_file_ids is not None and len(source_file_ids) > 0:
            drug_file_mapping = DrugFileMatcher.get_documents_drug_files(source_file_ids, db)
            context = f"{len(source_file_ids)} specific documents"
        elif collection_id:
            drug_file_mapping = DrugFileMatcher.get_collection_drug_files(collection_id, db)
            context = f"collection {collection_id}"
        
        #else:
        #    logger.error("Neither collection_id nor source_file_ids provided")
        #    return None
        
        if not drug_file_mapping:
            logger.info(f"No drug files found in {context}")
            return None
        
        # Get LLM instance
        llm = get_llm()
        
        # Check if we need two-stage approach
        if len(drug_file_mapping) > USE_TWO_STAGE_THRESHOLD:
            logger.info(f"Using two-stage approach for {len(drug_file_mapping)} drugs")
            
            # Stage 1: Get relevant drugs
            all_drug_names = list(drug_file_mapping.keys())
            relevant_drugs = await DrugFileMatcher.get_relevant_drugs_from_query(
                query, all_drug_names, llm
            )
            
            if not relevant_drugs:
                logger.info("No relevant drugs identified in stage 1")
                return None
            
            # Stage 2: Filter mapping to relevant drugs only
            filtered_mapping = {
                drug: files 
                for drug, files in drug_file_mapping.items() 
                if drug in relevant_drugs
            }
            
            logger.info(f"Filtered from {len(drug_file_mapping)} to {len(filtered_mapping)} drugs")
            
            # Use filtered mapping for file selection
            drug_file_mapping = filtered_mapping
        
        prompt = f"""You are a pharmaceutical file matcher. Given a user query and a list of drug names with their associated file names, 
identify which files would be most relevant to answer the query.

USER QUERY: {query}

AVAILABLE DRUGS AND FILES IN {context.upper()}:
{json.dumps(drug_file_mapping, indent=2)}

TASK: Return ONLY a JSON array of file names that are relevant to the query. 
- Include files for drugs explicitly mentioned in the query
- Include files for drugs related to the medical condition or treatment mentioned
- If the query asks for comparison, include all relevant drug files
- If the query is general or doesn't mention specific drugs, return an empty array []
- Return ONLY the JSON array, no explanations

Example responses:
["drug1_label.pdf", "drug2_prescribing_info.pdf"]
[]

Response:"""
        
        try:
            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Handle potential markdown formatting
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            if content.startswith('```'):
                content = content[3:]  # Remove ```
            if content.endswith('```'):
                content = content[:-3]  # Remove ending ```
            content = content.strip()
            
            logger.info(f"response: {response}")
            # Parse the JSON response
            file_names = json.loads(content)
            
            if isinstance(file_names, list) and len(file_names) > 0:
                # Validate that returned files exist in our mapping
                all_files = set()
                for files in drug_file_mapping.values():
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
    def get_collection_drug_files(collection_id: int, db: Session) -> Dict[str, List[str]]:
        """
        Get mapping of drug names to file names in a collection.
        Only includes documents that are indexed in the collection.
        
        Args:
            collection_id: Collection ID
            db: Database session
            
        Returns:
            Dictionary mapping drug names to list of file names (only indexed files)
        """
        try:
            results = db.query(
                SourceFiles.drug_name,
                SourceFiles.file_name
            ).join(
                collection_document_association,
                SourceFiles.id == collection_document_association.c.document_id
            ).filter(
                collection_document_association.c.collection_id == collection_id,
                collection_document_association.c.indexing_status == 'indexed',
                SourceFiles.drug_name.isnot(None)
            ).distinct().all()
            
            # Group by drug name
            drug_files = {}
            for drug_name, file_name in results:
                if drug_name and file_name:  # Ensure both are not None
                    if drug_name not in drug_files:
                        drug_files[drug_name] = []
                    if file_name not in drug_files[drug_name]:
                        drug_files[drug_name].append(file_name)
            
            logger.info(f"Found {len(drug_files)} drugs with indexed files in collection {collection_id}")
            return drug_files
            
        except Exception as e:
            logger.error(f"Error getting collection drug files: {e}")
            return {}
    
    @staticmethod
    def get_documents_drug_files(source_file_ids: List[int], db: Session) -> Dict[str, List[str]]:
        """
        Get mapping of drug names to file names for specific documents.
        
        Args:
            source_file_ids: List of source file IDs
            db: Database session
            
        Returns:
            Dictionary mapping drug names to list of file names
        """
        try:
            results = db.query(
                SourceFiles.drug_name,
                SourceFiles.file_name
            ).filter(
                SourceFiles.id.in_(source_file_ids),
                SourceFiles.drug_name.isnot(None)
            ).distinct().all()
            
            # Group by drug name
            drug_files = {}
            for drug_name, file_name in results:
                if drug_name and file_name:  # Ensure both are not None
                    if drug_name not in drug_files:
                        drug_files[drug_name] = []
                    if file_name not in drug_files[drug_name]:
                        drug_files[drug_name].append(file_name)
            
            logger.info(f"Found {len(drug_files)} drugs with files for {len(source_file_ids)} documents")
            logger.info(f"drug_files {drug_files} ")
            return drug_files
            
        except Exception as e:
            logger.error(f"Error getting documents drug files: {e}")
            return {}