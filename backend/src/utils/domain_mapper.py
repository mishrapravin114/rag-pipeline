"""
Domain mapping layer for backward compatibility and domain-specific terminology
Maps domain-specific terms to generic terms and vice versa
"""
from typing import Dict, Any, Optional

class DomainMapper:
    """Maps domain-specific terms to generic terms"""
    
    DOMAIN_MAPPINGS = {
        "pharmaceutical": {
            "entity": "entity",
            "entity_name": "entity_name",
            "entity_plural": "entities",
            "category": "therapeutic_area",
            "source": "manufacturer",
            "properties": "dosage_form",
            "features": "side_effects",
            "use_cases": "indications",
            "attributes": "active_ingredient"
        },
        "legal": {
            "entity": "case",
            "entity_name": "case_name",
            "entity_plural": "cases",
            "category": "jurisdiction",
            "source": "court",
            "properties": "case_type",
            "features": "key_points",
            "use_cases": "precedents",
            "attributes": "parties"
        },
        "corporate": {
            "entity": "document",
            "entity_name": "document_title",
            "entity_plural": "documents",
            "category": "department",
            "source": "author",
            "properties": "document_type",
            "features": "tags",
            "use_cases": "applications",
            "attributes": "metadata"
        },
        "research": {
            "entity": "paper",
            "entity_name": "paper_title",
            "entity_plural": "papers",
            "category": "research_area",
            "source": "journal",
            "properties": "publication_type",
            "features": "keywords",
            "use_cases": "citations",
            "attributes": "authors"
        }
    }
    
    @classmethod
    def get_domain_mapping(cls, domain: str = "pharmaceutical") -> Dict[str, str]:
        """Get mapping for a specific domain"""
        return cls.DOMAIN_MAPPINGS.get(domain.lower(), cls.DOMAIN_MAPPINGS["pharmaceutical"])
    
    @classmethod
    def to_generic(cls, domain: str, domain_term: str) -> str:
        """Convert domain-specific term to generic"""
        mapping = cls.get_domain_mapping(domain)
        reverse_mapping = {v: k for k, v in mapping.items()}
        return reverse_mapping.get(domain_term, domain_term)
    
    @classmethod
    def to_domain(cls, domain: str, generic_term: str) -> str:
        """Convert generic term to domain-specific"""
        mapping = cls.get_domain_mapping(domain)
        return mapping.get(generic_term, generic_term)
    
    @classmethod
    def get_entity_label(cls, domain: str = "pharmaceutical", plural: bool = False) -> str:
        """Get entity label for a domain"""
        mapping = cls.get_domain_mapping(domain)
        key = "entity_plural" if plural else "entity"
        return mapping.get(key, "entity")
    
    @classmethod
    def get_category_label(cls, domain: str = "pharmaceutical") -> str:
        """Get category label for a domain"""
        mapping = cls.get_domain_mapping(domain)
        return mapping.get("category", "category")
    
    @classmethod
    def get_source_label(cls, domain: str = "pharmaceutical") -> str:
        """Get source label for a domain"""
        mapping = cls.get_domain_mapping(domain)
        return mapping.get("source", "source")

