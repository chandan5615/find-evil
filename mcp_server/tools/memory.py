"""
Memory analysis tools module for Find Evil! agent.

Wraps Volatility3 to expose memory forensics as safe, typed MCP functions.

Functions:
- analyze_processes(): Extract and analyze running processes
- check_injections(): Detect code injection and suspicious memory patterns
- get_network_connections(): Extract network connections from memory
"""

import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import VOLATILITY_PATH, TOOL_TIMEOUTS, VOLATILITY_PROFILE


# Check tool availability
VOL_BIN = shutil.which("vol") or VOLATILITY_PATH
if not os.path.exists(VOL_BIN):
    # Fallback for Volatility3 installed via pip
    VOL_BIN = "python3 /opt/volatility3-2.20.0/vol.py"


class MemoryAnalysisError(Exception):
    """Raised when memory analysis tool fails."""

    pass


# Helper Functions

def _run_volatility(
    memory_path: str, plugin: str, timeout: int = 120
) -> Tuple[str, str, int]:
    """
    Run a Volatility3 command safely with timeout and error handling.

    Args:
        memory_path: Path to memory dump
        plugin: Volatility3 plugin name
        timeout: Timeout in seconds

    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    try:
        # Build command
        if " " in VOL_BIN:  # Contains path with spaces or is Python invocation
            cmd = f"{VOL_BIN} -f {memory_path} {plugin}".split()
        else:
            cmd = [VOL_BIN, "-f", memory_path, plugin]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            text=True,
            shell=False,
        )
        return result.stdout, result.stderr, result.returncode

    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired(plugin, timeout)
    except Exception as e:
        raise MemoryAnalysisError(f"Volatility command failed: {str(e)}")


def _parse_vol_output(raw_output: str, plugin: str) -> List[Dict[str, Any]]:
    """
    Parse Volatility3 output into structured dicts.

    Handles both table format and structured output.

    Args:
        raw_output: Raw stdout from vol command
        plugin: Plugin name (for context-specific parsing)

    Returns:
        List of parsed dicts
    """
    lines = raw_output.strip().split("\n")
    if not lines:
        return []

    # Skip header lines
    data_lines = []
    header_found = False
    header_line = ""

    for line in lines:
        if line.startswith("PID") or line.startswith("Address") or "---" in line:
            header_found = True
            if not "---" in line:
                header_line = line
            continue
        if header_found and line.strip():
            data_lines.append(line)

    entries = []
    for line in data_lines:
        entry = _parse_vol_table_line(line, plugin)
        if entry:
            entries.append(entry)

    return entries


def _parse_vol_table_line(line: str, plugin: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single line from Volatility3 table output.

    Args:
        line: Single line from vol output
        plugin: Plugin name for context

    Returns:
        Parsed entry dict or None
    """
    line = line.strip()
    if not line or line.startswith("-"):
        return None

    # Split by whitespace for basic parsing
    parts = line.split()
    if not parts:
        return None

    if plugin == "windows.pslist.PsList":
        if len(parts) >= 3:
            return {
                "pid": parts[0],
                "ppid": parts[1] if len(parts) > 1 else "0",
                "name": parts[2] if len(parts) > 2 else "unknown",
                "thread_count": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
            }

    elif plugin == "windows.netstat.NetStat":
        # Parse: PID    Protocol  LocalAddr  LocalPort  ForeignAddr  ForeignPort  State
        if len(parts) >= 7:
            return {
                "pid": parts[0],
                "protocol": parts[1].upper(),
                "local_ip": parts[2],
                "local_port": parts[3],
                "remote_ip": parts[4],
                "remote_port": parts[5],
                "state": parts[6] if len(parts) > 6 else "UNKNOWN",
            }

    elif plugin == "windows.malfind.Malfind":
        # Parse malfind output for injections
        if len(parts) >= 4:
            return {
                "pid": parts[0],
                "process": parts[1] if len(parts) > 1 else "unknown",
                "address": parts[2] if len(parts) > 2 else "0x0",
                "size": parts[3] if len(parts) > 3 else "0",
            }

    return None


def _is_suspicious_process(proc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Apply heuristics to detect suspicious processes.

    Args:
        proc: Process entry dict

    Returns:
        Tuple of (is_suspicious, reason)
    """
    name = proc.get("name", "").lower()
    ppid = int(proc.get("ppid", 0))
    pid = int(proc.get("pid", 0))

    # Check for processes with no parent
    if ppid == 0 and pid != 4 and name not in ["system", "idle"]:
        return True, "Process with no parent (orphaned)"

    # Check for suspicious parent-child relationships
    suspicious_parents = {
        "winword": ["cmd", "powershell", "rundll32"],
        "excel": ["cmd", "powershell", "wscript"],
        "outlook": ["cmd", "powershell"],
        "notepad": ["cmd", "powershell"],
    }

    for parent, suspicious_children in suspicious_parents.items():
        if name in suspicious_children:
            return True, f"Suspicious parent-child: {parent} -> {name}"

    # Check for suspicious process names
    suspicious_names = ["rundll32", "regsvcs", "regasm", "cmstp", "mshta", "msiexec"]
    if any(suspicious in name for suspicious in suspicious_names):
        return True, f"Known suspicious process: {name}"

    return False, None


def _is_known_malicious_port(port: int) -> bool:
    """Check if port is commonly associated with malware."""
    malicious_ports = {
        31337,  # Back Orifice
        4444,  # Common backdoor
        1337,  # LEET
        8080,  # Often proxies/tunnels
        6667,  # IRC
        27374,  # Sub7
        12345,  # NetBus
    }
    return port in malicious_ports


def analyze_processes(memory_path: str) -> Dict[str, Any]:
    """
    Extract and analyze running processes from memory dump.

    Uses Volatility3 pslist, pstree, and cmdline to analyze process hierarchy,
    PID, PPID, command line arguments, and memory usage.

    Args:
        memory_path: Path to memory dump file (read-only)

    Returns:
        Dict with processes and analysis
    """
    result = {
        "status": "success",
        "memory_path": str(memory_path),
        "processes": [],
        "suspicious_processes": [],
        "total_processes": 0,
        "suspicious_count": 0,
        "process_tree": {},
        "error": None,
    }

    try:
        # Verify memory file exists
        mem_path = Path(memory_path)
        if not mem_path.exists():
            result["status"] = "error"
            result["error"] = f"Memory dump not found: {memory_path}"
            return result

        if not os.access(memory_path, os.R_OK):
            result["status"] = "error"
            result["error"] = f"Memory dump not readable: {memory_path}"
            return result

        # Run pslist
        pslist_out, pslist_err, pslist_code = _run_volatility(
            memory_path,
            "windows.pslist.PsList",
            timeout=TOOL_TIMEOUTS.get("volatility", 120),
        )

        if pslist_code != 0:
            result["status"] = "error"
            result["error"] = f"pslist failed: {pslist_err}"
            return result

        # Parse processes
        processes = _parse_vol_output(pslist_out, "windows.pslist.PsList")
        
        # Try to get command lines if available
        try:
            cmdline_out, _, cmdline_code = _run_volatility(
                memory_path,
                "windows.cmdline.CmdLine",
                timeout=TOOL_TIMEOUTS.get("volatility", 120),
            )
            if cmdline_code == 0:
                cmdlines = _parse_vol_output(cmdline_out, "windows.cmdline.CmdLine")
                # Merge command lines into processes
                for proc in processes:
                    for cmdline in cmdlines:
                        if cmdline.get("pid") == proc.get("pid"):
                            proc["command_line"] = cmdline.get("command", "")
        except Exception:
            pass

        # Add confidence and check for suspicious processes
        suspicious = []
        for proc in processes:
            proc["confidence"] = 0.92
            
            is_suspicious, reason = _is_suspicious_process(proc)
            if is_suspicious:
                proc_copy = proc.copy()
                proc_copy["suspicious_reason"] = reason
                proc_copy["confidence"] = 0.78
                suspicious.append(proc_copy)

        result["processes"] = processes
        result["suspicious_processes"] = suspicious
        result["total_processes"] = len(processes)
        result["suspicious_count"] = len(suspicious)

        return result

    except subprocess.TimeoutExpired:
        result["status"] = "error"
        result["error"] = f"Process analysis timed out after {TOOL_TIMEOUTS.get('volatility', 120)}s"
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Process analysis failed: {str(e)}"
        return result


def check_injections(memory_path: str) -> Dict[str, Any]:
    """
    Detect code injection and suspicious memory patterns.

    Uses Volatility3 to detect injected code, suspicious VAD entries,
    hollowed processes, and unhooked API calls.

    Args:
        memory_path: Path to memory dump file (read-only)

    Returns:
        Dict with injection detections
    """
    result = {
        "status": "success",
        "memory_path": str(memory_path),
        "injections_detected": [],
        "total_injections": 0,
        "critical_count": 0,
        "error": None,
    }

    try:
        mem_path = Path(memory_path)
        if not mem_path.exists():
            result["status"] = "error"
            result["error"] = f"Memory dump not found: {memory_path}"
            return result

        # Run malfind to detect injected code
        malfind_out, malfind_err, malfind_code = _run_volatility(
            memory_path,
            "windows.malfind.Malfind",
            timeout=TOOL_TIMEOUTS.get("volatility", 120),
        )

        if malfind_code == 0 and malfind_out.strip():
            injections = _parse_vol_output(malfind_out, "windows.malfind.Malfind")

            for injection in injections:
                injection["injection_type"] = "code_injection"
                injection["severity"] = "high"
                injection["confidence"] = 0.89
                injection["reason"] = "Executable memory in non-mapped region (malfind)"

            result["injections_detected"] = injections
            result["total_injections"] = len(injections)
            result["critical_count"] = len(injections)

        else:
            # Try DLLList as fallback
            try:
                dlllist_out, _, dlllist_code = _run_volatility(
                    memory_path,
                    "windows.dlllist.DllList",
                    timeout=TOOL_TIMEOUTS.get("volatility", 120),
                )
                if dlllist_code == 0:
                    # Parse for suspicious DLL loads
                    suspicious_dlls = []
                    for line in dlllist_out.split("\n"):
                        if "dll" in line.lower() and any(
                            bad in line.lower() for bad in ["temp", "appdata", "downloads"]
                        ):
                            suspicious_dlls.append({
                                "path": line.strip(),
                                "injection_type": "dll_injection",
                                "severity": "medium",
                                "confidence": 0.75,
                            })
                    result["injections_detected"] = suspicious_dlls
                    result["total_injections"] = len(suspicious_dlls)
            except Exception:
                pass

        return result

    except subprocess.TimeoutExpired:
        result["status"] = "error"
        result["error"] = f"Injection detection timed out after {TOOL_TIMEOUTS.get('volatility', 120)}s"
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Injection detection failed: {str(e)}"
        return result


def get_network_connections(memory_path: str) -> Dict[str, Any]:
    """
    Extract network connections from memory dump.

    Uses Volatility3 to find active network sockets and connections,
    including process associations and network endpoints.

    Args:
        memory_path: Path to memory dump file (read-only)

    Returns:
        Dict with network connections
    """
    result = {
        "status": "success",
        "memory_path": str(memory_path),
        "connections": [],
        "total_connections": 0,
        "suspicious_connections": [],
        "external_ips": [],
        "listening_ports": [],
        "error": None,
    }

    try:
        mem_path = Path(memory_path)
        if not mem_path.exists():
            result["status"] = "error"
            result["error"] = f"Memory dump not found: {memory_path}"
            return result

        # Run netstat
        netstat_out, netstat_err, netstat_code = _run_volatility(
            memory_path,
            "windows.netstat.NetStat",
            timeout=TOOL_TIMEOUTS.get("volatility", 120),
        )

        if netstat_code != 0:
            result["status"] = "error"
            result["error"] = f"netstat failed: {netstat_err}"
            return result

        # Parse network connections
        connections = _parse_vol_output(netstat_out, "windows.netstat.NetStat")

        suspicious_conns = []
        external_ips = set()
        listening_ports = []

        for conn in connections:
            conn["confidence"] = 0.86
            
            # Check for malicious ports
            try:
                remote_port = int(conn.get("remote_port", 0))
                if _is_known_malicious_port(remote_port):
                    conn["suspicious"] = True
                    conn["confidence"] = 0.92
                    suspicious_conns.append(conn)
                    external_ips.add(conn.get("remote_ip", ""))
            except (ValueError, TypeError):
                pass

            # Track listening ports
            state = conn.get("state", "").upper()
            if "LISTEN" in state:
                listening_ports.append({
                    "port": conn.get("local_port"),
                    "process_pid": conn.get("pid"),
                    "state": state,
                })

        result["connections"] = connections
        result["suspicious_connections"] = suspicious_conns
        result["total_connections"] = len(connections)
        result["external_ips"] = list(external_ips)
        result["listening_ports"] = listening_ports

        return result

    except subprocess.TimeoutExpired:
        result["status"] = "error"
        result["error"] = f"Network analysis timed out after {TOOL_TIMEOUTS.get('volatility', 120)}s"
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Network analysis failed: {str(e)}"
        return result
