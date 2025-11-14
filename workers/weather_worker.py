"""
Weather Worker Agent
Provides weather information using MCP server.
"""

from typing import List, Dict, Any
from agents.base import BaseWorkerAgent, WorkerMetadata
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


class WeatherWorkerAgent(BaseWorkerAgent):
    """
    Weather information worker using MCP.
    Auto-discovered and registered at startup.
    """
    
    def __init__(self):
        self.mcp_client = None
        self.tools = None
    
    def get_metadata(self) -> WorkerMetadata:
        """Return worker metadata for supervisor."""
        return WorkerMetadata(
            name="weather_expert",
            description="Provides weather forecasts, current conditions, and climate information for any location worldwide",
            capabilities=[
                "weather",
                "forecast",
                "temperature",
                "climate",
                "precipitation",
                "conditions",
                "meteorology"
            ],
            priority=7,
            enabled=True,
            mcp_server_config={
                "transport": "sse",
                "url": "http://localhost:8001/sse",
                "timeout": 30
            }
        )
    
    async def get_tools(self) -> List[BaseTool]:
        """Load tools from MCP weather server."""
        if self.tools is None:
            try:
                metadata = self.get_metadata()
                self.mcp_client = MultiServerMCPClient({
                    "weather": metadata.mcp_server_config
                })
                self.tools = await self.mcp_client.get_tools()
                print(f"   Loaded {len(self.tools)} tools for weather_expert")
            except Exception as e:
                print(f"⚠️  Could not load weather tools: {e}")
                print("   Using mock tools for demonstration")
                self.tools = self._create_mock_tools()
        
        return self.tools
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute weather-specific task.
        Most execution is handled by supervisor + tools.
        """
        return state
    
    def _create_mock_tools(self) -> List[BaseTool]:
        """Create mock tools for development/testing."""
        from langchain_core.tools import tool
        
        @tool
        def get_current_weather(location: str) -> str:
            """Get current weather conditions for a location."""
            return f"Mock: Current weather in {location} is 72°F, partly cloudy"
        
        @tool
        def get_weather_forecast(location: str, days: int = 3) -> str:
            """Get weather forecast for a location."""
            return f"Mock: {days}-day forecast for {location}: Sunny with highs around 75°F"
        
        return [get_current_weather, get_weather_forecast]
