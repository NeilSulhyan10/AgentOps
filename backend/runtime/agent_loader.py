"""
Agent Definition Loader

Loads agent definitions from Markdown files and provides them as system prompts
for LLM-powered agent execution.

Any .md file placed in agents/markdown/ that is NOT a reserved name is treated
as a specialist analysis agent and will be available for dynamic dispatch.
Reserved names are used by the orchestrator itself and are never dispatched to
as a specialist: router, rca_synthesizer, remediation_planner, critic.
"""

from pathlib import Path
from typing import Dict, List, Optional
import logging

from backend.runtime.agent_spec import AgentSpec, spec_from_markdown

logger = logging.getLogger(__name__)

# Names that exist in agents/markdown/ but are orchestrator agents, not
# specialist analysis agents.  They are loaded normally but excluded from the
# pool of dispatchable agents.
RESERVED_AGENT_NAMES: frozenset[str] = frozenset(
    {"router", "rca_synthesizer", "remediation_planner", "critic"}
)


class AgentDefinitionLoader:
    """Loads and caches agent definitions from Markdown files."""

    def __init__(self, agents_dir: Optional[Path] = None):
        if agents_dir is None:
            # Default to backend/agents/markdown relative to this file
            self.agents_dir = Path(__file__).parent.parent / "agents" / "markdown"
        else:
            self.agents_dir = agents_dir

        self._cache: Dict[str, str] = {}      # name -> prompt text (front-matter removed)
        self._specs: Dict[str, AgentSpec] = {}
        self._loaded = False

    def load_all(self) -> Dict[str, str]:
        """Load all .md files from agents directory."""
        if self._loaded:
            return self._cache

        if not self.agents_dir.exists():
            logger.warning(f"Agents directory not found: {self.agents_dir}")
            return {}

        for md_file in sorted(self.agents_dir.glob("*.md")):
            agent_name = md_file.stem
            if agent_name.startswith("_"):      # _template.md and similar are not agents
                continue
            try:
                spec, content = spec_from_markdown(agent_name, md_file.read_text(encoding="utf-8"), str(md_file))
                self._cache[agent_name] = content
                self._specs[agent_name] = spec
                logger.info(f"Loaded agent definition: {agent_name}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")

        self._loaded = True
        logger.info(
            f"Discovered specialist agents: {self.get_specialist_agent_names()}"
        )
        return self._cache

    def get(self, agent_name: str) -> Optional[str]:
        """Get a specific agent definition by name."""
        if not self._loaded:
            self.load_all()
        return self._cache.get(agent_name)

    def reload(self) -> Dict[str, str]:
        """Force reload all agent definitions."""
        self._cache.clear()
        self._specs.clear()
        self._loaded = False
        return self.load_all()

    def get_spec(self, agent_name: str) -> Optional[AgentSpec]:
        if not self._loaded:
            self.load_all()
        return self._specs.get(agent_name)

    def get_specs(self) -> List[AgentSpec]:
        """Every specialist (reserved orchestrator agents excluded)."""
        return [self._specs[n] for n in self.get_specialist_agent_names()]

    def get_specialist_agent_names(self) -> List[str]:
        """
        Return the names of all dynamically discovered specialist agents —
        i.e., every loaded .md whose name is NOT in RESERVED_AGENT_NAMES.
        These are the agents that the router can dispatch to.
        """
        if not self._loaded:
            self.load_all()
        return [
            name
            for name in self._cache
            if name not in RESERVED_AGENT_NAMES
        ]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

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


def get_specialist_agent_names() -> List[str]:
    """
    Convenience wrapper — returns the names of all dispatchable specialist
    agents discovered on disk.
    """
    return get_agent_loader().get_specialist_agent_names()


def get_agent_spec(agent_name: str) -> Optional[AgentSpec]:
    return get_agent_loader().get_spec(agent_name)
