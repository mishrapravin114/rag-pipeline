import asyncio
import json
from typing import List, Set, Tuple, Optional
import logging
from langchain_core.language_models import BaseLLM

logger = logging.getLogger(__name__)

class MultiQueryGenerator:
    """
    Generates multiple query variations to improve retrieval recall
    and handle different interpretations of user intent.
    """
    
    def __init__(self, llm: BaseLLM, max_queries: int = 5):
        self.llm = llm
        self.max_queries = max_queries
    
    async def generate_queries(
        self, 
        original_query: str, 
        chat_history: Optional[List[Tuple[str, str]]] = None,
        domain: str = "pharmaceutical"
    ) -> List[str]:
        """
        Generate multiple query variations for comprehensive retrieval.
        
        Args:
            original_query: The user's original query
            chat_history: Previous conversation for context
            domain: Domain context for query generation
            
        Returns:
            List of query variations including the original
        """
        # Always include original query
        queries = [original_query]
        
        # Build context from chat history
        context = self._build_context(chat_history)
        
        # Generate variations
        try:
            variations = await self._generate_variations(original_query, context, domain)
            queries.extend(variations)
        except Exception as e:
            logger.error(f"Error generating query variations: {e}")
        
        # Generate sub-questions if complex
        try:
            sub_questions = await self._decompose_query(original_query, context)
            queries.extend(sub_questions)
        except Exception as e:
            logger.error(f"Error decomposing query: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q.lower().strip() not in seen:
                seen.add(q.lower().strip())
                unique_queries.append(q)
        
        # Limit to max_queries
        final_queries = unique_queries[:self.max_queries]
        
        logger.info(f"Generated {len(final_queries)} query variations: {final_queries}")
        return final_queries
    
    def _build_context(self, chat_history: Optional[List[Tuple[str, str]]]) -> str:
        """Build context string from chat history"""
        if not chat_history:
            return ""
        
        context = "Recent conversation:\n"
        for user_msg, assistant_msg in chat_history[-3:]:  # Last 3 exchanges
            context += f"User: {user_msg}\n"
            context += f"Assistant: {assistant_msg[:200]}...\n\n"
        
        return context
    
    async def _generate_variations(
        self, 
        query: str, 
        context: str, 
        domain: str
    ) -> List[str]:
        """Generate query variations using LLM"""
        
        prompt = f"""You are an expert at generating search queries for a {domain} knowledge base.
        
Given the original query and conversation context, generate {self.max_queries - 1} different search queries that:
1. Use different medical/pharmaceutical terminology and synonyms
2. Focus on different aspects of the question
3. Range from specific to general
4. Include relevant context from the conversation
5. Cover different interpretations of what the user might want

{context}

ORIGINAL QUERY: {query}

Rules:
- Each query should be different and explore a unique angle
- Use medical synonyms (e.g., "adverse effects" vs "side effects")
- Include brand names and generic names where applicable
- Consider both patient and healthcare provider perspectives
- DO NOT include the original query in your list

Return ONLY a JSON array of query strings, no explanation.

Example output:
["query variation 1", "query variation 2", "query variation 3"]"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                variations = json.loads(json_match.group())
                if isinstance(variations, list):
                    return [str(v) for v in variations if v]
            
            return []
            
        except Exception as e:
            logger.error(f"Error parsing variations: {e}")
            return self._generate_fallback_variations(query)
    
    async def _decompose_query(self, query: str, context: str) -> List[str]:
        """Decompose complex queries into sub-questions"""
        
        # Quick check if query might be complex
        complexity_indicators = ['and', 'or', 'vs', 'versus', 'compare', 'difference between']
        is_complex = any(indicator in query.lower() for indicator in complexity_indicators)
        
        if not is_complex and len(query.split()) < 10:
            return []  # Skip decomposition for simple queries
        
        prompt = f"""Analyze this pharmaceutical query and break it down into simpler sub-questions if needed.

{context}

QUERY: {query}

If the query asks about multiple aspects, comparisons, or complex topics, break it into individual questions.
If it's already simple and focused, return an empty list.

Rules:
- Only decompose if the query is genuinely complex
- Each sub-question should be complete and standalone
- Focus on pharmaceutical/medical aspects
- Maximum 3 sub-questions

Return as JSON array. Return empty array [] if decomposition not needed.

Examples:
- "Compare side effects and efficacy of Drug A vs Drug B" → ["What are the side effects of Drug A?", "What are the side effects of Drug B?", "What is the efficacy of Drug A compared to Drug B?"]
- "What is the dosage of aspirin?" → []"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                sub_questions = json.loads(json_match.group())
                if isinstance(sub_questions, list):
                    return [str(q) for q in sub_questions if q]
            
            return []
            
        except Exception as e:
            logger.error(f"Error decomposing query: {e}")
            return []
    
    def _generate_fallback_variations(self, query: str) -> List[str]:
        """Generate simple variations as fallback"""
        variations = []
        
        # Common pharmaceutical synonyms
        synonyms = {
            'side effects': 'adverse reactions',
            'dosage': 'dose',
            'drug': 'medication',
            'medicine': 'pharmaceutical',
            'interactions': 'drug interactions',
            'contraindications': 'when not to use',
            'mechanism': 'how it works',
            'efficacy': 'effectiveness'
        }
        
        # Generate variations using synonyms
        for original, replacement in synonyms.items():
            if original in query.lower():
                variation = query.lower().replace(original, replacement)
                variations.append(variation)
        
        return variations[:3]  # Limit fallback variations