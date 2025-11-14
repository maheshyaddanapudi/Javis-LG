"""
Planning Agent - Creates and updates execution plans.
Plans are persisted in database with versioning.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import uuid

from db.schema import ExecutionPlanDB
from .registry import worker_registry
from .base import WorkerMetadata


class TaskStep(BaseModel):
    """Individual step in the execution plan."""
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    worker: str = Field(description="Which worker handles this step")
    description: str = Field(description="What this step does")
    dependencies: List[str] = Field(
        default_factory=list,
        description="Step IDs that must complete first"
    )
    
    # Execution tracking
    planned: bool = Field(
        default=True,
        description="True if in original plan, False if dynamically added by supervisor"
    )
    status: Optional[Literal["pending", "running", "completed", "failed"]] = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExecutionPlan(BaseModel):
    """Complete execution plan for a user request."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    original_request: str
    intent_type: str
    steps: List[TaskStep]
    execution_mode: Literal["sequential", "parallel", "mixed"] = Field(
        description="How to execute steps"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1


class PlanningAgent:
    """
    Creates, updates, or retrieves execution plans.
    Plans are persisted in database.
    """
    
    def __init__(self, model: BaseChatModel, db_session: AsyncSession):
        """
        Initialize planning agent.
        
        Args:
            model: LLM with structured output support
            db_session: Database session for persistence
        """
        self.model = model.with_structured_output(ExecutionPlan)
        self.db = db_session
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for planning.
        Decides: create new plan, update existing, or pass through.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with planning results
        """
        intent = state.get("current_intent", {})
        intent_type = intent.get("intent_type")
        
        if intent_type == "new_request":
            return await self._create_plan(state)
        
        elif intent_type == "follow_up":
            return await self._update_plan(state)
        
        elif intent_type in ["interrupt", "clarification"]:
            # No planning needed, let supervisor handle directly
            return {
                "planning_action": "pass_through",
                "active_plan": None
            }
        
        return {"planning_action": "none"}
    
    async def _create_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new execution plan from scratch.
        
        Args:
            state: Current conversation state
            
        Returns:
            State update with new plan
        """
        messages = state.get("messages", [])
        if not messages:
            return {"planning_action": "error", "error": "No messages"}
        
        user_request = messages[-1].get("content", "")
        available_workers = worker_registry.get_all_metadata()
        
        planning_prompt = self._build_planning_prompt(user_request, available_workers)
        
        # Generate plan using LLM
        plan = await self.model.ainvoke([
            SystemMessage(content=planning_prompt)
        ])
        
        # Set conversation context
        plan.conversation_id = state.get("thread_id", "unknown")
        plan.created_at = datetime.utcnow()
        plan.updated_at = datetime.utcnow()
        
        # Persist to database
        await self._save_plan(plan)
        
        print(f"📋 Created plan: {plan.plan_id} with {len(plan.steps)} steps")
        
        return {
            "active_plan": plan.model_dump(),
            "planning_action": "created"
        }
    
    async def _update_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing plan with follow-up requirements.
        
        Args:
            state: Current conversation state
            
        Returns:
            State update with updated plan
        """
        conversation_id = state.get("thread_id")
        current_plan_data = await self._load_plan(conversation_id)
        
        if not current_plan_data:
            # No existing plan, create new one
            return await self._create_plan(state)
        
        messages = state.get("messages", [])
        followup_message = messages[-1].get("content", "")
        
        update_prompt = self._build_update_prompt(
            current_plan_data,
            followup_message
        )
        
        # Generate updated plan
        updated_plan = await self.model.ainvoke([
            SystemMessage(content=update_prompt)
        ])
        
        # Increment version
        updated_plan.plan_id = current_plan_data["plan_id"]
        updated_plan.conversation_id = conversation_id
        updated_plan.version = current_plan_data["version"] + 1
        updated_plan.updated_at = datetime.utcnow()
        
        # Save new version
        await self._save_plan(updated_plan)
        
        print(f"📋 Updated plan: {updated_plan.plan_id} to v{updated_plan.version}")
        
        return {
            "active_plan": updated_plan.model_dump(),
            "planning_action": "updated"
        }
    
    def _build_planning_prompt(
        self,
        user_request: str,
        workers: List[WorkerMetadata]
    ) -> str:
        """Build prompt for plan creation."""
        workers_desc = "\n".join([
            f"- {w.name}: {w.description}\n  Capabilities: {', '.join(w.capabilities)}"
            for w in workers
        ])
        
        return f"""Create an execution plan for this request: "{user_request}"

Available workers:
{workers_desc}

Analyze the request and create a step-by-step plan:
1. Identify which workers are needed
2. Determine if steps can run in parallel or must be sequential
3. Specify dependencies between steps (use step_id references)
4. Be specific about what each worker should do

Guidelines:
- Use parallel execution when steps are independent
- Use sequential when steps depend on each other
- Use mixed when you have both parallel and sequential steps

Example:
Request: "Plan trip to London with weather and hotels"
Plan:
- Step 1 (weather_expert): Get London weather forecast (no dependencies)
- Step 2 (hotel_expert): Find hotels in London (no dependencies)
- Execution mode: parallel (steps are independent)

Now create a detailed plan for the request above.
"""
    
    def _build_update_prompt(
        self,
        current_plan: Dict,
        followup: str
    ) -> str:
        """Build prompt for plan update."""
        return f"""Current execution plan:
{json.dumps(current_plan, indent=2)}

User follow-up: "{followup}"

Update the plan to incorporate the follow-up. Options:
1. Add new steps
2. Modify existing steps
3. Change execution order/mode
4. Update dependencies

Return the complete updated plan with all necessary changes.
Maintain the same plan_id but increment the version.
"""
    
    async def _save_plan(self, plan: ExecutionPlan):
        """Persist plan to database."""
        db_plan = ExecutionPlanDB(
            plan_id=plan.plan_id,
            conversation_id=plan.conversation_id,
            plan_data=plan.model_dump(),
            version=plan.version,
            created_at=plan.created_at,
            updated_at=plan.updated_at
        )
        
        self.db.add(db_plan)
        await self.db.commit()
    
    async def _load_plan(self, conversation_id: str) -> Optional[Dict]:
        """Load latest plan for conversation."""
        result = await self.db.execute(
            select(ExecutionPlanDB)
            .where(ExecutionPlanDB.conversation_id == conversation_id)
            .order_by(ExecutionPlanDB.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row.plan_data if row else None


class PlanningNode:
    """LangGraph node wrapper for planning agent."""
    
    def __init__(self, agent: PlanningAgent):
        self.agent = agent
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute planning logic."""
        return await self.agent.process(state)
