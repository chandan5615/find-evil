#!/usr/bin/env python3
"""
Find Evil! — Autonomous Incident Response Agent
SANS SIFT Workstation | Find Evil! Hackathon 2026

Master orchestration entry point that coordinates:
- MCP server startup
- TriageAgent orchestration
- Self-correction engine
- Accuracy reporting
- Log aggregation
"""

import asyncio
import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

from mcp_server.server import FindEvilMCPServer
from agent.triage_agent import TriageAgent
from agent.logger import StructuredLogger
from benchmarks.accuracy_report import AccuracyReporter
import config


def print_banner():
    """Print ASCII banner."""
    if RICH_AVAILABLE and Console:
        console = Console()
        console.print(Panel(
            "[bold cyan]FIND EVIL! — Autonomous IR[/bold cyan]\n"
            "[cyan]SANS SIFT Workstation Agent v1.0[/cyan]\n"
            "[cyan]Self-Correcting | MCP | MITRE ATT&CK[/cyan]",
            style="blue"
        ))
    else:
        print("╔═══════════════════════════════════════════╗")
        print("║         FIND EVIL! — Autonomous IR        ║")
        print("║      SANS SIFT Workstation Agent v1.0     ║")
        print("║   Self-Correcting | MCP | MITRE ATT&CK   ║")
        print("╚═══════════════════════════════════════════╝")


def validate_environment() -> tuple[bool, list[str]]:
    """
    Validate that all dependencies and tools are available.

    Returns:
        (all_ok, missing_list)
    """
    missing = []
    console = Console() if RICH_AVAILABLE else None

    checks = [
        ("Python 3.10+", lambda: sys.version_info >= (3, 10)),
        ("Sleuth Kit (fls)", lambda: shutil.which("fls") is not None),
        ("Sleuth Kit (mmls)", lambda: shutil.which("mmls") is not None),
        ("Volatility3", lambda: Path("/opt/volatility3-2.20.0/vol.py").exists()),
        ("RegRipper", lambda: shutil.which("rip.pl") is not None),
        ("Plaso", lambda: shutil.which("log2timeline.py") is not None),
        ("Package: mcp", lambda: _check_package("mcp")),
        ("Package: anthropic", lambda: _check_package("anthropic")),
        ("Package: rich", lambda: _check_package("rich")),
        ("Package: volatility3", lambda: _check_package("volatility3")),
        ("Package: evtx", lambda: _check_package("evtx")),
    ]

    for check_name, check_func in checks:
        try:
            result = check_func()
            status = "✓" if result else "✗"
            if not result:
                missing.append(check_name)
            if console:
                console.print(f"{status} {check_name}", style="green" if result else "red")
            else:
                print(f"{status} {check_name}")
        except Exception as e:
            if console:
                console.print(f"✗ {check_name}: {e}", style="red")
            else:
                print(f"✗ {check_name}: {e}")
            missing.append(check_name)

    return len(missing) == 0, missing


def _check_package(package_name: str) -> bool:
    """Check if a Python package is installed."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Find Evil! - Autonomous Incident Response Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run triage on case data
  python main.py --case-data ./case_data --verbose

  # With memory dump
  python main.py --case-data ./case_data --memory ./case_data/memory.dmp

  # With ground truth and custom output
  python main.py --case-data ./case_data --ground-truth ground_truth.json --output ./reports

  # Dry-run to validate setup
  python main.py --dry-run

  # With confidence threshold
  python main.py --case-data ./case_data --confidence 0.8
        """,
    )

    parser.add_argument(
        "--case-data",
        type=str,
        required=False,
        help="Path to case data directory (required unless using --dry-run)",
    )

    parser.add_argument(
        "--image",
        type=str,
        help="Path to disk image file (optional)",
    )

    parser.add_argument(
        "--memory",
        type=str,
        help="Path to memory dump file (optional)",
    )

    parser.add_argument(
        "--logs-dir",
        type=str,
        help="Path to logs directory (optional)",
    )

    parser.add_argument(
        "--ground-truth",
        type=str,
        help="Path to ground truth JSON for accuracy scoring (optional)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./reports",
        help="Output directory for reports (default: ./reports)",
    )

    parser.add_argument(
        "--max-iter",
        type=int,
        default=10,
        help="Max self-correction iterations (default: 10)",
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.7,
        help="Minimum confidence threshold (default: 0.7)",
    )

    parser.add_argument(
        "--report-format",
        choices=["json", "markdown", "both"],
        default="both",
        help="Report format (default: both)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed console output",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate setup without running analysis",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Find Evil! v1.0.0",
    )

    return parser.parse_args()


async def run_dry_run(args: argparse.Namespace) -> bool:
    """
    Run environment validation without full analysis.

    Args:
        args: Parsed arguments

    Returns:
        True if all checks pass
    """
    console = Console() if RICH_AVAILABLE else None

    if console:
        console.print("\n[blue]Running dry-run validation...[/blue]")

    # Validate environment
    env_ok, missing = validate_environment()
    if not env_ok:
        if console:
            console.print(f"[red]✗ Missing dependencies: {', '.join(missing)}[/red]")
        else:
            print(f"✗ Missing dependencies: {', '.join(missing)}")
        return False

    # Check case data directory
    case_path = Path(args.case_data)
    if not case_path.exists():
        if console:
            console.print(f"[red]✗ Case data directory not found: {case_path}[/red]")
        else:
            print(f"✗ Case data directory not found: {case_path}")
        return False

    if console:
        console.print(f"[green]✓ Case data directory found: {case_path}[/green]")

    # Check output directory
    out_path = Path(args.output)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
        if console:
            console.print(f"[green]✓ Output directory ready: {out_path}[/green]")
    except Exception as e:
        if console:
            console.print(f"[red]✗ Cannot create output directory: {e}[/red]")
        else:
            print(f"✗ Cannot create output directory: {e}")
        return False

    if console:
        console.print("\n[green]✓ All validation checks passed![/green]")

    return True


async def main():
    """Main orchestration function."""
    start_time = time.time()

    try:
        # Print banner
        print_banner()

        # Parse arguments
        args = parse_arguments()

        # Validate arguments
        if not args.dry_run and not args.case_data:
            print("\n[!] Error: --case-data is required unless using --dry-run")
            sys.exit(1)

        # Validate environment
        print("\n[*] Validating environment...")
        env_ok, missing = validate_environment()
        if not env_ok:
            print(f"\n[!] Missing dependencies: {', '.join(missing)}")
            sys.exit(1)

        # Handle dry-run
        if args.dry_run:
            success = await run_dry_run(args)
            sys.exit(0 if success else 1)

        # Create session and logger
        session_id = str(uuid4())[:8]
        logger = StructuredLogger(session_id, verbose=args.verbose)
        logger.log_event("startup", f"Find Evil! starting with session {session_id}", {
            "case_data": args.case_data,
            "memory_path": args.memory,
            "max_iterations": args.max_iter,
            "confidence_threshold": args.confidence,
        })

        console = Console() if RICH_AVAILABLE else None

        # Create output directory
        Path(args.output).mkdir(parents=True, exist_ok=True)

        print("\n[*] Starting MCP server...")
        server = FindEvilMCPServer()
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(1)  # Let server initialize

        # Initialize agent
        print("[*] Initializing triage agent...")
        agent = TriageAgent(
            mcp_server_url=f"http://localhost:{config.MCP_SERVER_PORT}",
            config={
                "max_iterations": args.max_iter,
                "confidence_threshold": args.confidence,
                "verbose": args.verbose,
            },
        )

        # Run triage
        print(f"\n[*] Starting triage on {args.case_data}...\n")

        if console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running triage phases...", total=None)
                report = await agent.run_triage(
                    case_data_path=args.case_data,
                    memory_path=args.memory,
                )
                progress.update(task, completed=True)
        else:
            report = await agent.run_triage(
                case_data_path=args.case_data,
                memory_path=args.memory,
            )

        # Score findings
        print("\n[*] Scoring findings...")
        reporter = AccuracyReporter(ground_truth_path=args.ground_truth)
        scoring = reporter.score_findings(
            report.get("findings", []),
        )

        # Get execution stats
        session_stats = logger.get_execution_stats()

        # Generate reports
        print("[*] Generating reports...")
        if args.report_format in ["markdown", "both"]:
            markdown = reporter.generate_markdown_report(scoring, report, session_stats)
            reporter.save_report(markdown, report, args.output)

        if args.report_format in ["json", "both"]:
            json_file = Path(args.output) / f"accuracy_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_file, "w") as f:
                json.dump({
                    "scoring": scoring,
                    "report": report,
                    "session_stats": session_stats,
                }, f, indent=2)
            print(f"✓ JSON report saved: {json_file}")

        # Save full trace
        logger.save_full_trace(report)

        # Print summary
        elapsed = time.time() - start_time
        print("\n" + "="*80)
        print("TRIAGE SUMMARY")
        print("="*80)

        if console:
            table = Table(title="Find Evil! Analysis Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            threat_level = report.get("threat_level", "UNKNOWN")
            threat_color = {
                "CRITICAL": "red",
                "HIGH": "yellow",
                "MEDIUM": "yellow",
                "LOW": "green",
                "CLEAN": "green",
            }.get(threat_level, "white")

            table.add_row("Threat Level", f"[{threat_color}]{threat_level}[/{threat_color}]")
            table.add_row("Total Findings", str(len(report.get("findings", []))))
            table.add_row("High Confidence (≥0.8)", str(scoring.get("high_confidence_findings", 0)))
            table.add_row("Low Confidence (<0.7)", str(scoring.get("low_confidence_findings", 0)))
            table.add_row("IOCs Identified", str(len(report.get("ioc_list", []))))
            table.add_row("MITRE Techniques", str(len(report.get("mitre_techniques", []))))
            table.add_row("Corrections Applied", str(session_stats.get("total_corrections", 0)))
            table.add_row("Execution Time", f"{elapsed:.2f}s")
            table.add_row("Tool Calls", str(session_stats.get("total_tool_calls", 0)))
            table.add_row("Precision", f"{scoring.get('precision', 0):.1%}")
            table.add_row("Recall", f"{scoring.get('recall', 0 or 'N/A')}")

            console.print(table)
        else:
            print(f"Threat Level: {report.get('threat_level', 'UNKNOWN')}")
            print(f"Total Findings: {len(report.get('findings', []))}")
            print(f"High Confidence: {scoring.get('high_confidence_findings', 0)}")
            print(f"Low Confidence: {scoring.get('low_confidence_findings', 0)}")
            print(f"IOCs: {len(report.get('ioc_list', []))}")
            print(f"MITRE Techniques: {len(report.get('mitre_techniques', []))}")
            print(f"Corrections: {session_stats.get('total_corrections', 0)}")
            print(f"Execution Time: {elapsed:.2f}s")

        print("="*80)
        print(f"✓ Analysis complete! Reports saved to {args.output}")
        print("="*80 + "\n")

        # Cleanup
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

        logger.log_event("completion", f"Triage completed successfully in {elapsed:.2f}s", {
            "threat_level": report.get("threat_level"),
            "findings_count": len(report.get("findings", [])),
        })

        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n[!] Triage interrupted by user")
        logger.log_event("interrupted", "User interrupted triage", {})
        sys.exit(130)

    except Exception as e:
        print(f"\n[!] Error during triage: {e}", file=sys.stderr)
        logger.log_event("error", str(e), {})
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

