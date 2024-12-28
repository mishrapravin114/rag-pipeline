import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from random import uniform
import pymupdf4llm
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from google.api_core.exceptions import ResourceExhausted
from config.settings import settings
from .llm_util import get_embeddings_model

logger = logging.getLogger(__name__)

class PyMuPDFProcessor:
    """PDF processor using pymupdf4llm for better structure preservation"""
    
    def __init__(self, chunk_size: int = 3000, chunk_overlap: int = 400, api_key: str = None):
        """
        Initialize the PyMuPDF processor
        
        Args:
            chunk_size: Maximum size of each chunk
            chunk_overlap: Overlap between chunks
            api_key: Google API key for Gemini
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Get API key
        actual_api_key = api_key or settings.GOOGLE_API_KEY
        if not actual_api_key:
            logger.error("No Google API key found! Check GOOGLE_API_KEY environment variable")
            raise ValueError("Google API key is required")
        
        logger.info(f"Initializing with API key: {'*' * 10}{actual_api_key[-4:]}")
        
        # Initialize Gemini model
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", 
            google_api_key=actual_api_key,
            temperature=0.3
        )
        
        # Initialize embeddings model
        self.embeddings_model = get_embeddings_model()
        
        # Define prompts
        self.summarization_prompt = PromptTemplate(
            template="""Summarize the following Markdown chunk in 200 words or less. 
        Preserve key points, especially from tables, lists, or headings.
        {table_instruction}

        **Content**:
        ```markdown
        {content}
        ```

        **Summary**:
""",
            input_variables=["content", "table_instruction"]
        )
        
        self.title_prompt = PromptTemplate(
            template="""Generate a concise, descriptive title (3-7 words) for the following content chunk. 
        The title should capture the main topic or key information in the chunk.
        
        **Content**:
        ```markdown
        {content}
        ```
        
        **Title**:
""",
            input_variables=["content"]
        )
        
        # Initialize text splitter once
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            keep_separator=True
        )
        
        logger.info(f"PyMuPDFProcessor initialized with chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def extract_pdf_to_markdown(self, pdf_path: str) -> str:
        """
        Extract structured Markdown from PDF using pymupdf4llm
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Markdown content as string
        """
        try:
            logger.info(f"Extracting PDF to Markdown: {pdf_path}")
            md_text = pymupdf4llm.to_markdown(pdf_path)
            logger.info(f"Successfully extracted {len(md_text)} characters of Markdown")
            return md_text
        except Exception as e:
            logger.error(f"Error extracting PDF to Markdown: {str(e)}")
            raise RuntimeError(f"Error extracting PDF: {str(e)}")
    
    def split_markdown_preserving_tables(self, markdown_content: str) -> List[Dict[str, Any]]:
        """
        Split Markdown content into chunks while preserving tables intact
        
        Args:
            markdown_content: Markdown text to split
            
        Returns:
            List of chunk dictionaries with metadata
        """
        try:
            segments = []
            lines = markdown_content.split('\n')
            i = 0
            current_segment = StringIO()
            in_table = False
            segment_type = 'text'

            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('|') and '|' in line[1:]:
                    if not in_table:
                        if current_segment.getvalue():
                            segments.append({
                                'type': segment_type,
                                'content': current_segment.getvalue().strip()
                            })
                            current_segment = StringIO()
                        in_table = True
                        segment_type = 'table'
                    current_segment.write(line + '\n')
                else:
                    if in_table:
                        segments.append({
                            'type': segment_type,
                            'content': current_segment.getvalue().strip()
                        })
                        current_segment = StringIO()
                        in_table = False
                        segment_type = 'text'
                    if line:
                        current_segment.write(line + '\n')
                i += 1

            if current_segment.getvalue():
                segments.append({
                    'type': segment_type,
                    'content': current_segment.getvalue().strip()
                })

            chunks = []
            chunk_number = 1
            current_chunk = StringIO()

            for segment in segments:
                if segment['type'] == 'table':
                    if current_chunk.getvalue():
                        chunks.append({
                            'content': current_chunk.getvalue().strip(),
                            'chunk_number': chunk_number,
                            'has_table': False
                        })
                        chunk_number += 1
                    chunks.append({
                        'content': segment['content'],
                        'chunk_number': chunk_number,
                        'has_table': True
                    })
                    chunk_number += 1
                    current_chunk = StringIO()
                else:
                    text_chunks = self.text_splitter.split_text(segment['content'])
                    for text_chunk in text_chunks:
                        if len(current_chunk.getvalue()) + len(text_chunk) > self.chunk_size:
                            if current_chunk.getvalue():
                                chunks.append({
                                    'content': current_chunk.getvalue().strip(),
                                    'chunk_number': chunk_number,
                                    'has_table': False
                                })
                                chunk_number += 1
                            current_chunk = StringIO()
                            current_chunk.write(text_chunk)
                        else:
                            if current_chunk.getvalue():
                                current_chunk.write('\n\n')
                            current_chunk.write(text_chunk)

            if current_chunk.getvalue():
                chunks.append({
                    'content': current_chunk.getvalue().strip(),
                    'chunk_number': chunk_number,
                    'has_table': False
                })

            logger.info(f"Created {len(chunks)} chunks from Markdown content")
            return chunks
        
        except Exception as e:
            logger.error(f"Error splitting Markdown: {str(e)}")
            raise RuntimeError(f"Error splitting Markdown: {str(e)}")
    
    def summarize_chunk(self, chunk: Dict[str, Any], file_name: str, index: int, total: int, file_url: str = None, max_retries: int = 3) -> Dict[str, Any]:
        """
        Summarize a single chunk using Gemini API and generate embeddings.
        
        Args:
            chunk: Chunk dictionary with content and metadata
            file_name: Source file name for metadata
            index: Chunk index for logging
            total: Total number of chunks for logging
            file_url: URL of the source file for metadata
            max_retries: Maximum retries for API rate limit errors
        
        Returns:
            Document dictionary with summary, embedding, and metadata
        """
        logger.info(f"Processing chunk {index+1}/{total}...")
        
        table_instruction = (
            "This chunk contains a table. Make sure to capture the key data points from the table in your summary."
            if chunk['has_table'] else ""
        )
        
        lines = chunk['content'].split('\n')
        chunk_title = ""
        for line in lines[:5]:
            if line.strip().startswith('#'):
                chunk_title = line.strip().lstrip('#').strip()
                break
        
        if not chunk_title:
            content_for_title = chunk['content'][:1000] if len(chunk['content']) > 1000 else chunk['content']
            for attempt in range(max_retries):
                try:
                    title_response = self.llm.invoke(self.title_prompt.format(content=content_for_title))
                    chunk_title = title_response.content.strip().strip('"\'').strip('.')
                    break
                except ResourceExhausted:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to generate title for chunk {index+1} after {max_retries} retries")
                        chunk_title = "Untitled Chunk"
                    else:
                        logger.warning(f"Rate limit hit for chunk {index+1} title. Retrying after delay...")
                        sleep(2 ** attempt + uniform(0, 1))
        
        # Generate summary
        summary = chunk['content'] # Fallback to original content
        try:
            formatted_prompt = self.summarization_prompt.format(
                content=chunk['content'],
                table_instruction=table_instruction
            )
            for attempt in range(max_retries):
                try:
                    response = self.llm.invoke(formatted_prompt)
                    summary = response.content
                    break
                except ResourceExhausted:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to summarize chunk {index+1} after {max_retries} retries. Using original content.")
                    else:
                        logger.warning(f"Rate limit hit for chunk {index+1} summary. Retrying after delay...")
                        sleep(2 ** attempt + uniform(0, 1))
        except Exception as e:
            logger.error(f"Error during summarization for chunk {index+1}: {e}. Using original content.")

        # Generate embedding for the summary
       # embedding = self.embeddings_model.embed_query(summary)
        
        document = {
            'page_content': summary,
            'metadata': {
                'original_content': chunk['content'],
                'chunk_title': chunk_title,
                'source': file_name,
                'chunk_number': chunk['chunk_number'],
                'has_table': chunk['has_table'],
                'file_url': file_url if file_url else ''
            }
        }
        
        return document
    
    def summarize_chunks_with_gemini(self, chunks: List[Dict[str, Any]], file_name: str, file_url: str = None) -> List[Dict[str, Any]]:
        """
        Summarize each chunk using Gemini 2.0 Flash with multi-threading.
        
        Args:
            chunks: List of chunk dictionaries
            file_name: Name of the source file
            file_url: URL of the source file
        
        Returns:
            List of document dictionaries with summaries
        """
        try:
            documents = []
            
            # Handle empty chunks case
            if not chunks:
                logger.warning(f"No chunks to process for file: {file_name}")
                return documents
            
            max_workers = min(8, len(chunks))  # Limit threads to avoid overwhelming API
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(self.summarize_chunk, chunk, file_name, i, len(chunks), file_url): i
                    for i, chunk in enumerate(chunks)
                }
                
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        document = future.result()
                        documents.append(document)
                    except Exception as e:
                        logger.error(f"Error summarizing chunk {index+1}: {str(e)}")
                        raise
            
            documents.sort(key=lambda x: x['metadata']['chunk_number'])
            
            logger.info(f"Successfully summarized {len(documents)} chunks")
            return documents
        
        except Exception as e:
            logger.error(f"Error summarizing chunks: {str(e)}")
            raise RuntimeError(f"Error summarizing chunks: {str(e)}")
    
    def process_pdf(self, pdf_path: str, file_name: str, file_url: str = None) -> List[Dict[str, Any]]:
        """
        Main entry point - process PDF and return document array
        
        Args:
            pdf_path: Path to the PDF file
            file_name: Name of the file for metadata
            file_url: URL of the source file
            
        Returns:
            List of document dictionaries ready for database storage
        """
        try:
            logger.info(f"Starting PDF processing for: {file_name}")
            
            markdown_content = self.extract_pdf_to_markdown(pdf_path)
            
            # Handle empty PDF content
            if not markdown_content or not markdown_content.strip():
                logger.warning(f"PDF has no extractable content: {file_name}")
                return []
            
            chunks = self.split_markdown_preserving_tables(markdown_content)
            documents = self.summarize_chunks_with_gemini(chunks, file_name, file_url)
            
            logger.info(f"PDF processing complete. Created {len(documents)} documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise
    
    def extract_chunks_only(self, pdf_path: str, file_name: str, file_url: str = None) -> List[Dict[str, Any]]:
        """
        Extract and chunk PDF without summarization - for batch processing.
        Includes chunk size validation and metadata enrichment.
        
        Returns:
            List of chunk dictionaries ready for batch summarization
        """
        try:
            logger.info(f"Extracting chunks only for: {file_name}")
            
            # Extract markdown content
            markdown_content = self.extract_pdf_to_markdown(pdf_path)
            
            if not markdown_content or not markdown_content.strip():
                logger.warning(f"PDF has no extractable content: {file_name}")
                return []
            
            # Split into chunks
            chunks = self.split_markdown_preserving_tables(markdown_content)
            
            validated_chunks = []
            for i, chunk in enumerate(chunks):
                # Validate and potentially split large chunks
                if self._estimate_tokens(chunk['content']) > 800000:
                    # Split large chunk into smaller pieces
                    sub_chunks = self._split_large_chunk(chunk['content'])
                    for j, sub_chunk in enumerate(sub_chunks):
                        validated_chunks.append({
                            'content': sub_chunk,
                            'chunk_id': f"{file_name}_{i+1}_{j+1}",
                            'file_name': file_name,
                            'file_url': file_url or '',
                            'chunk_index': f"{i}.{j}",
                            'has_table': chunk.get('has_table', False),
                            'original_chunk_index': i,
                            'is_sub_chunk': True
                        })
                else:
                    chunk['chunk_id'] = f"{file_name}_{i+1}"
                    chunk['file_name'] = file_name
                    chunk['file_url'] = file_url or ''
                    chunk['chunk_index'] = i
                    chunk['is_sub_chunk'] = False
                    validated_chunks.append(chunk)
            
            logger.info(f"Extracted {len(validated_chunks)} chunks for batch processing")
            return validated_chunks
            
        except Exception as e:
            logger.error(f"Error extracting chunks for {file_name}: {str(e)}")
            raise

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 characters)."""
        return len(text) // 4

    def _split_large_chunk(self, content: str, max_tokens: int = 700000) -> List[str]:
        """Split large chunks into smaller pieces while preserving context."""
        max_chars = max_tokens * 4
        chunks = []
        
        # Try to split at paragraph boundaries
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 < max_chars:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # If still too large, force split
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_chars:
                for i in range(0, len(chunk), max_chars):
                    final_chunks.append(chunk[i:i+max_chars])
            else:
                final_chunks.append(chunk)
        
        return final_chunks