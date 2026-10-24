"""
API Provider abstraction layer for multi-provider support.
Supports Groq, OpenAI, Anthropic, Ollama, and custom providers.
"""
from __future__ import annotations

import abc
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, Callable
from contextlib import asynccontextmanager

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from active_assistant.core.config import get_config, APIProviderConfig
from active_assistant.core.state import state


# ============================================================
# Models
# ============================================================

class ModelType(Enum):
    VISION = "vision"
    CHAT = "chat"
    FAST = "fast"
    REASONING = "reasoning"


@dataclass
class Message:
    """Chat message."""
    role: str  # system, user, assistant, tool
    content: str | List[Dict] = ""
    tool_calls: List[Dict] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""


@dataclass
class ToolCall:
    """Tool call from model."""
    id: str
    name: str
    arguments: Dict


@dataclass
class ChatResponse:
    """Chat completion response."""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: Dict = field(default_factory=dict)
    finish_reason: str = ""
    raw: Any = None


@dataclass
class ModelInfo:
    """Model information."""
    id: str
    name: str
    provider: str
    type: ModelType
    context_window: int = 4096
    supports_vision: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True


# ============================================================
# Base Provider
# ============================================================

class APIProvider(abc.ABC):
    """Abstract base class for API providers."""
    
    def __init__(self, config: APIProviderConfig):
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self._rate_limiter: asyncio.Semaphore | None = None
        self._last_request = 0.0
        self._request_count = 0
        self._window_start = time.time()
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @property
    @abc.abstractmethod
    def default_headers(self) -> Dict[str, str]:
        """Default headers for requests."""
        pass
    
    @property
    def rate_limit(self) -> int:
        return self.config.rate_limit or 30
    
    @property
    def timeout(self) -> float:
        return self.config.timeout or 30.0
    
    async def initialize(self):
        """Initialize the provider."""
        self._rate_limiter = asyncio.Semaphore(self.rate_limit)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=self.default_headers,
            timeout=self.timeout,
            limits=limits,
        )
        logger.info(f"Initialized {self.name} provider")
    
    async def close(self):
        """Close the provider."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        if self._rate_limiter:
            await self._rate_limiter.acquire()
            try:
                # Token bucket style
                now = time.time()
                if now - self._window_start >= 60:
                    self._window_start = now
                    self._request_count = 0
                
                if self._request_count >= self.rate_limit:
                    wait_time = 60 - (now - self._window_start)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    self._window_start = time.time()
                    self._request_count = 0
                
                self._request_count += 1
            finally:
                self._rate_limiter.release()
    
    @abc.abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        """Create a chat completion."""
        pass
    
    @abc.abstractmethod
    def get_model_name(self, model_type: ModelType) -> str:
        """Get model name for a given type."""
        pass
    
    @abc.abstractmethod
    def list_models(self) -> List[ModelInfo]:
        """List available models."""
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation."""
        return len(text) // 4


# ============================================================
# Groq Provider
# ============================================================

class GroqProvider(APIProvider):
    """Groq API provider."""
    
    @property
    def name(self) -> str:
        return "groq"
    
    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
    
    def get_model_name(self, model_type: ModelType) -> str:
        models = self.config.models
        return models.get(model_type.value, models.get("chat", "llama-3.1-70b-versatile"))
    
    def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("llama-3.2-11b-vision-preview", "Llama 3.2 11B Vision", "groq", ModelType.VISION, 128000, True, True),
            ModelInfo("llama-3.1-70b-versatile", "Llama 3.1 70B", "groq", ModelType.CHAT, 131072, False, True),
            ModelInfo("llama-3.1-8b-instant", "Llama 3.1 8B Instant", "groq", ModelType.FAST, 131072, False, True),
            ModelInfo("deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill Llama 70B", "groq", ModelType.REASONING, 131072, False, True),
        ]
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        await self._rate_limit()
        
        # Convert messages to API format
        api_messages = []
        for msg in messages:
            if isinstance(msg.content, list):
                # Multimodal content
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})
            
            if msg.tool_calls:
                api_messages[-1]["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                api_messages[-1]["tool_call_id"] = msg.tool_call_id
            if msg.name:
                api_messages[-1]["name"] = msg.name
        
        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        if stream:
            return self._stream_chat(payload)
        else:
            return await self._single_chat(payload)
    
    async def _single_chat(self, payload: Dict) -> ChatResponse:
        assert self.client is not None
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        choice = data["choices"][0]
        msg = choice["message"]
        
        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                ))
        
        return ChatResponse(
            content=msg.get("content", "") or "",
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )
    
    async def _stream_chat(self, payload: Dict) -> AsyncGenerator[ChatResponse, None]:
        assert self.client is not None
        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            buffer = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choice = data["choices"][0]
                        delta = choice.get("delta", {})
                        
                        content = delta.get("content", "")
                        if content:
                            buffer += content
                            yield ChatResponse(content=buffer, finish_reason=choice.get("finish_reason", ""))
                        
                        if choice.get("finish_reason") == "tool_calls":
                            # Handle tool calls in streaming
                            pass
                    except json.JSONDecodeError:
                        continue


# ============================================================
# OpenAI Provider
# ============================================================

class OpenAIProvider(APIProvider):
    """OpenAI API provider."""
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
    
    def get_model_name(self, model_type: ModelType) -> str:
        models = self.config.models
        return models.get(model_type.value, models.get("chat", "gpt-4o"))
    
    def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("gpt-4o", "GPT-4o", "openai", ModelType.CHAT, 128000, True, True),
            ModelInfo("gpt-4o-mini", "GPT-4o Mini", "openai", ModelType.FAST, 128000, True, True),
            ModelInfo("o1-preview", "o1 Preview", "openai", ModelType.REASONING, 128000, False, True),
        ]
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        await self._rate_limit()
        
        api_messages = []
        for msg in messages:
            if isinstance(msg.content, list):
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})
            if msg.tool_calls:
                api_messages[-1]["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                api_messages[-1]["tool_call_id"] = msg.tool_call_id
        
        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        if stream:
            return self._stream_chat(payload)
        else:
            return await self._single_chat(payload)
    
    async def _single_chat(self, payload: Dict) -> ChatResponse:
        assert self.client is not None
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        choice = data["choices"][0]
        msg = choice["message"]
        
        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"])
                ))
        
        return ChatResponse(
            content=msg.get("content", "") or "",
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", ""),
            raw=data,
        )
    
    async def _stream_chat(self, payload: Dict) -> AsyncGenerator[ChatResponse, None]:
        assert self.client is not None
        async with self.client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            buffer = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choice = data["choices"][0]
                        delta = choice.get("delta", {})
                        
                        content = delta.get("content", "")
                        if content:
                            buffer += content
                            yield ChatResponse(content=buffer, finish_reason=choice.get("finish_reason", ""))
                    except json.JSONDecodeError:
                        continue


# ============================================================
# Anthropic Provider
# ============================================================

class AnthropicProvider(APIProvider):
    """Anthropic API provider."""
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def default_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
    
    def get_model_name(self, model_type: ModelType) -> str:
        models = self.config.models
        return models.get(model_type.value, models.get("chat", "claude-3-5-sonnet-20241022"))
    
    def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "anthropic", ModelType.CHAT, 200000, True, True),
            ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "anthropic", ModelType.FAST, 200000, True, True),
        ]
    
    def _convert_messages(self, messages: List[Message]) -> tuple:
        """Convert to Anthropic format (system + messages)."""
        system = ""
        api_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system = msg.content if isinstance(msg.content, str) else ""
            else:
                content = msg.content
                if isinstance(content, list):
                    # Multimodal - keep as is for Anthropic
                    api_messages.append({"role": msg.role, "content": content})
                else:
                    api_messages.append({"role": msg.role, "content": content})
        
        return system, api_messages
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        await self._rate_limit()
        
        system, api_messages = self._convert_messages(messages)
        
        payload = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        
        if system:
            payload["system"] = system
        
        if tools:
            # Convert tools to Anthropic format
            payload["tools"] = self._convert_tools(tools)
        
        if stream:
            return self._stream_chat(payload)
        else:
            return await self._single_chat(payload)
    
    def _convert_tools(self, tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI tool format to Anthropic."""
        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                fn = tool["function"]
                converted.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
        return converted
    
    async def _single_chat(self, payload: Dict) -> ChatResponse:
        assert self.client is not None
        response = await self.client.post("/messages", json=payload)
        response.raise_for_status()
        data = response.json()
        
        content = ""
        tool_calls = []
        
        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"]
                ))
        
        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            finish_reason=data.get("stop_reason", ""),
            raw=data,
        )
    
    async def _stream_chat(self, payload: Dict) -> AsyncGenerator[ChatResponse, None]:
        assert self.client is not None
        async with self.client.stream("POST", "/messages", json=payload) as response:
            response.raise_for_status()
            buffer = ""
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                buffer += delta.get("text", "")
                                yield ChatResponse(content=buffer)
                            elif delta.get("type") == "tool_use":
                                # Handle streaming tool use
                                pass
                    except json.JSONDecodeError:
                        continue


# ============================================================
# Ollama Provider (Local)
# ============================================================

class OllamaProvider(APIProvider):
    """Ollama local provider."""
    
    @property
    def name(self) -> str:
        return "ollama"
    
    @property
    def default_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}
    
    def get_model_name(self, model_type: ModelType) -> str:
        models = self.config.models
        return models.get(model_type.value, models.get("chat", "llama3.1:latest"))
    
    def list_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("llama3.1:latest", "Llama 3.1", "ollama", ModelType.CHAT, 128000, False, True),
            ModelInfo("llava:latest", "LLaVA Vision", "ollama", ModelType.VISION, 128000, True, True),
            ModelInfo("deepseek-r1:latest", "DeepSeek R1", "ollama", ModelType.REASONING, 128000, False, True),
        ]
    
    async def chat_completion(
        self,
        messages: List[Message],
        model: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> Union[ChatResponse, AsyncGenerator[ChatResponse, None]]:
        await self._rate_limit()
        
        api_messages = []
        for msg in messages:
            if isinstance(msg.content, list):
                # Ollama supports images in messages
                api_messages.append({"role": msg.role, "content": msg.content})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})
        
        payload = {
            "model": model,
            "messages": api_messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": stream,
        }
        
        if tools:
            payload["tools"] = tools
        
        if stream:
            return self._stream_chat(payload)
        else:
            return await self._single_chat(payload)
    
    async def _single_chat(self, payload: Dict) -> ChatResponse:
        assert self.client is not None
        response = await self.client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        
        msg = data.get("message", {})
        content = msg.get("content", "")
        
        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tool_calls.append(ToolCall(
                    id=tc.get("id", str(uuid.uuid4())),
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"]
                ))
        
        return ChatResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", ""),
            usage={},
            finish_reason=data.get("done_reason", "stop"),
            raw=data,
        )
    
    async def _stream_chat(self, payload: Dict) -> AsyncGenerator[ChatResponse, None]:
        assert self.client is not None
        async with self.client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            buffer = ""
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            buffer += content
                            yield ChatResponse(content=buffer, finish_reason=data.get("done_reason", ""))
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue


# ============================================================
# Provider Factory & Manager
# ============================================================

class ProviderManager:
    """Manages multiple API providers."""
    
    def __init__(self):
        self._providers: Dict[str, APIProvider] = {}
        self._default_provider: Optional[str] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self, config_path: str | None = None):
        """Initialize all configured providers."""
        cfg = get_config()
        
        provider_classes = {
            "groq": GroqProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "ollama": OllamaProvider,
        }
        
        for name, provider_config in cfg.api_providers.items():
            if not provider_config.enabled:
                continue
            
            provider_class = provider_classes.get(name)
            if not provider_class:
                logger.warning(f"Unknown provider: {name}")
                continue
            
            try:
                provider = provider_class(provider_config)
                await provider.initialize()
                self._providers[name] = provider
                
                if provider_config.default or not self._default_provider:
                    self._default_provider = name
                
                logger.info(f"Loaded provider: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {name}: {e}")
        
        if not self._default_provider and self._providers:
            self._default_provider = next(iter(self._providers))
        
        logger.info(f"Provider manager initialized. Default: {self._default_provider}")
    
    async def close(self):
        """Close all providers."""
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()
    
    def get_provider(self, name: str | None = None) -> Optional[APIProvider]:
        """Get a provider by name, or default."""
        if name:
            return self._providers.get(name)
        return self._providers.get(self._default_provider) if self._default_provider else None
    
    def get_default_provider(self) -> Optional[APIProvider]:
        return self.get_provider()
    
    def get_model(self, model_type: ModelType, provider: str | None = None) -> str:
        """Get model name for type from provider."""
        prov = self.get_provider(provider)
        if prov:
            return prov.get_model_name(model_type)
        return ""
    
    def list_all_models(self) -> Dict[str, List[ModelInfo]]:
        """List models from all providers."""
        return {name: prov.list_models() for name, prov in self._providers.items()}
    
    @property
    def available_providers(self) -> List[str]:
        return list(self._providers.keys())


# Global provider manager
provider_manager = ProviderManager()


async def get_provider(name: str | None = None) -> Optional[APIProvider]:
    """Get an API provider."""
    return provider_manager.get_provider(name)


async def chat_completion(
    messages: List[Message],
    model_type: ModelType = ModelType.CHAT,
    provider: str | None = None,
    **kwargs
) -> ChatResponse:
    """High-level chat completion with automatic provider selection."""
    prov = provider_manager.get_provider(provider)
    if not prov:
        raise RuntimeError(f"Provider not available: {provider or 'default'}")
    
    model = prov.get_model_name(model_type)
    state.increment_metric("api_calls")
    
    try:
        return await prov.chat_completion(messages, model, **kwargs)
    except Exception as e:
        state.increment_metric("api_errors")
        logger.error(f"Chat completion failed: {e}")
        raise


async def stream_chat_completion(
    messages: List[Message],
    model_type: ModelType = ModelType.CHAT,
    provider: str | None = None,
    **kwargs
) -> AsyncGenerator[ChatResponse, None]:
    """High-level streaming chat completion."""
    prov = provider_manager.get_provider(provider)
    if not prov:
        raise RuntimeError(f"Provider not available: {provider or 'default'}")
    
    model = prov.get_model_name(model_type)
    state.increment_metric("api_calls")
    
    try:
        async for chunk in await prov.chat_completion(messages, model, stream=True, **kwargs):
            yield chunk
    except Exception as e:
        state.increment_metric("api_errors")
        logger.error(f"Streaming chat completion failed: {e}")
        raise