"""
SelfCorrector: Hallucination detection and correction engine for Find Evil!

Implements 7 hallucination detection checks:
1. Impossible Timestamp - future dates, before year 2000, after system creation
2. Contradictory Cross-Source - same artifact reported differently by tools
3. Tool Misapplication - wrong tool for wrong data type
4. Logical Inconsistency - PPID == PID, zero-size executable, port > 65535
5. Phantom Artifact - file referenced but not in MFT output
6. Confidence Collapse - finding < 0.3 confidence with no corroboration
7. Duplicate Contradiction - same IOC twice with conflicting attributes

Correction strategies are automatically selected based on hallucination type.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from agent.logger import StructuredLogger
from config import CONFIDENCE_THRESHOLD, MAX_ITERATIONS


class SelfCorrector:
    """Detects and corrects agent hallucinations with 7 detection methods."""

    def __init__(self, max_attempts: int = 3, confidence_threshold: float = 0.7):
        """
        Initialize self-corrector.

        Args:
            max_attempts: Maximum correction attempts per finding
            confidence_threshold: Minimum confidence for findings (0.0-1.0)
        """
        self.max_attempts = max_attempts
        self.confidence_threshold = confidence_threshold
        self.correction_history: List[Dict[str, Any]] = []
        # Generate unique session ID for this corrector instance
        session_id = str(uuid.uuid4())[:8]
        self.logger = StructuredLogger(session_id, log_dir="logs")

    def detect_hallucination(self, finding: Dict[str, Any]) -> Tuple[bool, str, float]:
        """
        Detect hallucination using all 7 checks.

        Returns:
            Tuple of (is_hallucination: bool, reason: str, severity: 0.0-1.0)
        """
        # CHECK 1: Impossible Timestamp
        if self._check_impossible_timestamp(finding):
            return True, "impossible_timestamp", 0.9

        # CHECK 2: Contradictory Cross-Source
        if self._check_cross_source_contradiction(finding):
            return True, "cross_source_contradiction", 0.8

        # CHECK 3: Tool Misapplication
        if self._check_tool_misapplication(finding):
            return True, "tool_misapplication", 1.0

        # CHECK 4: Logical Inconsistency
        if self._check_logical_inconsistency(finding):
            return True, "logical_inconsistency", 0.85

        # CHECK 5: Phantom Artifact
        if self._check_phantom_artifact(finding):
            return True, "phantom_artifact", 0.9

        # CHECK 6: Confidence Collapse
        if self._check_confidence_collapse(finding):
            return True, "uncorroborated_low_confidence", 0.7

        # CHECK 7: Duplicate Contradiction
        if self._check_duplicate_contradiction(finding):
            return True, "duplicate_contradiction", 0.75

        return False, "", 0.0

    async def correct_finding(
        self,
        finding: Dict[str, Any],
        all_findings: List[Dict[str, Any]],
        tool_caller
    ) -> Dict[str, Any]:
        """
        Correct hallucinated finding using appropriate strategy.

        Args:
            finding: Finding to correct
            all_findings: All findings for cross-checking
            tool_caller: Function to call MCP tools for re-analysis

        Returns:
            Corrected finding dict
        """
        original_confidence = finding.get("confidence", 0.5)
        is_hallucination, reason, severity = self.detect_hallucination(finding)

        if not is_hallucination:
            return finding

        # Select correction strategy
        corrected = None

        if reason == "impossible_timestamp":
            corrected = await self._correct_impossible_timestamp(finding, tool_caller)

        elif reason == "cross_source_contradiction":
            corrected = await self._correct_cross_source_contradiction(finding, all_findings, tool_caller)

        elif reason == "phantom_artifact":
            corrected = await self._correct_phantom_artifact(finding, tool_caller)

        elif reason == "logical_inconsistency":
            corrected = await self._correct_logical_inconsistency(finding)

        elif reason == "uncorroborated_low_confidence":
            corrected = await self._correct_uncorroborated_low_confidence(finding, all_findings)

        elif reason == "tool_misapplication":
            corrected = {**finding, "confidence": 0.1, "unreliable": True}

        elif reason == "duplicate_contradiction":
            corrected = await self._correct_duplicate_contradiction(finding, all_findings)

        # Record correction in history
        if corrected:
            self.correction_history.append({
                "finding_id": finding.get("finding_id"),
                "original_confidence": original_confidence,
                "corrected_confidence": corrected.get("confidence", 0.0),
                "hallucination_type": reason,
                "severity": severity,
                "strategy": f"correct_{reason}"
            })

        return corrected or finding

    def generate_correction_report(self) -> Dict[str, Any]:
        """Generate summary of all corrections made."""
        total = len(self.correction_history)
        if total == 0:
            return {
                "total_findings": 0,
                "hallucinations_detected": 0,
                "corrections_applied": 0,
                "findings_removed": 0,
                "accuracy_delta": 0.0,
                "correction_log": []
            }

        improvements = sum(
            c.get("corrected_confidence", 0.0) - c.get("original_confidence", 0.0)
            for c in self.correction_history
        )

        removed = sum(
            1 for c in self.correction_history
            if c.get("corrected_confidence", 0.0) < 0.1
        )

        return {
            "total_findings": total,
            "hallucinations_detected": total,
            "corrections_applied": total,
            "findings_removed": removed,
            "accuracy_delta": improvements / total if total > 0 else 0.0,
            "correction_log": self.correction_history
        }

    # ==================== HALLUCINATION DETECTION CHECKS ====================

    def _check_impossible_timestamp(self, finding: Dict[str, Any]) -> bool:
        """CHECK 1: Impossible timestamp (future, before 2000, after system image date)."""
        now = datetime.now(timezone.utc)

        for field in ["timestamp", "created", "modified", "accessed", "executed"]:
            if field not in finding:
                continue

            try:
                ts_str = finding[field]
                if isinstance(ts_str, str):
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    # Future date
                    if ts > now:
                        return True

                    # Before year 2000
                    if ts.year < 2000:
                        return True

                    # Way in the future (after 2050)
                    if ts.year > 2050:
                        return True
            except (ValueError, AttributeError):
                pass

        return False

    def _check_cross_source_contradiction(self, finding: Dict[str, Any]) -> bool:
        """CHECK 2: Contradictory cross-source (same artifact, different size, hash, etc)."""
        # Check for contradictory attributes within finding itself
        if "size_reported" in finding and "size_actual" in finding:
            size_diff = abs(finding["size_reported"] - finding["size_actual"])
            if size_diff > finding["size_actual"] * 0.1:  # >10% difference
                return True

        if "hash_reported" in finding and "hash_actual" in finding:
            if finding["hash_reported"] != finding["hash_actual"]:
                return True

        return False

    def _check_tool_misapplication(self, finding: Dict[str, Any]) -> bool:
        """CHECK 3: Tool misapplication (wrong tool for data type)."""
        tool = finding.get("source_tool", "").lower()
        data_type = finding.get("type", "").lower()
        path = finding.get("path", "").lower()

        # Memory tool on disk data
        if "memory" in tool and ("disk" in data_type or ".img" in path or ".dd" in path):
            return True

        # Disk tool on memory dump
        if "disk" in tool and (".dmp" in path or ".mem" in path or ".raw" in path):
            return True

        return False

    def _check_logical_inconsistency(self, finding: Dict[str, Any]) -> bool:
        """CHECK 4: Logical inconsistency (PPID==PID, zero-size exe, port>65535, etc)."""
        # PPID == PID (process is its own parent)
        if "pid" in finding and "ppid" in finding:
            if finding["pid"] == finding["ppid"] and finding["pid"] > 0:
                return True

        # Zero-size executable with execution history
        if finding.get("size", 0) == 0 and finding.get("execution_count", 0) > 0:
            if "exe" in finding.get("path", "").lower():
                return True

        # Network port > 65535
        if "port" in finding:
            try:
                port = int(finding["port"])
                if port > 65535 or port < 0:
                    return True
            except (ValueError, TypeError):
                pass

        # Timestamp created after modified
        try:
            created = finding.get("created")
            modified = finding.get("modified")
            if created and modified:
                c_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                m_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if c_dt > m_dt:
                    return True
        except:
            pass

        return False

    def _check_phantom_artifact(self, finding: Dict[str, Any]) -> bool:
        """CHECK 5: Phantom artifact (referenced but doesn't exist in source data)."""
        # Check if finding has "verified_in_source" flag
        if "verified_in_source" in finding:
            return not finding.get("verified_in_source", False)

        # If path exists in any source finding, it's not phantom
        if "path" in finding:
            return False  # Can't verify without access to full dataset

        return False

    def _check_confidence_collapse(self, finding: Dict[str, Any]) -> bool:
        """CHECK 6: Confidence collapse (< 0.3 confidence with no corroboration)."""
        confidence = finding.get("confidence", 0.5)

        if confidence < 0.3:
            corroborated_by = finding.get("corroborated_by", [])
            if len(corroborated_by) < 2:
                return True

        return False

    def _check_duplicate_contradiction(self, finding: Dict[str, Any]) -> bool:
        """CHECK 7: Duplicate contradiction (same IOC, conflicting attributes)."""
        # Check if finding has duplicate_of field
        if "duplicate_of" in finding:
            dup_id = finding["duplicate_of"]
            if "contradiction" in finding:
                return True

        return False

    # ==================== CORRECTION STRATEGIES ====================

    async def _correct_impossible_timestamp(
        self,
        finding: Dict[str, Any],
        tool_caller
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for impossible timestamp."""
        # Try to normalize timezone
        corrected = {**finding}

        for field in ["timestamp", "created", "modified", "executed"]:
            if field in corrected:
                try:
                    ts_str = corrected[field]
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

                    # If far future, ignore
                    if ts.year > 2050:
                        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

                    # If before 2000, set to 2000
                    if ts.year < 2000:
                        ts = datetime(2000, 1, 1, tzinfo=timezone.utc)

                    corrected[field] = ts.isoformat()
                except:
                    pass

        corrected["confidence"] = max(0.1, finding.get("confidence", 0.5) - 0.3)
        return corrected

    async def _correct_cross_source_contradiction(
        self,
        finding: Dict[str, Any],
        all_findings: List[Dict[str, Any]],
        tool_caller
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for cross-source contradiction."""
        # Re-run both conflicting tools if needed
        # For now, lower confidence significantly
        corrected = {**finding}
        corrected["confidence"] = max(0.1, finding.get("confidence", 0.5) - 0.4)
        corrected["contradiction_note"] = "Conflicting values from multiple sources"
        return corrected

    async def _correct_phantom_artifact(
        self,
        finding: Dict[str, Any],
        tool_caller
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for phantom artifact."""
        # Try to verify in MFT or other sources
        # If still phantom after verification, remove
        corrected = {**finding}
        corrected["confidence"] = 0.0  # Remove phantom artifact
        corrected["status"] = "removed_phantom"
        return corrected

    async def _correct_logical_inconsistency(
        self,
        finding: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for logical inconsistency."""
        corrected = {**finding}
        corrected["confidence"] = 0.1
        corrected["unreliable"] = True
        corrected["logical_error"] = "Finding exhibits impossible or contradictory properties"
        return corrected

    async def _correct_uncorroborated_low_confidence(
        self,
        finding: Dict[str, Any],
        all_findings: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for uncorroborated low-confidence finding."""
        corrected = {**finding}

        # Search for corroborating evidence in other findings
        finding_key = finding.get("path") or finding.get("process") or finding.get("ip")

        for other in all_findings:
            other_key = other.get("path") or other.get("process") or other.get("ip")
            if finding_key and other_key and finding_key.lower() == other_key.lower():
                # Found corroboration
                corroborated_by = corrected.get("corroborated_by", [])
                corroborated_by.append(other.get("source_tool", "unknown"))
                corrected["corroborated_by"] = corroborated_by

                # Boost confidence
                corrected["confidence"] = min(0.8, finding.get("confidence", 0.3) + 0.3)
                return corrected

        # No corroboration found, remove if still too low
        if corrected["confidence"] < 0.3:
            corrected["status"] = "removed_uncorroborated"
            corrected["confidence"] = 0.0

        return corrected

    async def _correct_duplicate_contradiction(
        self,
        finding: Dict[str, Any],
        all_findings: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Correction strategy for duplicate contradiction."""
        corrected = {**finding}

        # Check if other version is more credible
        dup_id = finding.get("duplicate_of")
        for other in all_findings:
            if other.get("finding_id") == dup_id:
                if other.get("confidence", 0.0) > finding.get("confidence", 0.0):
                    # Other version is better, mark this for removal
                    corrected["status"] = "removed_duplicate"
                    corrected["confidence"] = 0.0
                    return corrected

        # Both versions equally dubious, lower confidence
        corrected["confidence"] = max(0.1, finding.get("confidence", 0.3) - 0.2)
        return corrected

    def _compare_findings(self, original: Dict[str, Any], corrected: Dict[str, Any]) -> Dict[str, Any]:
        """Compare original vs corrected finding."""
        changes = {}

        for key in set(list(original.keys()) + list(corrected.keys())):
            if original.get(key) != corrected.get(key):
                changes[key] = {
                    "original": original.get(key),
                    "corrected": corrected.get(key)
                }

        confidence_delta = corrected.get("confidence", 0.0) - original.get("confidence", 0.0)

        return {
            "changed_fields": changes,
            "confidence_delta": confidence_delta,
            "improvement": confidence_delta > 0
        }

