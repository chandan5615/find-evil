"""
Central configuration for Find Evil! incident response agent.

Defines paths, thresholds, model settings, and tool configurations.
All settings can be overridden via environment variables.
"""

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.resolve()
CASE_DATA_DIR = PROJECT_ROOT / "case_data"
LOG_DIR = PROJECT_ROOT / "logs"
EXPORT_DIR = PROJECT_ROOT / "exports"

# Create directories if they don't exist
LOG_DIR.mkdir(exist_ok=True)
EXPORT_DIR.mkdir(exist_ok=True)

# SIFT tools paths
SIFT_TOOLS_PATH = os.getenv("SIFT_TOOLS_PATH", "/usr/local/bin")
VOLATILITY_PATH = os.getenv("VOLATILITY_PATH", "python3 /opt/volatility3-2.20.0/vol.py")
SLEUTHKIT_BIN = os.getenv("SLEUTHKIT_BIN", "/usr/bin")

# Agent settings
MAX_CORRECTION_ATTEMPTS = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))

# Model settings
MODEL = os.getenv("MODEL", "claude-sonnet-4-20250514")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Logging settings
VERBOSE = os.getenv("VERBOSE", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "json"  # json or text

# MCP Server settings
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8765"))
MCP_SERVER_URL = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}"

# Session and reporting settings
SESSION_LOG_DIR = "./logs"
REPORT_OUTPUT_DIR = "./reports"
VERSION = "1.0.0"
HACKATHON_NAME = "Find Evil! 2026"

# Forensic analysis thresholds
MIN_CONFIDENCE_FOR_REPORT = 0.5  # Include findings with this confidence or higher
HALLUCINATION_PATTERNS = {
    "impossible_timestamps": True,  # Dates in future or pre-system-creation
    "contradictory_findings": True,  # Conflicting evidence in same analysis
    "tool_misuse": True,  # Tool used on wrong file type
}

# Tool-specific settings
TOOL_TIMEOUTS = {
    "volatility": 300,  # 5 minutes
    "timeline": 600,    # 10 minutes
    "carving": 900,     # 15 minutes
    "default": 120,     # 2 minutes
}

# Memory analysis profiles
VOLATILITY_PROFILE = os.getenv("VOLATILITY_PROFILE", "auto")

# Read-only enforcement
READ_ONLY_MODE = True  # Never allow write operations
ALLOWED_FILE_MODES = {"r", "rb"}  # Only read modes allowed

# Feature flags
ENABLE_SELF_CORRECTION = True
ENABLE_BENCHMARKING = True
ENABLE_TOKEN_TRACKING = True

# Reporting
REPORT_FORMAT = "markdown"  # markdown, html, json
INCLUDE_CONFIDENCE_SCORES = True
INCLUDE_TOKEN_USAGE = True
