"""
Main entry point for the multi-agent system.
Starts the FastAPI server with the orchestrator.
"""

import asyncio
import uvicorn
from dotenv import load_dotenv
import os
import sys

from app import MultiAgentOrchestrator
from api import app, set_orchestrator
from db import cleanup_database


# Global orchestrator instance
orchestrator = None


async def startup():
    """Startup event - initialize the system."""
    global orchestrator
    
    print("\n" + "="*60)
    print("🌟 Starting LangGraph Multi-Agent System")
    print("="*60)
    
    try:
        # Initialize orchestrator
        orchestrator = MultiAgentOrchestrator()
        await orchestrator.initialize()
        
        # Set orchestrator reference in API
        set_orchestrator(orchestrator)
        
        print("\n🌐 API server starting...")
        print(f"   OpenAI-compatible endpoint: http://localhost:{os.getenv('API_PORT', 8000)}/v1/chat/completions")
        print(f"   Health check: http://localhost:{os.getenv('API_PORT', 8000)}/health")
        print(f"   Workers list: http://localhost:{os.getenv('API_PORT', 8000)}/workers")
        print(f"   API docs: http://localhost:{os.getenv('API_PORT', 8000)}/docs")
        
    except Exception as e:
        print(f"\n❌ Startup failed: {e}")
        sys.exit(1)


async def shutdown():
    """Shutdown event - cleanup resources."""
    global orchestrator
    
    print("\n🛑 Shutting down...")
    
    if orchestrator:
        await orchestrator.cleanup()
    
    await cleanup_database()
    
    print("✅ Cleanup complete")


# Register startup/shutdown events
@app.on_event("startup")
async def on_startup():
    """FastAPI startup event."""
    await startup()


@app.on_event("shutdown")
async def on_shutdown():
    """FastAPI shutdown event."""
    await shutdown()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    # Run server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=os.getenv("ENVIRONMENT", "dev") == "dev"
    )


if __name__ == "__main__":
    main()
