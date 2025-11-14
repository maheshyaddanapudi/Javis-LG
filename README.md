# LangGraph Multi-Agent System

Production-ready multi-agent orchestration system with dynamic worker discovery, conversation management, and OpenAI-compatible API.

## Architecture

```
User Input
    ↓
[Intent Extraction Agent] → Classify intent type
    ↓
[Planning Agent] → Create/Update/PassThrough plan
    ↓                 (Persisted in DB)
[Supervisor Agent] → Orchestrate workers via tools
    ↓                 (Out-of-box LangGraph)
[Workers Execute in Parallel]
    ├─ [Weather Worker] (code or YAML)
    ├─ [News Worker] (code or YAML)
    └─ [Research Worker] (code or YAML)
    ↓
[Synthesis Agent] → Aggregate results
    ↓
[Reflection Agent] → Quality check
    ↓
    ├─ Approved → Final Response
    └─ Not Approved → Loop to Planning/Supervisor
```

## Features

- **6-Layer Agent Architecture**: Intent → Planning → Supervisor → Workers → Synthesis → Reflection
- **Living Plan Architecture**: Plans dynamically sync with actual execution via callbacks (see [LIVING_PLAN.md](LIVING_PLAN.md))
- **Dynamic Worker Discovery**: Auto-register workers from code or YAML configuration
- **MCP Integration**: Model Context Protocol support for external tools
- **Conversation Management**: Thread-safe state with PostgreSQL/SQLite persistence
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI chat completions
- **Flexible Worker Definition**: Define workers in Python code or YAML (code wins on collision)
- **Quality Loop**: Reflection agent ensures output quality with iterative improvement
- **Execution Tracking**: Real-time tracking of worker executions with status, results, and timestamps
- **Supervisor Adaptation Detection**: Automatically detects and records when supervisor deviates from plan

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL (for production) or SQLite (for development)
- OpenAI API key (or compatible LLM provider)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd langgraph-multi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Environment Configuration

```bash
# .env file
ENVIRONMENT=dev  # or prod
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/agentdb  # for prod
# SQLite used automatically in dev mode

# Optional
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
```

### Running the System

```bash
# Development mode (SQLite)
python main.py

# The API will be available at http://localhost:8000
```

### API Usage

```bash
# OpenAI-compatible endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "langgraph-supervisor-v1",
    "messages": [
      {"role": "user", "content": "Plan a trip to London with weather and hotels"}
    ],
    "conversation_id": "optional-thread-id"
  }'
```

## Project Structure

```
langgraph-multi-agent/
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── .env.example             # Environment template
├── main.py                  # Application entry point
├── app.py                   # Main orchestrator
├── config/
│   └── workers.yaml         # YAML worker definitions
├── db/
│   ├── __init__.py
│   └── schema.py           # Database models
├── agents/
│   ├── __init__.py
│   ├── base.py             # BaseWorkerAgent interface
│   ├── registry.py         # Worker auto-discovery
│   ├── intent_router.py    # Intent classification
│   ├── planning.py         # Plan creation/updates
│   └── infrastructure.py   # Synthesis & Reflection
├── workers/
│   ├── __init__.py
│   ├── weather_worker.py   # Example code-based worker
│   ├── news_worker.py      # Example code-based worker
│   └── research_worker.py  # Example code-based worker
└── api/
    ├── __init__.py
    ├── routes.py           # FastAPI routes
    └── models.py           # API request/response models
```

## Adding New Workers

### Option 1: YAML Configuration (Simple)

Add to `config/workers.yaml`:

```yaml
workers:
  - name: translation_expert
    type: yaml
    description: "Translates text between languages"
    capabilities:
      - translation
      - language
      - translate
    priority: 5
    enabled: true
    mcp_server:
      transport: sse
      url: http://localhost:8005/sse
```

### Option 2: Python Code (Advanced)

Create `workers/translation_worker.py`:

```python
from agents.base import BaseWorkerAgent, WorkerMetadata
from typing import List, Dict, Any
from langchain_core.tools import BaseTool

class TranslationWorkerAgent(BaseWorkerAgent):
    def get_metadata(self) -> WorkerMetadata:
        return WorkerMetadata(
            name="translation_expert",
            description="Translates text between languages",
            capabilities=["translation", "language", "translate"],
            priority=5,
            enabled=True,
            mcp_server_config={
                "transport": "sse",
                "url": "http://localhost:8005/sse"
            }
        )
    
    async def get_tools(self) -> List[BaseTool]:
        # Your custom tool loading logic
        pass
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Custom execution logic if needed
        return state
```

System auto-discovers on startup. Code-based workers override YAML if names collide.

## Database Schema

The system automatically creates these tables:

- `execution_plans`: Stores conversation plans with versioning
- `conversation_history`: Full message history per thread
- `worker_executions`: Audit trail of worker invocations

## Configuration

### Worker Priority

Higher priority workers are suggested first to the supervisor (1-10 scale).

### MCP Server Transports

Supported transport types:
- `sse`: Server-Sent Events
- `stdio`: Standard I/O
- `streamable_http`: Streamable HTTP

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| ENVIRONMENT | dev | `dev` or `prod` |
| OPENAI_API_KEY | required | OpenAI API key |
| DATABASE_URL | sqlite | PostgreSQL URL for production |
| API_HOST | 0.0.0.0 | API server host |
| API_PORT | 8000 | API server port |

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

## API Endpoints

### POST /v1/chat/completions

OpenAI-compatible chat completion endpoint.

**Request:**
```json
{
  "model": "langgraph-supervisor-v1",
  "messages": [
    {"role": "user", "content": "Your message"}
  ],
  "conversation_id": "optional-thread-id",
  "stream": false,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "langgraph-supervisor-v1",
  "conversation_id": "thread-id",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Response here"
    },
    "finish_reason": "stop"
  }]
}
```

### GET /health

Health check endpoint.

## Troubleshooting

### Workers Not Discovered

- Check that worker files are in `workers/` directory
- Ensure worker class inherits from `BaseWorkerAgent`
- Check logs for registration messages

### Database Connection Issues

- Development: Ensure write permissions for SQLite file
- Production: Verify PostgreSQL connection string
- Check `DATABASE_URL` environment variable

### MCP Server Connection Failures

- Verify MCP server is running at configured URL
- Check transport type matches server configuration
- Review MCP server logs for errors

## License

MIT

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.
