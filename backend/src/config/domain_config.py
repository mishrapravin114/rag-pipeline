"""
Domain configuration for flexible domain support
"""
from typing import Dict, Any, Optional
from enum import Enum

class Domain(Enum):
    PHARMACEUTICAL = "pharmaceutical"
    LEGAL = "legal"
    CORPORATE = "corporate"
    RESEARCH = "research"
    CUSTOM = "custom"

class DomainConfig:
    """Configuration for different domains"""
    
    def __init__(self, domain: Domain = Domain.PHARMACEUTICAL):
        self.domain = domain
        self.config = self._load_config(domain)
    
    def _load_config(self, domain: Domain) -> Dict[str, Any]:
        configs = {
            Domain.PHARMACEUTICAL: {
                "entity_label": "Entity",
                "entity_plural": "Entities",
                "category_label": "Therapeutic Area",
                "source_label": "Manufacturer",
                "search_prompt_template": """You are an expert pharmaceutical regulatory and HTA information specialist.
Your role is to provide accurate, evidence-based information about entities, medications, and pharmaceutical regulations.
Always cite your sources and provide specific details from the documents.""",
                "extraction_prompt_template": "Extract pharmaceutical information including entity name, manufacturer, therapeutic area, dosage forms, side effects, and indications."
            },
            Domain.LEGAL: {
                "entity_label": "Case",
                "entity_plural": "Cases",
                "category_label": "Jurisdiction",
                "source_label": "Court",
                "search_prompt_template": """You are an expert legal research assistant.
Your role is to provide accurate legal information from case law, regulations, and legal documents.
Always cite your sources and provide specific case names, dates, and jurisdictions.""",
                "extraction_prompt_template": "Extract legal information including case name, court, jurisdiction, case type, key points, and precedents."
            },
            Domain.CORPORATE: {
                "entity_label": "Document",
                "entity_plural": "Documents",
                "category_label": "Department",
                "source_label": "Author",
                "search_prompt_template": """You are a corporate knowledge assistant.
Your role is to help users find and understand corporate documents, policies, and procedures.
Always cite your sources and provide specific document references.""",
                "extraction_prompt_template": "Extract corporate document information including title, author, department, document type, tags, and applications."
            },
            Domain.RESEARCH: {
                "entity_label": "Paper",
                "entity_plural": "Papers",
                "category_label": "Research Area",
                "source_label": "Journal",
                "search_prompt_template": """You are a research assistant.
Your role is to help users find and understand research papers and academic publications.
Always cite your sources and provide specific paper titles, authors, and publication details.""",
                "extraction_prompt_template": "Extract research paper information including title, authors, journal, research area, keywords, and citations."
            }
        }
        return configs.get(domain, configs[Domain.PHARMACEUTICAL])
    
    def get_entity_label(self, plural: bool = False) -> str:
        """Get entity label"""
        key = "entity_plural" if plural else "entity_label"
        return self.config.get(key, "Entity")
    
    def get_category_label(self) -> str:
        """Get category label"""
        return self.config.get("category_label", "Category")
    
    def get_source_label(self) -> str:
        """Get source label"""
        return self.config.get("source_label", "Source")
    
    def get_search_prompt(self) -> str:
        """Get search prompt template"""
        return self.config.get("search_prompt_template", "")
    
    def get_extraction_prompt(self) -> str:
        """Get extraction prompt template"""
        return self.config.get("extraction_prompt_template", "")

# Global default domain config
default_domain_config = DomainConfig(Domain.PHARMACEUTICAL)

