"""
Structured execution logger for Find Evil! agent.

Logs every tool call, agent iteration, and correction attempt with:
- Timestamp (UTC ISO 8601)
- Tool name and parameters
- Output summary
- Confidence score
- Token estimates

All logs automatically saved as JSON for parsing and analysis.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class StructuredLogger:
    """Structured logger with JSON output and optional rich console formatting."""

    def __init__(self, session_id: str, log_dir: str = "./logs", verbose: bool = False):
        """
        Initialize the structured logger.

        Args:
            session_id: Unique ID for this triage run (typically uuid4)
            log_dir: Directory where to save JSON logs
            verbose: If True, also print to console with rich formatting
        """
        self.session_id = session_id
        self.log_dir = Path(log_dir)
        self.verbose = verbose
        self.console = Console() if RICH_AVAILABLE and verbose else None

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logs
        self.session_start_time = datetime.now(timezone.utc)
        self.event_log: List[Dict[str, Any]] = []
        self.tool_call_log: List[Dict[str, Any]] = []
        self.correction_log: List[Dict[str, Any]] = []
        self.phase_log: List[Dict[str, Any]] = []

        # Create session log file
        self.session_file = self.log_dir / f"session_{session_id}.json"
        self._save_session_file()

        # Log session start
        self.log_event("session_start", f"Triage session {session_id} started", {})

    def log_tool_call(
        self,
        tool_name: str,
        params: dict,
        output: dict,
        confidence: float,
        duration_ms: int,
        token_estimate: int = 0,
    ) -> None:
        """
        Log a tool call with full metadata.

        Args:
            tool_name: Name of the tool (get_mft, analyze_processes, etc.)
            params: Input parameters (sanitized)
            output: Tool output dict
            confidence: Confidence score (0.0-1.0)
            duration_ms: Execution time in milliseconds
            token_estimate: Estimated tokens consumed
        """
        # Sanitize params (don't log huge file contents)
        sanitized_params = {}
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 500:
                sanitized_params[key] = "[CONTENT_TRUNCATED]"
            else:
                sanitized_params[key] = value

        # Extract finding count from output
        finding_count = 0
        if isinstance(output, dict):
            if "findings" in output and isinstance(output["findings"], list):
                finding_count = len(output["findings"])
            elif "entries" in output and isinstance(output["entries"], list):
                finding_count = len(output["entries"])
            elif "events" in output and isinstance(output["events"], list):
                finding_count = len(output["events"])

        # Get output summary (first 200 chars)
        output_summary = str(output)[:200] if output else ""

        # Build log entry
        entry = {
            "event_type": "tool_call",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "tool_name": tool_name,
            "params": sanitized_params,
            "output_summary": output_summary,
            "finding_count": finding_count,
            "confidence": confidence,
            "duration_ms": duration_ms,
            "token_estimate": token_estimate,
            "success": output.get("status") == "success" if isinstance(output, dict) else False,
        }

        self.tool_call_log.append(entry)
        self._save_session_file()

        # Console output if verbose
        if self.verbose and self.console:
            status = "✓" if entry["success"] else "✗"
            msg = f"{status} {tool_name} | {finding_count} findings | {confidence:.2f} conf | {duration_ms}ms"
            self.console.print(msg, style="green" if entry["success"] else "red")

    def log_phase(
        self,
        phase_name: str,
        status: str,
        confidence: float,
        findings_count: int,
        duration_ms: int,
        summary: str,
    ) -> None:
        """
        Log a complete phase execution.

        Args:
            phase_name: Phase name (RECONNAISSANCE, DISK_ANALYSIS, etc.)
            status: "success" or "error"
            confidence: Phase confidence (0.0-1.0)
            findings_count: Number of findings in this phase
            duration_ms: Execution time in milliseconds
            summary: Brief summary text
        """
        entry = {
            "event_type": "phase",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "phase_name": phase_name,
            "status": status,
            "confidence": confidence,
            "findings_count": findings_count,
            "duration_ms": duration_ms,
            "summary": summary,
        }

        self.phase_log.append(entry)
        self._save_session_file()

        # Console output if verbose
        if self.verbose and self.console:
            panel = Panel(
                f"[bold]{phase_name}[/bold]\n"
                f"Status: {status} | Confidence: {confidence:.2%} | Findings: {findings_count} | {duration_ms}ms\n"
                f"{summary}",
                style="blue" if status == "success" else "red",
            )
            self.console.print(panel)

    def log_correction(
        self,
        finding_id: str,
        original_confidence: float,
        corrected_confidence: float,
        hallucination_type: str,
        strategy_used: str,
        accepted: bool,
    ) -> None:
        """
        Log a correction attempt.

        Args:
            finding_id: UUID of the finding
            original_confidence: Confidence before correction
            corrected_confidence: Confidence after correction
            hallucination_type: Type of hallucination detected
            strategy_used: Correction strategy applied
            accepted: Whether the correction was accepted
        """
        improvement = corrected_confidence - original_confidence

        entry = {
            "event_type": "correction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "finding_id": finding_id,
            "original_confidence": original_confidence,
            "corrected_confidence": corrected_confidence,
            "improvement": improvement,
            "hallucination_type": hallucination_type,
            "strategy_used": strategy_used,
            "accepted": accepted,
        }

        self.correction_log.append(entry)
        self._save_session_file()

        # Console output if verbose
        if self.verbose and self.console:
            arrow = "↑" if improvement > 0 else "↓"
            msg = (
                f"{arrow} {hallucination_type} | "
                f"{original_confidence:.2f} → {corrected_confidence:.2f} | "
                f"Strategy: {strategy_used}"
            )
            style = "yellow" if improvement >= 0 else "red"
            self.console.print(msg, style=style)

    def log_event(self, event_type: str, message: str, metadata: Dict[str, Any] = None) -> None:
        """
        Log a general event.

        Args:
            event_type: Type of event
            message: Event message
            metadata: Additional metadata dict
        """
        entry = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "message": message,
            "metadata": metadata or {},
        }

        self.event_log.append(entry)
        self._save_session_file()

        # Console output if verbose
        if self.verbose and self.console:
            self.console.print(f"[cyan]{event_type}:[/cyan] {message}")

    def save_full_trace(self, report: Dict[str, Any]) -> None:
        """
        Save complete session trace as JSON and markdown.

        Args:
            report: Final triage report dict
        """
        # Full trace JSON
        trace = {
            "session_metadata": {
                "session_id": self.session_id,
                "start_time": self.session_start_time.isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_ms": int(
                    (datetime.now(timezone.utc) - self.session_start_time).total_seconds() * 1000
                ),
            },
            "phase_log": self.phase_log,
            "tool_call_log": self.tool_call_log,
            "correction_log": self.correction_log,
            "event_log": self.event_log,
            "final_report": report,
        }

        # Save JSON trace
        trace_file = self.log_dir / f"session_{self.session_id}_full_trace.json"
        with open(trace_file, "w") as f:
            json.dump(trace, f, indent=2)

        # Save markdown summary
        md_file = self.log_dir / f"session_{self.session_id}_summary.md"
        with open(md_file, "w") as f:
            f.write(self._generate_markdown_summary(trace))

        if self.verbose and self.console:
            self.console.print(f"\n✓ Full trace saved to {trace_file}")
            self.console.print(f"✓ Summary saved to {md_file}")

    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics for the session.

        Returns:
            Dict with execution stats
        """
        total_duration = datetime.now(timezone.utc) - self.session_start_time
        total_duration_ms = int(total_duration.total_seconds() * 1000)

        total_tool_calls = len(self.tool_call_log)
        successful_tool_calls = sum(1 for c in self.tool_call_log if c.get("success", False))
        failed_tool_calls = total_tool_calls - successful_tool_calls

        total_corrections = len(self.correction_log)
        successful_corrections = sum(1 for c in self.correction_log if c.get("accepted", False))

        # Calculate average confidence
        confidences = [c.get("confidence", 1.0) for c in self.tool_call_log]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Token estimate
        token_estimate_total = sum(c.get("token_estimate", 0) for c in self.tool_call_log)

        return {
            "total_duration_ms": total_duration_ms,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "total_corrections": total_corrections,
            "successful_corrections": successful_corrections,
            "average_confidence": average_confidence,
            "phases_completed": len(self.phase_log),
            "token_estimate_total": token_estimate_total,
        }

    def _save_session_file(self) -> None:
        """Save current session state to JSON file."""
        session_data = {
            "session_id": self.session_id,
            "start_time": self.session_start_time.isoformat(),
            "event_log": self.event_log,
            "tool_call_log": self.tool_call_log,
            "correction_log": self.correction_log,
            "phase_log": self.phase_log,
        }

        with open(self.session_file, "w") as f:
            json.dump(session_data, f, indent=2)

    def _generate_markdown_summary(self, trace: Dict[str, Any]) -> str:
        """Generate markdown summary of execution trace."""
        lines = [
            "# Find Evil! Execution Trace Summary",
            "",
            f"**Session ID**: `{self.session_id}`",
            f"**Start Time**: {trace['session_metadata']['start_time']}",
            f"**End Time**: {trace['session_metadata']['end_time']}",
            f"**Duration**: {trace['session_metadata']['duration_ms']}ms",
            "",
            "## Phases Executed",
            "",
        ]

        for phase in trace["phase_log"]:
            lines.append(
                f"- **{phase['phase_name']}** ({phase['status']}) - "
                f"{phase['findings_count']} findings, {phase['duration_ms']}ms"
            )

        lines.extend(
            [
                "",
                "## Tool Calls",
                "",
                "| Tool | Duration (ms) | Findings | Confidence | Success |",
                "|------|---------------|----------|------------|---------|",
            ]
        )

        for call in trace["tool_call_log"]:
            lines.append(
                f"| {call['tool_name']} | {call['duration_ms']} | "
                f"{call['finding_count']} | {call['confidence']:.2f} | "
                f"{'✓' if call['success'] else '✗'} |"
            )

        lines.extend(
            [
                "",
                "## Corrections Applied",
                "",
                "| Finding ID | Original Conf | Corrected Conf | Type | Strategy | Accepted |",
                "|-----------|---------------|----------------|------|----------|----------|",
            ]
        )

        for corr in trace["correction_log"]:
            lines.append(
                f"| {corr['finding_id'][:8]}... | {corr['original_confidence']:.2f} | "
                f"{corr['corrected_confidence']:.2f} | {corr['hallucination_type']} | "
                f"{corr['strategy_used']} | {'✓' if corr['accepted'] else '✗'} |"
            )

        return "\n".join(lines)

    def log_finding(self, phase: str, finding_type: str, data: Dict[str, Any]) -> None:
        """
        Log a finding with metadata.
        
        Args:
            phase: Current phase name (RECONNAISSANCE, DISK_ANALYSIS, etc.)
            finding_type: Type of finding (low_confidence, suspicious_process, etc.)
            data: Finding data dict
        """
        finding_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": phase,
            "finding_type": finding_type,
            "data": data,
        }
        self.event_log.append(finding_entry)

    def log_error(self, error_type: str, message: str, phase: Optional[str] = None) -> None:
        """
        Log an error or exception.
        
        Args:
            error_type: Type of error (e.g., "tool_execution", "parsing", "network")
            message: Error message
            phase: Optional phase where error occurred
        """
        error_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "message": message,
            "phase": phase,
        }
        self.event_log.append(error_entry)
        
        if self.console and RICH_AVAILABLE:
            self.console.print(f"[red]ERROR ({error_type})[/red]: {message}")
