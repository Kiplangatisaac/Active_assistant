#!/usr/bin/env python3
"""Setup script for Active Assistant."""
from setuptools import setup, find_packages
from pathlib import Path

# Read version
VERSION = "2.0.0"

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8") if (this_directory / "README.md").exists() else ""

# Read requirements
requirements = (this_directory / "requirements.txt").read_text(encoding="utf-8").strip().split("\n") if (this_directory / "requirements.txt").exists() else []

setup(
    name="active-assistant",
    version=VERSION,
    author="Isaac",
    author_email="isaac@example.com",
    description="AI-powered desktop assistant with vision, voice, and plugins",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/active-assistant",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
            "pre-commit>=3.5.0",
        ],
        "gpu": [
            "faiss-gpu>=1.7.4",
            "torch[cuda]>=2.0.0",
        ],
        "local-llm": [
            "llama-cpp-python>=0.2.0",
            "ctransformers>=0.2.27",
        ],
        "all": [
            "faiss-gpu>=1.7.4",
            "torch[cuda]>=2.0.0",
            "llama-cpp-python>=0.2.0",
            "ctransformers>=0.2.27",
        ],
    },
    entry_points={
        "console_scripts": [
            "active-assistant=active_assistant.main:main",
            "active-assistant-tray=active_assistant.tray:main",
            "active-assistant-ui=active_assistant.ui.main_window:main",
            "active-assistant-voice=active_assistant.voice.assistant:main",
            "active-assistant-setup=active_assistant.setup:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Desktop Environment",
        "Topic :: System :: Monitoring",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords=[
        "assistant", "ai", "screen-monitoring", "voice-assistant",
        "multi-agent", "plugins", "brave-search", "computer-vision",
        "groq", "openai", "anthropic", "local-llm",
    ],
    project_urls={
        "Bug Reports": "https://github.com/yourusername/active-assistant/issues",
        "Source": "https://github.com/yourusername/active-assistant",
        "Documentation": "https://github.com/yourusername/active-assistant/wiki",
    },
)