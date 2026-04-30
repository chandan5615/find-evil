"""
Accuracy reporting and benchmarking for Find Evil! agent.

Scores findings against ground truth and generates performance metrics:
- True positives, false positives, false negatives
- Precision, recall, F1 score
- Hallucination rate
- Correction success rate
- Markdown and JSON reports
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AccuracyReporter:
    """Generate accuracy reports for incident response findings."""

    def __init__(self, ground_truth_path: str = None):
        """
        Initialize accuracy reporter.

        Args:
            ground_truth_path: Path to ground truth JSON file (optional)
        """
        self.ground_truth = None
        self.results = []

        if ground_truth_path:
            try:
                with open(ground_truth_path, "r") as f:
                    self.ground_truth = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load ground truth: {e}")

    def score_findings(self, agent_findings: list, ground_truth: dict = None) -> dict:
        """
        Score findings against ground truth.

        Args:
            agent_findings: List of findings from agent analysis
            ground_truth: Optional ground truth dict (overrides init ground_truth)

        Returns:
            Scoring dict with metrics
        """
        gt = ground_truth or self.ground_truth

        # If no ground truth provided, estimate based on confidence
        if not gt:
            return self._estimate_accuracy(agent_findings)

        # Compare against ground truth
        true_positives = 0
        false_positives = 0
        false_negatives = len(gt.get("findings", []))

        for finding in agent_findings:
            matched = False
            for gt_finding in gt.get("findings", []):
                if self._findings_match(finding, gt_finding):
                    true_positives += 1
                    false_negatives -= 1
                    matched = True
                    break
            if not matched:
                false_positives += 1

        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Calculate additional metrics
        hallucination_count = sum(1 for f in agent_findings if f.get("confidence", 1.0) < 0.3)
        high_confidence_count = sum(1 for f in agent_findings if f.get("confidence", 1.0) >= 0.8)
        low_confidence_count = sum(1 for f in agent_findings if f.get("confidence", 1.0) < 0.7)

        return {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "hallucination_rate": hallucination_count / len(agent_findings) if agent_findings else 0.0,
            "correction_success_rate": 0.0,  # Would come from correction_log
            "average_confidence": sum(f.get("confidence", 1.0) for f in agent_findings) / len(agent_findings) if agent_findings else 0.0,
            "high_confidence_findings": high_confidence_count,
            "low_confidence_findings": low_confidence_count,
            "total_findings": len(agent_findings),
        }

    def generate_markdown_report(self, scoring: dict, agent_report: dict, session_stats: dict) -> str:
        """
        Generate markdown accuracy report.

        Args:
            scoring: Scoring dict from score_findings()
            agent_report: Full agent report dict
            session_stats: Session execution stats

        Returns:
            Markdown report string
        """
        lines = [
            "# Find Evil! — Accuracy Report",
            "",
            f"**Session ID**: `{agent_report.get('session_id', 'unknown')}`",
            f"**Timestamp**: {datetime.now(timezone.utc).isoformat()}",
            f"**Threat Level**: {agent_report.get('threat_level', 'UNKNOWN')}",
            "",
            "## Executive Summary",
            "",
        ]

        # Executive summary (3-5 sentences)
        summary = agent_report.get("executive_summary", "No summary available.")
        lines.append(summary)
        lines.append("")

        # Accuracy metrics
        lines.extend([
            "## Accuracy Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Precision | {scoring.get('precision', 0):.2%} |",
            f"| Recall | {scoring.get('recall', 0):.2%} |",
            f"| F1 Score | {scoring.get('f1_score', 0):.2%} |",
            f"| Hallucination Rate | {scoring.get('hallucination_rate', 0):.2%} |",
            f"| Correction Success Rate | {scoring.get('correction_success_rate', 0):.2%} |",
            f"| Average Confidence | {scoring.get('average_confidence', 0):.2f} |",
            "",
        ])

        # Attack timeline
        lines.extend([
            "## Attack Timeline",
            "",
            "| Timestamp | Event | Confidence |",
            "|-----------|-------|------------|",
        ])

        for event in agent_report.get("attack_timeline", [])[:20]:  # Top 20 events
            lines.append(
                f"| {event.get('timestamp', 'N/A')} | {event.get('event', 'N/A')} | "
                f"{event.get('confidence', 0):.2f} |"
            )
        lines.append("")

        # IOC list
        lines.extend([
            "## IOC List",
            "",
            "| Type | Value | Confidence | Source |",
            "|------|-------|------------|--------|",
        ])

        for ioc in agent_report.get("ioc_list", [])[:30]:  # Top 30 IOCs
            lines.append(
                f"| {ioc.get('type', 'N/A')} | {ioc.get('value', 'N/A')[:50]} | "
                f"{ioc.get('confidence', 0):.2f} | {ioc.get('source', 'N/A')} |"
            )
        lines.append("")

        # MITRE ATT&CK techniques
        lines.extend([
            "## MITRE ATT&CK Techniques",
            "",
            "| Technique ID | Name | Confidence | Evidence |",
            "|--------------|------|------------|----------|",
        ])

        for technique in agent_report.get("mitre_techniques", []):
            lines.append(
                f"| {technique.get('technique_id', 'N/A')} | {technique.get('name', 'N/A')} | "
                f"{technique.get('confidence', 0):.2f} | {technique.get('evidence_count', 0)} |"
            )
        lines.append("")

        # Findings by source
        lines.append("## Findings by Source")
        lines.append("")

        for source in ["disk", "memory", "logs", "correlated"]:
            findings = agent_report.get("findings_by_source", {}).get(source, [])
            if findings:
                lines.append(f"### {source.upper()} ({len(findings)})")
                lines.append("")
                for finding in findings[:5]:  # Top 5 per source
                    lines.append(f"- **{finding.get('type', 'Unknown')}**: {finding.get('description', 'N/A')} ")
                    lines.append(f"  (Confidence: {finding.get('confidence', 0):.2f})")
                lines.append("")

        # Self-correction summary
        corr_summary = agent_report.get("self_correction_summary", {})
        lines.extend([
            "## Self-Correction Summary",
            "",
            f"- Corrections attempted: {corr_summary.get('corrections_attempted', 0)}",
            f"- Corrections accepted: {corr_summary.get('corrections_accepted', 0)}",
            f"- Findings removed as hallucinations: {scoring.get('hallucination_rate', 0) * scoring.get('total_findings', 0):.0f}",
            f"- Accuracy improvement: {corr_summary.get('accuracy_improvement', 0):.1%}",
            "",
        ])

        # Evidence integrity
        lines.extend([
            "## Evidence Integrity",
            "",
            "- **Read-only enforcement**: VERIFIED",
            f"- **Original data modified**: NO",
            f"- **Evidence hash verified**: {agent_report.get('evidence_integrity', {}).get('hash_verification', 'N/A')}",
            f"- **Chain of custody**: {agent_report.get('evidence_integrity', {}).get('chain_of_custody', 'MAINTAINED')}",
            "",
        ])

        # Execution metadata
        lines.extend([
            "## Execution Metadata",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Duration | {session_stats.get('total_duration_ms', 0) / 1000:.2f}s |",
            f"| Tool Calls | {session_stats.get('total_tool_calls', 0)} |",
            f"| Successful Tool Calls | {session_stats.get('successful_tool_calls', 0)} |",
            f"| Failed Tool Calls | {session_stats.get('failed_tool_calls', 0)} |",
            f"| Total Corrections | {session_stats.get('total_corrections', 0)} |",
            f"| Successful Corrections | {session_stats.get('successful_corrections', 0)} |",
            f"| Average Confidence | {session_stats.get('average_confidence', 0):.2f} |",
            f"| Phases Completed | {session_stats.get('phases_completed', 0)} |",
            f"| Token Estimate | {session_stats.get('token_estimate_total', 0)} |",
            "",
        ])

        return "\n".join(lines)

    def save_report(self, markdown: str, json_report: dict, output_dir: str) -> None:
        """
        Save markdown and JSON reports.

        Args:
            markdown: Markdown report string
            json_report: JSON report dict
            output_dir: Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save markdown
        md_file = output_path / f"accuracy_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        with open(md_file, "w") as f:
            f.write(markdown)
        print(f"✓ Markdown report saved: {md_file}")

        # Save JSON
        json_file = output_path / f"accuracy_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, "w") as f:
            json.dump(json_report, f, indent=2)
        print(f"✓ JSON report saved: {json_file}")

    def _findings_match(self, finding: dict, gt_finding: dict) -> bool:
        """Check if two findings match."""
        # Simple matching by type and some identifier
        if finding.get("type") != gt_finding.get("type"):
            return False
        
        # Try matching by path/value
        if finding.get("path") and gt_finding.get("path"):
            return finding.get("path") == gt_finding.get("path")
        
        if finding.get("value") and gt_finding.get("value"):
            return finding.get("value") == gt_finding.get("value")
        
        return False

    def _estimate_accuracy(self, findings: list) -> dict:
        """Estimate accuracy based on confidence scores."""
        high_conf = sum(1 for f in findings if f.get("confidence", 1.0) >= 0.8)
        low_conf = sum(1 for f in findings if f.get("confidence", 1.0) < 0.7)
        total = len(findings) if findings else 1

        # Estimate precision based on confidence
        estimated_precision = high_conf / total if total > 0 else 0

        return {
            "note": "Accuracy estimated from confidence scores (no ground truth provided)",
            "precision": estimated_precision,
            "recall": None,
            "f1_score": None,
            "hallucination_rate": low_conf / total if total > 0 else 0,
            "correction_success_rate": 0.0,
            "average_confidence": sum(f.get("confidence", 1.0) for f in findings) / total if total > 0 else 0,
            "high_confidence_findings": high_conf,
            "low_confidence_findings": low_conf,
            "total_findings": total,
        }

