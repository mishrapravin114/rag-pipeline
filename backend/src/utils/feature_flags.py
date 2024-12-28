"""
Feature flags for gradual rollout of SOTA RAG improvements
"""
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class FeatureFlags:
    """
    Manages feature flags for SOTA RAG components.
    Can be controlled via environment variables or config.
    """
    
    # Default feature flags
    _flags = {
        "ENABLE_HYBRID_SEARCH": True,
        "ENABLE_MULTI_QUERY": True,
        "ENABLE_DYNAMIC_CONTEXT": True,
        "ENABLE_SEMANTIC_CACHE": True,
        "ENABLE_PERFORMANCE_METRICS": True,
        
        # Individual component flags
        "HYBRID_SEARCH_DENSE_WEIGHT": 0.7,
        "HYBRID_SEARCH_SPARSE_WEIGHT": 0.3,
        "MULTI_QUERY_MAX_QUERIES": 5,
        "DYNAMIC_CONTEXT_MAX_CONVERSATIONS": 10,
        "SEMANTIC_CACHE_SIMILARITY_THRESHOLD": 0.95,
        "SEMANTIC_CACHE_TTL_SECONDS": 3600,
        
        # Fallback to legacy implementation
        "FALLBACK_TO_LEGACY": False
    }
    
    @classmethod
    def get(cls, flag_name: str, default: Any = None) -> Any:
        """Get feature flag value, checking environment variables first"""
        # Check environment variable
        env_value = os.environ.get(f"RAG_{flag_name}")
        if env_value is not None:
            # Convert string to appropriate type
            if env_value.lower() in ['true', '1', 'yes', 'on']:
                return True
            elif env_value.lower() in ['false', '0', 'no', 'off']:
                return False
            else:
                try:
                    # Try to convert to float/int
                    return float(env_value) if '.' in env_value else int(env_value)
                except ValueError:
                    return env_value
        
        # Return from internal flags or default
        return cls._flags.get(flag_name, default)
    
    @classmethod
    def set(cls, flag_name: str, value: Any):
        """Set feature flag value programmatically"""
        cls._flags[flag_name] = value
        logger.info(f"Feature flag {flag_name} set to {value}")
    
    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """Check if a boolean feature flag is enabled"""
        return bool(cls.get(flag_name, False))
    
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all current feature flag values"""
        all_flags = {}
        for flag_name in cls._flags:
            all_flags[flag_name] = cls.get(flag_name)
        return all_flags
    
    @classmethod
    def disable_all_improvements(cls):
        """Quick rollback to disable all SOTA improvements"""
        cls.set("ENABLE_HYBRID_SEARCH", False)
        cls.set("ENABLE_MULTI_QUERY", False)
        cls.set("ENABLE_DYNAMIC_CONTEXT", False)
        cls.set("ENABLE_SEMANTIC_CACHE", False)
        cls.set("FALLBACK_TO_LEGACY", True)
        logger.warning("All SOTA RAG improvements disabled - using legacy implementation")
    
    @classmethod
    def enable_all_improvements(cls):
        """Enable all SOTA improvements"""
        cls.set("ENABLE_HYBRID_SEARCH", True)
        cls.set("ENABLE_MULTI_QUERY", True)
        cls.set("ENABLE_DYNAMIC_CONTEXT", True)
        cls.set("ENABLE_SEMANTIC_CACHE", True)
        cls.set("FALLBACK_TO_LEGACY", False)
        logger.info("All SOTA RAG improvements enabled")
    
    @classmethod
    def get_config_summary(cls) -> str:
        """Get a summary of current configuration"""
        flags = cls.get_all()
        enabled = [k for k, v in flags.items() if k.startswith("ENABLE_") and v]
        disabled = [k for k, v in flags.items() if k.startswith("ENABLE_") and not v]
        
        summary = f"SOTA RAG Configuration:\n"
        summary += f"Enabled: {', '.join(enabled)}\n"
        summary += f"Disabled: {', '.join(disabled)}\n"
        summary += f"Fallback to Legacy: {'Yes' if flags['FALLBACK_TO_LEGACY'] else 'No'}"
        
        return summary