"""
Intent Router Agent - Classifies user intent.
First layer in the agent pipeline.
"""

from typing import Literal, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class UserIntent(BaseModel):
    """Structured output for intent classification."""
    
    intent_type: Literal[
        "new_request",      # Start fresh task
        "follow_up",        # Extend/modify current task
        "interrupt",        # Context switch to new task
        "clarification"     # Clarify previous message
    ] = Field(description="Type of user intent")
    
    requires_context: bool = Field(
        description="Whether this requires previous conversation context"
    )
    
    context_window: int = Field(
        default=0,
        description="Number of previous conversation turns needed"
    )
    
    original_request: str = Field(
        description="The user's message"
    )
    
    reasoning: str = Field(
        description="Brief explanation of classification"
    )


class IntentRouter:
    """
    Pre-supervisor agent that classifies user intent.
    Determines conversation flow BEFORE hitting supervisor.
    """
    
    def __init__(self, model: BaseChatModel):
        """
        Initialize intent router.
        
        Args:
            model: LLM with structured output support
        """
        self.model = model.with_structured_output(UserIntent)
    
    async def classify(self, state: Dict[str, Any]) -> UserIntent:
        """
        Classify user's intent based on conversation history.
        
        Args:
            state: Current conversation state with messages
            
        Returns:
            UserIntent with classification results
        """
        messages = state.get("messages", [])
        
        if not messages:
            # Empty conversation - default to new request
            return UserIntent(
                intent_type="new_request",
                requires_context=False,
                context_window=0,
                original_request="",
                reasoning="Empty conversation"
            )
        
        current_msg = messages[-1].get("content", "")
        has_active_task = state.get("active_plan") is not None
        
        # Build classification prompt
        prompt = self._build_classification_prompt(
            current_msg,
            messages,
            has_active_task
        )
        
        # Get structured classification
        result = await self.model.ainvoke([
            SystemMessage(content=prompt)
        ])
        
        return result
    
    def _build_classification_prompt(
        self,
        current_msg: str,
        messages: List[Dict],
        has_active_task: bool
    ) -> str:
        """
        Build the classification prompt.
        
        Args:
            current_msg: Current user message
            messages: Full conversation history
            has_active_task: Whether there's an active task
            
        Returns:
            Classification prompt
        """
        # Get recent context (last 5 messages)
        recent_context = messages[-5:] if len(messages) > 1 else []
        context_str = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in recent_context[:-1]  # Exclude current message
        ]) if len(recent_context) > 1 else "No previous context"
        
        prompt = f"""Analyze this user message and classify the intent.

Current message: "{current_msg}"
Active task in progress: {has_active_task}
Recent conversation:
{context_str}

Classification types:
1. **new_request**: User wants to start a completely new task
   - Example: "Plan a trip to London"
   - Use when: First message or completely unrelated to current task

2. **follow_up**: User is adding to or modifying the current task
   - Example: "Include PST conversion" (after trip request)
   - Use when: Request extends/modifies the active task

3. **interrupt**: User is switching context to a different topic mid-task
   - Example: "What's the weather in Istanbul?" (during London planning)
   - Use when: Unrelated query while task is running

4. **clarification**: User is clarifying their previous message
   - Example: "I meant London, UK not London, Ontario"
   - Use when: Correcting or clarifying immediately previous message

Analyze the current message and classify appropriately.
"""
        return prompt


class IntentRouterNode:
    """
    LangGraph node wrapper for intent router.
    """
    
    def __init__(self, router: IntentRouter):
        self.router = router
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute intent classification.
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with intent classification
        """
        intent = await self.router.classify(state)
        
        return {
            "current_intent": intent.model_dump()
        }
