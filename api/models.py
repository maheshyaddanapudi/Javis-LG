"""
API Models - OpenAI-compatible request/response models
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """Single chat message."""
    role: Literal["user", "assistant", "system"]
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""
    model: str = Field(
        default="langgraph-supervisor-v1",
        description="Model identifier"
    )
    messages: List[ChatMessage] = Field(
        description="List of messages in the conversation"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation thread ID for multi-turn conversations"
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate"
    )


class ChatChoice(BaseModel):
    """Single completion choice."""
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "content_filter", "null"]


class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""
    id: str = Field(description="Unique completion ID")
    object: str = Field(default="chat.completion")
    created: int = Field(description="Unix timestamp")
    model: str
    conversation_id: str = Field(description="Thread ID for this conversation")
    choices: List[ChatChoice]
    usage: Optional[UsageInfo] = None


class StreamChoice(BaseModel):
    """Single streaming choice."""
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Streaming response chunk."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


class ErrorResponse(BaseModel):
    """Error response."""
    error: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    workers_registered: int
    database_connected: bool
