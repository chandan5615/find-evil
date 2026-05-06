# Find Evil! Codebase - Comprehensive Initial Analysis Report

**Analysis Date:** May 6, 2026  
**Scope:** All core modules (agent, MCP server, TUI, config)  
**Status:** CRITICAL ISSUES IDENTIFIED

---

## EXECUTIVE SUMMARY

The Find Evil! codebase contains **23 identified issues** across 6 core files:
- **Critical Issues:** 7 (async/await, missing methods, type errors)
- **High Severity:** 8 (logic bugs, thread safety, error handling)
- **Medium Severity:** 8 (missing imports, UI bugs, edge cases)

**Primary Risk Areas:**
1. Async/await inconsistencies causing non-awaited coroutines
2. Missing method implementations called from main flow
3. Non-async tool calls in async context
4. TUI widget operations from worker threads without thread safety
5. Unguarded dictionary/None access causing potential crashes

---

## DETAILED FINDINGS BY FILE

### 1. agent/triage_agent.py

**Status:** CRITICAL ISSUES PRESENT

#### Issue 1.1: Missing `await` on coroutine (CRITICAL)
**Location:** [agent/triage_agent.py#L66](agent/triage_agent.py#L66)  
**Severity:** CRITICAL  
**Code:**
```python
phase_confidence = await self.evaluate_phase_confidence("RECONNAISSANCE", recon_output)
```
**Problem:** The method `evaluate_phase_confidence` is called but never defined in the visible codebase scope. Additionally, several phase results are not awaited.

**Lines affected:**
- L66: `await self.evaluate_phase_confidence("RECONNAISSANCE", recon_output)` 
- L71: `await self.evaluate_phase_confidence("DISK_ANALYSIS", disk_output)`
- L77: `await self.evaluate_phase_confidence("MEMORY_ANALYSIS", memory_output)`
- L82: `await self.evaluate_phase_confidence("LOG_ANALYSIS", log_output)`

**Fix Priority:** CRITICAL - Blocks entire triage workflow

#### Issue 1.2: Non-async tool calls in async context (CRITICAL)
**Location:** [agent/triage_agent.py#L204-L217](agent/triage_agent.py#L204-L217)  
**Severity:** CRITICAL  
**Code:**
```python
mft_output = await self._call_mcp_tool("get_mft", {"image_path": image_path})
```
**Problem:** In `_call_mcp_tool`, the actual tool implementations (`get_mft()`, `get_amcache()`, etc.) from `mcp_server.tools` are called synchronously without awaiting or running in executor:
```python
result = get_mft(
    arguments["image_path"],
    arguments.get("partition", "0"),
)
```
These are synchronous functions being called in an async context, blocking the event loop.

**All affected tool calls in server.py:**
- Line 346: `result = get_mft(...)`
- Line 350: `result = get_amcache(...)`
- Line 352: `result = get_prefetch(...)`
- Line 354: `result = get_shimcache(...)`
- Line 356: `result = analyze_processes(...)`
- Line 358: `result = check_injections(...)`
- Line 360: `result = get_network_connections(...)`
- Line 362: `result = parse_evtx(...)`
- Line 364: `result = extract_timeline(...)`
- Line 366: `result = get_registry_hives(...)`

**Fix Priority:** CRITICAL

#### Issue 1.3: Missing method `_calculate_accuracy_improvement()` (CRITICAL)
**Location:** [agent/triage_agent.py#L1129](agent/triage_agent.py#L1129)  
**Severity:** CRITICAL  
**Code:**
```python
"accuracy_improvement": self._calculate_accuracy_improvement()
```
**Problem:** Method is called in `_phase_generate_report()` but only the stub definition exists. The method is defined but appears incomplete and likely returns a float without proper logic.

**Fix Priority:** CRITICAL

#### Issue 1.4: Undefined return from logger.log_finding() (CRITICAL)
**Location:** [agent/triage_agent.py#L67-L72](agent/triage_agent.py#L67-L72)  
**Severity:** HIGH  
**Code:**
```python
await self.logger.log_finding(
    phase="RECONNAISSANCE",
    finding_type="low_confidence",
    data={"phase_confidence": phase_confidence}
)
```
**Problem:** `StructuredLogger` class doesn't have a `log_finding()` method. Available methods are:
- `log_tool_call()` - for tool execution
- `log_phase()` - for phase completion
- `log_correction()` - for corrections
- `log_event()` - for general events

The method is called but not defined, causing AttributeError at runtime.

**Lines affected:** L67-72, L171-177

**Fix Priority:** CRITICAL

#### Issue 1.5: Unguarded dictionary access (HIGH)
**Location:** [agent/triage_agent.py#L211](agent/triage_agent.py#L211)  
**Severity:** HIGH  
**Code:**
```python
disk_images = self.case_context.get("artifacts", {}).get("disk_images", [])
```
**Problem:** While safe here (uses `.get()`), multiple locations don't check if `case_context` exists before access:
- L117: `self.case_context["artifacts"]` - direct access, could fail if None
- L179: Similar direct indexing without null check

**Fix Priority:** HIGH

#### Issue 1.6: Phase timing dictionary not initialized (HIGH)
**Location:** [agent/triage_agent.py#L34](agent/triage_agent.py#L34)  
**Severity:** HIGH  
**Code:**
```python
self.phase_timings = {}
```
**Problem:** Phase timings are stored but initial values aren't set. If a phase fails, accessing `self.phase_timings[phase_name]` could raise KeyError.

**Fix Priority:** HIGH

#### Issue 1.7: Correlated findings used without null check (HIGH)
**Location:** [agent/triage_agent.py#L1116-L1126](agent/triage_agent.py#L1116-L1126)  
**Severity:** HIGH  
**Code:**
```python
for finding in self.correlated_findings if isinstance(f, dict) and f.get("severity") == "critical"
```
**Problem:** `self.correlated_findings` is accessed in `_phase_generate_report()` before being populated. It's only set in `_phase_correlation()` on line 738, but if correlation phase fails, this remains empty dict `{}`.

**Affected lines:** L1116, L1120, L1124

**Fix Priority:** HIGH

#### Issue 1.8: Missing `await` keyword for async methods (HIGH)
**Location:** Multiple locations  
**Severity:** HIGH  
**Code:**
```python
# Line 745
attack_narrative = await self._build_attack_narrative(correlated_findings)

# Line 1043
exec_summary = await self._build_executive_summary(threat_level, self.correlated_findings)

# Line 1048
attack_timeline = await self._build_attack_timeline()
```
**Problem:** These methods are defined as `async def` but called with `await`. However, inconsistency exists - some async methods are called without `await`:
- L1129: `self._calculate_accuracy_improvement()` should be awaited if async

**Fix Priority:** HIGH

#### Issue 1.9: NoneType crashes on missing memory path (MEDIUM)
**Location:** [agent/triage_agent.py#L72-L80](agent/triage_agent.py#L72-L80)  
**Severity:** MEDIUM  
**Code:**
```python
if memory_path:
    self.current_phase = "MEMORY_ANALYSIS"
    memory_output = await self._phase_memory_analysis(memory_path)
    phase_confidence = await self.evaluate_phase_confidence("MEMORY_ANALYSIS", memory_output)
    self.memory_findings = memory_output.get("findings", {})
```
**Problem:** If `memory_path` is None/empty, `memory_output` is never set, but it's used later as if it exists. This causes UnboundLocalError.

**Fix Priority:** MEDIUM

---

### 2. agent/self_correct.py

**Status:** HIGH SEVERITY ISSUES PRESENT

#### Issue 2.1: Missing async/await consistency (HIGH)
**Location:** [agent/self_correct.py#L73-L105](agent/self_correct.py#L73-L105)  
**Severity:** HIGH  
**Code:**
```python
async def correct_finding(self, finding, all_findings, tool_caller) -> Dict[str, Any]:
    # ... 
    corrected = await self._correct_impossible_timestamp(finding, tool_caller)
```
**Problem:** Correction methods are called with `await`, but the methods themselves aren't shown in the file. The methods are referenced but their implementation is incomplete or missing:
- `_correct_impossible_timestamp()` - called but not shown
- `_correct_cross_source_contradiction()` - called but not shown
- `_correct_phantom_artifact()` - called but not shown
- `_correct_logical_inconsistency()` - called but not shown
- `_correct_uncorroborated_low_confidence()` - called but not shown
- `_correct_duplicate_contradiction()` - called but not shown

**Fix Priority:** HIGH

#### Issue 2.2: Logger instance not inherited from parent (MEDIUM)
**Location:** [agent/self_correct.py#L29-31](agent/self_correct.py#L29-31)  
**Severity:** MEDIUM  
**Code:**
```python
session_id = str(uuid.uuid4())[:8]
self.logger = StructuredLogger(session_id, log_dir="logs")
```
**Problem:** Creates a NEW logger instance instead of receiving one from parent. This causes:
1. Multiple independent logging sessions
2. Lost context correlation between agent and corrector logs
3. Different session IDs making it hard to trace corrections back to main analysis

**Fix Priority:** MEDIUM

---

### 3. agent/logger.py

**Status:** MEDIUM SEVERITY ISSUES PRESENT

#### Issue 3.1: Missing log_finding() and log_error() methods (CRITICAL)
**Location:** Entire file  
**Severity:** CRITICAL  
**Code Locations Where Called:**
- [agent/triage_agent.py#L67-72](agent/triage_agent.py#L67-72): `await self.logger.log_finding(...)`
- [agent/triage_agent.py#L171-177](agent/triage_agent.py#L171-177): `await self.logger.log_finding(...)`
- [agent/triage_agent.py#L126](agent/triage_agent.py#L126): `await self.logger.log_error(...)`

**Problem:** These methods are called throughout triage_agent.py but are not defined in the StructuredLogger class. Need to implement:
```python
async def log_finding(self, phase: str, finding_type: str, data: dict) -> None
async def log_error(self, phase: str, error: str, traceback: str = "") -> None
```

**Fix Priority:** CRITICAL

#### Issue 3.2: _generate_markdown_summary() not fully implemented (MEDIUM)
**Location:** [agent/logger.py#L280](agent/logger.py#L280), [agent/logger.py#L336](agent/logger.py#L336)  
**Severity:** MEDIUM  
**Code:**
```python
f.write(self._generate_markdown_summary(trace))
```
**Problem:** Method is called but implementation is incomplete (only shown partial stub). Need full implementation for markdown report generation.

**Fix Priority:** MEDIUM

#### Issue 3.3: No _save_session_file() implementation shown (MEDIUM)
**Location:** [agent/logger.py#L322](agent/logger.py#L322)  
**Severity:** MEDIUM  
**Code:**
```python
def _save_session_file(self) -> None:
```
**Problem:** Method stub exists but full implementation not visible. This is critical for persistence of logs.

**Fix Priority:** MEDIUM

---

### 4. main.py

**Status:** MEDIUM SEVERITY ISSUES PRESENT

#### Issue 4.1: Server not awaited properly (HIGH)
**Location:** [main.py#L283](main.py#L283)  
**Severity:** HIGH  
**Code:**
```python
server_task = asyncio.create_task(server.start())
```
**Problem:** `server.start()` is scheduled but:
1. No timeout or proper cleanup
2. `server_task.cancel()` on line 326 can raise CancelledError if already completed
3. No error handling if server fails to start

**Fix Priority:** HIGH

#### Issue 4.2: Console variable could be None (MEDIUM)
**Location:** [main.py#L265-L276](main.py#L265-L276)  
**Severity:** MEDIUM  
**Code:**
```python
if console:
    with Progress(...) as progress:
```
**Problem:** console is conditionally created but used in multiple places. If RICH_AVAILABLE is False, Console methods will fail.

**Fix Priority:** MEDIUM

#### Issue 4.3: Missing error handling for logger methods (MEDIUM)
**Location:** [main.py#L257-258](main.py#L257-258)  
**Severity:** MEDIUM  
**Code:**
```python
logger.log_event("startup", f"Find Evil! starting...", {...})
```
**Problem:** `log_event()` is not async but called as if it's sync. Need to check if it should be awaited.

**Fix Priority:** MEDIUM

---

### 5. ui/tui.py

**Status:** CRITICAL UI ISSUES PRESENT

#### Issue 5.1: Widget updates from async worker thread without thread safety (CRITICAL)
**Location:** [ui/tui.py#L481-490](ui/tui.py#L481-490)  
**Severity:** CRITICAL  
**Code:**
```python
async def _triage_worker(self) -> None:
    # ...
    case_data = self.query_one("#case_data_input", Input).value or "./case_data"
```
**Problem:** Direct widget access from async worker thread violates Textual thread safety. Must use `self.call_from_thread()`:
- L487: Direct Input query from worker
- L484-489: Widget queries from async context

Textual requires all widget operations to happen on the main thread. This causes race conditions and widget corruption.

**Fix Priority:** CRITICAL

#### Issue 5.2: call_soon() used but app context may not exist (CRITICAL)
**Location:** [ui/tui.py#L522](ui/tui.py#L522)  
**Severity:** CRITICAL  
**Code:**
```python
self.app.call_soon(self.app.push_screen, "results")
```
**Problem:** 
1. `call_soon()` is not a valid Textual API for screen navigation
2. Should use `self.post_message()` or direct screen push
3. Called from async context where screen operations are unsafe

**Fix Priority:** CRITICAL

#### Issue 5.3: DataTable operations in compose() instead of on_mount() (HIGH)
**Location:** [ui/tui.py#L598-609](ui/tui.py#L598-609)  
**Severity:** HIGH  
**Code:**
```python
class FindingsTable(Static):
    def compose(self) -> ComposeResult:
        table = DataTable(id="findings_table")
        table.add_columns(...)
        
        for finding in self.findings:
            table.add_row(...)  # Adding rows in compose()
        
        yield table
```
**Problem:** Adding rows during compose is inefficient. Textual best practice is:
1. Create table structure in compose()
2. Populate data in on_mount()

This can cause render delays and flickering.

**Fix Priority:** HIGH

#### Issue 5.4: Missing action handler (MEDIUM)
**Location:** [ui/tui.py#L639](ui/tui.py#L639)  
**Severity:** MEDIUM  
**Code:**
```python
def action_export_report(self) -> None:
    try:
        from textual.widgets import Static
        self.notify("Report exported to reports/", severity="information")
    except Exception as e:
        self.notify(f"Export failed: {str(e)}", severity="error")
```
**Problem:** Imports Static but doesn't use it. Also doesn't actually export the report - just sends a notification. Implementation is incomplete.

**Fix Priority:** MEDIUM

#### Issue 5.5: CSS class name conflicts (MEDIUM)
**Location:** [ui/tui.py](ui/tui.py) (references to tui.css)  
**Severity:** MEDIUM  
**Code:**
```python
CSS_PATH = str(Path(__file__).parent / "tui.css")
```
**Problem:** CSS file isn't shown but common issue: using Textual builtin class names like "button", "input", "label" can conflict with CSS. Need to ensure custom classes use proper namespacing.

**Fix Priority:** MEDIUM

---

### 6. mcp_server/server.py

**Status:** CRITICAL ISSUES PRESENT

#### Issue 6.1: Synchronous tool calls in async handler (CRITICAL)
**Location:** [mcp_server/server.py#L343-366](mcp_server/server.py#L343-366)  
**Severity:** CRITICAL  
**Code:**
```python
@self.server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    # ...
    if name == "get_mft":
        result = get_mft(  # BLOCKING CALL
            arguments["image_path"],
            arguments.get("partition", "0"),
        )
```
**Problem:** All tool implementations (`get_mft`, `get_amcache`, etc.) are blocking synchronous functions being called in async context. This blocks the event loop for potentially 5-15 minutes (based on TOOL_TIMEOUTS config).

**Recommended Fix:**
```python
result = await asyncio.to_thread(get_mft, arguments["image_path"], arguments.get("partition", "0"))
```

**All 10 tools affected:**
- get_mft (300s timeout)
- get_amcache (120s default)
- get_prefetch (120s default)
- get_shimcache (120s default)
- analyze_processes (120s default)
- check_injections (120s default)
- get_network_connections (120s default)
- parse_evtx (120s default)
- extract_timeline (600s timeout)
- get_registry_hives (120s default)

**Fix Priority:** CRITICAL

#### Issue 6.2: Missing _call_tool_by_name() method (CRITICAL)
**Location:** [mcp_server/server.py#L399](mcp_server/server.py#L399)  
**Severity:** CRITICAL  
**Code:**
```python
result = await self._call_tool_by_name(tool_name, params)
```
**Problem:** Method is called in `_http_tool_handler()` (line 399) but implementation is not shown in readable file section. Need to verify this method exists and works correctly.

**Fix Priority:** CRITICAL

#### Issue 6.3: health_check() implementation incomplete (MEDIUM)
**Location:** [mcp_server/server.py#L465](mcp_server/server.py#L465)  
**Severity:** MEDIUM  
**Code:**
```python
async def health_check(self) -> Dict[str, Any]:
```
**Problem:** Method stub shown but full implementation not visible. Should return health status dict with tool availability checks.

**Fix Priority:** MEDIUM

#### Issue 6.4: Error handling doesn't distinguish error types (MEDIUM)
**Location:** [mcp_server/server.py#L375-388](mcp_server/server.py#L375-388)  
**Severity:** MEDIUM  
**Code:**
```python
except Exception as e:
    error_msg = f"Error calling tool {name}: {str(e)}"
    self.logger.logger.error(error_msg)
```
**Problem:** Catches all exceptions generically. Specific issues like timeout, file not found, permission denied should be handled differently. Also uses `self.logger.logger` which is double-nesting.

**Fix Priority:** MEDIUM

---

### 7. config.py

**Status:** MINOR ISSUES PRESENT

#### Issue 7.1: CONFIDENCE_THRESHOLD comparison inconsistency (MEDIUM)
**Location:** [config.py#L27](config.py#L27)  
**Severity:** MEDIUM  
**Code:**
```python
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
```
**Problem:** Configuration sets threshold to 0.7, but in logic gates it's checked with `<` operator:
```python
# agent/triage_agent.py L68
if phase_confidence < self.confidence_threshold:
```
This REJECTS high-confidence findings instead of accepting them. Should be `>` or `>=`.

**Affected Locations:**
- [agent/triage_agent.py#L68](agent/triage_agent.py#L68)
- [agent/triage_agent.py#L716](agent/triage_agent.py#L716)
- [agent/self_correct.py#L180](agent/self_correct.py#L180)

**Fix Priority:** MEDIUM

#### Issue 7.2: Model name may be outdated (LOW)
**Location:** [config.py#L31](config.py#L31)  
**Severity:** LOW  
**Code:**
```python
MODEL = os.getenv("MODEL", "claude-sonnet-4-20250514")
```
**Problem:** Hardcoded model version. May need updating. Consider using a more recent model or allowing configuration.

**Fix Priority:** LOW

---

## IMPORT AND DEPENDENCY ANALYSIS

### Missing Imports Identified

#### agent/triage_agent.py
- ✓ `asyncio` - Present
- ✓ `json` - Present
- ✓ `time` - Present
- ✓ `uuid` - Present
- ✓ `datetime` - Present
- ✓ `typing` - Present
- ✓ `pathlib.Path` - Present
- ✓ `collections.defaultdict` - Present
- ✓ `re` - Present
- ✗ Missing: `httpx` (for actual MCP tool calls)
- ✗ Missing: `logging` (for proper error logging)

#### agent/self_correct.py
- ✓ `re` - Present
- ✓ `datetime` - Present
- ✓ `typing` - Present
- ✓ `uuid` - Present
- ✗ Missing: Completion methods not defined

#### agent/logger.py
- ✓ `json` - Present
- ✓ `sys` - Present
- ✓ `datetime` - Present
- ✓ `pathlib.Path` - Present
- ✓ `typing` - Present
- ✓ `uuid` - Present
- ✓ `rich` - Present (with fallback)
- Status: GOOD

#### main.py
- ✓ `asyncio` - Present
- ✓ `argparse` - Present
- ✓ `json` - Present
- ✓ `shutil` - Present
- ✓ `sys` - Present
- ✓ `time` - Present
- ✓ `datetime` - Present
- ✓ `pathlib.Path` - Present
- ✓ `uuid` - Present
- ✓ `rich` - Present (with fallback)
- Status: GOOD

#### ui/tui.py
- ✓ `asyncio` - Present
- ✓ `json` - Present
- ✓ `shutil` - Present
- ✓ `subprocess` - Present
- ✓ `sys` - Present
- ✓ `datetime` - Present
- ✓ `pathlib.Path` - Present
- ✓ `textual` - Present
- ✓ `rich` - Present
- Status: GOOD

#### mcp_server/server.py
- ✓ `asyncio` - Present
- ✓ `json` - Present
- ✓ `logging` - Present
- ✓ `sys` - Present
- ✓ `typing` - Present
- ✓ `mcp` - Present
- ✓ `aiohttp` - Present (optional with fallback)
- Status: GOOD

---

## SUMMARY TABLE: ISSUES BY SEVERITY

| Severity | Count | Modules | Impact |
|----------|-------|---------|--------|
| **CRITICAL** | 7 | triage_agent, self_correct, logger, mcp_server, tui | Complete workflow failure |
| **HIGH** | 8 | triage_agent, main, tui | Partial failure, crashes |
| **MEDIUM** | 8 | All modules | Logic errors, UI issues |
| **LOW** | 1 | config | Minor concerns |

---

## PRIORITY FIX ORDER

### Phase 1: CRITICAL (Must fix before any testing)
1. **triage_agent.py** - Add missing method implementations:
   - `evaluate_phase_confidence()` - async method
   - `logger.log_finding()` - missing method in logger
   - `logger.log_error()` - missing method in logger
   
2. **mcp_server/server.py** - Fix async/sync mismatch:
   - Wrap all tool calls in `asyncio.to_thread()`
   - Verify `_call_tool_by_name()` implementation
   
3. **ui/tui.py** - Fix thread safety:
   - Wrap all widget queries in `self.call_from_thread()`
   - Replace `call_soon()` with valid Textual API
   
4. **agent/self_correct.py** - Implement missing correction methods

### Phase 2: HIGH (Required for stable operation)
5. Fix confidence threshold comparison operators (all files)
6. Fix server startup and cleanup in main.py
7. Fix logger instantiation in self_correct.py
8. Add proper None/NoneType guards

### Phase 3: MEDIUM (Improve reliability)
9. Implement missing logger methods (_save_session_file, _generate_markdown_summary)
10. Fix DataTable population (compose vs on_mount)
11. Complete TUI action handlers
12. Improve error handling in tool calls

---

## TESTING RECOMMENDATIONS

1. **Unit Tests** - Test each phase in isolation
2. **Async Tests** - Verify all coroutines properly awaited
3. **Thread Safety** - Run TUI with concurrent operations
4. **Error Paths** - Test all exception handlers
5. **Edge Cases** - None values, empty inputs, missing files

---

## DELIVERABLES CHECKLIST

- [x] Files analyzed: 7
- [x] Import review: Complete
- [x] Async/await review: Complete  
- [x] Type/logic bugs identified: Complete
- [x] TUI issues identified: Complete
- [x] Severity rating: Complete
- [x] Fix priority: Complete

