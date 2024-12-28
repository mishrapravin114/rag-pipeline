import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple, Optional, Dict
import tiktoken
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DynamicContextSelector:
    """
    Intelligently selects relevant conversation history within token constraints
    using relevance scoring and recency weighting.
    """
    
    def __init__(
        self, 
        embeddings_model,
        max_tokens: int = 50000,  # Conservative limit for Gemini Flash
        recency_weight: float = 0.3,
        relevance_weight: float = 0.7,
        min_similarity_threshold: float = 0.5
    ):
        self.embeddings_model = embeddings_model
        self.max_tokens = max_tokens
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight
        self.min_similarity_threshold = min_similarity_threshold
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Token overhead for system prompts and response
        self.token_overhead = 2000
        self.effective_max_tokens = max_tokens - self.token_overhead
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback estimation
            return len(text) // 4
    
    async def select_context(
        self, 
        current_query: str,
        all_history: List[Tuple[str, str, float]],  # (user_msg, assistant_msg, timestamp)
        min_conversations: int = 1,
        max_conversations: int = 10,
        always_include_last: bool = True
    ) -> List[Tuple[str, str]]:
        """
        Select most relevant context within token budget.
        
        Args:
            current_query: Current user query
            all_history: All available conversation history with timestamps
            min_conversations: Minimum conversations to include
            max_conversations: Maximum conversations to include
            always_include_last: Always include the most recent conversation
            
        Returns:
            Selected conversation pairs optimized for relevance and token budget
        """
        if not all_history:
            return []
        
        # Count tokens for current query
        query_tokens = self.count_tokens(current_query)
        remaining_budget = self.effective_max_tokens - query_tokens
        
        logger.info(f"Dynamic context selection: Query tokens={query_tokens}, "
                   f"Budget remaining={remaining_budget}")
        
        # Embed current query
        try:
            query_embedding = await self.embeddings_model.aembed_query(current_query)
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            # Fallback to recent conversations
            return self._select_recent_only(all_history, remaining_budget, max_conversations)
        
        # Score all conversations
        scored_conversations = await self._score_conversations(
            query_embedding, 
            all_history,
            current_time=time.time()
        )
        
        # Select optimal subset
        selected = self._select_optimal_subset(
            scored_conversations,
            remaining_budget,
            min_conversations,
            max_conversations,
            always_include_last
        )
        
        return selected
    
    async def _score_conversations(
        self,
        query_embedding: List[float],
        all_history: List[Tuple[str, str, float]],
        current_time: float
    ) -> List[Dict]:
        """Score each conversation based on relevance and recency"""
        scored = []
        
        # Batch embed all user messages for efficiency
        user_messages = [h[0] for h in all_history]
        try:
            user_embeddings = await self.embeddings_model.aembed_documents(user_messages)
        except Exception as e:
            logger.error(f"Error embedding history: {e}")
            user_embeddings = [[0] * len(query_embedding)] * len(user_messages)
        
        for i, (user_msg, assistant_msg, timestamp) in enumerate(all_history):
            # Calculate relevance score
            relevance = cosine_similarity(
                [query_embedding], 
                [user_embeddings[i]]
            )[0][0]
            
            # Calculate recency score (exponential decay)
            hours_ago = (current_time - timestamp) / 3600
            recency = np.exp(-hours_ago / 24)  # 24-hour half-life
            
            # Combined score
            combined_score = (
                self.relevance_weight * relevance + 
                self.recency_weight * recency
            )
            
            # Token count for this conversation
            tokens = self.count_tokens(user_msg + assistant_msg)
            
            scored.append({
                'conversation': (user_msg, assistant_msg),
                'score': combined_score,
                'relevance': relevance,
                'recency': recency,
                'tokens': tokens,
                'position': i,
                'timestamp': timestamp,
                'hours_ago': hours_ago
            })
        
        # Sort by score (highest first)
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        return scored
    
    def _select_optimal_subset(
        self,
        scored_conversations: List[Dict],
        token_budget: int,
        min_conversations: int,
        max_conversations: int,
        always_include_last: bool
    ) -> List[Tuple[str, str]]:
        """Select optimal subset of conversations within constraints"""
        selected = []
        selected_indices = set()
        total_tokens = 0
        
        # Always include the most recent conversation if requested
        if always_include_last and scored_conversations:
            # Find the most recent by position
            most_recent = max(scored_conversations, key=lambda x: x['position'])
            if most_recent['tokens'] <= token_budget:
                selected.append(most_recent)
                selected_indices.add(most_recent['position'])
                total_tokens += most_recent['tokens']
                logger.info(f"Included most recent conversation (tokens={most_recent['tokens']})")
        
        # Add conversations by score
        for conv in scored_conversations:
            if conv['position'] in selected_indices:
                continue
                
            # Skip if relevance too low (unless we need minimum conversations)
            if (conv['relevance'] < self.min_similarity_threshold and 
                len(selected) >= min_conversations):
                continue
            
            # Check token budget
            if total_tokens + conv['tokens'] <= token_budget:
                selected.append(conv)
                selected_indices.add(conv['position'])
                total_tokens += conv['tokens']
                
                if len(selected) >= max_conversations:
                    break
            elif len(selected) < min_conversations:
                # Include even if over budget to meet minimum
                selected.append(conv)
                selected_indices.add(conv['position'])
                total_tokens += conv['tokens']
                logger.warning(f"Exceeded token budget to meet minimum conversations")
                break
        
        # Sort selected by position to maintain chronological order
        selected.sort(key=lambda x: x['position'])
        
        # Log selection summary
        self._log_selection_summary(selected, total_tokens, token_budget)
        
        return [conv['conversation'] for conv in selected]
    
    def _select_recent_only(
        self,
        all_history: List[Tuple[str, str, float]],
        token_budget: int,
        max_conversations: int
    ) -> List[Tuple[str, str]]:
        """Fallback: Select most recent conversations within budget"""
        selected = []
        total_tokens = 0
        
        # Start from most recent
        for user_msg, assistant_msg, _ in reversed(all_history[-max_conversations:]):
            tokens = self.count_tokens(user_msg + assistant_msg)
            if total_tokens + tokens <= token_budget:
                selected.append((user_msg, assistant_msg))
                total_tokens += tokens
            else:
                break
        
        # Return in chronological order
        return list(reversed(selected))
    
    def _log_selection_summary(
        self, 
        selected: List[Dict], 
        total_tokens: int, 
        token_budget: int
    ):
        """Log detailed selection summary"""
        logger.info(f"Context Selection Summary:")
        logger.info(f"  Selected: {len(selected)} conversations")
        logger.info(f"  Total tokens: {total_tokens} / {token_budget}")
        logger.info(f"  Token utilization: {total_tokens/token_budget*100:.1f}%")
        
        if selected:
            avg_relevance = np.mean([c['relevance'] for c in selected])
            avg_recency = np.mean([c['hours_ago'] for c in selected])
            logger.info(f"  Average relevance: {avg_relevance:.3f}")
            logger.info(f"  Average age: {avg_recency:.1f} hours")
            
            # Log top selections
            for i, conv in enumerate(selected[:3]):
                logger.debug(f"  {i+1}. Score={conv['score']:.3f}, "
                           f"Relevance={conv['relevance']:.3f}, "
                           f"Age={conv['hours_ago']:.1f}h, "
                           f"Tokens={conv['tokens']}")