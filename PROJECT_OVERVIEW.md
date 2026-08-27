# LangGraph Multi-Agent System - Project Overview

## Complete File Structure

```
langgraph-multi-agent/
├── README.md                      # Comprehensive documentation
├── QUICKSTART.md                  # Quick start guide
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── main.py                        # Application entry point
├── app.py                         # Main orchestrator
├── example.py                     # Usage examples
│
├── config/
│   └── workers.yaml               # Worker configuration
│
├── db/
│   ├── __init__.py               # Database module exports
│   └── schema.py                  # SQLAlchemy models
│
├── agents/
│   ├── __init__.py               # Agents module exports
│   ├── base.py                    # BaseWorkerAgent interface
│   ├── registry.py                # Worker auto-discovery
│   ├── intent_router.py           # Intent classification
│   ├── planning.py                # Plan creation/updates
│   ├── infrastructure.py          # Synthesis & Reflection
│   └── callbacks.py               # LivePlanSyncCallback for execution tracking
│
├── workers/
│   ├── __init__.py               # Workers module exports
│   ├── weather_worker.py          # Weather information worker
│   ├── news_worker.py             # News and events worker
│   └── research_worker.py         # Research and search worker
│
└── api/
    ├── __init__.py               # API module exports
    ├── models.py                  # Pydantic models
    └── routes.py                  # FastAPI endpoints
```

## Architecture Layers

### 1. Intent Extraction Layer
- **File**: `agents/intent_router.py`
- **Purpose**: Classifies user intent (new_request, follow_up, interrupt, clarification)
- **Input**: User message + conversation history
- **Output**: Structured intent classification

### 2. Planning Layer
- **File**: `agents/planning.py`
- **Purpose**: Creates/updates execution plans
- **Features**: 
  - Database persistence with versioning
  - Plan merging for follow-ups
  - Pass-through for interrupts
- **Output**: Execution plan with steps and dependencies

### 3. Supervisor Layer
- **Integration**: LangGraph Supervisor (`langgraph-supervisor`)
- **Purpose**: Orchestrates workers via handoff tools
- **Features**:
  - Automatic routing based on worker capabilities
  - LLM-driven decision making
  - Parallel execution support

### 4. Worker Layer
- **Files**: `workers/*.py` + `config/workers.yaml`
- **Purpose**: Execute specialized tasks via MCP tools
- **Features**:
  - Code-based and YAML-based workers
  - Auto-discovery at startup
  - MCP integration for external tools
  - Mock tools for development

### 5. Synthesis Layer
- **File**: `agents/infrastructure.py` (SynthesisAgent)
- **Purpose**: Aggregates worker results into coherent response
- **Features**:
  - Combines parallel results
  - Eliminates redundancy
  - Maintains consistency

### 6. Reflection Layer
- **File**: `agents/infrastructure.py` (ReflectionAgent)
- **Purpose**: Quality checks synthesized response
- **Features**:
  - Multi-criteria evaluation
  - Iterative improvement loop
  - Configurable max iterations

## Key Features

### 1. Dynamic Worker Discovery
Workers are automatically discovered from:
- Python code in `workers/` directory (highest priority)
- YAML configuration in `config/workers.yaml` (fallback)
- Code-based workers override YAML on name collision

### 2. Conversation Management
- Thread-based state with checkpointer
- PostgreSQL (production) or SQLite (development)
- Full conversation history persistence
- Plan versioning

### 3. OpenAI-Compatible API
- Drop-in replacement for OpenAI API
- Supports multi-turn conversations
- Streaming responses (basic implementation)
- Standard authentication (extensible)

### 4. MCP Integration
- Model Context Protocol for external tools
- Support for SSE, stdio, and HTTP transports
- Graceful fallback to mock tools
- Multi-server client support

## Database Schema

### execution_plans
- Stores execution plans with versioning
- Fields: plan_id, conversation_id, plan_data (JSON), version, timestamps

### conversation_history
- Stores complete message history
- Fields: conversation_id, role, content, message_data (JSON), timestamp

### worker_executions
- Audit trail of worker invocations
- Fields: execution_id, plan_id, worker_name, input/output, status, timestamps

## Configuration

### Environment Variables (.env)
- `ENVIRONMENT`: dev or prod
- `OPENAI_API_KEY`: Required
- `DATABASE_URL`: Optional (auto-configured)
- `API_HOST`: Default 0.0.0.0
- `API_PORT`: Default 8000
- `MAX_REFLECTION_ITERATIONS`: Default 2

### Worker Configuration (config/workers.yaml)
```yaml
workers:
  - name: worker_name
    type: yaml  # or code
    description: "..."
    capabilities: [...]
    priority: 5
    enabled: true
    mcp_server:
      transport: sse
      url: http://...
```

## API Endpoints

### OpenAI-Compatible
- `POST /v1/chat/completions` - Chat completion
- `GET /v1/models` - List models

### Custom
- `GET /health` - Health check
- `GET /workers` - List registered workers
- `GET /docs` - Interactive API documentation

## Usage Examples

### 1. Simple Query
```python
import requests

requests.post("http://localhost:8000/v1/chat/completions", json={
    "messages": [{"role": "user", "content": "What's the weather?"}]
})
```

### 2. Multi-turn Conversation
```python
# First message
response1 = requests.post(..., json={
    "conversation_id": "my-thread",
    "messages": [{"role": "user", "content": "Plan trip to London"}]
})

# Follow-up
response2 = requests.post(..., json={
    "conversation_id": "my-thread",
    "messages": [
        {"role": "user", "content": "Plan trip to London"},
        {"role": "assistant", "content": response1_content},
        {"role": "user", "content": "Add PST conversion"}
    ]
})
```

### 3. With OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
response = client.chat.completions.create(
    model="langgraph-supervisor-v1",
    messages=[{"role": "user", "content": "Your query"}]
)
```

## Development Workflow

### 1. Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run Development Server
```bash
python main.py
# Server runs with auto-reload in dev mode
```

### 3. Test
```bash
python example.py
# Or use curl/Postman/OpenAI SDK
```

### 4. Add Workers
- Option A: Create `workers/my_worker.py`
- Option B: Add to `config/workers.yaml`
- Restart server for auto-discovery

### 5. Production Deployment
```bash
# Set production environment
export ENVIRONMENT=prod
export DATABASE_URL=postgresql://...

# Run with gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Extending the System

### Add New Agent Layer
1. Create agent in `agents/`
2. Add node to graph in `app.py`
3. Define edges and conditions

### Add New Worker Type
1. Extend `BaseWorkerAgent`
2. Implement required methods
3. Place in `workers/` directory
4. Restart for auto-discovery

### Custom MCP Server
1. Build MCP server per MCP spec
2. Configure in worker metadata
3. Tools auto-loaded at startup

### Custom API Endpoints
1. Add routes to `api/routes.py`
2. Follow OpenAI patterns for compatibility

## Production Considerations

### Performance
- Use PostgreSQL for production
- Configure worker concurrency limits
- Implement proper rate limiting
- Add request/response caching

### Security
- Add API authentication
- Validate user inputs
- Sanitize worker outputs
- Secure MCP connections

### Monitoring
- Enable LangSmith tracing
- Log worker executions
- Monitor database performance
- Track API latencies

### Scaling
- Horizontal scaling via load balancer
- Database read replicas
- Worker pool management
- Asynchronous processing

## Common Issues & Solutions

### Workers Not Loading
- Check console logs for errors
- Verify MCP servers are accessible
- Disable problematic workers in YAML
- Check worker class inheritance

### Database Connection Issues
- Verify DATABASE_URL format
- Check database permissions
- Ensure tables are created
- Review connection pooling

### Quality/Accuracy Issues
- Adjust reflection iterations
- Improve worker tool descriptions
- Enhance supervisor prompt
- Add worker priority tuning

### Performance Issues
- Profile with LangSmith
- Optimize database queries
- Reduce reflection iterations
- Implement worker timeouts

## License & Support

- License: MIT
- Issues: GitHub Issues
- Documentation: README.md & code comments
- Examples: example.py & QUICKSTART.md

---

**Status**: Working prototype
**Last Updated**: 2025-01-XX
**Version**: 1.0.0
