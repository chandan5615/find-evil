"""Tools package for Find Evil! MCP server."""

from .disk import get_amcache, get_mft, get_prefetch, get_shimcache
from .logs import extract_timeline, get_registry_hives, parse_evtx
from .memory import analyze_processes, check_injections, get_network_connections

__all__ = [
    "get_mft",
    "get_amcache",
    "get_prefetch",
    "get_shimcache",
    "analyze_processes",
    "check_injections",
    "get_network_connections",
    "parse_evtx",
    "extract_timeline",
    "get_registry_hives",
]
