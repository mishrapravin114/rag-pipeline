"""
Custom Qdrant wrapper that transforms payloads to match Agno's expected format
"""
import logging
from typing import List, Dict, Any, Optional
from agno.vectordb.qdrant import Qdrant
from agno.document import Document
from qdrant_client import models

logger = logging.getLogger(__name__)


class CustomQdrantWrapper(Qdrant):
    """
    Custom Qdrant wrapper that transforms document payloads to match Agno's expected format.
    
    Our Qdrant collections have fields at root level (source, drug_name, content, etc.)
    but Agno expects specific field names: name, meta_data, content.
    """
    
    def _build_search_results(self, results, query: str) -> List[Document]:
        """
        Override to transform our payload format to Agno's expected format.
        
        Our format:
        - file_name or source -> name
        - all fields except content -> meta_data
        - content -> content
        """
        search_results: List[Document] = []
        
        for result in results:
            if result.payload is None:
                continue
                
            # Extract content
            content = result.payload.get("content", "")
            
            # Use file_name or source as the name
            name = result.payload.get("file_name") or result.payload.get("source", "unknown")
            
            # All other fields go into meta_data
            meta_data = {}
            for key, value in result.payload.items():
                if key != "content":  # Everything except content goes to meta_data
                    meta_data[key] = value
            
            # Create Document with Agno's expected format
            search_results.append(
                Document(
                    name=name,
                    meta_data=meta_data,
                    content=content,
                    embedding=result.vector
                )
            )
            
        # Apply reranking if configured
        if self.reranker is not None:
            search_results = self.reranker.rerank(query=query, documents=search_results)
            
        logger.info(f"Found {len(search_results)} documents")
        return search_results
    
    def _format_filters(self, filters: Optional[Dict[str, Any]]) -> Optional[models.Filter]:
        """
        Override to handle filters at root level instead of under meta_data.
        
        Since our Qdrant collection has fields at root level, we don't need
        to add the 'meta_data.' prefix that Agno normally adds.
        """
        if not filters:
            return None
            
        filter_conditions = []
        for key, value in filters.items():
            # Don't add meta_data prefix - our fields are at root level
            if isinstance(value, dict):
                # Handle operators like $in
                if "$in" in value:
                    # Qdrant uses MatchAny for 'in' operations
                    filter_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=value["$in"])
                        )
                    )
                else:
                    # Handle other nested dictionaries if needed
                    for sub_key, sub_value in value.items():
                        filter_conditions.append(
                            models.FieldCondition(
                                key=f"{key}.{sub_key}",
                                match=models.MatchValue(value=sub_value)
                            )
                        )
            else:
                # Direct key-value pairs
                filter_conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
        
        if filter_conditions:
            return models.Filter(must=filter_conditions)
        
        return None