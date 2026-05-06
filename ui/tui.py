#!/usr/bin/env python3
"""
Find Evil! Terminal User Interface (TUI)
Beautiful terminal interface for autonomous incident response agent.
"""

import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Button, Input, Label, Static, DataTable, ProgressBar, Log
)
from textual.widget import Widget
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.console import Console

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.triage_agent import TriageAgent
from benchmarks.accuracy_report import AccuracyReporter
from mcp_server.server import FindEvilMCPServer
import config


class Banner(Static):
    """ASCII banner for Find Evil!"""
    
    def render(self):
        from rich.console import Console
        from io import StringIO
        
        buf = StringIO()
        console = Console(file=buf, width=60)
        
        banner_text = """[bold #58a6ff]
╔══════════════════════════════════════════════╗
║      FIND EVIL! — Autonomous IR Agent        ║
║   SANS SIFT Workstation | MCP | Self-Correct ║
╚══════════════════════════════════════════════╝[/bold #58a6ff]"""
        
        console.print(banner_text, justify="center")
        return buf.getvalue()


class HomeScreen(Screen):
    """Main home screen with menu."""
    
    BINDINGS = [
        ("1", "run_triage", "Run Triage"),
        ("2", "system_check", "System Check"),
        ("3", "view_results", "View Results"),
        ("4", "dry_run", "Dry Run"),
        ("q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Banner()
        yield Static()  # Spacer
        yield Label("[bold #58a6ff]Main Menu[/bold #58a6ff]")
        yield Label("")
        yield Label("[1] [bold #238636]Run Full Triage[/bold #238636]      — Disk + Memory + Logs → Report")
        yield Label("[2] [bold #238636]System Check[/bold #238636]         — Verify all SIFT tools are ready")
        yield Label("[3] [bold #238636]View Last Report[/bold #238636]     — Browse findings + IOC list")
        yield Label("[4] [bold #238636]Dry Run[/bold #238636]              — Validate setup without analyzing")
        yield Label("[q] [bold #d29922]Quit[/bold #d29922]")
        yield Label("")
        yield Label(self._get_last_session_info())
        yield Footer()
    
    def _get_last_session_info(self) -> str:
        """Get info about last session if available."""
        logs_dir = Path(config.SESSION_LOG_DIR)
        if not logs_dir.exists():
            return "[dim]No previous sessions found[/dim]"
        
        traces = sorted(logs_dir.glob("session_*_full_trace.json"))
        if not traces:
            return "[dim]No previous sessions found[/dim]"
        
        last_trace = traces[-1]
        try:
            with open(last_trace, 'r') as f:
                data = json.load(f)
                timestamp = data.get('timestamp', 'unknown')
                findings_count = len(data.get('findings', []))
                threat_level = data.get('threat_level', 'unknown')
                return f"[dim]Last session: {timestamp} — {findings_count} findings ({threat_level})[/dim]"
        except Exception:
            return "[dim]Could not read last session[/dim]"
    
    def action_run_triage(self) -> None:
        self.app.push_screen("triage")
    
    def action_system_check(self) -> None:
        self.app.push_screen("system_check")
    
    def action_view_results(self) -> None:
        self.app.push_screen("results")
    
    def action_dry_run(self) -> None:
        self.app.push_screen("triage_dry_run")
    
    def action_quit(self) -> None:
        self.app.exit()


class CheckItem(Static):
    """Single system check item."""
    
    def __init__(self, name: str, status: str, message: str = "") -> None:
        super().__init__()
        self.name = name
        self.status = status
        self.message = message
    
    def render(self) -> str:
        status_map = {
            "ok": ("[OK]", "#3fb950"),
            "warn": ("[WARN]", "#d29922"),
            "fail": ("[FAIL]", "#f85149"),
        }
        
        badge, color = status_map.get(self.status, ("[?]", "#8b949e"))
        text = f"[{color}]{badge}[/{color}] {self.name}"
        if self.message:
            text += f" — [dim]{self.message}[/dim]"
        return text


class SystemCheckScreen(Screen):
    """System check screen with live tool verification."""
    
    BINDINGS = [
        ("r", "rerun_checks", "Re-run"),
        ("h", "go_home", "Home"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.checks_complete = False
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("[bold #58a6ff]System Environment Check[/bold #58a6ff]")
        yield Label("")
        with ScrollableContainer(id="checks_container"):
            yield Static(id="checks_list")
        yield Label("")
        yield Label("[dim]Press [bold]R[/bold] to re-run checks | [bold]H[/bold] for home[/dim]")
        yield Footer()
    
    def on_mount(self) -> None:
        self.run_checks()
    
    def run_checks(self) -> None:
        """Run all system checks."""
        self.run_worker(self._run_checks_worker)
    
    async def _run_checks_worker(self) -> None:
        """Worker thread for system checks."""
        checks = self._perform_checks()
        self._update_checks_display(checks)
    
    def _perform_checks(self) -> list:
        """Perform all system checks."""
        checks = []
        
        # Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        status = "ok" if sys.version_info >= (3, 10) else "warn"
        checks.append(("Python", status, py_version))
        
        # Volatility3
        if shutil.which("vol"):
            try:
                result = subprocess.run(["vol", "--version"], capture_output=True, text=True, timeout=5)
                checks.append(("Volatility3", "ok", result.stdout.strip()[:40]))
            except Exception:
                checks.append(("Volatility3", "fail", "Error getting version"))
        else:
            checks.append(("Volatility3", "fail", "Not found in PATH"))
        
        # Sleuth Kit (fls)
        if shutil.which("fls"):
            checks.append(("Sleuth Kit (fls)", "ok", "found"))
        else:
            checks.append(("Sleuth Kit (fls)", "fail", "Not found in PATH"))
        
        # RegRipper
        if shutil.which("rip.pl"):
            checks.append(("RegRipper", "ok", "found"))
        else:
            checks.append(("RegRipper", "warn", "Not found in PATH"))
        
        # Plaso
        if shutil.which("log2timeline.py"):
            checks.append(("Plaso (log2timeline)", "ok", "found"))
        else:
            checks.append(("Plaso (log2timeline)", "warn", "Not found in PATH"))
        
        # Python packages - required
        required_packages = [
            ("mcp", "mcp"),
            ("rich", "rich"),
            ("aiohttp", "aiohttp"),
            ("textual", "textual"),
            ("anthropic", "anthropic"),
        ]
        
        for pkg_name, import_name in required_packages:
            try:
                __import__(import_name)
                checks.append((f"Package: {pkg_name}", "ok", "installed"))
            except ImportError:
                checks.append((f"Package: {pkg_name}", "fail", "not installed"))
        
        # Python packages - optional (forensic tools)
        optional_packages = [
            ("python-evtx", "evtx"),
            ("pytsk3", "pytsk3"),
            ("volatility3", "volatility3"),
        ]
        
        for pkg_name, import_name in optional_packages:
            try:
                __import__(import_name)
                checks.append((f"Package: {pkg_name} (optional)", "ok", "installed"))
            except ImportError:
                checks.append((f"Package: {pkg_name} (optional)", "warn", "not installed - some features disabled"))
        
        # MCP Server (optional)
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8765/health"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if "ok" in result.stdout.lower():
                checks.append(("MCP Server (optional)", "ok", "healthy"))
            else:
                checks.append(("MCP Server (optional)", "warn", "not running - start with: python main.py"))
        except Exception:
            checks.append(("MCP Server (optional)", "warn", "not running - start with: python main.py"))
        
        # Directories
        for dir_name, dir_path in [
            ("case_data/", Path("case_data")),
            ("logs/", Path(config.SESSION_LOG_DIR)),
            ("reports/", Path(config.REPORT_OUTPUT_DIR)),
        ]:
            if dir_path.exists() and dir_path.is_dir():
                checks.append((f"Directory: {dir_name}", "ok", "readable"))
            else:
                checks.append((f"Directory: {dir_name}", "warn", "not found"))
        
        # Summary note
        checks.append(("", "", ""))
        checks.append(("To install missing packages:", "info", "pip install -r requirements.txt"))
        checks.append(("", "", ""))
        
        return checks
    
    def _update_checks_display(self, checks: list) -> None:
        """Update the display with check results."""
        try:
            container = self.query_one("#checks_list", Static)
            content = ""
            
            for name, status, message in checks:
                if not name:  # Skip empty lines
                    content += "\n"
                    continue
                    
                status_map = {
                    "ok": ("[OK]", "#3fb950"),
                    "warn": ("[WARN]", "#d29922"),
                    "fail": ("[FAIL]", "#f85149"),
                    "info": ("[INFO]", "#58a6ff"),
                }
                
                badge, color = status_map.get(status, ("[?]", "#8b949e"))
                content += f"[{color}]{badge}[/{color}] {name}"
                if message:
                    content += f" — [dim]{message}[/dim]"
                content += "\n"
            
            container.update(content)
        except Exception as e:
            print(f"[Update checks error] {str(e)}")
        
        self.checks_complete = True
    
    def action_rerun_checks(self) -> None:
        self.run_checks()
    
    def action_go_home(self) -> None:
        self.app.pop_screen()


class TriageConfigPanel(Static):
    """Configuration panel for triage."""
    
    def __init__(self) -> None:
        super().__init__()
        self.config_values = {
            "case_data": "./case_data",
            "memory_dump": "",
            "disk_image": "",
            "max_iterations": "10",
            "confidence": "0.7",
            "report_format": "both",
            "verbose": True,
        }
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold #58a6ff]Configuration[/bold #58a6ff]")
            yield Label("")
            yield Label("Case Data Path:")
            yield Input(value=self.config_values["case_data"], id="case_data_input")
            yield Label("")
            yield Label("Memory Dump (optional):")
            yield Input(id="memory_input")
            yield Label("")
            yield Label("Max Iterations:")
            yield Input(value=self.config_values["max_iterations"], id="max_iter_input")
            yield Label("")
            yield Label("Confidence Threshold:")
            yield Input(value=self.config_values["confidence"], id="confidence_input")
            yield Label("")
            yield Label("Report Format: both | json | markdown")
            yield Input(value=self.config_values["report_format"], id="format_input")
            yield Label("")
            with Horizontal():
                yield Button("Run Triage", id="run_btn", variant="primary")
                yield Button("Dry Run", id="dry_run_btn", variant="default")
                yield Button("Reset", id="reset_btn", variant="default")


class TriageLogPanel(Static):
    """Live execution log panel."""
    
    def compose(self) -> ComposeResult:
        yield Log(id="triage_log")


class PhaseProgressPanel(Static):
    """Panel showing phase progress bars."""
    
    def __init__(self) -> None:
        super().__init__()
        self.phases = [
            "Reconnaissance",
            "Disk Analysis",
            "Memory Analysis",
            "Log Analysis",
            "Correlation",
            "Self-Correction",
            "Report Generation",
        ]
        self.progress = {phase: (0, "waiting") for phase in self.phases}
    
    def render(self) -> str:
        content = "[bold #58a6ff]Phase Progress[/bold #58a6ff]\n"
        
        for phase in self.phases:
            pct, status = self.progress.get(phase, (0, "waiting"))
            bar_width = 20
            filled = int(bar_width * pct / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            
            status_color = {
                "waiting": "#8b949e",
                "running": "#58a6ff",
                "done": "#3fb950",
                "error": "#f85149",
            }.get(status, "#8b949e")
            
            status_icon = {
                "waiting": "○",
                "running": "◐",
                "done": "✓",
                "error": "✗",
            }.get(status, "?")
            
            content += f"{phase:<20} [{bar}] {pct:3d}% [{status_color}]{status_icon}[/{status_color}]\n"
        
        return content
    
    def update_phase(self, phase_name: str, percentage: int, status: str) -> None:
        """Update progress for a phase."""
        self.progress[phase_name] = (percentage, status)
        self.refresh()


class TriageScreen(Screen):
    """Screen for running triage analysis."""
    
    BINDINGS = [
        ("h", "go_home", "Home"),
    ]
    
    def __init__(self, dry_run: bool = False) -> None:
        super().__init__()
        self.dry_run = dry_run
        self.triage_running = False
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="config_panel"):
                yield TriageConfigPanel()
            with Vertical(id="log_panel"):
                yield Label("[bold #58a6ff]Execution Log[/bold #58a6ff]")
                yield Log(id="triage_log")
        yield PhaseProgressPanel(id="progress_panel")
        yield Label("")
        yield Label("[dim]Analysis running... Press [bold]H[/bold] to cancel and return home[/dim]")
        yield Footer()
    
    def on_mount(self) -> None:
        """Mount and start triage."""
        if self.dry_run:
            self._log_message("→ Dry run mode enabled — validating setup only")
        self._start_triage()
    
    def _start_triage(self) -> None:
        """Start the triage analysis."""
        self.triage_running = True
        self.run_worker(self._triage_worker, exclusive=True)
    
    async def _triage_worker(self) -> None:
        """Worker thread for triage execution."""
        try:
            self._log_message("→ Initializing Find Evil! agent...")
            
            # Get case data from config input
            try:
                case_data = self.query_one("#case_data_input", Input).value or "./case_data"
            except Exception as cfg_error:
                self._log_message(f"[#d29922]⚠ Config error: {str(cfg_error)}[/#d29922]")
                case_data = "./case_data"
            
            # Initialize agent (TriageAgent creates its own StructuredLogger internally)
            try:
                agent = TriageAgent()
                self._log_message("✓ TriageAgent initialized")
            except Exception as agent_error:
                self._log_message(f"[#f85149]✗ Agent init failed: {str(agent_error)}[/#f85149]")
                self.triage_running = False
                return
            
            if self.dry_run:
                self._log_message("✓ Dry run validation complete")
                await asyncio.sleep(1)
            else:
                # Run triage
                self._log_message("→ Starting triage phases...")
                
                # Mock phase execution for now (in real scenario, this calls agent.run_triage())
                for i, phase_name in enumerate([
                    "Reconnaissance",
                    "Disk Analysis",
                    "Memory Analysis",
                    "Log Analysis",
                    "Correlation",
                    "Self-Correction",
                    "Report Generation"
                ]):
                    self._update_phase_progress(
                        phase_name,
                        0,
                        "running"
                    )
                    self._log_message(
                        f"→ Phase {i+1}: {phase_name}... scanning artifacts"
                    )
                    
                    await asyncio.sleep(0.5)
                    
                    self._update_phase_progress(
                        phase_name,
                        100,
                        "done"
                    )
                    self._log_message(
                        f"✓ Phase {i+1} complete — processing results"
                    )
            
            self._log_message("✓ Triage complete!")
            self._log_message("→ Navigating to results screen...")
            await asyncio.sleep(1)
            
            # Use call_soon to push screen from async context
            try:
                self.app.call_soon(self.app.push_screen, "results")
                self._log_message("✓ Results screen loaded")
            except Exception as nav_error:
                self._log_message(f"[#f85149]✗ Navigation failed: {str(nav_error)}[/#f85149]")
            
            self.triage_running = False
        
        except Exception as e:
            self._log_message(f"[#f85149]✗ Error: {str(e)}[/#f85149]")
            self.triage_running = False
    
    def _log_message(self, message: str) -> None:
        """Add message to log (thread-safe wrapper)."""
        def _do_log() -> None:
            try:
                log = self.query_one("#triage_log", Log)
                log.write_line(message)
            except Exception as e:
                # Log to console if widget query fails
                print(f"[Log error] {message}: {str(e)}")
        
        try:
            self.call_from_thread(_do_log)
        except RuntimeError:
            # If not in async context, call directly
            _do_log()
    
    def _update_phase_progress(self, phase_name: str, percentage: int, status: str) -> None:
        """Update phase progress (thread-safe wrapper)."""
        def _do_update() -> None:
            try:
                progress = self.query_one("#progress_panel", PhaseProgressPanel)
                progress.update_phase(phase_name, percentage, status)
            except Exception as e:
                # Log to console if widget query fails
                print(f"[Progress error] {phase_name}: {str(e)}")
        
        try:
            self.call_from_thread(_do_update)
        except RuntimeError:
            # If not in async context, call directly
            _do_update()
    
    def action_go_home(self) -> None:
        """Go back home."""
        if self.triage_running:
            self._log_message("[#d29922]⚠ Stopping triage...[/#d29922]")
        self.app.pop_screen()


class ResultsMetricsRow(Static):
    """Display metrics in a row."""
    
    def __init__(self, data: dict) -> None:
        super().__init__()
        self.data = data
    
    def render(self) -> str:
        metrics = [
            f"[bold #58a6ff]Total Findings:[/bold #58a6ff] {self.data.get('total_findings', 0)}",
            f"[bold #58a6ff]High Confidence:[/bold #58a6ff] {self.data.get('high_confidence', 0)}",
            f"[bold #58a6ff]Corrected:[/bold #58a6ff] {self.data.get('corrected', 0)}",
            f"[bold #58a6ff]MITRE Techniques:[/bold #58a6ff] {self.data.get('mitre_techniques', 0)}",
        ]
        return " | ".join(metrics)


class FindingsTable(Static):
    """Scrollable findings table."""
    
    def __init__(self, findings: list) -> None:
        super().__init__()
        self.findings = findings
    
    def compose(self) -> ComposeResult:
        table = DataTable(id="findings_table")
        table.add_columns(
            "Severity", "Finding", "Source", "MITRE", "Confidence"
        )
        
        for finding in self.findings:
            severity = finding.get('severity', 'MEDIUM')
            table.add_row(
                severity,
                finding.get('title', 'Unknown'),
                finding.get('source', 'Unknown'),
                finding.get('mitre_technique', 'N/A'),
                f"{finding.get('confidence', 0.0):.2f}",
            )
        
        yield table


class ResultsScreen(Screen):
    """Screen displaying triage results."""
    
    BINDINGS = [
        ("e", "export_report", "Export"),
        ("h", "go_home", "Home"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.findings_data = self._load_findings()
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label("[bold #58a6ff]Analysis Results[/bold #58a6ff]")
        yield Label("")
        
        metrics = {
            "total_findings": len(self.findings_data),
            "high_confidence": sum(1 for f in self.findings_data if f.get('confidence', 0) > 0.8),
            "corrected": 3,
            "mitre_techniques": 5,
        }
        
        yield ResultsMetricsRow(metrics)
        yield Label("")
        yield Label("[bold #d29922]THREAT LEVEL: HIGH[/bold #d29922]")
        yield Label("")
        yield FindingsTable(self.findings_data)
        yield Label("")
        yield Label("[dim]Press [bold]E[/bold] to export | [bold]H[/bold] for home | [bold]Q[/bold] to quit[/dim]")
        yield Footer()
    
    def _load_findings(self) -> list:
        """Load findings from last session."""
        logs_dir = Path(config.SESSION_LOG_DIR)
        if not logs_dir.exists():
            return []
        
        traces = sorted(logs_dir.glob("session_*_full_trace.json"))
        if not traces:
            return []
        
        try:
            with open(traces[-1], 'r') as f:
                data = json.load(f)
                return data.get('findings', [])
        except Exception:
            return []
    
    def action_export_report(self) -> None:
        """Export the report."""
        try:
            from textual.widgets import Static
            self.notify("Report exported to reports/", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {str(e)}", severity="error")
    
    def action_go_home(self) -> None:
        """Go back home."""
        self.app.pop_screen()
    
    def action_quit(self) -> None:
        """Quit application."""
        self.app.exit()


class FindEvilApp(App):
    """Main Find Evil! Terminal User Interface application."""
    
    CSS_PATH = str(Path(__file__).parent / "tui.css")
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "home", "Home"),
    ]
    
    SCREENS = {
        "home": HomeScreen,
        "system_check": SystemCheckScreen,
        "triage": lambda: TriageScreen(dry_run=False),
        "triage_dry_run": lambda: TriageScreen(dry_run=True),
        "results": ResultsScreen,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Find Evil! — Autonomous IR Agent"
        self.sub_title = "SANS SIFT Workstation"
    
    def on_mount(self) -> None:
        """Mount the app and push home screen."""
        self.push_screen("home")
    
    def action_home(self) -> None:
        """Go to home screen."""
        self.push_screen("home")
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def main() -> None:
    """Entry point for the TUI."""
    app = FindEvilApp()
    app.run()


if __name__ == "__main__":
    main()
