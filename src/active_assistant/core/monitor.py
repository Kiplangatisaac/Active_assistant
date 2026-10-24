"""
Screen monitoring for Active Assistant.
Captures active window, computes perceptual hashes, detects changes.
"""
from __future__ import annotations

import asyncio
import base64
import io
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import mss
from PIL import Image, ImageDraw
from loguru import logger

from active_assistant.core.config import get_config
from active_assistant.core.state import state, event_bus, AppState
from active_assistant.agents.manager import agent_manager
from active_assistant.core.providers import chat_completion, ModelType, Message


# ============================================================
# Windows API
# ============================================================

import ctypes
from ctypes import wintypes
import win32gui
import win32process

# DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

DWMWA_EXTENDED_FRAME_BOUNDS = 9

# Win32 constants
MB_YESNO = 0x00000004
MB_ICONQUESTION = 0x00000020
MB_ICONWARNING = 0x00000030
MB_SYSTEMMODAL = 0x00001000
MB_SETFOREGROUND = 0x00010000
IDYES = 6


# ============================================================
# Configuration
# ============================================================

MONITORED_PROCESSES = {
    "code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe",
    "sublime_text.exe", "notepad++.exe", "notepad.exe",
    "windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
    "mintty.exe", "winword.exe", "obsidian.exe",
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "devenv.exe", "rider64.exe", "webstorm64.exe", "clion64.exe",
}

IGNORED_TITLE_KEYWORDS = [
    "spotify", "youtube", "netflix", "vlc", "task manager", "settings",
    "calculator", "notifications", "action center", "start menu",
]

MAX_IMAGE_DIMENSION = 1280
JPEG_QUALITY = 80
HASH_SIZE = 8
HASH_DIFFERENCE_THRESHOLD = 5


# ============================================================
# Screen Capture
# ============================================================

class ScreenCapture:
    """High-performance screen capture with MSS."""
    
    def __init__(self):
        self._sct: Optional[mss.mss] = None
        self._lock = threading.Lock()
    
    def get_instance(self) -> mss.mss:
        """Get or create MSS instance."""
        with self._lock:
            if self._sct is None:
                self._sct = mss.mss()
            return self._sct
    
    def capture_region(self, left: int, top: int, width: int, height: int) -> Optional[Image.Image]:
        """Capture a screen region."""
        sct = self.get_instance()
        region = {"left": left, "top": top, "width": width, "height": height}
        try:
            sct_img = sct.grab(region)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return img
        except Exception as e:
            logger.warning(f"Screen capture failed: {e}")
            return None
    
    def close(self):
        """Close MSS instance."""
        with self._lock:
            if self._sct:
                try:
                    self._sct.close()
                except Exception:
                    pass
                self._sct = None


# Global capture instance
screen_capture = ScreenCapture()


# ============================================================
# Window Management
# ============================================================

def get_foreground_window_info() -> Tuple[Optional[int], str, str, int]:
    """Get foreground window handle, title, process name, and PID."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindowVisible(hwnd):
        return None, "Desktop", "", 0
    
    title = win32gui.GetWindowText(hwnd).strip()
    
    # Get process info
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(len(buf))
            success = ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            ctypes.windll.kernel32.CloseHandle(handle)
            if success:
                proc_name = Path(buf.value).name.lower()
                return hwnd, title, proc_name, pid
    except Exception:
        pass
    
    return hwnd, title, "", 0


def get_window_bounds(hwnd: int) -> Tuple[int, int, int, int]:
    """Get window bounds using DWM for accurate frame bounds."""
    rect = wintypes.RECT()
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if result == 0:
        return rect.left, rect.top, rect.right, rect.bottom
    return win32gui.GetWindowRect(hwnd)


def is_window_monitored(title: str, proc_name: str) -> bool:
    """Check if window should be monitored."""
    title_lower = title.lower()
    
    # Check ignored keywords
    for keyword in IGNORED_TITLE_KEYWORDS:
        if keyword in title_lower:
            return False
    
    # Check monitored processes
    if proc_name not in MONITORED_PROCESSES:
        return False
    
    return True


# ============================================================
# Perceptual Hashing
# ============================================================

def compute_dhash(image: Image.Image, hash_size: int = HASH_SIZE) -> int:
    """Compute difference hash (dHash) for image similarity."""
    # Resize to (hash_size+1, hash_size) grayscale
    resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
    pixels = list(resized.getdata())
    
    # Compute horizontal gradients
    diff_bits = 0
    bit_index = 0
    for row in range(hash_size):
        row_offset = row * (hash_size + 1)
        for col in range(hash_size):
            if pixels[row_offset + col] > pixels[row_offset + col + 1]:
                diff_bits |= 1 << bit_index
            bit_index += 1
    return diff_bits


def hash_distance(h1: Optional[int], h2: Optional[int], hash_size: int = HASH_SIZE) -> int:
    """Compute Hamming distance between two hashes."""
    if h1 is None or h2 is None:
        return hash_size * hash_size
    return bin(h1 ^ h2).count("1")


def image_to_base64(image: Image.Image) -> str:
    """Convert PIL image to base64 JPEG."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def prepare_image_for_vision(image: Image.Image) -> Image.Image:
    """Prepare image for vision model (resize if needed)."""
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
    return image


# ============================================================
# Vision Analysis
# ============================================================

VISION_SYSTEM_PROMPT = """You are an active background assistant observing the user's screen.
Your task is to detect grammar errors, broken code, syntax issues, terminal errors, UI problems, or security concerns.

You have tools to read files, patch code, run terminal commands, search the web, and more.
Sensitive tools (write_file, execute_command) will trigger a user authorization popup.

RULES:
1. If there are NO actionable issues on screen, respond with ONLY: NONE
2. If you detect an issue, provide a concise 1-2 sentence summary
3. If you need to take action, use the appropriate tools
4. Focus on: code errors, terminal output, UI bugs, security issues, grammar mistakes
5. Ignore: normal application UI, non-error content, videos, games

Current window: '{window_title}'"""


async def analyze_screen(image: Image.Image, window_title: str) -> str:
    """Analyze screen capture with vision model."""
    try:
        # Prepare image
        image = prepare_image_for_vision(image)
        b64_data = image_to_base64(image)
        
        messages = [
            Message(role="system", content=VISION_SYSTEM_PROMPT.format(window_title=window_title)),
            Message(role="user", content=[
                {"type": "text", "text": f"Analyze this screenshot from window: '{window_title}'"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
            ])
        ]
        
        # Get available tools
        from active_assistant.tools.base import tool_registry
        tools = tool_registry.get_openai_tools()
        
        response = await chat_completion(
            messages,
            model_type=ModelType.VISION,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1000,
        )
        
        # Handle tool calls
        if response.tool_calls:
            from active_assistant.tools.base import tool_registry
            for tc in response.tool_calls:
                result = await tool_registry.execute(tc.name, **tc.arguments)
                logger.info(f"Vision tool {tc.name}: {result.success}")
        
        return response.content.strip() if response.content else "NONE"
        
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return "NONE"


# ============================================================
# Screen Monitor
# ============================================================

class ScreenMonitor:
    """Main screen monitoring loop."""
    
    def __init__(self):
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # State
        self._last_hash: Optional[int] = None
        self._last_title: str = ""
        self._last_capture_time: Optional[datetime] = None
        self._capture_count = 0
        self._issue_count = 0
    
    def start(self):
        """Start monitoring in background thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ScreenMonitor")
        self._thread.start()
        logger.info("Screen monitor started")
    
    def stop(self):
        """Stop monitoring."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        screen_capture.close()
        logger.info("Screen monitor stopped")
    
    def pause(self):
        """Pause monitoring."""
        self._paused = True
    
    def resume(self):
        """Resume monitoring."""
        self._paused = False
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        cfg = get_config()
        check_interval = cfg.rules.screen_monitoring.check_interval_seconds
        
        while self._running and not self._stop_event.is_set():
            # Check pause
            if self._paused or state.is_paused:
                time.sleep(1)
                continue
            
            # Check app state
            if state.state != AppState.RUNNING:
                time.sleep(1)
                continue
            
            try:
                self._capture_and_analyze()
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            
            # Sleep with frequent pause checks
            for _ in range(int(check_interval * 2)):
                if self._stop_event.is_set() or self._paused or state.is_paused:
                    break
                time.sleep(0.5)
    
    def _capture_and_analyze(self):
        """Capture screen and analyze if changed."""
        # Get foreground window
        hwnd, title, proc_name, pid = get_foreground_window_info()
        if hwnd is None:
            return
        
        # Check if monitored
        if not is_window_monitored(title, proc_name):
            return
        
        # Get bounds
        left, top, right, bottom = get_window_bounds(hwnd)
        width, height = right - left, bottom - top
        
        if width <= 60 or height <= 60:
            return
        
        # Capture
        image = screen_capture.capture_region(left, top, width, height)
        if image is None:
            return
        
        # Compute hash
        current_hash = compute_dhash(image)
        
        # Check for changes
        window_switched = title != self._last_title
        pixels_changed = (
            self._last_hash is None or
            hash_distance(current_hash, self._last_hash) > HASH_DIFFERENCE_THRESHOLD
        )
        
        if not window_switched and not pixels_changed:
            return  # No significant change
        
        # Update state
        self._last_hash = current_hash
        self._last_title = title
        self._last_capture_time = datetime.now()
        self._capture_count += 1
        
        # Update global state
        state.update_window(
            hwnd=hwnd,
            title=title,
            process_name=proc_name,
            process_id=pid,
            bounds=(left, top, right, bottom),
            last_hash=current_hash,
            is_monitored=True,
        )
        state.increment_metric("screens_captured")
        
        # Run vision analysis asynchronously
        asyncio.run_coroutine_threadsafe(
            self._process_vision(image, title),
            asyncio.get_event_loop()
        )
    
    async def _process_vision(self, image: Image.Image, window_title: str):
        """Process vision analysis asynchronously."""
        try:
            analysis = await analyze_screen(image, window_title)
            
            if analysis and analysis.upper() != "NONE":
                self._issue_count += 1
                state.increment_metric("issues_detected")
                state.add_notification(
                    f"Vision: {window_title[:30]}",
                    analysis,
                    "warning"
                )
                logger.info(f"[Vision Alert] {window_title}: {analysis}")
                
        except Exception as e:
            logger.error(f"Vision processing error: {e}")
    
    def get_stats(self) -> dict:
        """Get monitor statistics."""
        return {
            "running": self._running,
            "paused": self._paused,
            "captures": self._capture_count,
            "issues": self._issue_count,
            "last_title": self._last_title,
            "last_capture": self._last_capture_time.isoformat() if self._last_capture_time else None,
        }


# Global monitor instance
screen_monitor = ScreenMonitor()


async def initialize_monitor():
    """Initialize screen monitor."""
    # Subscribe to state changes
    def on_state_changed(event):
        if event.payload.get("new") == "paused":
            screen_monitor.pause()
        elif event.payload.get("new") == "running":
            screen_monitor.resume()
    
    event_bus.subscribe("state_changed", on_state_changed)
    screen_monitor.start()
    logger.info("Screen monitor initialized")


async def shutdown_monitor():
    """Shutdown screen monitor."""
    screen_monitor.stop()