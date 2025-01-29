"""
Metadata Extraction Service for FDA RAG Pipeline
Handles extraction of metadata from source files using ChromaDB and LLM integration.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from database.database import SourceFiles, MetadataConfiguration, EntityMetadata, DocumentData
from utils.qdrant_util import QdrantUtil
# from utils.llm_utils import get_llm  # Removed, not used
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class MetadataExtractionService:
    
    @staticmethod
    def get_source_files_for_metadata_view(db: Session) -> List[Dict[str, Any]]:
        """Get all source files with their metadata extraction status for the view-metadata page."""
        try:
            # Get all source files with their metadata extraction status
            source_files = db.query(SourceFiles).all()
            
            results = []
            for file in source_files:
                # Count extracted metadata for this file
                metadata_count = db.query(EntityMetadata).filter(
                    EntityMetadata.source_file_id == file.id
                ).count()
                
                # Get unique metadata names extracted for this file
                unique_metadata = db.query(EntityMetadata.metadata_name).filter(
                    EntityMetadata.source_file_id == file.id
                ).distinct().all()
                unique_metadata_names = [m[0] for m in unique_metadata]
                
                results.append({
                    "id": file.id,
                    "file_name": file.file_name,
                    "file_url": file.file_url,
                    "entity_name": file.entity_name,
                    "us_ma_date": file.us_ma_date,
                    "status": file.status,
                    "metadata_extracted": file.metadata_extracted,
                    "metadata_count": metadata_count,
                    "extracted_metadata_names": unique_metadata_names,
                    "created_at": file.created_at.isoformat() if file.created_at else None,
                    "updated_at": file.updated_at.isoformat() if file.updated_at else None
                })
            
            logger.info(f"Retrieved {len(results)} source files for metadata view")
            return results
            
        except Exception as e:
            logger.error(f"Error getting source files for metadata view: {str(e)}")
            return []
    
    @staticmethod
    def get_source_files_for_metadata_view_paginated(
        db: Session, 
        limit: int = 25, 
        offset: int = 0,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated source files with their metadata extraction status."""
        try:
            # Base query
            query = db.query(SourceFiles)
            
            # Apply status filter
            if status and status != "all":
                query = query.filter(SourceFiles.status == status.upper())
            
            # Apply search filter
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    SourceFiles.file_name.ilike(search_term) |
                    SourceFiles.file_url.ilike(search_term) |
                    SourceFiles.entity_name.ilike(search_term)
                )
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply pagination
            source_files = query.order_by(SourceFiles.created_at.desc()).offset(offset).limit(limit).all()
            
            results = []
            for file in source_files:
                # Count extracted metadata for this file
                metadata_count = db.query(EntityMetadata).filter(
                    EntityMetadata.source_file_id == file.id
                ).count()
                
                # Get unique metadata names extracted for this file
                unique_metadata = db.query(EntityMetadata.metadata_name).filter(
                    EntityMetadata.source_file_id == file.id
                ).distinct().all()
                unique_metadata_names = [m[0] for m in unique_metadata]
                
                results.append({
                    "id": file.id,
                    "file_name": file.file_name,
                    "file_url": file.file_url,
                    "entity_name": file.entity_name,
                    "us_ma_date": file.us_ma_date,
                    "status": file.status,
                    "metadata_extracted": file.metadata_extracted,
                    "metadata_count": metadata_count,
                    "extracted_metadata_names": unique_metadata_names,
                    "created_at": file.created_at.isoformat() if file.created_at else None,
                    "updated_at": file.updated_at.isoformat() if file.updated_at else None
                })
            
            logger.info(f"Retrieved {len(results)} source files (total: {total_count})")
            
            return {
                "source_files": results,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            logger.error(f"Error getting paginated source files for metadata view: {str(e)}")
            return {
                "source_files": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset
            }
    
    @staticmethod
    def get_metadata_extraction_stats(db: Session) -> Dict[str, Any]:
        """Get statistics for metadata extraction."""
        try:
            # Total files count
            total_files = db.query(SourceFiles).count()
            
            # Files ready for extraction (status is READY or COMPLETED and not yet extracted)
            ready_for_extraction = db.query(SourceFiles).filter(
                SourceFiles.status.in_(['READY', 'COMPLETED']),
                SourceFiles.metadata_extracted == False
            ).count()
            
            # Files with metadata extracted
            metadata_extracted = db.query(SourceFiles).filter(
                SourceFiles.metadata_extracted == True
            ).count()
            
            # Total metadata fields extracted
            total_metadata_fields = db.query(EntityMetadata).count()
            
            return {
                "total": total_files,
                "readyForExtraction": ready_for_extraction,
                "metadataExtracted": metadata_extracted,
                "totalMetadataFields": total_metadata_fields
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata extraction stats: {str(e)}")
            return {
                "total": 0,
                "readyForExtraction": 0,
                "metadataExtracted": 0,
                "totalMetadataFields": 0
            }
    
    @staticmethod
    def extract_metadata_for_source_file(
        source_file_id: int, 
        user_id: int, 
        db: Session
    ) -> Dict[str, Any]:
        """Extract metadata for a specific source file using enhanced multi-pass extraction with increased document retrieval."""
        
        try:
            logger.info(f"Starting enhanced metadata extraction for source_file_id: {source_file_id}")
            
            # Get source file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
            if not source_file:
                return {"success": False, "error": "Source file not found"}
            
            
            # Get active metadata configurations
            metadata_configs = db.query(MetadataConfiguration).filter(
                MetadataConfiguration.is_active == True
            ).all()
            
            if not metadata_configs:
                return {"success": False, "error": "No active metadata configurations found"}
            
            logger.info(f"Found {len(metadata_configs)} active metadata configurations")
            
            # Initialize ChromaDB
            vector_db = QdrantUtil.get_instance()
            
            # Check if documents exist for this file in ChromaDB
            doc_count = vector_db.get_document_count_by_source_file(
                source_file_name=source_file.file_name,
                collection_name="fda_documents"
            )
            
            if doc_count == 0:
                return {
                    "success": False, 
                    "error": f"No documents found in ChromaDB for file: {source_file.file_name}. Please ensure the file is processed and indexed first."
                }
            
            logger.info(f"Found {doc_count} documents in ChromaDB for file: {source_file.file_name}")
            
            # Extract metadata for each configuration with enhanced approach
            extraction_results = []
            successful_extractions = 0
            
            for config in metadata_configs:
                try:
                    logger.info(f"Extracting metadata: {config.metadata_name}")
                    
                    # Enhanced multi-pass extraction with increased document retrieval
                    extraction_result = MetadataExtractionService._enhanced_metadata_extraction(
                        vector_db=vector_db,
                        config=config,
                        source_file=source_file,
                        doc_count=doc_count
                    )
                    
                    if extraction_result["success"]:
                        # Save to database
                        entity_metadata = EntityMetadata(
                            metadata_name=config.metadata_name,
                            value=extraction_result["value"],
                            entityname=source_file.entity_name,
                            source_file_id=source_file_id,
                            file_url=source_file.file_url,
                            extracted_by=user_id,
                            extraction_prompt=config.extraction_prompt,
                            confidence_score=extraction_result["confidence_score"],
                            metadata_details=json.dumps(extraction_result.get("metadata_details", []))
                        )
                        
                        # Check if metadata already exists for this file and metadata name
                        existing = db.query(EntityMetadata).filter(
                            and_(
                                EntityMetadata.source_file_id == source_file_id,
                                EntityMetadata.metadata_name == config.metadata_name
                            )
                        ).first()
                        
                        if existing:
                            # Update existing metadata
                            existing.value = extraction_result["value"]
                            existing.extraction_prompt = config.extraction_prompt
                            existing.extracted_by = user_id
                            existing.confidence_score = extraction_result["confidence_score"]
                            existing.updated_at = datetime.now()
                            existing.metadata_details = json.dumps(extraction_result.get("metadata_details", []))
                            logger.info(f"Updated existing metadata: {config.metadata_name} (confidence: {extraction_result['confidence_score']})")
                        else:
                            # Add new metadata
                            db.add(entity_metadata)
                            logger.info(f"Added new metadata: {config.metadata_name} (confidence: {extraction_result['confidence_score']})")
                        
                        extraction_results.append({
                            "metadata_name": config.metadata_name,
                            "value": extraction_result["value"],
                            "confidence_score": extraction_result["confidence_score"],
                            "status": "success"
                        })
                        successful_extractions += 1
                        
                    else:
                        extraction_results.append({
                            "metadata_name": config.metadata_name,
                            "value": None,
                            "status": "failed",
                            "error": extraction_result.get("error", "Extraction failed")
                        })
                        logger.warning(f"Failed to extract metadata: {config.metadata_name}")
                
                except Exception as e:
                    extraction_results.append({
                        "metadata_name": config.metadata_name,
                        "value": None,
                        "status": "error",
                        "error": str(e)
                    })
                    logger.error(f"Error extracting metadata {config.metadata_name}: {str(e)}")
            
            # Update source file metadata_extracted status
            if successful_extractions > 0:
                source_file.metadata_extracted = True
                source_file.updated_at = datetime.now()
            
            # Commit all changes
            db.commit()
            
            logger.info(f"Metadata extraction completed: {successful_extractions}/{len(metadata_configs)} successful")
            
            
            return {
                "success": True,
                "message": f"Metadata extraction completed: {successful_extractions}/{len(metadata_configs)} successful",
                "extracted_count": successful_extractions,
                "total_configs": len(metadata_configs),
                "results": extraction_results,
            }
            
        except Exception as e:
            logger.error(f"Error in metadata extraction: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _enhanced_metadata_extraction(
        vector_db: QdrantUtil,
        config: MetadataConfiguration,
        source_file: SourceFiles,
        doc_count: int,
    ) -> Dict[str, Any]:
        """Enhanced metadata extraction with increased document retrieval and multi-pass approach."""
        debug_data = {
            "config": config,
            "prompts": {},
            "vector_db_query": {},
            "retrieved_documents": [],
            "llm_responses": {},
            "errors": [],
            "method": "enhanced_multi_pass"
        }
        
        try:
            # Determine optimal number of documents to retrieve (increased from 5 to 15-20)
            # Use more documents for better context, but cap based on available documents
            n_results = min(max(15, doc_count // 3), 20) if doc_count > 5 else doc_count
            
            logger.info(f"Using {n_results} documents for enhanced extraction of {config.metadata_name}")
            
            # Enhanced extraction prompt optimized for high-accuracy metadata extraction
            enhanced_prompt = f"""
🎯 **ULTRA-PRECISION METADATA EXTRACTION**

**TARGET METADATA:** {config.metadata_name}
**FIELD TYPE:** {config.data_type or 'text'} | **DESCRIPTION:** {config.description or 'Comprehensive extraction required'}

**📋 EXTRACTION MANDATE:**
{config.extraction_prompt}

**🔍 ADVANCED ANALYSIS PROTOCOL:**
1. **COMPREHENSIVE SCAN:** Process every word, phrase, and context clue across ALL document chunks
2. **MULTI-LAYER DETECTION:** Identify explicit statements, implicit references, and contextual indicators
3. **CROSS-VALIDATION:** Verify findings across multiple document sections for consistency
4. **TERMINOLOGY EXPANSION:** Consider medical terms, FDA-specific language, abbreviations, and synonyms
5. **REGULATORY COMPLIANCE:** Align with FDA documentation standards and pharmaceutical terminology
6. **EVIDENCE TRIANGULATION:** Build confidence through multiple supporting references

**📊 CONFIDENCE CALIBRATION GUIDE:**
- **95-100%:** Multiple explicit mentions with clear supporting evidence
- **85-94%:** Single clear statement with contextual support
- **75-84%:** Strong implied evidence from context and terminology
- **65-74%:** Moderate evidence requiring interpretation
- **Below 65%:** Weak or ambiguous evidence

**⚡ RESPONSE PROTOCOL (MANDATORY JSON FORMAT):**
```json
{{
    "extracted_value": "precise extracted value or 'Not found in document'",
    "confidence_level": 98,
    "evidence_summary": "Detailed summary of all supporting evidence found across document sections",
    "source_sections": ["specific section names or document parts where evidence was located"],
    "validation_notes": "Cross-reference validation and consistency checks performed"
}}
```

**🎯 OPTIMIZATION DIRECTIVES:**
- Aim for 95-100% confidence by leveraging advanced reasoning capabilities
- Use document context to infer implied information when explicit data is absent
- Cross-reference multiple document chunks to validate extracted information
- Apply medical and regulatory domain knowledge for accurate interpretation

**📄 BEGIN ULTRA-PRECISION EXTRACTION FROM FDA DOCUMENT CONTENT:**
"""
            
            # Store prompt for debugging
            debug_data["prompts"]["enhanced_prompt"] = enhanced_prompt
            
            # First pass: Standard extraction with enhanced document count
            metadata_filter = {"source": source_file.file_name}
            
            # Store query parameters for debugging
            debug_data["vector_db_query"] = {
                "collection_name": "fda_documents",
                "n_results": n_results,
                "filter": metadata_filter,
                "metadata_name": config.metadata_name,
                "enable_document_grading": True
            }
            
            # Use enhanced metadata extraction method for better confidence
            enhanced_result = vector_db.query_with_llm_enhanced_metadata(
                query=enhanced_prompt,
                collection_name="fda_documents",
                n_results=n_results,  # Increased from 5 to 15-20
                filter_dict=metadata_filter,
                metadata_name=config.metadata_name,
                enable_document_grading=True
            )
            
            # Store retrieved documents for debugging
            if "documents" in enhanced_result:
                debug_data["retrieved_documents"] = enhanced_result["documents"]
            elif "metadata_details" in enhanced_result:
                debug_data["retrieved_documents"] = enhanced_result["metadata_details"]
            
            response = enhanced_result.get("response", "")
            debug_data["llm_responses"]["first_pass"] = response
            
            # Handle case where response might be a dict or other non-string type
            if isinstance(response, dict):
                # If response is already a dict, convert to string for parsing
                response = json.dumps(response)
            elif not isinstance(response, str):
                # Convert any other type to string
                response = str(response) if response else ""
            
            if not response or (isinstance(response, str) and response.strip() == ""):
                return {"success": False, "error": "No response from LLM"}
            
            # Parse the JSON response
            parsed_result = MetadataExtractionService._parse_enhanced_response(response)
            
            if not parsed_result["success"]:
                # Fallback: Try with simplified prompt if JSON parsing failed
                logger.warning(f"JSON parsing failed for {config.metadata_name}, trying fallback extraction")
                fallback_result = MetadataExtractionService._fallback_extraction(
                    vector_db, config, source_file, n_results
                )
                return fallback_result
            
            extracted_value = parsed_result["extracted_value"]
            confidence = parsed_result["confidence_level"]
            
            # Use enhanced confidence from ChromaDB utility if available
            enhanced_confidence = enhanced_result.get("confidence_score", 0.0) * 100
            if enhanced_confidence > confidence:
                confidence = enhanced_confidence
                logger.info(f"Using enhanced confidence score: {confidence}% for {config.metadata_name}")
            
            # If confidence is low, try second pass with different approach
            if confidence < 80 and extracted_value != "Not found in document":
                logger.info(f"Low confidence ({confidence}%), attempting second pass extraction")
                second_pass_result = MetadataExtractionService._second_pass_extraction(
                    vector_db, config, source_file, n_results, extracted_value
                )
                
                if second_pass_result["success"] and second_pass_result["confidence_score"] > confidence:
                    confidence = second_pass_result["confidence_score"]
                    extracted_value = second_pass_result["value"]
                    logger.info(f"Second pass improved confidence to {confidence}%")
            
            # Clean and validate the response
            if extracted_value and extracted_value != "Not found in document":
                cleaned_value = MetadataExtractionService._clean_extracted_value(
                    extracted_value, config.data_type
                )
                
                # Boost confidence for successfully cleaned and validated data
                if cleaned_value != extracted_value:
                    confidence = min(confidence + 5, 100)  # Small boost for successful cleaning
                
                result = {
                    "success": True,
                    "value": cleaned_value,
                    "confidence_score": confidence / 100.0,  # Convert to 0-1 range
                    "evidence": parsed_result.get("evidence_summary", ""),
                    "source_sections": parsed_result.get("source_sections", []),
                    "metadata_details": enhanced_result.get("metadata_details", [])  # Include document details
                }
                
                # Log successful extraction
                debug_data["final_result"] = result
                
                return result
            else:
                result = {
                    "success": False,
                    "error": "Metadata not found in document",
                    "confidence_score": 0.0
                }
                
                # Log failed extraction
                debug_data["final_result"] = result
                
                return result
                
        except Exception as e:
            logger.error(f"Error in enhanced metadata extraction: {str(e)}")
            
            # Log error
            debug_data["errors"].append(str(e))
            debug_data["final_result"] = {"success": False, "error": str(e)}
            
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _parse_enhanced_response(response: str) -> Dict[str, Any]:
        """Parse the enhanced JSON response from the language model."""
        try:
            # Ensure response is a string
            if not isinstance(response, str):
                response = str(response) if response else ""
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                
                # Check if this is the expected format with extracted_value
                if "extracted_value" in parsed:
                    return {
                        "success": True,
                        "extracted_value": parsed.get("extracted_value", ""),
                        "confidence_level": parsed.get("confidence_level", 50),
                        "evidence_summary": parsed.get("evidence_summary", ""),
                        "source_sections": parsed.get("source_sections", []),
                        "validation_notes": parsed.get("validation_notes", "")
                    }
                else:
                    # Handle complex/nested JSON responses (like Basic Entity Information)
                    # Convert the entire JSON to a formatted string
                    if isinstance(parsed, dict):
                        # Calculate average confidence if multiple fields have confidence levels
                        confidence_sum = 0
                        confidence_count = 0
                        evidence_parts = []
                        source_sections = []
                        
                        # Format the nested JSON into a readable text format
                        formatted_parts = []
                        for key, value in parsed.items():
                            if isinstance(value, dict):
                                # Handle nested structures
                                extracted = value.get("extracted_value", value.get("value", ""))
                                if extracted and extracted != "Not found in document":
                                    formatted_key = key.replace("_", " ").title()
                                    formatted_parts.append(f"{formatted_key}: {extracted}")
                                
                                # Collect confidence scores
                                if "confidence_level" in value:
                                    confidence_sum += value["confidence_level"]
                                    confidence_count += 1
                                
                                # Collect evidence
                                if "evidence_summary" in value:
                                    evidence_parts.append(value["evidence_summary"])
                                
                                # Collect source sections
                                if "source_sections" in value:
                                    source_sections.extend(value["source_sections"])
                            else:
                                # Simple key-value pairs
                                formatted_key = key.replace("_", " ").title()
                                formatted_parts.append(f"{formatted_key}: {value}")
                        
                        # Calculate average confidence
                        avg_confidence = (confidence_sum / confidence_count) if confidence_count > 0 else 85
                        
                        # Join all parts into a comprehensive response
                        extracted_value = "\n".join(formatted_parts) if formatted_parts else json.dumps(parsed, indent=2)
                        
                        return {
                            "success": True,
                            "extracted_value": extracted_value,
                            "confidence_level": avg_confidence,
                            "evidence_summary": " | ".join(evidence_parts) if evidence_parts else "Complex structured data extracted",
                            "source_sections": list(set(source_sections)),  # Remove duplicates
                            "validation_notes": "Parsed from complex JSON structure"
                        }
                    else:
                        # If not a dict, convert to string
                        return {
                            "success": True,
                            "extracted_value": str(parsed),
                            "confidence_level": 80,
                            "evidence_summary": "JSON data extracted",
                            "source_sections": []
                        }
            else:
                # If no JSON found, treat entire response as extracted value
                return {
                    "success": True,
                    "extracted_value": response.strip(),
                    "confidence_level": 60,  # Medium confidence for non-JSON response
                    "evidence_summary": "Direct text extraction",
                    "source_sections": []
                }
                
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Failed to parse JSON response"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error parsing response: {str(e)}"
            }
    
    @staticmethod
    def _fallback_extraction(
        vector_db: QdrantUtil,
        config: MetadataConfiguration,
        source_file: SourceFiles,
        n_results: int
    ) -> Dict[str, Any]:
        """Fallback extraction with simplified prompt."""
        try:
            simple_prompt = f"""
Extract the following information from this FDA document: {config.metadata_name}

{config.extraction_prompt}

Provide only the extracted value. If not found, respond with "Not found in document".
"""
            
            metadata_filter = {"source": source_file.file_name}
            
            # Use enhanced query to get metadata details
            enhanced_result = vector_db.query_with_llm_enhanced_metadata(
                query=simple_prompt,
                collection_name="fda_documents",
                n_results=n_results,
                filter_dict=metadata_filter
            )
            
            response = enhanced_result.get("response", "")
            
            # Handle case where response might be a dict or other non-string type
            if isinstance(response, dict):
                response = json.dumps(response)
            elif not isinstance(response, str):
                response = str(response) if response else ""
            
            if response and isinstance(response, str) and response.strip() and response.strip() != "Not found in document":
                cleaned_value = MetadataExtractionService._clean_extracted_value(
                    response.strip(), config.data_type
                )
                return {
                    "success": True,
                    "value": cleaned_value,
                    "confidence_score": 0.75,  # Medium confidence for fallback
                    "metadata_details": enhanced_result.get("metadata_details", [])  # Include document details
                }
            else:
                return {
                    "success": False,
                    "error": "No valid response from fallback extraction"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Fallback extraction failed: {str(e)}"
            }
    
    @staticmethod
    def _second_pass_extraction(
        vector_db: QdrantUtil,
        config: MetadataConfiguration,
        source_file: SourceFiles,
        n_results: int,
        first_pass_value: str
    ) -> Dict[str, Any]:
        """Second pass extraction to validate and improve confidence."""
        try:
            validation_prompt = f"""
You previously extracted this value for {config.metadata_name}: "{first_pass_value}"

Please verify this extraction by re-examining the FDA document. Look for:
1. Confirmation of the extracted value
2. Alternative representations or synonyms
3. Any contradictory information
4. Additional supporting evidence

{config.extraction_prompt}

Respond with JSON:
{{
    "verified_value": "confirmed value or corrected value",
    "confidence": 95,
    "validation_notes": "explanation of verification"
}}
"""
            
            metadata_filter = {"source": source_file.file_name}
            
            # Use enhanced query to get metadata details
            enhanced_result = vector_db.query_with_llm_enhanced_metadata(
                query=validation_prompt,
                collection_name="fda_documents",
                n_results=n_results,
                filter_dict=metadata_filter
            )
            
            response = enhanced_result.get("response", "")
            
            # Parse validation response
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    verified_value = parsed.get("verified_value", first_pass_value)
                    confidence = parsed.get("confidence", 80)
                    
                    if verified_value and verified_value != "Not found in document":
                        cleaned_value = MetadataExtractionService._clean_extracted_value(
                            verified_value, config.data_type
                        )
                        return {
                            "success": True,
                            "value": cleaned_value,
                            "confidence_score": confidence / 100.0,
                            "metadata_details": enhanced_result.get("metadata_details", [])  # Include document details
                        }
                
            except (json.JSONDecodeError, TypeError):
                pass  # Fall through to fallback
            
            # Fallback: return original with slight confidence boost
            return {
                "success": True,
                "value": first_pass_value,
                "confidence_score": 0.82,  # Slight boost for second pass attempt
                "metadata_details": enhanced_result.get("metadata_details", [])  # Include document details even in fallback
            }
            
        except Exception as e:
            logger.error(f"Second pass extraction error: {str(e)}")
            return {
                "success": False,
                "error": f"Second pass failed: {str(e)}"
            }

    @staticmethod
    def get_extracted_metadata_for_source_file(source_file_id: int, db: Session) -> Dict[str, Any]:
        """Get extracted metadata for a specific source file for viewing, including all active configurations."""
        try:
            logger.info(f"Getting extracted metadata for source_file_id: {source_file_id}")
            
            # Get source file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
            if not source_file:
                return {"success": False, "error": "Source file not found"}
            
            # Get all active metadata configurations
            active_configs = db.query(MetadataConfiguration).filter(
                MetadataConfiguration.is_active == True
            ).order_by(MetadataConfiguration.metadata_name).all()
            
            # Get extracted metadata
            extracted_metadata = db.query(EntityMetadata).filter(
                EntityMetadata.source_file_id == source_file_id
            ).all()
            
            # Create a dictionary for quick lookup
            extracted_dict = {meta.metadata_name: meta for meta in extracted_metadata}
            
            # Format metadata for display - include all active configurations
            metadata_list = []
            for config in active_configs:
                if config.metadata_name in extracted_dict:
                    # Metadata was extracted
                    metadata = extracted_dict[config.metadata_name]
                    metadata_list.append({
                        "id": metadata.id,
                        "metadata_name": metadata.metadata_name,
                        "value": metadata.value,
                        "entityname": metadata.entityname,
                        "source_file_id": metadata.source_file_id,
                        "file_url": metadata.file_url,
                        "extracted_by": metadata.extracted_by,
                        "extraction_prompt": metadata.extraction_prompt,
                        "confidence_score": metadata.confidence_score,
                        "metadata_details": metadata.metadata_details,  # Include metadata_details
                        "created_at": metadata.created_at.isoformat() if metadata.created_at else None,
                        "updated_at": metadata.updated_at.isoformat() if metadata.updated_at else None
                    })
                else:
                    # Metadata was not extracted - show as "Not found" or "Not extracted"
                    metadata_list.append({
                        "id": None,
                        "metadata_name": config.metadata_name,
                        "value": None,  # Will show as "Not found" in UI
                        "entityname": source_file.entity_name,
                        "source_file_id": source_file_id,
                        "file_url": source_file.file_url,
                        "extracted_by": None,
                        "extraction_prompt": config.extraction_prompt,
                        "confidence_score": 0,
                        "metadata_details": None,  # No metadata details for not found
                        "created_at": None,
                        "updated_at": None
                    })
            
            return {
                "success": True,
                "source_file": {
                    "id": source_file.id,
                    "file_name": source_file.file_name,
                    "entity_name": source_file.entity_name,
                    "file_url": source_file.file_url
                },
                "metadata": metadata_list,
                "total_count": len(metadata_list)
            }
            
        except Exception as e:
            logger.error(f"Error getting extracted metadata: {str(e)}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _clean_extracted_value(value: str, data_type: str) -> str:
        """Clean and validate extracted metadata value based on data type."""
        if not value:
            return ""
        
        # Ensure value is a string
        if not isinstance(value, str):
            value = str(value)
        
        # Remove common prefixes and clean up the value
        cleaned_value = value.strip()
        
        # Remove common response patterns
        prefixes_to_remove = [
            "According to the document,",
            "Based on the FDA document,", 
            "The document states that",
            "From the document:",
            "The FDA document indicates",
            "According to FDA documentation,",
            "Based on the provided information,"
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned_value.lower().startswith(prefix.lower()):
                cleaned_value = cleaned_value[len(prefix):].strip()
        
        # Data type specific cleaning
        if data_type:
            data_type_lower = data_type.lower()
            
            if data_type_lower in ['number', 'integer', 'float']:
                # Extract numeric values
                numeric_match = re.search(r'[\d.,]+', cleaned_value)
                if numeric_match:
                    cleaned_value = numeric_match.group(0)
            
            elif data_type_lower in ['date', 'datetime']:
                # Extract date patterns
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{4}-\d{1,2}-\d{1,2}',
                    r'\w+ \d{1,2}, \d{4}',
                    r'\d{1,2} \w+ \d{4}'
                ]
                for pattern in date_patterns:
                    date_match = re.search(pattern, cleaned_value)
                    if date_match:
                        cleaned_value = date_match.group(0)
                        break
            
            elif data_type_lower == 'boolean':
                # Convert to boolean representation
                value_lower = cleaned_value.lower()
                if any(word in value_lower for word in ['yes', 'true', 'approved', 'positive']):
                    cleaned_value = "Yes"
                elif any(word in value_lower for word in ['no', 'false', 'denied', 'negative']):
                    cleaned_value = "No"
        
        # Final cleanup
        cleaned_value = re.sub(r'\s+', ' ', cleaned_value)  # Normalize whitespace
        cleaned_value = cleaned_value.strip('"\'')  # Remove quotes
        
        return cleaned_value

    @staticmethod
    def delete_extracted_metadata(source_file_id: int, db: Session) -> Dict[str, Any]:
        """Delete all extracted metadata for a source file and reset its metadata_extracted status."""
        try:
            logger.info(f"Deleting extracted metadata for source_file_id: {source_file_id}")
            
            # Get source file
            source_file = db.query(SourceFiles).filter(SourceFiles.id == source_file_id).first()
            if not source_file:
                return {"success": False, "error": "Source file not found"}
            
            # Delete all metadata for this source file
            deleted_count = db.query(EntityMetadata).filter(
                EntityMetadata.source_file_id == source_file_id
            ).delete()
            
            # Reset metadata_extracted status
            source_file.metadata_extracted = False
            source_file.updated_at = datetime.now()
            
            # Commit changes
            db.commit()
            
            logger.info(f"Deleted {deleted_count} metadata entries for source file: {source_file.file_name}")
            
            return {
                "success": True,
                "message": f"Successfully deleted {deleted_count} metadata entries",
                "deleted_count": deleted_count,
                "source_file_name": source_file.file_name
            }
            
        except Exception as e:
            logger.error(f"Error deleting extracted metadata: {str(e)}")
            db.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_all_metadata_for_export(db: Session) -> Dict[str, Any]:
        """Get all metadata using join query for JSON and Excel export."""
        try:
            logger.info("Getting all metadata for export using join query")
            
            # Use the join query with MetadataConfiguration to include only active metadata
            from sqlalchemy import text
            query = text("""
            SELECT
              sf.entity_name,
              sf.us_ma_date,
              sf.file_url AS document_url,
              dm.metadata_name,
              dm.value,
              dm.confidence_score,
              dm.created_at
            FROM SourceFiles sf
            JOIN EntityMetadata dm ON sf.id = dm.source_file_id
            JOIN MetadataConfiguration mc ON dm.metadata_name = mc.metadata_name
            WHERE mc.is_active = true
            ORDER BY sf.entity_name, sf.us_ma_date
            """)
            
            result = db.execute(query)
            rows = result.fetchall()
            
            # Group data by entity_name and us_ma_date for JSON structure
            grouped_data = {}
            flat_data = []
            
            for row in rows:
                entity_name = row[0] or 'Unknown Entity'
                us_ma_date = row[1] or 'No Date'
                document_url = row[2] or ''
                metadata_name = row[3] or ''
                value = row[4] or 'Not found'
                confidence_score = row[5] if row[5] is not None else 0.0
                # Handle both datetime and string types for created_at
                extraction_date = ''
                if row[6]:
                    if isinstance(row[6], str):
                        extraction_date = row[6]
                    else:
                        extraction_date = row[6].strftime('%Y-%m-%d %H:%M:%S')
                
                # For JSON structure (grouped)
                if entity_name not in grouped_data:
                    grouped_data[entity_name] = {}
                if us_ma_date not in grouped_data[entity_name]:
                    grouped_data[entity_name][us_ma_date] = {
                        'documentUrl': document_url,
                        'metadata': {}
                    }
                
                grouped_data[entity_name][us_ma_date]['metadata'][metadata_name] = {
                    'value': value,
                    'confidence_score': confidence_score,
                    'extraction_date': extraction_date
                }
                
                # For Excel structure (flat)
                flat_data.append({
                    'File URL': document_url,
                    'Entity Name': entity_name,
                    'US MA Date': us_ma_date,
                    'Metadata Name': metadata_name,
                    'Extracted Value': value,
                    'Confidence Score': f"{confidence_score:.2f}" if confidence_score > 0 else '',
                    'Extraction Date': extraction_date
                })
            
            logger.info(f"Retrieved {len(rows)} metadata records for {len(grouped_data)} entities")
            
            return {
                "success": True,
                "grouped_data": grouped_data,
                "flat_data": flat_data,
                "total_records": len(rows),
                "total_entities": len(grouped_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata for export: {str(e)}")
            return {"success": False, "error": str(e)}