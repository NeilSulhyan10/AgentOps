"""
Agent Definition Loader

Loads agent definitions from Markdown files and provides them as system prompts
for LLM-powered agent execution.
"""

from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AgentDefinitionLoader:
    """Loads and caches agent definitions from Markdown files."""
    
    def __init__(self, agents_dir: Optional[Path] = None):
        if agents_dir is None:
            # Default to backend/agents/markdown relative to this file
            self.agents_dir = Path(__file__).parent.parent / "agents" / "markdown"
        else:
            self.agents_dir = agents_dir
        
        self._cache: Dict[str, str] = {}
        self._loaded = False
    
    def load_all(self) -> Dict[str, str]:
        """Load all .md files from agents directory."""
        if self._loaded:
            return self._cache
        
        if not self.agents_dir.exists():
            logger.warning(f"Agents directory not found: {self.agents_dir}")
            return {}
        
        for md_file in self.agents_dir.glob("*.md"):
            agent_name = md_file.stem
            try:
                content = md_file.read_text(encoding="utf-8")
                self._cache[agent_name] = content
                logger.info(f"Loaded agent definition: {agent_name}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")
        
        self._loaded = True
        return self._cache
    
    def get(self, agent_name: str) -> Optional[str]:
        """Get a specific agent definition by name."""
        if not self._loaded:
            self.load_all()
        return self._cache.get(agent_name)
    
    def reload(self) -> Dict[str, str]:
        """Force reload all agent definitions."""
        self._cache.clear()
        self._loaded = False
        return self.load_all()


# Global loader instance
_loader: Optional[AgentDefinitionLoader] = None


def get_agent_loader() -> AgentDefinitionLoader:
    """Get the global agent definition loader."""
    global _loader
    if _loader is None:
        _loader = AgentDefinitionLoader()
    return _loader


def load_agent_definition(agent_name: str) -> str:
    """Load a single agent definition by name."""
    loader = get_agent_loader()
    definition = loader.get(agent_name)
    if definition is None:
        raise ValueError(f"Agent definition not found: {agent_name}")
    return definition


def load_all_agent_definitions() -> Dict[str, str]:
    """Load all agent definitions."""
    loader = get_agent_loader()
    return loader.load_all()


def reload_agent_definitions() -> Dict[str, str]:
    """Reload all agent definitions from disk."""
    loader = get_agent_loader()
    return loader.reload()