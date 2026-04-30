# Find Evil! - Autonomous Incident Response Agent

**A SANS Hackathon Submission** building an AI-powered incident response automation framework on the SANS SIFT Workstation.

---

## 🚀 Quick Start (5 minutes)

### Automated Setup
```bash
git clone https://github.com/your-username/find-evil.git
cd find-evil
bash setup.sh
```

### Launch the Terminal UI
```bash
./run.sh
```

### Or Use CLI Directly
```bash
source venv/bin/activate
python main.py --case-data ./case_data --verbose
```

### Validate Setup (Dry Run)
```bash
python main.py --dry-run
```

---

## Overview

Find Evil! is an autonomous agent that triages forensic case data using AI and the Model Context Protocol (MCP). It orchestrates SIFT forensics tools, detects its own hallucinations, and generates actionable intelligence reports.

### Key Features

✅ **Automated Triage** - Orchestrates disk, memory, and log analysis in sequence  
✅ **Self-Correcting** - Detects and corrects AI hallucinations in real-time  
✅ **Typed Safety** - MCP-wrapped tools with type hints and input validation  
✅ **Read-Only Forensics** - Never modifies evidence (chain of custody preserved)  
✅ **Structured Logging** - Full execution trace with confidence scores and token tracking  
✅ **Accuracy Scoring** - Benchmarking against ground truth  

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Find Evil! Agent                          │
│                   (Orchestration Loop)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ├──► Disk Analysis    ├─► MFT
                      │    (get_mft,       ├─► AmCache
                      │     get_amcache,   ├─► Prefetch
                      │     get_prefetch)  └─► Shimcache
                      │
                      ├──► Memory Analysis  ├─► Processes
                      │    (analyze_       ├─► Injections
                      │     processes,     └─► Network Conns
                      │     check_inject)
                      │
                      ├──► Log Analysis     ├─► Timeline
                      │    (extract_       ├─► Registry
                      │     timeline,      └─► EVTX
                      │     get_registry)
                      │
                      ├──► Self-Correction  ├─► Hallucination Detection
                      │    (Detect &        ├─► Confidence Reweighting
                      │     Fix Issues)     └─► Iterative Refinement
                      │
                      └──► Report Generation ─► JSON + Markdown
                           (Correlation,
                            Metrics)

┌─────────────────────────────────────────────────────────────┐
│                  MCP Server (Type-Safe)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ mcp_server/                                          │   │
│  │  ├─ server.py (MCP Protocol Handler)                │   │
│  │  └─ tools/                                           │   │
│  │     ├─ disk.py (Sleuth Kit + SIFT)                  │   │
│  │     ├─ memory.py (Volatility3)                      │   │
│  │     └─ logs.py (EvtxECmd + Plaso)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              SIFT Tools (Read-Only Execution)               │
│  • fls, icat, ils (Sleuth Kit)                              │
│  • Volatility3 (Memory Analysis)                            │
│  • EvtxECmd (Event Log Parsing)                             │
│  • Plaso/log2timeline (Timeline Extraction)                 │
│  • RegRipper (Registry Analysis)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
find-evil/
├── mcp_server/                 # MCP Server (Type-safe Tool Wrapper)
│   ├── __init__.py
│   ├── server.py              # MCP Protocol Implementation
│   └── tools/
│       ├── __init__.py
│       ├── disk.py            # Disk forensics (MFT, AmCache, etc.)
│       ├── memory.py          # Memory forensics (Volatility3)
│       └── logs.py            # Log analysis (EVTX, Timeline, Registry)
│
├── agent/                      # Main Agent Components
│   ├── __init__.py
│   ├── triage_agent.py        # Orchestration Loop
│   ├── self_correct.py        # Hallucination Detection & Correction
│   └── logger.py              # Structured JSON Logging
│
├── benchmarks/                 # Accuracy & Performance Reporting
│   ├── __init__.py
│   └── accuracy_report.py     # Score findings vs ground truth
│
├── case_data/                  # Case Artifact Directory
│   └── README.md              # Instructions for placing evidence
│
├── logs/                       # Execution Traces (auto-generated)
│   └── .gitkeep
│
├── exports/                    # Reports & Findings (auto-generated)
│   └── (reports saved here)
│
├── config.py                   # Central Configuration
├── main.py                     # CLI Entry Point
├── requirements.txt            # Python Dependencies
└── README.md                   # This file
```

---

## Setup Instructions

### Prerequisites

- **OS:** SANS SIFT Workstation (Ubuntu 22.04 LTS)
- **Python:** 3.10+
- **Memory:** 8GB+ RAM
- **Disk:** 50GB+ free space for artifacts and analysis

### Step 1: Clone/Extract Project

```bash
cd ~/Desktop
unzip find-evil.zip
cd find-evil
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Verify SIFT tools are available:

```bash
# Check Volatility3
python3 /opt/volatility3-2.20.0/vol.py --version

# Check Sleuth Kit
fls --version

# Check EvtxECmd
dotnet /opt/zimmermantools/EvtxeCmd/EvtxECmd.dll --version
```

### Step 4: Set Environment Variables (Optional)

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
export VOLATILITY_PROFILE="Win10"
export VERBOSE=true
```

---

## Usage

### Basic Usage

```bash
# Run triage with disk image and memory dump
python main.py \
  --case-data ./case_data \
  --image disk.dd \
  --memory memory.dmp \
  --verbose
```

### Advanced Options

```bash
# Generate both JSON and Markdown reports
python main.py \
  --case-data ./case_data \
  --image disk.dd \
  --memory memory.dmp \
  --report-format both \
  --max-iter 5 \
  --ground-truth ground_truth.json

# Save report to custom location
python main.py \
  --case-data ./case_data \
  --image disk.dd \
  --report /tmp/my_incident_report.json
```

### Output

Reports are generated in `./exports/`:

- **report.md** - Human-readable findings
- **report.json** - Machine-parsable findings with metadata
- **execution_trace_YYYYMMDD_HHMMSS.json** - Full agent execution log
- **iteration_NNN.json** - Per-iteration logs

---

## How Self-Correction Works

### Hallucination Detection

The agent detects potential hallucinations by checking for:

1. **Impossible Timestamps**
   - Future dates (after current time)
   - Pre-system-creation dates (before Jan 1, 2024)

2. **Contradictory Findings**
   - Same artifact with conflicting values (e.g., file size mismatch)
   - Duplicate entries with different metadata

3. **Tool Misuse**
   - EVTX parser applied to non-log files
   - Prefetch parser on registry hives
   - Shimcache on prefetch files

4. **Logical Inconsistencies**
   - Process with PPID > PID
   - Zero-size file with execution history
   - Invalid network ports (outside 1-65535)

### Correction Loop

When hallucinations are detected:

```
Finding with Confidence < 0.7
         ↓
Hallucination Detection (SelfCorrector.detect_hallucination)
         ↓
Correction Attempted (SelfCorrector.correct_finding)
         ↓
Confidence Reweighted (Reduced by 30% per attempt, max 3 attempts)
         ↓
Finding Marked for Manual Review if Confidence < 0.3
```

### Logging

Every correction attempt is logged with:
- Original confidence score
- Corrected confidence score
- Hallucination type detected
- Correction reasoning
- Before/after comparison

---

## Example Workflow

### 1. Disk Analysis Phase

```
Phase 1: Disk Analysis
  ├─ Extracting MFT (Master File Table)...
  ├─ Extracting AmCache (Application Cache)...
  ├─ Extracting Prefetch files...
  └─ Extracting Shimcache...

Findings: 4/4 high confidence
```

### 2. Memory Analysis Phase

```
Phase 2: Memory Analysis
  ├─ Analyzing Processes...
  ├─ Checking Code Injections...
  └─ Extracting Network Connections...

Findings: 3/3 high confidence
```

### 3. Log Analysis Phase

```
Phase 3: Log Analysis
  ├─ Extracting Timeline (Plaso)...
  └─ Extracting Registry Hives...

Findings: 2/2 high confidence
```

### 4. Self-Correction Phase

```
Phase 4: Self-Correction
  Iteration 1: 2 findings flagged for correction
    ├─ Hallucination: impossible_timestamp in MFT entry
    ├─ Correction: Confidence 0.65 → 0.35
    └─ Finding marked for manual review

  No more corrections needed.
```

### 5. Correlation & Reporting

```
Phase 5: Correlation
  ├─ Correlating 11 findings across domains
  ├─ Identifying threat patterns
  └─ Generating final report

FINDINGS SUMMARY:
  Total: 11
  High Confidence: 10
  Critical: 2
  
Execution Time: 42.3s
Tool Calls: 12
Corrections: 1
Hallucinations Detected: 1
```

---

## Submission Context: Find Evil! Hackathon

This project was built for the **SANS Find Evil! Hackathon**, challenging students to build innovative DFIR tools.

### Hackathon Goals Addressed

✅ **Problem:** Manual incident response is slow and error-prone  
✅ **Solution:** Autonomous agent that triages cases 24/7  

✅ **Problem:** AI hallucinations in security tools are dangerous  
✅ **Solution:** Built-in self-correction with confidence scoring  

✅ **Problem:** Tool integration is complex  
✅ **Solution:** MCP-wrapped SIFT tools with type safety  

✅ **Problem:** Tool outputs are inconsistent  
✅ **Solution:** Structured JSON returns with standardized schemas  

---

## Configuration

See [config.py](config.py) for all settings:

```python
MAX_CORRECTION_ATTEMPTS = 3       # Max self-correction retries
CONFIDENCE_THRESHOLD = 0.7        # Flag findings below this
MAX_ITERATIONS = 10               # Max triage iterations
MODEL = "claude-sonnet-4-20250514"  # LLM model
VOLATILITY_PROFILE = "auto"       # Memory profile (auto-detect)
```

---

## Troubleshooting

### "Volatility3 not found"

```bash
# Install Volatility3
pip install volatility3

# Or verify path
python3 /opt/volatility3-2.20.0/vol.py --version
```

### "EvtxECmd missing"

```bash
# Verify .NET runtime
dotnet --version

# Check path
dotnet /opt/zimmermantools/EvtxeCmd/EvtxECmd.dll --version
```

### "API key not found"

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### "Permission denied on evidence files"

The agent uses read-only mode (`'rb'`). Verify:
- Files are world-readable: `chmod 644 disk.dd`
- Running without sudo (not needed)
- No process holding exclusive lock on file

---

## Development

### Adding a New Tool

1. Create function in `mcp_server/tools/` (e.g., `tools/custom.py`)
2. Add to `mcp_server/tools/__init__.py`
3. Register in `mcp_server/server.py` (add to `ALL_TOOLS` list)
4. Import in `agent/triage_agent.py` and call

### Running Tests

```bash
# Unit tests (future)
pytest tests/

# Manual testing
python -c "from mcp_server.tools import get_mft; print(get_mft('test.dd'))"
```

---

## Performance Notes

- **Disk Analysis:** 5-30s per tool (depends on image size)
- **Memory Analysis:** 30-60s per tool (depends on dump size)
- **Log Analysis:** 60-300s (Plaso timeline generation)
- **Self-Correction:** <5s per iteration
- **Total:** 2-10 minutes for full triage (typical case)

Use `--max-iter` to limit correction iterations if speed is critical.

---

## Security & Privacy

- **Chain of Custody:** Never modifies evidence (read-only enforcement)
- **Logging:** All actions logged with timestamps (UTC)
- **Sanitization:** Redact PII in exported reports
- **API Keys:** Store in environment variables, never commit to repo
- **Sensitive Data:** Mark findings with high-confidence for manual review

---

## Contributing

For improvements or bug fixes:

1. Create feature branch: `git checkout -b feature/my-feature`
2. Add type hints and docstrings to all code
3. Test with sample case data
4. Submit pull request with detailed description

---

## License

Built for SANS Hackathon 2024  
Open for educational and authorized forensic analysis use only

---

## Contact & Support

- **Hackathon:** SANS FindEvil! 2024
- **SIFT VM:** https://www.sans.org/tools/sift-workstation/
- **MCP Spec:** https://modelcontextprotocol.io/
- **Volatility3:** https://github.com/volatilityfoundation/volatility3

---

## Changelog

### v1.0.0 (2024-01-15)

- ✨ Initial release
- 🚀 Disk, memory, log analysis
- 🔄 Self-correction loop
- 📊 Accuracy benchmarking
- 📝 Structured JSON logging

---

**Find Evil! - Making Incident Response Autonomous & Accurate**
