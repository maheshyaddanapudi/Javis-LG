"""
Research Worker Agent
Performs web research and information gathering using MCP server.
"""

from typing import List, Dict, Any
from agents.base import BaseWorkerAgent, WorkerMetadata
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


class ResearchWorkerAgent(BaseWorkerAgent):
    """
    Web research and search worker using MCP.
    Auto-discovered and registered at startup.
    """
    
    def __init__(self):
        self.mcp_client = None
        self.tools = None
    
    def get_metadata(self) -> WorkerMetadata:
        """Return worker metadata for supervisor."""
        return WorkerMetadata(
            name="research_expert",
            description="Performs comprehensive web research, information gathering, fact-checking, and detailed analysis",
            capabilities=[
                "research",
                "search",
                "information",
                "web",
                "lookup",
                "find",
                "investigate",
                "analysis",
                "fact-check"
            ],
            priority=8,
            enabled=True,
            mcp_server_config={
                "transport": "sse",
                "url": "http://localhost:8003/sse",
                "timeout": 60
            }
        )
    
    async def get_tools(self) -> List[BaseTool]:
        """Load tools from MCP research server."""
        if self.tools is None:
            try:
                metadata = self.get_metadata()
                self.mcp_client = MultiServerMCPClient({
                    "research": metadata.mcp_server_config
                })
                self.tools = await self.mcp_client.get_tools()
                print(f"   Loaded {len(self.tools)} tools for research_expert")
            except Exception as e:
                print(f"⚠️  Could not load research tools: {e}")
                print("   Using mock tools for demonstration")
                self.tools = self._create_mock_tools()
        
        return self.tools
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research-specific task."""
        return state
    
    def _create_mock_tools(self) -> List[BaseTool]:
        """Create mock tools for development/testing."""
        from langchain_core.tools import tool
        
        @tool
        def web_search(query: str) -> str:
            """Search the web for information."""
            return f"Mock: Web search results for '{query}': Found comprehensive information from 10 sources"
        
        @tool
        def research_topic(topic: str, depth: str = "medium") -> str:
            """Conduct in-depth research on a topic."""
            return f"Mock: {depth.capitalize()} depth research on '{topic}': Gathered insights from academic papers, expert opinions, and industry reports"
        
        @tool
        def fact_check(claim: str) -> str:
            """Verify factual claims."""
            return f"Mock: Fact-check result for '{claim}': Verified across multiple sources"
        
        return [web_search, research_topic, fact_check]
