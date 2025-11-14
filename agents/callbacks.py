"""
Live Plan Synchronization Callbacks
Keeps execution plan synchronized with actual supervisor execution in real-time.
"""

from langchain.callbacks.base import BaseCallbackHandler
from typing import Any, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
import uuid

from db.schema import ExecutionPlanDB, WorkerExecution


class LivePlanSyncCallback(BaseCallbackHandler):
    """
    Synchronizes execution plan with actual supervisor behavior in real-time.
    
    Features:
    - Updates step status as workers execute
    - Adds dynamic steps when supervisor adapts
    - Stores results and errors
    - Maintains "planned vs actual" audit trail
    
    The plan becomes a living document that reflects reality.
    """
    
    def __init__(self, db_session: AsyncSession, plan_id: str, plan: Dict[str, Any]):
        """
        Initialize callback.
        
        Args:
            db_session: Database session for persistence
            plan_id: ID of the plan being executed
            plan: Current plan state (will be modified)
        """
        self.db = db_session
        self.plan_id = plan_id
        self.plan = plan
        self.step_sequence = len(plan.get("steps", []))
        self.worker_invocation_count = {}  # Track multiple invocations of same worker
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """
        Called when supervisor invokes a worker.
        
        Checks if this was planned or is a supervisor adaptation.
        Updates plan accordingly.
        """
        tool_name = serialized.get("name", "unknown")
        
        # Track invocation count for this worker
        self.worker_invocation_count[tool_name] = \
            self.worker_invocation_count.get(tool_name, 0) + 1
        
        # Try to find matching planned step
        matching_step = self._find_next_pending_step(tool_name)
        
        if matching_step:
            # ✅ This was in the plan - update status
            await self._update_step(
                matching_step["step_id"],
                status="running",
                started_at=datetime.utcnow()
            )
            print(f"✅ Executing planned step: {matching_step['step_id']} ({tool_name})")
        
        else:
            # 🆕 Supervisor adapted! This wasn't in the plan
            new_step = {
                "step_id": f"dynamic-{self.step_sequence}",
                "worker": tool_name,
                "description": f"Dynamically invoked by supervisor: {tool_name}",
                "dependencies": [],
                "planned": False,  # Mark as emergent/adaptive
                "status": "running",
                "result": None,
                "error": None,
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None
            }
            
            # Add to plan
            self.plan["steps"].append(new_step)
            self.step_sequence += 1
            
            # Persist
            await self._save_plan()
            
            print(f"🆕 Supervisor adapted! Added dynamic step: {new_step['step_id']} ({tool_name})")
    
    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any
    ) -> None:
        """
        Called when worker completes successfully.
        Updates step with result.
        """
        # Extract tool name from kwargs or serialized
        tool_name = self._extract_tool_name(kwargs)
        
        # Find the running step for this worker
        step = self._find_running_step(tool_name)
        
        if step:
            await self._update_step(
                step["step_id"],
                status="completed",
                result={"output": output},
                completed_at=datetime.utcnow()
            )
            print(f"✅ Step completed: {step['step_id']} ({tool_name})")
        else:
            print(f"⚠️  Warning: Completed worker {tool_name} but no running step found")
    
    async def on_tool_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """
        Called when worker fails.
        Updates step with error.
        """
        tool_name = self._extract_tool_name(kwargs)
        
        # Find the running step for this worker
        step = self._find_running_step(tool_name)
        
        if step:
            await self._update_step(
                step["step_id"],
                status="failed",
                error=str(error),
                completed_at=datetime.utcnow()
            )
            print(f"❌ Step failed: {step['step_id']} ({tool_name}) - {error}")
        else:
            print(f"⚠️  Warning: Failed worker {tool_name} but no running step found")
    
    def _find_next_pending_step(self, tool_name: str) -> Optional[Dict]:
        """
        Find the next pending step that matches this worker.
        
        Args:
            tool_name: Name of the worker being invoked
            
        Returns:
            Matching step dict or None
        """
        for step in self.plan.get("steps", []):
            if (step["worker"] == tool_name and 
                step.get("status") == "pending" and
                step.get("planned", True)):  # Only match planned steps
                return step
        return None
    
    def _find_running_step(self, tool_name: str) -> Optional[Dict]:
        """
        Find the currently running step for this worker.
        
        Handles multiple invocations by finding the most recent running step.
        
        Args:
            tool_name: Name of the worker
            
        Returns:
            Running step dict or None
        """
        # Find all running steps for this worker (reverse order for most recent)
        for step in reversed(self.plan.get("steps", [])):
            if step["worker"] == tool_name and step.get("status") == "running":
                return step
        return None
    
    def _extract_tool_name(self, kwargs: Dict) -> str:
        """Extract tool name from callback kwargs."""
        # Try various locations where tool name might be
        serialized = kwargs.get("serialized", {})
        return (
            kwargs.get("name") or 
            serialized.get("name") or 
            kwargs.get("tool_name") or
            "unknown"
        )
    
    async def _update_step(self, step_id: str, **updates) -> None:
        """
        Update a step in both memory and database.
        
        Args:
            step_id: ID of step to update
            **updates: Fields to update
        """
        # Update in-memory plan
        for step in self.plan.get("steps", []):
            if step["step_id"] == step_id:
                # Convert datetime objects to ISO strings for JSON serialization
                for key, value in updates.items():
                    if isinstance(value, datetime):
                        updates[key] = value.isoformat()
                
                step.update(updates)
                break
        
        # Persist to database
        await self._save_plan()
    
    async def _save_plan(self) -> None:
        """Persist current plan state to database."""
        try:
            await self.db.execute(
                update(ExecutionPlanDB)
                .where(ExecutionPlanDB.plan_id == self.plan_id)
                .values(
                    plan_data=self.plan,
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.commit()
        except Exception as e:
            print(f"❌ Error saving plan: {e}")
            await self.db.rollback()
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get execution summary statistics.
        
        Returns:
            Dictionary with execution statistics
        """
        steps = self.plan.get("steps", [])
        
        planned_steps = [s for s in steps if s.get("planned", True)]
        dynamic_steps = [s for s in steps if not s.get("planned", True)]
        
        completed = [s for s in steps if s.get("status") == "completed"]
        failed = [s for s in steps if s.get("status") == "failed"]
        running = [s for s in steps if s.get("status") == "running"]
        pending = [s for s in steps if s.get("status") == "pending"]
        
        return {
            "total_steps": len(steps),
            "planned_steps": len(planned_steps),
            "dynamic_steps": len(dynamic_steps),
            "completed": len(completed),
            "failed": len(failed),
            "running": len(running),
            "pending": len(pending),
            "supervisor_adapted": len(dynamic_steps) > 0
        }


class WorkerExecutionCallback(BaseCallbackHandler):
    """
    Tracks individual worker executions for audit trail.
    Separate from plan tracking - logs every invocation.
    """
    
    def __init__(self, db_session: AsyncSession, conversation_id: str, plan_id: str):
        """
        Initialize callback.
        
        Args:
            db_session: Database session
            conversation_id: Current conversation ID
            plan_id: Current plan ID
        """
        self.db = db_session
        self.conversation_id = conversation_id
        self.plan_id = plan_id
        self.current_execution_id = None
    
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any
    ) -> None:
        """Log worker execution start."""
        tool_name = serialized.get("name", "unknown")
        
        execution = WorkerExecution(
            execution_id=str(uuid.uuid4()),
            conversation_id=self.conversation_id,
            plan_id=self.plan_id,
            worker_name=tool_name,
            input_data={"input": input_str},
            status="running",
            started_at=datetime.utcnow()
        )
        
        self.db.add(execution)
        await self.db.commit()
        self.current_execution_id = execution.execution_id
    
    async def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log worker execution completion."""
        if self.current_execution_id:
            await self.db.execute(
                update(WorkerExecution)
                .where(WorkerExecution.execution_id == self.current_execution_id)
                .values(
                    status="completed",
                    output_data={"output": output},
                    completed_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            self.current_execution_id = None
    
    async def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Log worker execution failure."""
        if self.current_execution_id:
            await self.db.execute(
                update(WorkerExecution)
                .where(WorkerExecution.execution_id == self.current_execution_id)
                .values(
                    status="failed",
                    error_message=str(error),
                    completed_at=datetime.utcnow()
                )
            )
            await self.db.commit()
            self.current_execution_id = None
