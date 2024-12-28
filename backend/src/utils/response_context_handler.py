"""
Response Context Handler for processing follow-up questions
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from utils.llm_util import get_llm
from utils.enhanced_intent_classifier import EnhancedIntent
import json
import re

logger = logging.getLogger(__name__)


class ResponseContextHandler:
    """Handles follow-up questions using previous response context"""
    
    def __init__(self):
        self.llm = get_llm()
    
    async def process_follow_up_query(
        self,
        current_query: str,
        previous_response: str,
        intent: EnhancedIntent,
        original_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process follow-up queries using the previous response as context
        
        Args:
            current_query: The follow-up question
            previous_response: The previous assistant response
            intent: Classified intent of the follow-up
            original_query: The original query that generated the previous response
            
        Returns:
            Dict with processed response and metadata
        """
        logger.info(f"Processing follow-up with intent: {intent.value}")
        
        # Clean HTML from previous response if present
        clean_previous = self._clean_html_tags(previous_response)
        
        # Handle different intent types
        if intent == EnhancedIntent.FOLLOW_UP_FILTER:
            return await self._handle_filter_request(current_query, clean_previous, original_query)
        elif intent == EnhancedIntent.FOLLOW_UP_DETAIL:
            return await self._handle_detail_request(current_query, clean_previous, original_query)
        elif intent == EnhancedIntent.REFERENCE_PREVIOUS:
            return await self._handle_reference_request(current_query, clean_previous, original_query)
        elif intent == EnhancedIntent.CLARIFICATION:
            return await self._handle_clarification_request(current_query, clean_previous, original_query)
        else:
            # For other intents, enhance the query with context
            return await self._handle_general_follow_up(current_query, clean_previous, original_query)
    
    def _clean_html_tags(self, text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return text
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()
    
    async def _handle_filter_request(
        self,
        query: str,
        previous_response: str,
        original_query: Optional[str]
    ) -> Dict[str, Any]:
        """Handle filtering requests like 'show top 3' or 'only serious ones'"""
        
        prompt = f"""You are processing a follow-up filter request on a previous pharmaceutical response.

ORIGINAL QUESTION: {original_query or "Not provided"}

PREVIOUS RESPONSE:
{previous_response[:2000]}...

FOLLOW-UP REQUEST: {query}

TASK: Extract and filter information from the previous response based on the follow-up request.

RULES:
1. ONLY use information from the previous response
2. If asking for "top N", select the first N items from any list
3. If asking for specific criteria (serious, mild, etc.), filter accordingly
4. Maintain the same format and structure as the original
5. If the requested filter cannot be applied, explain why

Filtered Response:"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'response': content,
                'type': 'filtered',
                'used_previous_context': True,
                'needs_document_search': False,
                'metadata': {
                    'intent': 'follow_up_filter',
                    'processed_from': 'previous_response'
                }
            }
            
        except Exception as e:
            logger.error(f"Error in filter processing: {e}")
            return {
                'response': "I encountered an error processing your filter request. Please try rephrasing.",
                'type': 'error',
                'used_previous_context': False,
                'needs_document_search': False
            }
    
    async def _handle_detail_request(
        self,
        query: str,
        previous_response: str,
        original_query: Optional[str]
    ) -> Dict[str, Any]:
        """Handle requests for more details about something in previous response"""
        
        prompt = f"""You are providing more details based on a previous pharmaceutical response.

ORIGINAL QUESTION: {original_query or "Not provided"}

PREVIOUS RESPONSE:
{previous_response[:2000]}...

FOLLOW-UP REQUEST: {query}

TASK: Identify what the user wants more details about and provide an enhanced query for document search.

ANALYSIS:
1. What specific aspect is the user asking about?
2. What drug/topic from the previous response is relevant?
3. What additional information would be helpful?

Generate an enhanced search query that will find detailed information about the requested topic.
Include drug names, specific aspects, and medical terms.

Enhanced Search Query:"""

        try:
            response = await self.llm.ainvoke(prompt)
            enhanced_query = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'response': None,  # Will be filled by document search
                'enhanced_query': enhanced_query.strip(),
                'type': 'detail_request',
                'used_previous_context': True,
                'needs_document_search': True,
                'metadata': {
                    'intent': 'follow_up_detail',
                    'original_aspect': query
                }
            }
            
        except Exception as e:
            logger.error(f"Error in detail request processing: {e}")
            return self._fallback_response(query)
    
    async def _handle_reference_request(
        self,
        query: str,
        previous_response: str,
        original_query: Optional[str]
    ) -> Dict[str, Any]:
        """Handle queries with pronouns referencing previous content"""
        
        prompt = f"""You are resolving pronoun references in a pharmaceutical conversation.

ORIGINAL QUESTION: {original_query or "Not provided"}

PREVIOUS RESPONSE:
{previous_response[:1500]}...

FOLLOW-UP WITH PRONOUNS: {query}

TASK: 
1. Identify what "this", "that", "it", "they" etc. refer to from the previous response
2. Rewrite the query with explicit references instead of pronouns
3. Include relevant drug names and medical terms

EXAMPLE:
- Follow-up: "What are the contraindications for this?"
- If previous was about Keytruda: "What are the contraindications for Keytruda pembrolizumab?"

Rewritten Query with Explicit References:"""

        try:
            response = await self.llm.ainvoke(prompt)
            resolved_query = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'response': None,
                'enhanced_query': resolved_query.strip(),
                'type': 'reference_resolved',
                'used_previous_context': True,
                'needs_document_search': True,
                'metadata': {
                    'intent': 'reference_previous',
                    'original_with_pronouns': query,
                    'resolved_references': resolved_query.strip()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in reference resolution: {e}")
            return self._fallback_response(query)
    
    async def _handle_clarification_request(
        self,
        query: str,
        previous_response: str,
        original_query: Optional[str]
    ) -> Dict[str, Any]:
        """Handle clarification requests about previous response"""
        
        prompt = f"""You are clarifying information from a previous pharmaceutical response.

PREVIOUS RESPONSE:
{previous_response[:2000]}...

CLARIFICATION REQUEST: {query}

TASK: Provide a clear, detailed explanation addressing the clarification request.
Focus on the specific aspect the user is asking about.
Use information from the previous response and expand where needed.

Clarification:"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'response': content,
                'type': 'clarification',
                'used_previous_context': True,
                'needs_document_search': False,
                'metadata': {
                    'intent': 'clarification',
                    'clarified_aspect': query
                }
            }
            
        except Exception as e:
            logger.error(f"Error in clarification processing: {e}")
            return self._fallback_response(query)
    
    async def _handle_general_follow_up(
        self,
        query: str,
        previous_response: str,
        original_query: Optional[str]
    ) -> Dict[str, Any]:
        """Handle general follow-up questions"""
        
        # Extract key entities from previous response
        entities = self._extract_key_entities(previous_response)
        
        # Enhance query with context
        enhanced_query = query
        if entities.get('drugs'):
            enhanced_query += f" {' '.join(entities['drugs'])}"
        
        return {
            'response': None,
            'enhanced_query': enhanced_query,
            'type': 'general_follow_up',
            'used_previous_context': True,
            'needs_document_search': True,
            'metadata': {
                'extracted_entities': entities
            }
        }
    
    def _extract_key_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract drug names and key medical terms from text"""
        entities = {
            'drugs': [],
            'conditions': [],
            'terms': []
        }
        
        # Simple pattern matching for drug names (can be enhanced)
        # Look for capitalized words that might be drug names
        drug_patterns = [
            r'\b[A-Z][a-z]+(?:mab|nib|tide|cycline|statin|pril|sartan|olol|azole)\b',
            r'\b[A-Z][a-z]+\s+\([a-z]+\)',  # Drug (generic)
        ]
        
        for pattern in drug_patterns:
            matches = re.findall(pattern, text)
            entities['drugs'].extend(matches)
        
        # Remove duplicates
        entities['drugs'] = list(set(entities['drugs']))
        
        return entities
    
    def _fallback_response(self, query: str) -> Dict[str, Any]:
        """Fallback response when processing fails"""
        return {
            'response': None,
            'enhanced_query': query,  # Use original query
            'type': 'fallback',
            'used_previous_context': False,
            'needs_document_search': True,
            'metadata': {
                'reason': 'processing_failed'
            }
        }
    
    def should_use_previous_response(self, intent: EnhancedIntent) -> bool:
        """Determine if we should process using previous response or search documents"""
        return intent in [
            EnhancedIntent.FOLLOW_UP_FILTER,
            EnhancedIntent.CLARIFICATION
        ]