# Quick Start Guide

## 1. Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## 2. Run the System

```bash
# Start the server
python main.py

# Server will start on http://localhost:8000
```

## 3. Test the API

### Using curl:

```bash
# Simple request
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the weather in San Francisco?"}
    ]
  }'

# Multi-turn conversation
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "my-conversation-123",
    "messages": [
      {"role": "user", "content": "Plan a trip to London"}
    ]
  }'

# Follow-up in same conversation
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "my-conversation-123",
    "messages": [
      {"role": "user", "content": "Plan a trip to London"},
      {"role": "assistant", "content": "...previous response..."},
      {"role": "user", "content": "Include PST timezone conversion"}
    ]
  }'
```

### Using Python:

```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "messages": [
            {"role": "user", "content": "What's the weather in NYC?"}
        ],
        "conversation_id": "test-123"
    }
)

print(response.json()["choices"][0]["message"]["content"])
```

### Using OpenAI Python SDK:

```python
from openai import OpenAI

# Point to your local server
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # API key not required for local
)

response = client.chat.completions.create(
    model="langgraph-supervisor-v1",
    messages=[
        {"role": "user", "content": "Plan a trip to Paris with weather and hotels"}
    ]
)

print(response.choices[0].message.content)
```

## 4. Check System Health

```bash
# Health check
curl http://localhost:8000/health

# List registered workers
curl http://localhost:8000/workers

# API documentation
open http://localhost:8000/docs
```

## 5. Add Custom Workers

### Option 1: YAML Configuration

Edit `config/workers.yaml`:

```yaml
workers:
  - name: my_custom_worker
    type: yaml
    description: "Does something amazing"
    capabilities:
      - custom
      - amazing
    enabled: true
    mcp_server:
      transport: sse
      url: http://localhost:8005/sse
```

### Option 2: Python Code

Create `workers/my_custom_worker.py`:

```python
from agents.base import BaseWorkerAgent, WorkerMetadata
from langchain_core.tools import BaseTool

class MyCustomWorker(BaseWorkerAgent):
    def get_metadata(self) -> WorkerMetadata:
        return WorkerMetadata(
            name="my_custom_worker",
            description="Does something amazing",
            capabilities=["custom", "amazing"],
            priority=5,
            enabled=True
        )
    
    async def get_tools(self) -> List[BaseTool]:
        # Return your tools
        pass
    
    async def execute(self, state):
        return state
```

Restart server - worker will be auto-discovered!

## 6. Troubleshooting

### Database Issues
```bash
# SQLite issues - delete and restart
rm agent_dev.db checkpoints.db
python main.py
```

### Worker Not Loading
```bash
# Check logs for errors
python main.py
# Look for "Registered: worker_name" messages
```

### Connection Errors
```bash
# Verify MCP servers are running
# Or disable workers in config/workers.yaml:
enabled: false
```

## Next Steps

- Read the full [README.md](README.md)
- Explore API docs at http://localhost:8000/docs
- Add your own workers
- Integrate with your existing systems
