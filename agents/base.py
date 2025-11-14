"""
Base interface for all worker agents.
Workers implementing this interface are auto-discovered at startup.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from langchain_core.tools import BaseTool


@dataclass
class WorkerMetadata:
    """
    Metadata for worker registration.
    Used by supervisor to understand worker capabilities.
    """
    name: str
    description: str
    capabilities: List[str]
    priority: int = 0
    enabled: bool = True
    mcp_server_config: Optional[Dict[str, Any]] = None


class BaseWorkerAgent(ABC):
    """
    Base interface for all worker agents.
    
    Any class implementing this interface will be automatically
    discovered and registered at system startup.
    
    Workers can be defined in Python code or YAML configuration.
    If both exist for the same name, code-based worker wins.
    """
    
    @abstractmethod
    def get_metadata(self) -> WorkerMetadata:
        """
        Return worker metadata for supervisor routing.
        
        Returns:
            WorkerMetadata with name, description, and capabilities
        """
        pass
    
    @abstractmethod
    async def get_tools(self) -> List[BaseTool]:
        """
        Return LangChain-compatible tools for this worker.
        
        Typically loads tools from MCP server or defines custom tools.
        
        Returns:
            List of BaseTool instances
        """
        pass
    
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute worker-specific logic.
        
        Optional: Most workers don't need custom execute logic,
        as the supervisor + tools handle execution.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state dictionary
        """
        pass
    
    def supports_task(self, task_description: str) -> bool:
        """
        Optional: Custom logic to determine if worker can handle task.
        
        Default implementation checks if any capability keyword
        appears in the task description.
        
        Args:
            task_description: Description of the task
            
        Returns:
            True if worker can handle the task
        """
        metadata = self.get_metadata()
        task_lower = task_description.lower()
        return any(
            cap.lower() in task_lower 
            for cap in metadata.capabilities
        )
