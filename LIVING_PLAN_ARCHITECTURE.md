# Living Plan Architecture

## Overview

The system implements a **"Living Plan" architecture** where execution plans are dynamically synchronized with actual supervisor behavior in real-time.

## Key Concept

```
Planning Agent creates Plan (intended behavior)
    ↓
Supervisor executes (autonomous, may adapt)
    ↓
Callbacks detect actual execution
    ↓
Plan updates to reflect reality
    ↓
Plan = living document (intended + actual)
```

## How It Works

### 1. Plan Creation
```python
Planning Agent → Creates ExecutionPlan
{
  "steps": [
    {"step_id": "step-1", "worker": "weather_expert", "status": "pending", "planned": true},
    {"step_id": "step-2", "worker": "hotel_expert", "status": "pending", "planned": true}
  ]
}
```

### 2. Supervisor Execution with Callback
```python
# Supervisor receives plan as guidance
callback = LivePlanSyncCallback(db, plan_id, plan)

result = await supervisor.ainvoke(
    {...},
    config={"callbacks": [callback]}  # ← Tracks in real-time
)
```

### 3. Real-Time Synchronization

**Scenario: Supervisor Follows Plan**
```
Callback detects: weather_expert starting
→ Updates: step-1.status = "running"

Callback detects: weather_expert completed
→ Updates: step-1.status = "completed", step-1.result = {...}
```

**Scenario: Supervisor Adapts (adds worker not in plan)**
```
Callback detects: news_expert starting ← NOT IN PLAN!
→ Creates: step-dynamic-1 = {worker: "news_expert", status: "running", planned: false}
→ Persists updated plan to DB

Callback detects: news_expert completed
→ Updates: step-dynamic-1.status = "completed"
```

### 4. Final Plan State
```json
{
  "steps": [
    {
      "step_id": "step-1",
      "worker": "weather_expert",
      "planned": true,    ← Original plan
      "status": "completed",
      "result": {...}
    },
    {
      "step_id": "step-dynamic-1",
      "worker": "news_expert",
      "planned": false,   ← Supervisor adapted!
      "status": "completed",
      "result": {...}
    },
    {
      "step_id": "step-2",
      "worker": "hotel_expert",
      "planned": true,
      "status": "completed",
      "result": {...}
    }
  ]
}
```

## Database Schema

### TaskStep Fields
```python
step_id: str           # Unique identifier
worker: str            # Which worker
description: str       # What it does
dependencies: List[str] # Prerequisites

# Execution Tracking
planned: bool          # true = in original plan, false = dynamic
status: str            # pending, running, completed, failed
result: Dict           # Execution output
error: str             # Error message if failed
started_at: datetime   # When started
completed_at: datetime # When finished
```

## Benefits

### ✅ Supervisor Intelligence Preserved
- Supervisor can adapt and improvise
- LLM makes smart routing decisions
- No constraints on autonomy

### ✅ Complete Audit Trail
- See what was planned (`planned: true`)
- See what supervisor added (`planned: false`)
- Full execution history with results
- Timestamps for each step

### ✅ Plan-Reality Alignment
- Plan always reflects actual execution
- No "plan says X but did Y" confusion
- Living document that evolves

### ✅ Resume Capability
- Check step statuses
- Skip completed steps
- Retry only failed steps
- Works even with adaptations

### ✅ Reflection Intelligence
- Reflection agent sees ACTUAL execution
- Can distinguish planned vs emergent steps
- Better failure diagnosis

## Implementation

### LivePlanSyncCallback
```python
class LivePlanSyncCallback(BaseCallbackHandler):
    """Synchronizes plan with supervisor execution."""
    
    async def on_tool_start(self, ...):
        """When worker starts, update plan."""
        - Find matching planned step OR
        - Create dynamic step if supervisor adapted
        - Update status to "running"
        - Persist to DB
    
    async def on_tool_end(self, ...):
        """When worker completes, update plan."""
        - Find running step
        - Update status to "completed"
        - Store result
        - Persist to DB
    
    async def on_tool_error(self, ...):
        """When worker fails, update plan."""
        - Find running step
        - Update status to "failed"
        - Store error
        - Persist to DB
```

### Usage in Supervisor Node
```python
async def supervisor_node(state):
    plan = state["active_plan"]
    
    # Create callback
    callback = LivePlanSyncCallback(db, plan_id, plan)
    
    # Execute with tracking
    result = await supervisor.ainvoke(
        {...},
        config={"callbacks": [callback]}
    )
    
    # Plan is now synchronized!
    return {"active_plan": plan}  # Updated plan
```

## Reflection Loop Enhancement

With living plan, reflection can make smarter decisions:

```python
def reflection_routing(state):
    plan = state["active_plan"]
    steps = plan["steps"]
    
    # Check if all planned steps completed
    planned_steps = [s for s in steps if s["planned"]]
    all_completed = all(s["status"] == "completed" for s in planned_steps)
    
    # Check if supervisor added anything
    dynamic_steps = [s for s in steps if not s["planned"]]
    supervisor_adapted = len(dynamic_steps) > 0
    
    if not all_completed:
        # Execution failed
        return "supervisor"  # Retry execution
    
    elif synthesis_quality_poor:
        # Synthesis issue
        return "synthesis"  # Re-synthesize
    
    else:
        # Plan was wrong
        return "planning"  # Create new plan
```

## Monitoring

Get execution summary:
```python
summary = callback.get_execution_summary()

{
    "total_steps": 3,
    "planned_steps": 2,
    "dynamic_steps": 1,  ← Supervisor added 1 step
    "completed": 3,
    "failed": 0,
    "supervisor_adapted": true
}
```

## Example Output

```
📊 Supervisor executing plan: abc-123
   Initial steps: 2

✅ Executing planned step: step-1 (weather_expert)
✅ Step completed: step-1 (weather_expert)
🆕 Supervisor adapted! Added dynamic step: dynamic-0 (news_expert)
✅ Step completed: dynamic-0 (news_expert)
✅ Executing planned step: step-2 (hotel_expert)
✅ Step completed: step-2 (hotel_expert)

📊 Execution Summary:
   Total steps: 3
   Planned: 2, Dynamic: 1
   Completed: 3, Failed: 0
```

## Best of Both Worlds

This architecture gives you:
1. **Supervisor intelligence** (can adapt and improvise)
2. **Accurate tracking** (know what actually happened)
3. **No compromise** (use out-of-box LangGraph supervisor)
4. **Living audit trail** (planned vs actual)

The plan becomes a **living document** that reflects reality, not just intentions.
