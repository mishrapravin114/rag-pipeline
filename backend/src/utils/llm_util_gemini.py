import logging
import os
import sys
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
            convert_system_message_to_human=True
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
            convert_system_message_to_human=True
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
            convert_system_message_to_human=True
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
            convert_system_message_to_human=True
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
        """Embed documents with 768 dimensions"""
        embeddings = []
        for text in texts:
            try:
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                embeddings.append(result['embedding'])
            except Exception as e:
                logger.error(f"Error embedding document: {str(e)}")
                # Use base embeddings as fallback
                base_result = self.base_embeddings.embed_documents([text])
                if base_result and len(base_result[0]) > 768:
                    # Truncate to 768 dimensions if needed
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
        logger.info(f"Embeddings: Google Gemini - {settings.LLM_GEMINI_EMBEDDING} (forced to 768 dimensions)")
        base_embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.LLM_GEMINI_EMBEDDING,
            google_api_key=settings.GOOGLE_API_KEY
        )
        return Fixed768DimensionEmbeddings(base_embeddings)
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


class GeminiEmbeddingFunction:
    """Custom embedding function for ChromaDB using Google's gemini-embedding-001"""
    
    def __init__(self, api_key: str, model_name: str = "models/gemini-embedding-001"):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        embeddings = []
        for text in input:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=768  # Force 768 dimensions to match existing collection
            )
            embeddings.append(result['embedding'])
        return embeddings


def get_embeddings_function():
    """
    Returns a Google Gemini embeddings function for ChromaDB.
    """
    if settings.LLM_TYPE == 'gemini':
        logger.info(f"ChromaDB Embeddings: Google Gemini - {settings.LLM_GEMINI_EMBEDDING}")
        return GeminiEmbeddingFunction(
            api_key=settings.GOOGLE_API_KEY,
            model_name=settings.LLM_GEMINI_EMBEDDING
        )
    else:
        logger.error(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")
        raise ValueError(f"Unsupported LLM type: {settings.LLM_TYPE}. Only 'gemini' is supported.")


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