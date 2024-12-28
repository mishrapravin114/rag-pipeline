from typing import List, Tuple, Dict, Optional, Set, Any
from dataclasses import dataclass
import re
import logging
from langchain_core.documents import Document
from utils.llm_util import get_llm
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """Represents a citation with source information"""
    claim: str
    document_id: int
    snippet: str
    confidence: float
    start_pos: int  # Position in response where citation should be added
    end_pos: int

@dataclass
class EnhancedSourceDocument:
    """Enhanced source document with citation details"""
    id: str
    filename: str
    snippet: str
    citation_number: int
    relevance_score: float
    page_number: Optional[int] = None
    drug_name: Optional[str] = None
    used_in_response: bool = True  # Track if actually used in response
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata including file_url

class EnhancedFactChecker:
    """Enhanced fact checker that ensures source documents match response content"""
    
    def __init__(self):
        self.llm = get_llm()
        self.claim_pattern = re.compile(
            r'([^.!?]+(?:[.!?](?![0-9])|$))'  # Split by sentences
        )
    
    async def verify_and_cite_with_tracking(
        self,
        response: str,
        query: str,
        documents: List[Document],
        generation_prompt: Optional[str] = None
    ) -> Tuple[str, List[EnhancedSourceDocument], List[int]]:
        """
        Enhanced verify and cite that tracks which documents were actually used
        
        Args:
            response: Generated response text
            query: User's query
            documents: Source documents used
            generation_prompt: Original prompt used to generate response (for tracking)
            
        Returns:
            Tuple of (cited_response, enhanced_source_documents, used_document_indices)
        """
        # Check if response indicates no information found
        no_info_indicators = [
            "No relevant information found",
            "couldn't find any relevant information",
            "no relevant documents found",
            "I cannot find this information",
            "cannot find this information",
            "no information available",
            "unable to find information"
        ]
        
        response_lower = response.lower()
        is_no_info_response = any(indicator.lower() in response_lower for indicator in no_info_indicators)
        
        if is_no_info_response:
            logger.info("Response indicates no information found - skipping citations")
            return response, [], []
        
        # Step 1: Identify which documents were actually used in the response
        used_doc_indices = await self._identify_used_documents(response, documents)
        logger.info(f"Documents actually used in response: {used_doc_indices}")
        
        # Step 2: Extract factual claims from response
        claims = self._extract_claims(response)
        
        # Step 3: Find supporting evidence for each claim (only from used documents)
        used_documents = [documents[i] for i in used_doc_indices]
        citations = await self._find_evidence_for_claims(claims, used_documents, used_doc_indices)
        
        # Step 4: Add inline citations to response
        cited_response = self._add_inline_citations(response, citations)
        
        # Step 5: Create enhanced source documents (include all used documents)
        enhanced_sources = self._create_enhanced_sources_v2(
            citations, documents, used_doc_indices
        )
        
        return cited_response, enhanced_sources, used_doc_indices
    
    async def _identify_used_documents(
        self, 
        response: str, 
        documents: List[Document]
    ) -> List[int]:
        """Identify which documents were actually used to generate the response"""
        
        # Use LLM to analyze which documents contributed to the response
        doc_summaries = []
        for i, doc in enumerate(documents):
            summary = f"[Doc {i+1}]: {doc.metadata.get('drug_name', 'Unknown')} - "
            # Extract key topics from document
            # Use original_content from metadata
            content = doc.metadata.get('original_content')
            content_preview = content[:500]
            doc_summaries.append(summary + self._extract_key_topics(content_preview))
        
        prompt = f"""Analyze this response and identify which documents were used to generate it.

RESPONSE:
{response}

AVAILABLE DOCUMENTS:
{chr(10).join(doc_summaries)}

TASK: List the document numbers that contain information present in the response.
Only include documents whose content is actually reflected in the response.

Format your answer as a comma-separated list of document numbers (e.g., "1,3,5").
If no documents were clearly used, respond with "NONE".

Document numbers used:"""

        try:
            result = await self.llm.ainvoke(prompt)
            doc_list = result.content.strip()
            
            if "NONE" in doc_list:
                # If no specific documents identified, use similarity matching
                return await self._fallback_document_matching(response, documents)
            
            # Parse document numbers
            used_indices = []
            for num in doc_list.split(','):
                try:
                    idx = int(num.strip()) - 1  # Convert to 0-based index
                    if 0 <= idx < len(documents):
                        used_indices.append(idx)
                except ValueError:
                    continue
            
            # If no valid indices, use fallback
            if not used_indices:
                return await self._fallback_document_matching(response, documents)
            
            return sorted(used_indices)
            
        except Exception as e:
            logger.error(f"Error identifying used documents: {e}")
            # Fallback to including top documents
            return list(range(min(5, len(documents))))
    
    def _extract_key_topics(self, content: str) -> str:
        """Extract key topics from document content"""
        # Look for key pharmaceutical terms
        topics = []
        
        # Check for efficacy data
        if any(term in content.lower() for term in ['orr', 'response rate', 'efficacy', 'survival']):
            topics.append("efficacy data")
        
        # Check for safety data
        if any(term in content.lower() for term in ['adverse', 'side effect', 'safety', 'toxicity']):
            topics.append("safety/adverse events")
        
        # Check for dosing
        if any(term in content.lower() for term in ['dose', 'dosage', 'mg', 'administration']):
            topics.append("dosing information")
        
        # Check for mechanism
        if any(term in content.lower() for term in ['mechanism', 'pathway', 'target', 'inhibitor']):
            topics.append("mechanism of action")
        
        return ", ".join(topics) if topics else "general information"
    
    async def _fallback_document_matching(
        self, 
        response: str, 
        documents: List[Document]
    ) -> List[int]:
        """Fallback method using content similarity"""
        # Extract key terms from response
        response_lower = response.lower()
        
        doc_scores = []
        for i, doc in enumerate(documents):
            score = 0
            # Use original_content from metadata
            content = doc.metadata.get('original_content')
            doc_content_lower = content.lower()
            
            # Check for specific data mentions
            if "orr" in response_lower and "orr" in doc_content_lower:
                score += 10
            if "response rate" in response_lower and "response rate" in doc_content_lower:
                score += 10
            if "adverse" in response_lower and "adverse" in doc_content_lower:
                score += 8
            if any(f"{pct}%" in response_lower for pct in range(0, 101)):
                # Check if document has similar percentages
                for pct in range(0, 101):
                    if f"{pct}%" in response_lower and f"{pct}%" in doc_content_lower:
                        score += 5
            
            doc_scores.append((i, score))
        
        # Sort by score and return indices of documents with score > 0
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        used_indices = [idx for idx, score in doc_scores if score > 0]
        
        # Always include at least top 3 documents
        if len(used_indices) < 3:
            used_indices = [idx for idx, _ in doc_scores[:3]]
        
        return used_indices
    
    def _extract_claims(self, response: str) -> List[Dict[str, any]]:
        """Extract factual claims that need citation"""
        claims = []
        
        # Split into sentences
        sentences = self.claim_pattern.findall(response)
        
        current_pos = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains factual information
            if self._is_factual_claim(sentence):
                start_pos = response.find(sentence, current_pos)
                end_pos = start_pos + len(sentence)
                
                claims.append({
                    'text': sentence,
                    'start_pos': start_pos,
                    'end_pos': end_pos
                })
                
                current_pos = end_pos
        
        return claims
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """Determine if a sentence contains a factual claim needing citation"""
        # Patterns indicating factual claims
        factual_indicators = [
            r'\d+%',  # Percentages
            r'\d+\s*mg',  # Dosages
            r'study|trial|research',  # Research references
            r'approved|indication',  # Regulatory info
            r'efficacy|safety',  # Clinical outcomes
            r'adverse|side effect',  # Safety data
            r'patient|subject',  # Clinical data
            r'significant|statistical',  # Statistical claims
            r'dose|dosage|administration',  # Dosing info
            r'contraindication|warning',  # Safety warnings
            r'orr|response rate',  # Efficacy metrics
            r'median|mean|average',  # Statistical measures
        ]
        
        sentence_lower = sentence.lower()
        
        # Check for factual indicators
        for pattern in factual_indicators:
            if re.search(pattern, sentence_lower):
                return True
        
        # Skip general statements
        general_patterns = [
            r'^i cannot find',
            r'^i don\'t have',
            r'^the documents do not',
            r'^this information is not',
            r'^based on the conversation',
        ]
        
        for pattern in general_patterns:
            if re.match(pattern, sentence_lower):
                return False
        
        return False
    
    async def _find_evidence_for_claims(
        self, 
        claims: List[Dict], 
        documents: List[Document],
        original_indices: List[int]
    ) -> List[Citation]:
        """Find supporting evidence in documents for each claim"""
        citations = []
        
        for claim in claims:
            best_match = await self._find_best_document_match_v2(
                claim['text'], 
                documents,
                original_indices
            )
            
            if best_match:
                citations.append(Citation(
                    claim=claim['text'],
                    document_id=best_match['doc_id'],
                    snippet=best_match['snippet'],
                    confidence=best_match['confidence'],
                    start_pos=claim['start_pos'],
                    end_pos=claim['end_pos']
                ))
        
        return citations
    
    async def _find_best_document_match_v2(
        self, 
        claim: str, 
        documents: List[Document],
        original_indices: List[int]
    ) -> Optional[Dict]:
        """Enhanced document matching that preserves original document numbering"""
        # Use LLM to find supporting evidence
        doc_contents = []
        for i, (doc, orig_idx) in enumerate(zip(documents, original_indices)):
            # Use original document number for display
            # Use original_content from metadata
            content = doc.metadata.get('original_content')
            if not content:
                logger.warning(f"Document {orig_idx + 1} missing original_content, using page_content")
                content = doc.page_content
            doc_contents.append(f"[Doc {orig_idx + 1}]: {content[:1000]}")
        
        prompt = f"""Find the document that best supports this claim:

Claim: {claim}

Documents:
{chr(10).join(doc_contents)}

If a document supports the claim, respond with:
DOC_ID: [original document number as shown above]
SNIPPET: [exact text from document that supports the claim]
CONFIDENCE: [HIGH/MEDIUM/LOW]

If no document supports the claim, respond with:
NO_SUPPORT

Response:"""

        try:
            response = await self.llm.ainvoke(prompt)
            result = response.content.strip()
            
            if "NO_SUPPORT" in result:
                return None
            
            # Parse response
            doc_id_match = re.search(r'DOC_ID:\s*(\d+)', result)
            snippet_match = re.search(r'SNIPPET:\s*(.+?)(?=CONFIDENCE:|$)', result, re.DOTALL)
            confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', result)
            
            if doc_id_match and snippet_match:
                confidence_value = confidence_match.group(1) if confidence_match else 'MEDIUM'
                confidence_scores = {'HIGH': 0.9, 'MEDIUM': 0.7, 'LOW': 0.5}
                
                return {
                    'doc_id': int(doc_id_match.group(1)),
                    'snippet': snippet_match.group(1).strip(),
                    'confidence': confidence_scores.get(confidence_value, 0.7)
                }
            
        except Exception as e:
            logger.error(f"Error finding document match: {e}")
        
        return None
    
    def _add_inline_citations(
        self, 
        response: str, 
        citations: List[Citation]
    ) -> str:
        """Add inline citations to response text"""
        # Sort citations by position (reverse order to maintain positions)
        citations.sort(key=lambda x: x.start_pos, reverse=True)
        
        cited_response = response
        used_docs = set()
        
        for citation in citations:
            # Only add citation for high confidence matches
            if citation.confidence >= 0.7:
                # Insert citation at end of claim
                citation_text = f" [{citation.document_id}]"
                insert_pos = citation.end_pos
                
                # Check if there's already a citation here
                if insert_pos < len(cited_response) and \
                   cited_response[insert_pos:insert_pos+1] != '[':
                    cited_response = (
                        cited_response[:insert_pos] + 
                        citation_text + 
                        cited_response[insert_pos:]
                    )
                    used_docs.add(citation.document_id)
        
        return cited_response
    
    def _create_enhanced_sources_v2(
        self, 
        citations: List[Citation], 
        documents: List[Document],
        used_doc_indices: List[int]
    ) -> List[EnhancedSourceDocument]:
        """Create enhanced source documents ensuring all used documents are included"""
        enhanced_sources = []
        doc_citation_map = {}
        
        # Group citations by document
        for citation in citations:
            if citation.document_id not in doc_citation_map:
                doc_citation_map[citation.document_id] = []
            doc_citation_map[citation.document_id].append(citation)
        
        # Create a set of all documents that should be included
        docs_to_include = set()
        
        # Add all cited documents
        docs_to_include.update(doc_citation_map.keys())
        
        # Add all used documents (convert indices to 1-based doc IDs)
        for idx in used_doc_indices:
            docs_to_include.add(idx + 1)
        
        # Create enhanced source for each document to include
        for doc_id in sorted(docs_to_include):
            if doc_id <= len(documents):
                doc = documents[doc_id - 1]
                
                # Get citations for this document if any
                doc_citations = doc_citation_map.get(doc_id, [])
                
                if doc_citations:
                    # Document has citations - combine snippets
                    snippets = [c.snippet for c in doc_citations]
                    combined_snippet = " [...] ".join(snippets[:3])
                    used_in_response = True
                else:
                    # Document was used but no specific citations - include summary
                    # Use original_content from metadata
                    original_text = doc.metadata.get('original_content')
                    combined_snippet = original_text[:300] + "..."
                    used_in_response = doc_id - 1 in used_doc_indices
                
                # Create metadata with original content and file URL
                metadata = {
                    'original_content': doc.metadata.get('original_content'),
                    'file_url': doc.metadata.get('file_url', '')
                }
                
                enhanced_sources.append(EnhancedSourceDocument(
                    id=doc.metadata.get('id', f'doc_{doc_id}'),
                    filename=doc.metadata.get('source_file_name', doc.metadata.get('source', doc.metadata.get('file_name', 'Unknown'))),
                    snippet=combined_snippet,
                    citation_number=doc_id,
                    relevance_score=doc.metadata.get('relevance_score', 0.0),
                    page_number=doc.metadata.get('page_number'),
                    drug_name=doc.metadata.get('drug_name'),
                    used_in_response=used_in_response,
                    metadata=metadata
                ))
        
        # Sort by citation number
        enhanced_sources.sort(key=lambda x: x.citation_number)
        
        return enhanced_sources