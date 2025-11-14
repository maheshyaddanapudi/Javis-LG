"""
Infrastructure Agents - Synthesis and Reflection
These agents operate at the infrastructure layer.
"""

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import os


class SynthesisAgent:
    """
    Aggregates results from parallel workers into coherent response.
    """
    
    def __init__(self, model: BaseChatModel):
        """
        Initialize synthesis agent.
        
        Args:
            model: LLM for synthesis
        """
        self.model = model
    
    async def synthesize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine results from all workers into unified response.
        
        Args:
            state: Current state with worker results
            
        Returns:
            State update with synthesis
        """
        worker_results = state.get("worker_results", [])
        original_request = state.get("messages", [{}])[0].get("content", "")
        execution_summary = state.get("execution_summary", {})
        active_plan = state.get("active_plan", {})
        
        if not worker_results:
            # No results to synthesize
            return {
                "synthesis": "No worker results available to synthesize."
            }
        
        # Format worker results for synthesis
        results_text = self._format_results(worker_results)
        
        # Add context about supervisor adaptations
        adaptation_context = ""
        if execution_summary:
            dynamic_count = execution_summary.get("dynamic_steps", 0)
            if dynamic_count > 0:
                adaptation_context = f"\n\nNote: The supervisor autonomously added {dynamic_count} additional step(s) beyond the original plan to better address your request."
        
        synthesis_prompt = f"""Synthesize the following worker results into a coherent, well-structured response.

Original user request: "{original_request}"

Worker results:
{results_text}
{adaptation_context}

Create a unified answer that:
1. Combines all relevant information
2. Eliminates redundancy
3. Maintains consistency
4. Presents information in a logical flow
5. Directly addresses the user's request

Provide a natural, conversational response.
"""
        
        response = await self.model.ainvoke([
            SystemMessage(content=synthesis_prompt)
        ])
        
        synthesis_content = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "synthesis": synthesis_content
        }
    
    def _format_results(self, results: list) -> str:
        """Format worker results for synthesis prompt."""
        formatted = []
        for i, result in enumerate(results, 1):
            worker_name = result.get("worker", "unknown")
            content = result.get("result", {})
            formatted.append(f"Worker {i} ({worker_name}):\n{content}\n")
        return "\n".join(formatted)


class ReflectionAgent:
    """
    Quality checks the synthesized response.
    Can trigger re-planning if quality is insufficient.
    """
    
    def __init__(self, model: BaseChatModel):
        """
        Initialize reflection agent.
        
        Args:
            model: LLM for reflection
        """
        self.model = model
        self.max_iterations = int(os.getenv("MAX_REFLECTION_ITERATIONS", "2"))
    
    async def reflect(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Critique and potentially improve the synthesized response.
        
        Args:
            state: Current state with synthesis
            
        Returns:
            State update with approval status and feedback
        """
        synthesis = state.get("synthesis", "")
        iteration = state.get("iteration", 0)
        original_request = state.get("messages", [{}])[0].get("content", "")
        
        # Check iteration limit
        if iteration >= self.max_iterations:
            print(f"⚠️  Max reflection iterations ({self.max_iterations}) reached")
            return {
                "reflection_approved": True,
                "final_response": synthesis,
                "reflection_feedback": None
            }
        
        # Build reflection prompt
        reflection_prompt = self._build_reflection_prompt(
            original_request,
            synthesis,
            iteration
        )
        
        # Get reflection
        response = await self.model.ainvoke([
            SystemMessage(content=reflection_prompt)
        ])
        
        reflection_content = response.content if hasattr(response, 'content') else str(response)
        
        # Check if approved
        if "APPROVED" in reflection_content.upper():
            print("✅ Response approved by reflection agent")
            return {
                "reflection_approved": True,
                "final_response": synthesis,
                "reflection_feedback": None
            }
        else:
            print(f"🔄 Reflection iteration {iteration + 1}: improvements suggested")
            return {
                "reflection_approved": False,
                "reflection_feedback": reflection_content,
                "iteration": iteration + 1
            }
    
    def _build_reflection_prompt(
        self,
        original_request: str,
        synthesis: str,
        iteration: int
    ) -> str:
        """Build reflection prompt."""
        return f"""Review this response for quality (iteration {iteration + 1}).

Original user request: "{original_request}"

Generated response:
{synthesis}

Evaluate the response on these criteria:
1. **Accuracy**: Is the information correct and factual?
2. **Completeness**: Are all aspects of the request addressed?
3. **Clarity**: Is it well-structured and easy to understand?
4. **Consistency**: Are there any contradictions?
5. **Relevance**: Does it directly answer the user's question?

If the response meets all criteria at a high level, respond with: APPROVED

If improvements are needed, provide specific, actionable feedback on what needs to be fixed or enhanced.
Focus on the most critical issues.
"""


class SynthesisNode:
    """LangGraph node wrapper for synthesis agent."""
    
    def __init__(self, agent: SynthesisAgent):
        self.agent = agent
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute synthesis logic."""
        return await self.agent.synthesize(state)


class ReflectionNode:
    """LangGraph node wrapper for reflection agent."""
    
    def __init__(self, agent: ReflectionAgent):
        self.agent = agent
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reflection logic."""
        return await self.agent.reflect(state)
