"""
Main Orchestrator - Builds and manages the complete multi-agent system
Integrates all 6 layers: Intent → Planning → Supervisor → Workers → Synthesis → Reflection
"""

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.postgres import AsyncPostgresSaver
from langgraph.checkpoint.sqlite import AsyncSqliteSaver
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from dotenv import load_dotenv
import os

from agents import (
    worker_registry,
    IntentRouter,
    IntentRouterNode,
    PlanningAgent,
    PlanningNode,
    SynthesisAgent,
    SynthesisNode,
    ReflectionAgent,
    ReflectionNode,
)
from agents.callbacks import LivePlanSyncCallback
from db import get_engine, init_database, get_db_session


# Load environment variables
load_dotenv()


class ConversationState(TypedDict):
    """Complete state for the multi-agent conversation."""
    thread_id: str
    messages: Annotated[List[Dict], "Conversation messages"]
    
    # Intent layer
    current_intent: Optional[Dict]
    
    # Planning layer
    active_plan: Optional[Dict]
    planning_action: Optional[str]
    
    # Execution layer
    worker_results: Annotated[List[Dict], "Worker execution results"]
    execution_summary: Optional[Dict]  # Summary of what was actually executed
    
    # Synthesis layer
    synthesis: Optional[str]
    
    # Reflection layer
    reflection_approved: bool
    reflection_feedback: Optional[str]
    iteration: int
    
    # Output
    final_response: Optional[str]


class MultiAgentOrchestrator:
    """
    Main orchestrator that builds and manages the complete system.
    Handles initialization, graph construction, and execution.
    """
    
    def __init__(self):
        """Initialize orchestrator."""
        self.model = None
        self.db_session = None
        self.checkpointer = None
        self.app = None
        
        # Agent layers
        self.intent_agent = None
        self.planning_agent = None
        self.supervisor_graph = None
        self.synthesis_agent = None
        self.reflection_agent = None
        
        self.worker_agents = {}
    
    async def initialize(self):
        """
        Complete system initialization.
        Call this before using the orchestrator.
        """
        print("\n" + "="*60)
        print("🚀 Multi-Agent System Initialization")
        print("="*60)
        
        # 1. Initialize LLM
        print("\n🤖 Initializing LLM...")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        
        self.model = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.7
        )
        print("   ✓ LLM initialized")
        
        # 2. Initialize database
        print("\n💾 Initializing database...")
        await init_database()
        
        # Get database session
        async for session in get_db_session():
            self.db_session = session
            break
        
        # Initialize checkpointer
        db_url = os.getenv("DATABASE_URL")
        env = os.getenv("ENVIRONMENT", "dev")
        
        if env == "prod" and db_url and "postgresql" in db_url:
            self.checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
            print("   ✓ Using PostgreSQL checkpointer")
        else:
            self.checkpointer = AsyncSqliteSaver.from_conn_string("checkpoints.db")
            print("   ✓ Using SQLite checkpointer")
        
        # 3. Worker discovery
        worker_registry.auto_discover_all("workers")
        
        # 4. Initialize agent layers
        print("\n🤖 Initializing agent layers...")
        
        # Intent layer
        self.intent_agent = IntentRouterNode(IntentRouter(self.model))
        print("   ✓ Intent Extraction Agent")
        
        # Planning layer
        self.planning_agent = PlanningNode(
            PlanningAgent(self.model, self.db_session)
        )
        print("   ✓ Planning Agent (with persistence)")
        
        # Infrastructure layers
        self.synthesis_agent = SynthesisNode(SynthesisAgent(self.model))
        print("   ✓ Synthesis Agent")
        
        self.reflection_agent = ReflectionNode(ReflectionAgent(self.model))
        print("   ✓ Reflection Agent")
        
        # 5. Create worker agents for supervisor
        print("\n🔧 Setting up worker agents...")
        worker_agent_list = []
        
        for worker in worker_registry.get_all_workers():
            metadata = worker.get_metadata()
            tools = await worker.get_tools()
            
            # Create ReAct agent for each worker
            agent = create_react_agent(
                self.model,
                tools=tools,
                name=metadata.name,
                state_modifier=f"You are {metadata.description}"
            )
            
            self.worker_agents[metadata.name] = agent
            worker_agent_list.append(agent)
            
            print(f"   ✓ {metadata.name}: {len(tools)} tools")
        
        # 6. Create supervisor
        print("\n📊 Creating supervisor agent...")
        self.supervisor_graph = create_supervisor(
            worker_agent_list,
            model=self.model,
            prompt=self._build_supervisor_prompt()
        )
        print("   ✓ Supervisor created")
        
        # 7. Build complete graph
        print("\n🏗️  Building complete workflow graph...")
        self._build_graph()
        print("   ✓ Graph compiled")
        
        print("\n✅ System Ready!")
        print("="*60 + "\n")
    
    def _build_supervisor_prompt(self) -> str:
        """Build supervisor prompt with worker descriptions."""
        workers = worker_registry.get_all_metadata()
        workers_desc = "\n".join([
            f"- {w.name}: {w.description}"
            for w in workers
        ])
        
        return f"""You are a supervisor executing a pre-defined plan.

Available team members:
{workers_desc}

Your role:
1. Review the execution plan provided
2. Delegate tasks to appropriate team members
3. Each team member has specialized tools for their domain
4. Coordinate execution and gather results
5. Ensure all plan steps are completed

When given a plan, follow it methodically. Delegate to workers as specified.
Workers will use their tools to complete assigned tasks.
"""
    
    def _build_graph(self):
        """Build the complete 6-layer graph."""
        graph = StateGraph(ConversationState)
        
        # Add all agent nodes
        graph.add_node("intent", self.intent_agent)
        graph.add_node("planning", self.planning_agent)
        graph.add_node("supervisor", self._supervisor_node)
        graph.add_node("synthesis", self.synthesis_agent)
        graph.add_node("reflection", self.reflection_agent)
        
        # Define flow
        graph.add_edge(START, "intent")
        graph.add_edge("intent", "planning")
        
        # Planning decides: execute via supervisor or pass through
        graph.add_conditional_edges(
            "planning",
            lambda x: "supervisor" if x.get("planning_action") not in ["pass_through", "none"] else "synthesis"
        )
        
        graph.add_edge("supervisor", "synthesis")
        graph.add_edge("synthesis", "reflection")
        
        # Reflection loop: approved → END, not approved → planning
        graph.add_conditional_edges(
            "reflection",
            lambda x: END if x.get("reflection_approved") else "planning"
        )
        
        # Compile with checkpointer
        self.app = graph.compile(checkpointer=self.checkpointer)
    
    async def _supervisor_node(self, state: ConversationState):
        """
        Supervisor node - orchestrates workers based on plan.
        Uses callback to synchronize plan with actual execution.
        """
        plan = state.get("active_plan")
        
        if not plan:
            # No plan, pass through
            return {"worker_results": []}
        
        plan_id = plan["plan_id"]
        
        # Create live plan sync callback
        callback = LivePlanSyncCallback(
            db_session=self.db_session,
            plan_id=plan_id,
            initial_plan=plan
        )
        
        print(f"\n📊 Supervisor executing plan: {plan_id}")
        print(f"   Initial steps: {len(plan.get('steps', []))}")
        
        # Execute plan through supervisor WITH callback tracking
        try:
            result = await self.supervisor_graph.ainvoke(
                {
                    "messages": state["messages"] + [
                        {
                            "role": "system",
                            "content": f"""Execute this plan (use as guidance, adapt as needed):

Plan ID: {plan_id}
Steps:
{self._format_plan_for_supervisor(plan)}

Invoke the appropriate workers to accomplish these tasks.
You may adapt the plan if you determine better approaches.
"""
                        }
                    ]
                },
                config={
                    "configurable": {"thread_id": state.get("thread_id", "default")},
                    "callbacks": [callback]  # ← MAGIC: Track execution in real-time
                }
            )
            
            # Get execution summary
            summary = callback.get_execution_summary()
            print(f"\n📊 Execution Summary:")
            print(f"   Total steps: {summary['total_steps']}")
            print(f"   Planned: {summary['planned_steps']}, Dynamic: {summary['dynamic_steps']}")
            print(f"   Completed: {summary['completed']}, Failed: {summary['failed']}")
            
            # Extract worker results from supervisor output
            worker_results = []
            if "messages" in result:
                for msg in result["messages"]:
                    if msg.get("role") == "assistant":
                        worker_results.append({
                            "worker": "supervisor",
                            "result": msg.get("content", "")
                        })
            
            # Also include the synchronized plan with execution details
            return {
                "worker_results": worker_results,
                "active_plan": callback.plan,  # Return updated plan with execution details
                "execution_summary": summary
            }
        
        except Exception as e:
            print(f"❌ Supervisor error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "worker_results": [{
                    "worker": "error",
                    "result": f"Error during execution: {str(e)}"
                }],
                "active_plan": plan  # Return original plan on error
            }
    
    def _format_plan_for_supervisor(self, plan: Dict) -> str:
        """Format plan steps for supervisor prompt."""
        steps = plan.get("steps", [])
        formatted = []
        for i, step in enumerate(steps, 1):
            formatted.append(
                f"{i}. {step['worker']}: {step['description']}"
            )
        return "\n".join(formatted)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.db_session:
            await self.db_session.close()
        if self.checkpointer:
            await self.checkpointer.__aexit__(None, None, None)
