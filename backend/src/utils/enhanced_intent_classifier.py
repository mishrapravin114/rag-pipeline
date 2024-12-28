"""
Enhanced Intent Classifier for better conversation support
"""
import logging
from typing import List, Tuple, Optional
from enum import Enum
from utils.llm_util import get_llm
import re

logger = logging.getLogger(__name__)


class EnhancedIntent(Enum):
    """Enhanced intent types for better conversation understanding"""
    NEW_TOPIC = "new_topic"
    FOLLOW_UP_FILTER = "follow_up_filter"  # e.g., "list top 3", "show only serious ones"
    FOLLOW_UP_DETAIL = "follow_up_detail"  # e.g., "tell me more about X"
    FOLLOW_UP_COMPARISON = "follow_up_comparison"  # e.g., "how does it compare to Y"
    CLARIFICATION = "clarification"  # e.g., "what do you mean by X"
    REFERENCE_PREVIOUS = "reference_previous"  # Direct reference to previous response
    META_QUESTION = "meta_question"  # Questions about the system or process


class EnhancedIntentClassifier:
    """Enhanced intent classification with better follow-up detection"""
    
    def __init__(self):
        self.llm = get_llm()
        
        # Keywords that strongly indicate follow-up questions
        self.follow_up_indicators = {
            'filter': ['top', 'first', 'last', 'only', 'just', 'list', 'show me'],
            'reference': ['this', 'that', 'these', 'those', 'it', 'they', 'them'],
            'continuation': ['also', 'additionally', 'furthermore', 'what about', 'how about'],
            'clarification': ['mean', 'explain', 'clarify', 'what is'],
            'comparison': ['compare', 'versus', 'vs', 'difference', 'better', 'worse']
        }
    
    async def classify_intent_with_context(
        self,
        current_query: str,
        chat_history: List[Tuple[str, str]],
        last_response: Optional[str] = None
    ) -> Tuple[EnhancedIntent, float, str]:
        """
        Classify intent with enhanced context understanding
        
        Returns:
            Tuple of (intent, confidence, reasoning)
        """
        # Quick pattern matching for obvious follow-ups
        quick_intent = self._quick_pattern_match(current_query, last_response)
        if quick_intent:
            return quick_intent
        
        # Use LLM for more complex classification
        return await self._llm_classification(current_query, chat_history, last_response)
    
    def _quick_pattern_match(
        self,
        query: str,
        last_response: Optional[str]
    ) -> Optional[Tuple[EnhancedIntent, float, str]]:
        """Quick pattern matching for obvious cases"""
        query_lower = query.lower()
        
        # Check for filter follow-ups (e.g., "list top 3", "show only serious ones")
        filter_patterns = [
            r'\b(top|first|last)\s+\d+\b',
            r'\b(only|just)\s+(the\s+)?(serious|severe|mild|common)',
            r'\blist\s+(only|just)?\s*(the\s+)?',
            r'\bshow\s+me\s+(only|just)?\s*(the\s+)?'
        ]
        
        for pattern in filter_patterns:
            if re.search(pattern, query_lower):
                if last_response:  # Only if there's a previous response to filter
                    return (
                        EnhancedIntent.FOLLOW_UP_FILTER,
                        0.95,
                        "Query contains filtering/listing pattern with previous context"
                    )
        
        # Check for direct references without context
        if any(word in query_lower.split() for word in ['this', 'that', 'it', 'they']):
            if len(query_lower.split()) < 10:  # Short queries with references
                return (
                    EnhancedIntent.REFERENCE_PREVIOUS,
                    0.9,
                    "Short query with direct reference pronouns"
                )
        
        return None
    
    async def _llm_classification(
        self,
        current_query: str,
        chat_history: List[Tuple[str, str]],
        last_response: Optional[str]
    ) -> Tuple[EnhancedIntent, float, str]:
        """Use LLM for sophisticated intent classification"""
        
        # Build context for classification
        context = ""
        if chat_history:
            last_exchange = chat_history[-1] if chat_history else None
            if last_exchange:
                user_q, assistant_r = last_exchange
                # Truncate for prompt efficiency
                context = f"Last User Question: {user_q[:200]}...\n"
                context += f"Last Assistant Response: {assistant_r[:300]}...\n"
        
        prompt = f"""Classify the intent of this user query in a pharmaceutical conversation.

CONTEXT:
{context if context else "No previous conversation"}

CURRENT QUERY: {current_query}

INTENT TYPES:
1. NEW_TOPIC - Completely new question unrelated to previous discussion
2. FOLLOW_UP_FILTER - Wants to filter/narrow down previous response (e.g., "show top 3", "only serious ones")
3. FOLLOW_UP_DETAIL - Wants more details about something from previous response
4. FOLLOW_UP_COMPARISON - Wants to compare with something else
5. CLARIFICATION - Needs clarification about previous response
6. REFERENCE_PREVIOUS - Direct reference to previous response using pronouns
7. META_QUESTION - Question about the system or how it works

ANALYSIS:
1. Does the query reference the previous response? (pronouns, implicit references)
2. Is it asking to filter or reorganize previous information?
3. Is it a completely new topic?

Respond with ONLY the intent type and confidence (0-1):
INTENT: [type]
CONFIDENCE: [0.0-1.0]"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse response
            intent_match = re.search(r'INTENT:\s*(\w+)', content)
            confidence_match = re.search(r'CONFIDENCE:\s*([\d.]+)', content)
            
            if intent_match and confidence_match:
                intent_str = intent_match.group(1).upper()
                confidence = float(confidence_match.group(1))
                
                # Map to enum
                intent_map = {
                    'NEW_TOPIC': EnhancedIntent.NEW_TOPIC,
                    'FOLLOW_UP_FILTER': EnhancedIntent.FOLLOW_UP_FILTER,
                    'FOLLOW_UP_DETAIL': EnhancedIntent.FOLLOW_UP_DETAIL,
                    'FOLLOW_UP_COMPARISON': EnhancedIntent.FOLLOW_UP_COMPARISON,
                    'CLARIFICATION': EnhancedIntent.CLARIFICATION,
                    'REFERENCE_PREVIOUS': EnhancedIntent.REFERENCE_PREVIOUS,
                    'META_QUESTION': EnhancedIntent.META_QUESTION
                }
                
                intent = intent_map.get(intent_str, EnhancedIntent.NEW_TOPIC)
                reasoning = f"LLM classified as {intent_str} with {confidence:.2f} confidence"
                
                return (intent, confidence, reasoning)
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
        
        # Default fallback
        return (EnhancedIntent.NEW_TOPIC, 0.5, "Failed to classify, defaulting to new topic")