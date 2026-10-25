"""
Main entry point for Active Assistant.
Initializes all components and runs the application.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import threading
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from active_assistant.core.config import load_config, get_config
from active_assistant.core.logging import setup_logging
from active_assistant.core.state import state, AppState
from active_assistant.core.monitor import initialize_monitor, shutdown_monitor
from active_assistant.core.providers import provider_manager
from active_assistant.agents.manager import agent_manager
from active_assistant.plugins.manager import plugin_manager
from active_assistant.voice.assistant import initialize_voice, start_voice, stop_voice
from active_assistant.web.crawler import initialize_web
from active_assistant.web.stream import create_streaming_routes
from active_assistant.mcp.server import MCPServer
from active_assistant.startup.manager import startup_manager
from active_assistant.tools.base import tool_registry


# ============================================================
# Global Application
# ============================================================

class ActiveAssistantApp:
    """Main application class."""
    
    def __init__(self):
        self._running = False
        self._ui_thread: threading.Thread | None = None
        self._tray = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._mcp_server: MCPServer | None = None
        self._streaming_server = None
    
    async def initialize(self, config_path: str | None = None):
        """Initialize all components."""
        logger.info("Initializing Active Assistant...")
        
        # Load configuration
        load_config(config_path)
        setup_logging(config_path)
        
        cfg = state._config if hasattr(state, '_config') else None
        
        # Initialize providers
        await provider_manager.initialize(config_path)
        
        # Initialize agents
        await agent_manager.initialize(config_path)
        
        # Initialize plugins
        await plugin_manager.initialize(config_path)
        
        # Initialize web
        await initialize_web()
        
        # Initialize voice (optional)
        if get_config().voice.enabled:
            await initialize_voice()
            await start_voice()
        
        # Configure startup
        if get_config().startup.enabled:
            await startup_manager.configure()
        
        # Initialize screen monitor
        await initialize_monitor()
        
        # Initialize MCP server
        self._mcp_server = MCPServer()
        if await self._mcp_server.initialize():
            logger.info("MCP server initialized")
        
        logger.info("All components initialized")
    
    def run_tray(self):
        """Run system tray in thread."""
        from active_assistant.tray import TrayIcon
        
        def on_open_ui():
            self._launch_ui()
        
        def on_exit():
            self.shutdown()
        
        self._tray = TrayIcon(on_open_ui=on_open_ui, on_exit=on_exit)
        self._tray.run_in_thread()
    
    def _launch_ui(self):
        """Launch the main UI window."""
        if self._ui_thread and self._ui_thread.is_alive():
            logger.info("UI already running")
            return
        
        def run_ui():
            from active_assistant.ui.main_window import main
            main()
        
        self._ui_thread = threading.Thread(target=run_ui, daemon=True, name="UI")
        self._ui_thread.start()
    
    def run_console(self):
        """Run in console mode (no UI)."""
        self._running = True
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("Active Assistant running in console mode. Press Ctrl+C to exit.")
        
        try:
            while self._running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
    
    async def shutdown(self):
        """Shutdown all components."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Shutting down Active Assistant...")
        
        # Stop tray
        if self._tray:
            self._tray.stop()
        
        # Shutdown components
        await shutdown_monitor()
        await agent_manager.shutdown()
        await plugin_manager.shutdown()
        await stop_voice()
        
        if provider_manager._providers:
            await provider_manager.close()
        
        state.request_shutdown()
        logger.info("Shutdown complete")


# ============================================================
# Entry Points
# ============================================================

    def start_streaming_server(self):
        """Start the streaming server in a background thread."""
        import threading
        import uvicorn
        from starlette.applications import Starlette
        from active_assistant.web.stream import create_streaming_routes
        
        streaming_app = Starlette(routes=create_streaming_routes())
        
        def run_server():
            uvicorn.run(streaming_app, host="127.0.0.1", port=8765, log_level="warning")
        
        self._streaming_thread = threading.Thread(target=run_server, daemon=True)
        self._streaming_thread.start()
        logger.info("Streaming server started on http://127.0.0.1:8765")

    def run_tray_mode(config_path: str | None = None):
        """Run with system tray (default)."""
        app = ActiveAssistantApp()
        
        # Run async initialization
        asyncio.run(app.initialize(config_path))
        
        # Start streaming server
        app.start_streaming_server()
    
    # Run tray
    app.run_tray()
    
    # Keep main thread alive
    try:
        while state.state != AppState.STOPPING:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(app.shutdown())


def run_console_mode(config_path: str | None = None):
    """Run in console mode."""
    app = ActiveAssistantApp()
    
    asyncio.run(app.initialize(config_path))
    app.run_console()


def run_ui_mode(config_path: str | None = None):
    """Run with UI window."""
    app = ActiveAssistantApp()
    
    asyncio.run(app.initialize(config_path))
    app.start_streaming_server()
    app._launch_ui()
    
    # Also run tray for easy access
    app.run_tray()
    
    try:
        while state.state != AppState.STOPPING:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(app.shutdown())


def run_setup():
    """Run interactive setup."""
    print("=" * 60)
    print("Active Assistant Setup")
    print("=" * 60)
    
    # Check for .env file
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        print("\nNo .env file found. Creating from template...")
        template = """# Active Assistant Environment Variables
# Get your free API keys from:
# Groq: https://console.groq.com/keys
# OpenAI: https://platform.openai.com/api-keys
# Anthropic: https://console.anthropic.com/
# Brave Search: https://brave.com/search/api/

GROQ_API_KEY=your_groq_key_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
BRAVE_API_KEY=your_brave_key_here

# Optional: Override config values
# ACTIVE_ASSISTANT_THEME=dark
# ACTIVE_ASSISTANT_LOG_LEVEL=INFO
"""
        env_path.write_text(template)
        print(f"Created {env_path}. Please edit with your API keys.")
    else:
        print(f"\nFound existing .env at {env_path}")
    
    # Check config
    config_path = Path.cwd() / "config.yaml"
    if not config_path.exists():
        print("Creating default config.yaml...")
        import shutil
        default = Path(__file__).parent / "config" / "default_config.yaml"
        if default.exists():
            shutil.copy(default, config_path)
            print(f"Created {config_path}")
    
    print("\nSetup complete! Next steps:")
    print("1. Edit .env with your API keys")
    print("2. Run 'active-assistant' to start")
    print("3. Run 'active-assistant-ui' for the full interface")
    print("4. Run 'active-assistant-setup' to configure startup")


def main():
    """Main entry point with argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Active Assistant - AI-powered desktop assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  active-assistant              # Run with system tray
  active-assistant --console    # Run in console mode
  active-assistant --ui         # Run with full UI
  active-assistant --setup      # Run interactive setup
  active-assistant-tray         # Run tray only
  active-assistant-ui           # Launch UI window
  active-assistant-setup        # Run setup wizard
        """
    )
    
    parser.add_argument(
        "--console", "-c",
        action="store_true",
        help="Run in console mode (no tray/UI)"
    )
    parser.add_argument(
        "--ui", "-u",
        action="store_true",
        help="Run with full UI window"
    )
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Run interactive setup"
    )
    parser.add_argument(
        "--config", "-f",
        type=str,
        help="Path to config file"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    
    args = parser.parse_args()
    
    if args.version:
        print("Active Assistant v2.0.0")
        return 0
    
    if args.setup:
        run_setup()
        return 0
    
    config_path = args.config if args.config else None
    
    if args.console:
        run_console_mode(config_path)
    elif args.ui:
        run_ui_mode(config_path)
    else:
        run_tray_mode(config_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())