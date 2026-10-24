"""
Multi-agent system for Active Assistant.
Each agent has a specific role and can be invoked independently or collaboratively.
"""
from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from contextlib import asynccontextmanager

from loguru import logger
from pydantic import BaseModel, Field

from active_assistant.core.config import get_config, AgentConfig
from active_assistant.core.providers import chat_completion, ModelType, Message, ChatResponse
from active_assistant.core.state import state, event_bus
from active_assistant.tools.base import tool_registry, ToolResult


# ============================================================
# Agent Models
# ============================================================

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentTask:
    """Task assigned to an agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = ""
    description: str = ""
    input_data: Dict = field(default_factory=dict)
    status: AgentStatus = AgentStatus.IDLE
    result: Any = None
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    output: str = ""
    data: Dict = field(default_factory=dict)
    tools_used: List[str] = field(default_factory=list)
    error: str = ""
    execution_time: float = 0


# ============================================================
# Base Agent
# ============================================================

class BaseAgent(ABC):
    """Abstract base class for agents."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.IDLE
        self._current_task: Optional[AgentTask] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._tools: Dict[str, Any] = {}
        self._system_prompt = config.system_prompt
        self._model_type = self._get_model_type(config.model)
    
    def _get_model_type(self, model_key: str) -> ModelType:
        """Map model key to ModelType."""
        mapping = {
            "vision": ModelType.VISION,
            "chat": ModelType.CHAT,
            "fast": ModelType.FAST,
            "reasoning": ModelType.REASONING,
        }
        return mapping.get(model_key, ModelType.CHAT)
    
    @property
    def id(self) -> str:
        return self.config.id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @abstractmethod
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a task. Must be implemented by subclasses."""
        pass
    
    async def start(self):
        """Start the agent worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        state.add_active_agent(self.id)
        logger.info(f"Agent started: {self.name} ({self.id})")
    
    async def stop(self):
        """Stop the agent worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        state.remove_active_agent(self.id)
        logger.info(f"Agent stopped: {self.name} ({self.id})")
    
    async def submit_task(self, description: str, input_data: Dict = None) -> str:
        """Submit a task to the agent."""
        task = AgentTask(
            agent_id=self.id,
            description=description,
            input_data=input_data or {},
        )
        await self._task_queue.put(task)
        return task.id
    
    async def _worker_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                await self._execute_task(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Agent {self.id} worker error: {e}")
    
    async def _execute_task(self, task: AgentTask):
        """Execute a single task."""
        self.status = AgentStatus.RUNNING
        task.status = AgentStatus.RUNNING
        task.started_at = datetime.now()
        self._current_task = task
        
        event_bus.publish(Event("agent_task_started", {"agent_id": self.id, "task_id": task.id}))
        
        try:
            result = await self.process_task(task)
            task.result = result
            task.status = AgentStatus.COMPLETED if result.success else AgentStatus.FAILED
            task.error = result.error
        except Exception as e:
            task.status = AgentStatus.FAILED
            task.error = str(e)
            logger.error(f"Agent {self.id} task {task.id} failed: {e}")
        finally:
            task.completed_at = datetime.now()
            self.status = AgentStatus.IDLE
            self._current_task = None
            event_bus.publish(Event("agent_task_completed", {
                "agent_id": self.id,
                "task_id": task.id,
                "success": task.status == AgentStatus.COMPLETED,
            }))
    
    async def _call_llm(
        self,
        messages: List[Message],
        tools: List[Dict] = None,
        **kwargs
    ) -> ChatResponse:
        """Call LLM with agent's configured model."""
        return await chat_completion(
            messages,
            model_type=self._model_type,
            tools=tools,
            **kwargs
        )
    
    async def _execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool through the registry."""
        return await tool_registry.execute(name, **kwargs)
    
    def get_available_tools(self) -> List[Dict]:
        """Get available tools in OpenAI format."""
        tool_names = self.config.tools
        tools = []
        for name in tool_names:
            executor = tool_registry.get(name)
            if executor:
                tools.append(executor.tool.to_openai_format())
        return tools


# ============================================================
# Specialized Agents
# ============================================================

class VisionAnalystAgent(BaseAgent):
    """Analyzes screen content for issues."""
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        try:
            image_data = task.input_data.get("image")
            window_title = task.input_data.get("window_title", "")
            prompt = task.input_data.get("prompt", self._system_prompt)
            
            if not image_data:
                return AgentResult(False, error="No image data provided")
            
            # Encode image if needed
            if isinstance(image_data, (str, Path)):
                import base64
                async with aiofiles.open(image_data, 'rb') as f:
                    image_data = await f.read()
            
            if isinstance(image_data, bytes):
                import base64
                b64 = base64.b64encode(image_data).decode('utf-8')
                image_data = f"data:image/jpeg;base64,{b64}"
            
            messages = [
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=[
                    {"type": "text", "text": f"Window: {window_title}\nTask: {task.description}"},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ])
            ]
            
            tools = self.get_available_tools()
            response = await self._call_llm(messages, tools=tools if tools else None)
            
            # Handle tool calls
            tools_used = []
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc.name, **tc.arguments)
                    tools_used.append(tc.name)
                    # Could feed back to LLM for multi-turn
            
            return AgentResult(
                success=True,
                output=response.content,
                tools_used=tools_used,
                execution_time=(datetime.now() - start).total_seconds(),
            )
        except Exception as e:
            return AgentResult(False, error=str(e), execution_time=(datetime.now() - start).total_seconds())


class CodeFixerAgent(BaseAgent):
    """Fixes code issues and implements features."""
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        try:
            file_path = task.input_data.get("file_path")
            issue_description = task.input_data.get("issue", task.description)
            context = task.input_data.get("context", "")
            
            # Read the file first
            if file_path:
                read_result = await self._execute_tool("read_file", path=file_path)
                if not read_result.success:
                    return AgentResult(False, error=f"Failed to read file: {read_result.error}")
                file_content = read_result.output
            else:
                file_content = ""
            
            messages = [
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=f"""
Task: {task.description}
Issue: {issue_description}
File: {file_path or 'N/A'}
Context: {context}

File Content:
{file_content}

Please analyze and provide a fix. If you need to make changes, use the write_file tool.
""")
            ]
            
            tools = self.get_available_tools()
            response = await self._call_llm(messages, tools=tools if tools else None)
            
            tools_used = []
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc.name, **tc.arguments)
                    tools_used.append(tc.name)
            
            return AgentResult(
                success=True,
                output=response.content,
                tools_used=tools_used,
                execution_time=(datetime.now() - start).total_seconds(),
            )
        except Exception as e:
            return AgentResult(False, error=str(e), execution_time=(datetime.now() - start).total_seconds())


class ResearcherAgent(BaseAgent):
    """Performs web research and fact-checking."""
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        try:
            query = task.input_data.get("query", task.description)
            max_sources = task.input_data.get("max_sources", 5)
            
            messages = [
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=f"""
Research query: {query}
Maximum sources: {max_sources}

Please search the web and provide a comprehensive answer with citations.
""")
            ]
            
            tools = self.get_available_tools()
            response = await self._call_llm(messages, tools=tools if tools else None)
            
            tools_used = []
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc.name, **tc.arguments)
                    tools_used.append(tc.name)
            
            return AgentResult(
                success=True,
                output=response.content,
                tools_used=tools_used,
                execution_time=(datetime.now() - start).total_seconds(),
            )
        except Exception as e:
            return AgentResult(False, error=str(e), execution_time=(datetime.now() - start).total_seconds())


class VoiceHandlerAgent(BaseAgent):
    """Handles voice commands."""
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        try:
            command = task.input_data.get("command", task.description)
            context = task.input_data.get("context", "")
            
            messages = [
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=f"""
Voice command: {command}
Context: {context}

Process this command and execute appropriate actions. Keep response concise for speech.
""")
            ]
            
            tools = self.get_available_tools()
            response = await self._call_llm(messages, tools=tools if tools else None)
            
            tools_used = []
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc.name, **tc.arguments)
                    tools_used.append(tc.name)
            
            return AgentResult(
                success=True,
                output=response.content,
                tools_used=tools_used,
                execution_time=(datetime.now() - start).total_seconds(),
            )
        except Exception as e:
            return AgentResult(False, error=str(e), execution_time=(datetime.now() - start).total_seconds())


class FileOrganizerAgent(BaseAgent):
    """Organizes files and downloads."""
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        start = datetime.now()
        try:
            directory = task.input_data.get("directory", "~/Downloads")
            action = task.input_data.get("action", "organize")
            
            messages = [
                Message(role="system", content=self._system_prompt),
                Message(role="user", content=f"""
Organize files in: {directory}
Action: {action}

Analyze the directory and organize files appropriately.
""")
            ]
            
            tools = self.get_available_tools()
            response = await self._call_llm(messages, tools=tools if tools else None)
            
            tools_used = []
            if response.tool_calls:
                for tc in response.tool_calls:
                    result = await self._execute_tool(tc.name, **tc.arguments)
                    tools_used.append(tc.name)
            
            return AgentResult(
                success=True,
                output=response.content,
                tools_used=tools_used,
                execution_time=(datetime.now() - start).total_seconds(),
            )
        except Exception as e:
            return AgentResult(False, error=str(e), execution_time=(datetime.now() - start).total_seconds())


# ============================================================
# Agent Manager
# ============================================================

class AgentManager:
    """Manages multiple agents and coordinates them."""
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._config_agents: Dict[str, AgentConfig] = {}
        self._task_results: Dict[str, AgentResult] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self, config_path: str | None = None):
        """Initialize agents from configuration."""
        cfg = get_config()
        
        if not cfg.rules.agents.enabled:
            logger.info("Agents disabled in configuration")
            return
        
        agent_classes = {
            "vision_analyst": VisionAnalystAgent,
            "code_fixer": CodeFixerAgent,
            "researcher": ResearcherAgent,
            "voice_handler": VoiceHandlerAgent,
            "file_organizer": FileOrganizerAgent,
        }
        
        for agent_config in cfg.rules.agents.agents:
            agent_class = agent_classes.get(agent_config.id)
            if not agent_class:
                logger.warning(f"Unknown agent type: {agent_config.id}")
                continue
            
            try:
                agent = agent_class(agent_config)
                await agent.start()
                self._agents[agent_config.id] = agent
                self._config_agents[agent_config.id] = agent_config
                logger.info(f"Initialized agent: {agent_config.name} ({agent_config.id})")
            except Exception as e:
                logger.error(f"Failed to initialize agent {agent_config.id}: {e}")
        
        logger.info(f"Agent manager initialized with {len(self._agents)} agents")
    
    async def shutdown(self):
        """Shutdown all agents."""
        for agent in self._agents.values():
            await agent.stop()
        self._agents.clear()
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> List[Dict]:
        """List all agents with status."""
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "status": agent.status.value,
                "current_task": agent._current_task.id if agent._current_task else None,
            }
            for agent in self._agents.values()
        ]
    
    async def run_agent(self, agent_id: str, description: str, input_data: Dict = None) -> AgentResult:
        """Run a specific agent with a task."""
        agent = self._agents.get(agent_id)
        if not agent:
            return AgentResult(False, error=f"Agent not found: {agent_id}")
        
        task_id = await agent.submit_task(description, input_data)
        
        # Wait for completion (with timeout)
        for _ in range(300):  # 60 second timeout
            await asyncio.sleep(0.2)
            task = agent._current_task
            if task and task.id == task_id and task.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                return task.result or AgentResult(False, error=task.error)
        
        return AgentResult(False, error="Task timeout")
    
    async def run_parallel(self, tasks: List[Dict]) -> List[AgentResult]:
        """Run multiple agents in parallel."""
        async def run_one(t):
            return await self.run_agent(t["agent_id"], t["description"], t.get("input_data"))
        
        return await asyncio.gather(*[run_one(t) for t in tasks])
    
    async def delegate_to_best(self, description: str, input_data: Dict = None) -> AgentResult:
        """Automatically delegate to the best agent based on task description."""
        # Simple keyword-based routing
        desc_lower = description.lower()
        
        if any(kw in desc_lower for kw in ["screen", "screenshot", "vision", "image", "look at", "see"]):
            return await self.run_agent("vision_analyst", description, input_data)
        elif any(kw in desc_lower for kw in ["code", "bug", "fix", "refactor", "implement", "error"]):
            return await self.run_agent("code_fixer", description, input_data)
        elif any(kw in desc_lower for kw in ["search", "research", "find", "lookup", "what is", "how to"]):
            return await self.run_agent("researcher", description, input_data)
        elif any(kw in desc_lower for kw in ["voice", "speak", "say", "listen"]):
            return await self.run_agent("voice_handler", description, input_data)
        elif any(kw in desc_lower for kw in ["organize", "sort", "clean", "files", "downloads"]):
            return await self.run_agent("file_organizer", description, input_data)
        else:
            # Default to researcher for general queries
            return await self.run_agent("researcher", description, input_data)


# Global agent manager
agent_manager = AgentManager()


# Import for async file operations
import aiofiles
from pathlib import Path
from active_assistant.core.state import Event