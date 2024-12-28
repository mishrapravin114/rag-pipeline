from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import re
import logging
from langchain_core.documents import Document
from utils.llm_util import get_llm

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

class FactChecker:
    """Verifies claims and adds inline citations to responses"""
    
    def __init__(self):
        self.llm = get_llm()
        self.claim_pattern = re.compile(
            r'([^.!?]+(?:[.!?](?![0-9])|$))'  # Split by sentences
        )
    
    async def verify_and_cite(
        self,
        response: str,
        query: str,
        documents: List[Document]
    ) -> Tuple[str, List[EnhancedSourceDocument]]:
        """
        Verify claims in response and add inline citations
        
        Args:
            response: Generated response text
            query: User's query
            documents: Source documents used
            
        Returns:
            Tuple of (cited_response, enhanced_source_documents)
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
            return response, []
        
        # Step 1: Extract factual claims from response
        claims = self._extract_claims(response)
        
        # Step 2: Find supporting evidence for each claim
        citations = await self._find_evidence_for_claims(claims, documents)
        
        # Step 3: Add inline citations to response
        cited_response = self._add_inline_citations(response, citations)
        
        # Step 4: Create enhanced source documents
        enhanced_sources = self._create_enhanced_sources(citations, documents)
        
        return cited_response, enhanced_sources
    
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
        documents: List[Document]
    ) -> List[Citation]:
        """Find supporting evidence in documents for each claim"""
        citations = []
        
        for claim in claims:
            best_match = await self._find_best_document_match(
                claim['text'], 
                documents
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
    
    async def _find_best_document_match(
        self, 
        claim: str, 
        documents: List[Document]
    ) -> Optional[Dict]:
        """Find the best matching document snippet for a claim"""
        # Use LLM to find supporting evidence
        doc_contents = []
        for i, doc in enumerate(documents, 1):
            # Use original_content from metadata if available, otherwise fall back to page_content
            content = doc.metadata.get('original_content', doc.page_content)
            doc_contents.append(f"[Doc {i}]: {content[:1000]}")
        
        prompt = f"""Find the document that best supports this claim:

Claim: {claim}

Documents:
{chr(10).join(doc_contents)}

If a document supports the claim, respond with:
DOC_ID: [number]
SNIPPET: [exact text from document]
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
            if citation.confidence >= 0.7 and citation.document_id not in used_docs:
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
    
    def _create_enhanced_sources(
        self, 
        citations: List[Citation], 
        documents: List[Document]
    ) -> List[EnhancedSourceDocument]:
        """Create enhanced source documents with citation details"""
        enhanced_sources = []
        doc_citation_map = {}
        
        # Group citations by document
        for citation in citations:
            if citation.document_id not in doc_citation_map:
                doc_citation_map[citation.document_id] = []
            doc_citation_map[citation.document_id].append(citation)
        
        # Create enhanced source for each cited document
        for doc_id, doc_citations in doc_citation_map.items():
            if doc_id <= len(documents):
                doc = documents[doc_id - 1]
                
                # Combine all snippets for this document
                snippets = [c.snippet for c in doc_citations]
                combined_snippet = " [...] ".join(snippets[:3])  # Limit to 3 snippets
                
                enhanced_sources.append(EnhancedSourceDocument(
                    id=doc.metadata.get('id', f'doc_{doc_id}'),
                    filename=doc.metadata.get('source_file', 'Unknown'),
                    snippet=combined_snippet,
                    citation_number=doc_id,
                    relevance_score=doc.metadata.get('relevance_score', 0.0),
                    page_number=doc.metadata.get('page_number'),
                    drug_name=doc.metadata.get('drug_name')
                ))
        
        # Sort by citation number
        enhanced_sources.sort(key=lambda x: x.citation_number)
        
        return enhanced_sources