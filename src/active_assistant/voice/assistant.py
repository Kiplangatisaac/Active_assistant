"""
Voice assistant for Active Assistant.
Supports wake word detection, speech recognition, and text-to-speech.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
from loguru import logger

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus
from active_assistant.agents.manager import agent_manager
from active_assistant.core.state import agent_context


# ============================================================
# Voice Models
# ============================================================

class VoiceEngine(Enum):
    VOSK = "vosk"
    WHISPER = "whisper"
    AZURE = "azure"
    GOOGLE = "google"


class TTSProvider(Enum):
    PYTTSX3 = "pyttsx3"
    AZURE = "azure"
    ELEVENLABS = "elevenlabs"
    COQUI = "coqui"


@dataclass
class VoiceCommand:
    """Recognized voice command."""
    text: str
    confidence: float
    timestamp: datetime
    wake_word_detected: bool = False
    processed: bool = False
    response: str = ""


@dataclass
class AudioConfig:
    """Audio configuration."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    format: int = 16  # 16-bit
    vad_threshold: float = 0.5
    silence_timeout: float = 2.0


# ============================================================
# Speech Recognition
# ============================================================

class SpeechRecognizer:
    """Base class for speech recognition."""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self._running = False
    
    @abstractmethod
    async def recognize(self, audio_data: bytes) -> Optional[str]:
        """Recognize speech from audio data."""
        pass
    
    @abstractmethod
    async def start_streaming(self, callback: Callable[[str], None]):
        """Start streaming recognition."""
        pass
    
    @abstractmethod
    async def stop_streaming(self):
        """Stop streaming recognition."""
        pass


class VoskRecognizer(SpeechRecognizer):
    """Vosk offline speech recognition."""
    
    def __init__(self, config: AudioConfig, model_path: str = ""):
        super().__init__(config)
        self.model_path = model_path or os.path.expanduser("~/.active_assistant/models/vosk")
        self._model = None
        self._rec = None
        self._stream_callback = None
        self._audio_queue = asyncio.Queue()
    
    async def initialize(self):
        """Initialize Vosk model."""
        try:
            from vosk import Model, KaldiRecognizer
            
            if not Path(self.model_path).exists():
                logger.warning(f"Vosk model not found at {self.model_path}")
                logger.info("Download from https://alphacephei.com/vosk/models")
                return False
            
            self._model = Model(self.model_path)
            self._rec = KaldiRecognizer(self._model, self.config.sample_rate)
            logger.info("Vosk recognizer initialized")
            return True
        except ImportError:
            logger.error("Vosk not installed. Run: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"Vosk initialization failed: {e}")
            return False
    
    async def recognize(self, audio_data: bytes) -> Optional[str]:
        if not self._rec:
            return None
        
        if self._rec.AcceptWaveform(audio_data):
            result = json.loads(self._rec.Result())
            return result.get("text", "")
        
        # Partial result
        partial = json.loads(self._rec.PartialResult())
        return partial.get("partial", "")
    
    async def start_streaming(self, callback: Callable[[str], None]):
        self._stream_callback = callback
        self._running = True
        
        async def process_audio():
            while self._running:
                try:
                    audio_chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=0.1)
                    if self._rec.AcceptWaveform(audio_chunk):
                        result = json.loads(self._rec.Result())
                        text = result.get("text", "")
                        if text and self._stream_callback:
                            await self._stream_callback(text)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Vosk streaming error: {e}")
        
        asyncio.create_task(process_audio())
    
    async def stop_streaming(self):
        self._running = False
        if self._rec:
            final = json.loads(self._rec.FinalResult())
            text = final.get("text", "")
            if text and self._stream_callback:
                await self._stream_callback(text)
    
    async def feed_audio(self, audio_data: bytes):
        """Feed audio data to recognition queue."""
        await self._audio_queue.put(audio_data)


# ============================================================
# Text-to-Speech
# ============================================================

class TTSEngine:
    """Base class for text-to-speech."""
    
    def __init__(self, rate: int = 180, volume: float = 0.9, voice_id: str = ""):
        self.rate = rate
        self.volume = volume
        self.voice_id = voice_id
    
    @abstractmethod
    async def speak(self, text: str) -> bool:
        """Speak text."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop current speech."""
        pass


class Pyttsx3Engine(TTSEngine):
    """pyttsx3 TTS engine."""
    
    def __init__(self, rate: int = 180, volume: float = 0.9, voice_id: str = ""):
        super().__init__(rate, volume, voice_id)
        self._engine = None
        self._lock = threading.Lock()
    
    def _get_engine(self):
        """Lazy initialization of pyttsx3 engine."""
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    import pyttsx3
                    self._engine = pyttsx3.init()
                    self._engine.setProperty('rate', self.rate)
                    self._engine.setProperty('volume', self.volume)
                    if self.voice_id:
                        voices = self._engine.getProperty('voices')
                        for v in voices:
                            if self.voice_id in v.id:
                                self._engine.setProperty('voice', v.id)
                                break
        return self._engine
    
    async def speak(self, text: str) -> bool:
        try:
            engine = self._get_engine()
            # Run in thread pool since pyttsx3 is blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._speak_sync, engine, text)
            return True
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False
    
    def _speak_sync(self, engine, text: str):
        engine.say(text)
        engine.runAndWait()
    
    async def stop(self):
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass


# ============================================================
# Wake Word Detection
# ============================================================

class WakeWordDetector:
    """Wake word detection using simple keyword matching."""
    
    def __init__(self, wake_words: List[str], config: AudioConfig):
        self.wake_words = [w.lower() for w in wake_words]
        self.config = config
        self._running = False
        self._callback: Optional[Callable] = None
    
    def set_callback(self, callback: Callable[[str], None]):
        """Set callback when wake word detected."""
        self._callback = callback
    
    def check_text(self, text: str) -> Optional[str]:
        """Check if text contains wake word."""
        text_lower = text.lower()
        for wake_word in self.wake_words:
            if wake_word in text_lower:
                return wake_word
        return None
    
    async def start(self, audio_callback: Callable[[bytes], None]):
        """Start listening for wake word."""
        self._running = True
        # This would integrate with audio input
        logger.info(f"Wake word detector started: {self.wake_words}")
    
    async def stop(self):
        self._running = False


# ============================================================
# Audio Input
# ============================================================

class AudioInput:
    """Audio input from microphone."""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self._stream = None
        self._running = False
        self._callback: Optional[Callable[[bytes], None]] = None
        self._audio_queue = queue.Queue()
    
    def set_callback(self, callback: Callable[[bytes], None]):
        self._callback = callback
    
    async def start(self):
        """Start audio capture."""
        try:
            import sounddevice as sd
            
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                if self._callback:
                    self._callback(bytes(indata))
            
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                blocksize=self.config.chunk_size,
                dtype='int16',
                callback=audio_callback,
            )
            self._stream.start()
            self._running = True
            logger.info("Audio input started")
        except ImportError:
            logger.error("sounddevice not installed. Run: pip install sounddevice")
        except Exception as e:
            logger.error(f"Audio input start failed: {e}")
    
    async def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Audio input stopped")


# ============================================================
# Voice Assistant
# ============================================================

class VoiceAssistant:
    """Main voice assistant coordinating all components."""
    
    def __init__(self):
        self.config = get_config().voice
        self.audio_config = AudioConfig(
            sample_rate=self.config.sample_rate,
            vad_threshold=self.config.vad_threshold,
            silence_timeout=self.config.silence_timeout,
        )
        
        self.recognizer: Optional[SpeechRecognizer] = None
        self.tts: Optional[TTSEngine] = None
        self.wake_detector: Optional[WakeWordDetector] = None
        self.audio_input: Optional[AudioInput] = None
        
        self._running = False
        self._listening = False
        self._processing = False
        self._command_queue = asyncio.Queue()
    
    async def initialize(self):
        """Initialize all voice components."""
        # Initialize recognizer
        engine = self.config.engine
        if engine == VoiceEngine.VOSK.value:
            self.recognizer = VoskRecognizer(self.audio_config)
            await self.recognizer.initialize()
        else:
            logger.warning(f"Speech engine {engine} not fully implemented, using Vosk")
            self.recognizer = VoskRecognizer(self.audio_config)
            await self.recognizer.initialize()
        
        # Initialize TTS
        tts_engine = self.config.response_voice.get("engine", "pyttsx3")
        if tts_engine == TTSProvider.PYTTSX3.value:
            self.tts = Pyttsx3Engine(
                rate=self.config.response_voice.get("rate", 180),
                volume=self.config.response_voice.get("volume", 0.9),
                voice_id=self.config.response_voice.get("voice_id", ""),
            )
        
        # Initialize wake word detector
        self.wake_detector = WakeWordDetector(self.config.wake_words, self.audio_config)
        self.wake_detector.set_callback(self._on_wake_word)
        
        # Initialize audio input
        self.audio_input = AudioInput(self.audio_config)
        self.audio_input.set_callback(self._on_audio_data)
        
        # Set up recognizer streaming
        if hasattr(self.recognizer, 'start_streaming'):
            await self.recognizer.start_streaming(self._on_recognized_text)
        
        logger.info("Voice assistant initialized")
    
    async def start(self):
        """Start voice assistant."""
        if self._running:
            return
        
        await self.audio_input.start()
        await self.wake_detector.start(self._on_audio_data)
        self._running = True
        self._listening = True
        
        # Start command processor
        asyncio.create_task(self._process_commands())
        
        logger.info("Voice assistant started")
        state.add_notification("Voice Assistant", "Voice assistant started. Say wake word to activate.", "info")
    
    async def stop(self):
        """Stop voice assistant."""
        self._running = False
        self._listening = False
        
        if self.audio_input:
            await self.audio_input.stop()
        if self.wake_detector:
            await self.wake_detector.stop()
        if self.recognizer and hasattr(self.recognizer, 'stop_streaming'):
            await self.recognizer.stop_streaming()
        
        logger.info("Voice assistant stopped")
    
    def _on_audio_data(self, audio_data: bytes):
        """Handle incoming audio data (thread-safe) - feed to recognizer's queue."""
        if self.recognizer and hasattr(self.recognizer, '_audio_queue'):
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.recognizer._audio_queue.put_nowait, audio_data)
            except RuntimeError:
                # No running loop, use sync queue
                self.recognizer._audio_queue.put_nowait(audio_data)
    
    def _on_wake_word(self, wake_word: str):
        """Handle wake word detection."""
        logger.info(f"Wake word detected: {wake_word}")
        state.add_notification("Voice Assistant", f"Wake word detected: {wake_word}", "info")
        self._listening = True
    
    async def _on_recognized_text(self, text: str):
        """Handle recognized speech."""
        if not text.strip():
            return
        
        logger.debug(f"Recognized: {text}")
        
        # Check for wake word if not already listening
        if not self._listening and self.wake_detector:
            wake_word = self.wake_detector.check_text(text)
            if wake_word:
                self._on_wake_word(wake_word)
                # Remove wake word from command
                text = text.lower().replace(wake_word, "").strip()
        
        if self._listening:
            await self._command_queue.put(VoiceCommand(
                text=text,
                confidence=1.0,
                timestamp=datetime.now(),
                wake_word_detected=bool(self.wake_detector and self.wake_detector.check_text(text)),
            ))
    
    async def _process_commands(self):
        """Process voice commands."""
        while self._running:
            try:
                command = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                await self._execute_command(command)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Command processing error: {e}")
    
    async def _execute_command(self, command: VoiceCommand):
        """Execute a voice command."""
        self._processing = True
        state.increment_metric("voice_commands")
        
        try:
            # Use voice handler agent
            result = await agent_manager.run_agent(
                "voice_handler",
                command.text,
                {"command": command.text, "voice": True}
            )
            
            response = result.output if result.success else f"Sorry, I couldn't process that: {result.error}"
            
            # Speak response
            if self.tts and response:
                await self.tts.speak(response)
            
            state.add_notification("Voice Assistant", f"You: {command.text}\nAssistant: {response}", "info")
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            if self.tts:
                await self.tts.speak("Sorry, I encountered an error.")
        finally:
            self._processing = False
    
    async def speak(self, text: str):
        """Speak text directly."""
        if self.tts:
            await self.tts.speak(text)
    
    def is_listening(self) -> bool:
        return self._listening
    
    def is_processing(self) -> bool:
        return self._processing


# Global voice assistant instance
voice_assistant = VoiceAssistant()


async def initialize_voice():
    """Initialize voice assistant."""
    await voice_assistant.initialize()


async def start_voice():
    """Start voice assistant."""
    await voice_assistant.start()


async def stop_voice():
    """Stop voice assistant."""
    await voice_assistant.stop()