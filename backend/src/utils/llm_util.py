import logging
import os
import sys
import time
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# ChromaDB embedding functions removed - using direct Gemini embeddings
from typing import List, Dict, Any

from config.settings import settings

logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=settings.GOOGLE_API_KEY)


def get_llm():
    """
    Returns a Google Gemini LLM instance.
    """
    if settings.LLM_TYPE == 'gemini':
        logger.info(f"LLM: Google Gemini - {settings.LLM_GEMINI_MODEL}")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=settings.LLM_GEMINI_TEMPERATURE,
            # convert_system_message_to_human=True  # Deprecated, removed
        )
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


def get_llm_text_table_summary():
    """
    Returns a Google Gemini LLM instance for text and table summarization.
    """
    if settings.LLM_TYPE == 'gemini':
        logger.info(f"LLM: Google Gemini text/table summary - {settings.LLM_GEMINI_MODEL}")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.3,
            # convert_system_message_to_human=True  # Deprecated, removed
        )
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


def get_llm_grading():
    """
    Returns a Google Gemini LLM instance for grading with zero temperature.
    """
    if settings.LLM_TYPE == 'gemini':
        logger.info(f"LLM: Google Gemini grading - {settings.LLM_GEMINI_MODEL}")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.0,
            # convert_system_message_to_human=True  # Deprecated, removed
        )
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


def get_llm_image_summary():
    """
    Returns a Google Gemini LLM instance for image analysis (vision model).
    """
    if settings.LLM_TYPE == 'gemini':
        logger.info(f"LLM: Google Gemini vision - {settings.LLM_GEMINI_MODEL}")
        return ChatGoogleGenerativeAI(
            model=settings.LLM_GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=settings.LLM_GEMINI_TEMPERATURE,
            # convert_system_message_to_human=True  # Deprecated, removed
        )
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


class Fixed768DimensionEmbeddings:
    """Wrapper for GoogleGenerativeAIEmbeddings that forces 768-dimensional output"""
    
    def __init__(self, base_embeddings):
        self.base_embeddings = base_embeddings
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model_name = base_embeddings.model
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed documents with 768 dimensions using batch processing"""
        if not texts:
            return []
        
        embeddings = []
        batch_size = 100  # Process 100 texts at a time
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                # Gemini API supports batch embedding
                results = genai.embed_content(
                    model=self.model_name,
                    content=batch,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                # Handle both single and batch responses
                if isinstance(results, dict) and 'embedding' in results:
                    # Single embedding response
                    embeddings.append(results['embedding'])
                elif isinstance(results, dict) and 'embeddings' in results:
                    # Batch embedding response
                    embeddings.extend(results['embeddings'])
                else:
                    # Fallback to individual processing
                    logger.warning(f"Unexpected batch response format, falling back to individual processing")
                    for text in batch:
                        try:
                            result = genai.embed_content(
                                model=self.model_name,
                                content=text,
                                task_type="retrieval_document",
                                output_dimensionality=768
                            )
                            embeddings.append(result['embedding'])
                        except Exception as e:
                            logger.error(f"Error embedding individual document: {str(e)}")
                            # Use base embeddings as fallback
                            base_result = self.base_embeddings.embed_documents([text])
                            if base_result and len(base_result[0]) > 768:
                                embeddings.append(base_result[0][:768])
                            else:
                                embeddings.append(base_result[0] if base_result else [0.0] * 768)
            except Exception as e:
                logger.error(f"Error in batch embedding: {str(e)}")
                # Fallback to individual processing for this batch
                for text in batch:
                    try:
                        result = genai.embed_content(
                            model=self.model_name,
                            content=text,
                            task_type="retrieval_document",
                            output_dimensionality=768
                        )
                        embeddings.append(result['embedding'])
                    except Exception as e2:
                        logger.error(f"Error embedding document in fallback: {str(e2)}")
                        # Use base embeddings as fallback
                        base_result = self.base_embeddings.embed_documents([text])
                        if base_result and len(base_result[0]) > 768:
                            embeddings.append(base_result[0][:768])
                        else:
                            embeddings.append(base_result[0] if base_result else [0.0] * 768)
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed query with 768 dimensions"""
        try:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_query",
                output_dimensionality=768
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error embedding query: {str(e)}")
            # Use base embeddings as fallback
            base_result = self.base_embeddings.embed_query(text)
            if len(base_result) > 768:
                return base_result[:768]
            return base_result
    
    def __getattr__(self, name):
        """Delegate other attributes to base embeddings"""
        return getattr(self.base_embeddings, name)


def get_embeddings_model():
    """
    Returns a Google Gemini embeddings model with 768-dimensional output.
    """
    if settings.LLM_TYPE == 'gemini':
        try:
            logger.info(f"Embeddings: Google Gemini - {settings.LLM_GEMINI_EMBEDDING} (forced to 768 dimensions)")
            base_embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.LLM_GEMINI_EMBEDDING,
                google_api_key=settings.GOOGLE_API_KEY
            )
            return Fixed768DimensionEmbeddings(base_embeddings)
        except Exception as e:
            logger.error(f"Failed to initialize Google Gemini embeddings: {str(e)}")
            # Try fallback embedding model
            try:
                logger.warning("Attempting fallback embedding model: models/embedding-001 (forced to 768 dimensions)")
                base_embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001",
                    google_api_key=settings.GOOGLE_API_KEY
                )
                return Fixed768DimensionEmbeddings(base_embeddings)
            except Exception as fallback_error:
                logger.error(f"Fallback embedding model also failed: {str(fallback_error)}")
                raise RuntimeError(f"Unable to initialize embedding model. Please check your Google API key and model availability.")
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


class GeminiEmbeddingFunction:
    """Custom embedding function for ChromaDB using Google's gemini-embedding-001 model"""
    
    def __init__(self, api_key: str, model_name: str = "models/gemini-embedding-001"):
        from config.settings import settings
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        self.retry_delay = 2.0  # Initial retry delay in seconds (increased)
        self.max_retries = 5
        self.rate_limit_delay = settings.EMBEDDING_RATE_LIMIT_DELAY  # Configurable delay between embeddings
        self.sequential_mode = True  # Force sequential processing to avoid quota issues
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts with sequential processing to avoid quota issues"""
        if not input:
            return []
            
        embeddings = []
        
        # Force sequential mode due to aggressive quota limits
        if self.sequential_mode:
            logger.info(f"Processing {len(input)} texts sequentially to avoid quota limits")
            for idx, text in enumerate(input):
                # Add delay between each embedding request
                if idx > 0:
                    time.sleep(self.rate_limit_delay)
                
                # Process single text with retry
                embedding_result = self._embed_single_with_retry(text)
                if embedding_result and len(embedding_result) > 0:
                    embeddings.append(embedding_result[0])  # _embed_single_with_retry returns a list with one embedding
                
                # Log progress every 10 items
                if (idx + 1) % 10 == 0:
                    logger.info(f"Processed {idx + 1}/{len(input)} embeddings")
        else:
            # Original batch processing logic (kept for future use when quotas are increased)
            batch_size =  5 # Reduced batch size to avoid rate limits
            
            for i in range(0, len(input), batch_size):
                batch = input[i:i + batch_size]
                
                # Add delay between batches to avoid rate limiting
                if i > 0:
                    time.sleep(self.rate_limit_delay)
                
                retry_count = 0
                batch_processed = False
                
                while retry_count < self.max_retries and not batch_processed:
                    try:
                        # Try batch embedding
                        results = genai.embed_content(
                            model=self.model_name,
                            content=batch,
                            task_type="retrieval_document",
                            output_dimensionality=768  # Force 768 dimensions to match existing collection
                        )
                        # Handle both single and batch responses
                        if isinstance(results, dict) and 'embedding' in results:
                            # Single embedding response
                            embeddings.append(results['embedding'])
                        elif isinstance(results, dict) and 'embeddings' in results:
                            # Batch embedding response
                            embeddings.extend(results['embeddings'])
                        else:
                            # Fallback to individual processing
                            logger.warning(f"Unexpected batch response format, falling back to individual processing")
                            for text in batch:
                                result = self._embed_single_with_retry(text)
                                if result and len(result) > 0:
                                    embeddings.append(result[0])
                        
                        batch_processed = True
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "429" in error_msg or "quota" in error_msg.lower():
                            retry_count += 1
                            if retry_count < self.max_retries:
                                delay = self.retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                                logger.warning(f"Rate limit hit, retrying in {delay} seconds... (attempt {retry_count}/{self.max_retries})")
                                time.sleep(delay)
                            else:
                                logger.error(f"Max retries exceeded for batch. Processing individually with delays.")
                                # Process individually with delays
                                for text in batch:
                                    time.sleep(1.0)  # Longer delay between individual requests
                                    result = self._embed_single_with_retry(text)
                                    if result and len(result) > 0:
                                        embeddings.append(result[0])
                                batch_processed = True
                        else:
                            logger.error(f"Error in batch embedding: {error_msg}")
                            # Fallback to individual processing for this batch
                            for text in batch:
                                result = self._embed_single_with_retry(text)
                                if result and len(result) > 0:
                                    embeddings.append(result[0])
                            batch_processed = True
        
        if len(embeddings) != len(input):
            logger.warning(f"Embedding count mismatch: expected {len(input)}, got {len(embeddings)}")
            # Don't pad - let the caller handle missing embeddings
            # Padding with zero vectors can cause dimension issues
        
        return embeddings
    
    def _embed_single_with_retry(self, text: str) -> List[List[float]]:
        """Embed a single text with retry logic and fallback"""
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                return [result['embedding']]
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    retry_count += 1
                    if retry_count < self.max_retries:
                        # Exponential backoff with jitter
                        base_delay = self.retry_delay * (2 ** (retry_count - 1))
                        jitter = base_delay * 0.1 * (2 * (retry_count % 2) - 1)  # ±10% jitter
                        delay = base_delay + jitter
                        logger.warning(f"Rate limit hit for single text, retrying in {delay:.1f} seconds... (attempt {retry_count}/{self.max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries exceeded for gemini-embedding-001 model")
                        break
                else:
                    logger.error(f"Non-quota error embedding single text: {error_msg}")
                    break
        
        # Try fallback models in order
        fallback_models = [
            ("models/embedding-001", 768),
            ("models/gemini-embedding-001", 256),  # Try lower dimensions
        ]
        
        for fallback_model, dimensions in fallback_models:
            try:
                logger.warning(f"Attempting fallback with {fallback_model} (dim={dimensions}) for text: {text[:50]}...")
                time.sleep(1.0)  # Small delay before fallback
                
                result = genai.embed_content(
                    model=fallback_model,
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=dimensions
                )
                
                embedding = result['embedding']
                # Pad or truncate to 768 dimensions
                if len(embedding) < 768:
                    embedding.extend([0.0] * (768 - len(embedding)))
                elif len(embedding) > 768:
                    embedding = embedding[:768]
                    
                return [embedding]
                
            except Exception as fallback_error:
                logger.error(f"Fallback {fallback_model} also failed: {str(fallback_error)}")
                continue
        
        # All attempts failed, return zero vector
        logger.error(f"All embedding attempts failed for text. Returning zero vector.")
        return [[0.0] * 768]


def get_embeddings_function():
    """
    Returns a Google Gemini embeddings function for ChromaDB with error handling.
    """
    logger.info(f"Embeddings: Google Gemini - {settings.LLM_GEMINI_EMBEDDING} for ChromaDB")
    return GeminiEmbeddingFunction(
        api_key=settings.GOOGLE_API_KEY,
        model_name=settings.LLM_GEMINI_EMBEDDING
    )


# Legacy functions for backward compatibility
def get_azure_openai_embeddings(texts):
    """Google Gemini embeddings function (replaces Azure)."""
    if settings.LLM_TYPE == 'gemini':
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model=settings.LLM_GEMINI_EMBEDDING,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768  # Force 768 dimensions to match existing collection
            )
            embeddings.append(result['embedding'])
        return embeddings
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


def get_azure_openai_embeddings_function():
    """Legacy function name - returns Google Gemini embeddings function."""
    return get_embeddings_function()


def get_azure_embeddings_function():
    """Legacy function name - returns Google Gemini embeddings model."""
    return get_embeddings_model()