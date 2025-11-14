"""
FastAPI routes - OpenAI-compatible chat completion API
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import json
from typing import AsyncGenerator

from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessage,
    UsageInfo,
    ChatCompletionChunk,
    StreamChoice,
    ErrorResponse,
    HealthResponse,
)
from agents.registry import worker_registry
from db import get_database_url

# Global reference to orchestrator (set during startup)
_orchestrator = None


def set_orchestrator(orchestrator):
    """Set global orchestrator reference."""
    global _orchestrator
    _orchestrator = orchestrator


def get_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="LangGraph Multi-Agent API",
        description="OpenAI-compatible multi-agent system with LangGraph",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = get_app()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check if database is accessible
        db_url = get_database_url()
        db_connected = bool(db_url)
        
        return HealthResponse(
            status="healthy" if db_connected else "degraded",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            workers_registered=len(worker_registry.get_all_workers()),
            database_connected=db_connected
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint.
    
    Supports:
    - Multi-turn conversations via conversation_id
    - Intent classification
    - Planning and execution
    - Worker orchestration
    - Quality reflection
    """
    if _orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System not initialized"
        )
    
    # Handle streaming
    if request.stream:
        return StreamingResponse(
            stream_completion(request),
            media_type="text/event-stream"
        )
    
    # Generate or use existing conversation_id
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    # Get last user message
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message found"
        )
    
    user_message = user_messages[-1].content
    
    try:
        # Invoke orchestrator
        result = await _orchestrator.app.ainvoke(
            {
                "thread_id": conversation_id,
                "messages": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ],
                "worker_results": [],
                "iteration": 0
            },
            config={"configurable": {"thread_id": conversation_id}}
        )
        
        # Extract final response
        final_response = result.get("final_response", "No response generated")
        
        # Build OpenAI-compatible response
        completion_id = f"chatcmpl-{uuid.uuid4()}"
        
        return ChatCompletionResponse(
            id=completion_id,
            created=int(datetime.utcnow().timestamp()),
            model=request.model,
            conversation_id=conversation_id,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=final_response
                    ),
                    finish_reason="stop"
                )
            ],
            usage=UsageInfo(
                prompt_tokens=0,  # TODO: Implement token counting
                completion_tokens=0,
                total_tokens=0
            )
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )


async def stream_completion(
    request: ChatCompletionRequest
) -> AsyncGenerator[str, None]:
    """
    Stream chat completion response.
    
    Yields Server-Sent Events (SSE) format.
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())
    completion_id = f"chatcmpl-{uuid.uuid4()}"
    
    try:
        # Stream from orchestrator
        async for chunk in _orchestrator.app.astream(
            {
                "thread_id": conversation_id,
                "messages": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ],
                "worker_results": [],
                "iteration": 0
            },
            config={"configurable": {"thread_id": conversation_id}}
        ):
            # Extract content from chunk
            if "final_response" in chunk:
                response_chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=int(datetime.utcnow().timestamp()),
                    model=request.model,
                    choices=[
                        StreamChoice(
                            index=0,
                            delta={"content": chunk["final_response"]},
                            finish_reason="stop"
                        )
                    ]
                )
                yield f"data: {response_chunk.model_dump_json()}\n\n"
        
        # Send done signal
        yield "data: [DONE]\n\n"
    
    except Exception as e:
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "server_error"
            }
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatibility)."""
    return {
        "object": "list",
        "data": [
            {
                "id": "langgraph-supervisor-v1",
                "object": "model",
                "created": int(datetime(2024, 1, 1).timestamp()),
                "owned_by": "langgraph-multi-agent"
            }
        ]
    }


@app.get("/workers")
async def list_workers():
    """List all registered workers (custom endpoint)."""
    workers = worker_registry.get_all_metadata()
    return {
        "workers": [
            {
                "name": w.name,
                "description": w.description,
                "capabilities": w.capabilities,
                "priority": w.priority,
                "enabled": w.enabled
            }
            for w in workers
        ]
    }
