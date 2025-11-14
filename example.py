"""
Example usage script - demonstrates how to use the multi-agent system
Run this after starting the server with: python main.py
"""

import asyncio
import requests
from typing import Dict, Any


class MultiAgentClient:
    """Simple client for the multi-agent API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.conversation_id = None
    
    def chat(self, message: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Send a message and get response.
        
        Args:
            message: User message
            conversation_id: Optional conversation ID for multi-turn
            
        Returns:
            Response dictionary
        """
        if conversation_id:
            self.conversation_id = conversation_id
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": message}],
                "conversation_id": self.conversation_id
            }
        )
        
        result = response.json()
        
        # Save conversation ID for multi-turn
        if "conversation_id" in result:
            self.conversation_id = result["conversation_id"]
        
        return result
    
    def get_response_text(self, result: Dict[str, Any]) -> str:
        """Extract response text from API result."""
        return result["choices"][0]["message"]["content"]
    
    def health_check(self) -> Dict[str, Any]:
        """Check system health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def list_workers(self) -> Dict[str, Any]:
        """List all registered workers."""
        response = requests.get(f"{self.base_url}/workers")
        return response.json()


def main():
    """Example usage."""
    print("="*60)
    print("Multi-Agent System - Example Usage")
    print("="*60)
    
    # Initialize client
    client = MultiAgentClient()
    
    # 1. Health check
    print("\n1. Health Check")
    print("-" * 60)
    health = client.health_check()
    print(f"Status: {health['status']}")
    print(f"Workers: {health['workers_registered']}")
    print(f"Database: {'✓' if health['database_connected'] else '✗'}")
    
    # 2. List workers
    print("\n2. Available Workers")
    print("-" * 60)
    workers = client.list_workers()
    for worker in workers["workers"]:
        print(f"- {worker['name']}: {worker['description']}")
    
    # 3. Simple query
    print("\n3. Simple Query")
    print("-" * 60)
    result = client.chat("What's the weather like in San Francisco?")
    print(f"Response: {client.get_response_text(result)}")
    
    # 4. Complex multi-step query
    print("\n4. Complex Query (Plan Trip)")
    print("-" * 60)
    result = client.chat(
        "Plan a 3-day trip to London. Include weather forecast and hotel recommendations."
    )
    print(f"Response: {client.get_response_text(result)}")
    print(f"Conversation ID: {result['conversation_id']}")
    
    # 5. Follow-up in same conversation
    print("\n5. Follow-up Query")
    print("-" * 60)
    result = client.chat(
        "Also include PST timezone conversion for the trip dates.",
        conversation_id=result['conversation_id']
    )
    print(f"Response: {client.get_response_text(result)}")
    
    # 6. Interrupt (new topic in same conversation)
    print("\n6. Interrupt with New Query")
    print("-" * 60)
    result = client.chat(
        "What's the latest tech news?",
        conversation_id=result['conversation_id']
    )
    print(f"Response: {client.get_response_text(result)}")
    
    print("\n" + "="*60)
    print("Example complete!")
    print("="*60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server")
        print("Make sure the server is running: python main.py")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
