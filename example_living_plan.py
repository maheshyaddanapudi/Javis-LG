"""
Living Plan Inspection Example
Demonstrates how to inspect execution plans and see supervisor adaptations.
"""

import requests
from typing import Dict, Any
import json


def inspect_plan_execution():
    """
    Example showing how to retrieve and inspect execution plans.
    """
    print("="*60)
    print("Living Plan Inspection Example")
    print("="*60)
    
    # Make a request
    print("\n1. Making complex request...")
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": "Plan a trip to London with weather and hotels"}
            ]
        }
    )
    
    result = response.json()
    conversation_id = result["conversation_id"]
    print(f"Conversation ID: {conversation_id}")
    
    # In a real implementation, you'd query the database to get the plan
    # For this example, we'll show what the structure looks like
    
    print("\n2. Execution Plan Structure:")
    print("-" * 60)
    
    # Example of what you'd retrieve from database
    example_plan = {
        "plan_id": "abc-123",
        "conversation_id": conversation_id,
        "steps": [
            {
                "step_id": "step-1",
                "worker": "weather_expert",
                "description": "Get London weather forecast",
                "planned": True,
                "status": "completed",
                "result": {"temperature": "72F", "conditions": "partly cloudy"},
                "started_at": "2025-01-15T10:00:00",
                "completed_at": "2025-01-15T10:00:05"
            },
            {
                "step_id": "step-dynamic-1",
                "worker": "news_expert",
                "description": "Supervisor adaptation: news_expert invoked autonomously",
                "planned": False,  # ← Supervisor added this!
                "status": "completed",
                "result": {"headlines": "London hosting major tech conference"},
                "started_at": "2025-01-15T10:00:06",
                "completed_at": "2025-01-15T10:00:10"
            },
            {
                "step_id": "step-2",
                "worker": "hotel_expert",
                "description": "Find hotels in London",
                "planned": True,
                "status": "completed",
                "result": {"hotels": ["Hilton", "Marriott"]},
                "started_at": "2025-01-15T10:00:11",
                "completed_at": "2025-01-15T10:00:15"
            }
        ],
        "execution_summary": {
            "total_steps": 3,
            "planned_steps": 2,
            "dynamic_steps": 1,
            "completed": 3,
            "failed": 0
        }
    }
    
    print(json.dumps(example_plan, indent=2))
    
    # Analyze the plan
    print("\n3. Plan Analysis:")
    print("-" * 60)
    
    planned = [s for s in example_plan["steps"] if s["planned"]]
    dynamic = [s for s in example_plan["steps"] if not s["planned"]]
    
    print(f"Planned steps executed: {len(planned)}")
    for step in planned:
        duration = calculate_duration(step)
        print(f"  ✓ {step['worker']}: {step['status']} ({duration}s)")
    
    if dynamic:
        print(f"\nSupervisor adaptations: {len(dynamic)}")
        for step in dynamic:
            duration = calculate_duration(step)
            print(f"  🆕 {step['worker']}: {step['status']} ({duration}s)")
            print(f"     Reason: Supervisor deemed this helpful for better results")
    
    # Show execution timeline
    print("\n4. Execution Timeline:")
    print("-" * 60)
    for i, step in enumerate(example_plan["steps"], 1):
        status_emoji = {
            "completed": "✅",
            "failed": "❌",
            "running": "🔄",
            "pending": "⏳"
        }[step["status"]]
        
        planned_emoji = "📋" if step["planned"] else "🆕"
        
        print(f"{i}. {status_emoji} {planned_emoji} {step['worker']}")
        print(f"   Started: {step['started_at']}")
        print(f"   Completed: {step['completed_at']}")
        if step.get("result"):
            print(f"   Result: {truncate(str(step['result']))}")
    
    # Show what this means
    print("\n5. Interpretation:")
    print("-" * 60)
    print("""
This execution shows:
- Planning Agent created a 2-step plan (weather + hotels)
- Supervisor executed step 1 (weather) as planned ✓
- Supervisor autonomously added news check (not in original plan) 🆕
- Supervisor executed step 2 (hotels) as planned ✓

The supervisor adapted by adding news_expert because it determined
that checking current events would provide better travel recommendations.

This is the "Living Plan" architecture in action:
- Plan starts as intention (what we planned to do)
- Plan evolves during execution (what actually happened)
- We have full transparency into supervisor decisions
""")


def calculate_duration(step: Dict) -> float:
    """Calculate step duration in seconds."""
    from datetime import datetime
    
    if not step.get("started_at") or not step.get("completed_at"):
        return 0.0
    
    start = datetime.fromisoformat(step["started_at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(step["completed_at"].replace("Z", "+00:00"))
    
    return (end - start).total_seconds()


def truncate(text: str, length: int = 50) -> str:
    """Truncate text for display."""
    return text if len(text) <= length else text[:length] + "..."


if __name__ == "__main__":
    try:
        inspect_plan_execution()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: This is a demonstration of the data structure.")
        print("To see real execution, start the server and make actual requests.")
