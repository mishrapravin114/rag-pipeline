from enum import Enum
from typing import List, Tuple, Optional
import logging
from utils.llm_util import get_llm

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    NEW_TOPIC = "new_topic"
    FOLLOW_UP = "follow_up" 
    CLARIFICATION = "clarification"
    OFF_TOPIC = "off_topic"

class IntentClassifier:
    """Classifies user query intent for optimal retrieval strategy"""
    
    def __init__(self):
        self.llm = get_llm()
    
    async def classify_intent(
        self, 
        query: str, 
        chat_history: List[Tuple[str, str]],
        use_fast_classification: bool = True
    ) -> QueryIntent:
        """
        Classifies the user's query intent based on conversation context
        
        Args:
            query: Current user query
            chat_history: List of (user_query, assistant_response) tuples
            use_fast_classification: Use pattern matching before LLM
            
        Returns:
            QueryIntent enum value
        """
        # Fast pattern-based classification
        if use_fast_classification:
            intent = self._fast_classify(query, chat_history)
            if intent != QueryIntent.OFF_TOPIC:  # OFF_TOPIC as fallback
                return intent
        
        # LLM-based classification for complex cases
        return await self._llm_classify(query, chat_history)
    
    def _fast_classify(
        self, 
        query: str, 
        chat_history: List[Tuple[str, str]]
    ) -> QueryIntent:
        """Fast pattern-based classification"""
        query_lower = query.lower()
        
        # No history = new topic
        if not chat_history:
            return QueryIntent.NEW_TOPIC
        
        # Check for follow-up indicators
        follow_up_patterns = [
            "what about", "how about", "and the", "also", 
            "additionally", "furthermore", "moreover",
            "in addition", "another", "other"
        ]
        
        # Check for clarification indicators
        clarification_patterns = [
            "what do you mean", "can you explain", "clarify",
            "i don't understand", "confused about", "elaborate",
            "more details", "specifically", "exactly"
        ]
        
        # Check for pronouns referring to previous context
        context_pronouns = ["it", "this", "that", "these", "those", "they"]
        
        # Pattern matching
        for pattern in follow_up_patterns:
            if pattern in query_lower:
                return QueryIntent.FOLLOW_UP
        
        for pattern in clarification_patterns:
            if pattern in query_lower:
                return QueryIntent.CLARIFICATION
        
        # Check if query starts with context pronouns
        first_word = query_lower.split()[0] if query_lower.split() else ""
        if first_word in context_pronouns:
            return QueryIntent.FOLLOW_UP
        
        # Default to OFF_TOPIC for LLM classification
        return QueryIntent.OFF_TOPIC
    
    async def _llm_classify(
        self, 
        query: str, 
        chat_history: List[Tuple[str, str]]
    ) -> QueryIntent:
        """LLM-based intent classification"""
        # Format recent history
        history_text = ""
        if chat_history:
            # Use only last 2 exchanges for efficiency
            for user_q, assistant_r in chat_history[-2:]:
                history_text += f"User: {user_q}\nAssistant: {assistant_r[:200]}...\n\n"
        
        prompt = f"""Classify the user's query intent based on the conversation history.

Conversation History:
{history_text if history_text else "No previous conversation"}

Current Query: {query}

Intent Categories:
- NEW_TOPIC: User is asking about something completely new
- FOLLOW_UP: User is asking a follow-up question about the previous topic
- CLARIFICATION: User wants clarification about the previous response
- OFF_TOPIC: Query is unrelated to pharmaceutical/medical topics

Respond with only the intent category name.

Intent:"""

        try:
            response = await self.llm.ainvoke(prompt)
            intent_str = response.content.strip().upper()
            
            # Map to enum
            for intent in QueryIntent:
                if intent.name == intent_str:
                    return intent
            
            # Default to NEW_TOPIC if unclear
            return QueryIntent.NEW_TOPIC
            
        except Exception as e:
            logger.error(f"Error in LLM intent classification: {e}")
            return QueryIntent.NEW_TOPIC