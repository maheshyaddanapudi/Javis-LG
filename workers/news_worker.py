"""
News Worker Agent
Provides news and current events using MCP server.
"""

from typing import List, Dict, Any
from agents.base import BaseWorkerAgent, WorkerMetadata
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


class NewsWorkerAgent(BaseWorkerAgent):
    """
    News and current events worker using MCP.
    Auto-discovered and registered at startup.
    """
    
    def __init__(self):
        self.mcp_client = None
        self.tools = None
    
    def get_metadata(self) -> WorkerMetadata:
        """Return worker metadata for supervisor."""
        return WorkerMetadata(
            name="news_expert",
            description="Provides latest news, current events, headlines, and breaking news from various sources",
            capabilities=[
                "news",
                "current events",
                "headlines",
                "articles",
                "breaking news",
                "journalism",
                "media"
            ],
            priority=6,
            enabled=True,
            mcp_server_config={
                "transport": "sse",
                "url": "http://localhost:8002/sse",
                "timeout": 30
            }
        )
    
    async def get_tools(self) -> List[BaseTool]:
        """Load tools from MCP news server."""
        if self.tools is None:
            try:
                metadata = self.get_metadata()
                self.mcp_client = MultiServerMCPClient({
                    "news": metadata.mcp_server_config
                })
                self.tools = await self.mcp_client.get_tools()
                print(f"   Loaded {len(self.tools)} tools for news_expert")
            except Exception as e:
                print(f"⚠️  Could not load news tools: {e}")
                print("   Using mock tools for demonstration")
                self.tools = self._create_mock_tools()
        
        return self.tools
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute news-specific task."""
        return state
    
    def _create_mock_tools(self) -> List[BaseTool]:
        """Create mock tools for development/testing."""
        from langchain_core.tools import tool
        
        @tool
        def get_latest_news(topic: str = "general") -> str:
            """Get latest news headlines for a topic."""
            return f"Mock: Latest {topic} news: Major developments in AI technology, Economic indicators show growth"
        
        @tool
        def search_news(query: str) -> str:
            """Search for news articles matching query."""
            return f"Mock: News search for '{query}': Found 5 relevant articles"
        
        return [get_latest_news, search_news]
