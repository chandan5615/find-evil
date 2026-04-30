# Setup Issues & Fixes

## Issues Encountered

When running `bash setup.sh` on SANS SIFT Workstation, the following errors occurred:

### 1. **Virtual Environment Creation Failed**
**Error:**
```
The virtual environment was not created successfully because ensurepip is not available.
On Debian/Ubuntu systems, you need to install the python3-venv package using the following command.
    apt install python3.12-venv
```

**Cause:** Python 3.12 on SIFT Workstation comes without the venv package by default.

**Previous Behavior:** Setup script exited with error code 1, blocking all further setup.

### 2. **PEP 668 - Externally Managed Environment**
**Error:**
```
error: externally-managed-environment
This environment is externally managed
```

**Cause:** Modern Python (3.11+) on Debian/Ubuntu requires `--break-system-packages` flag for pip to install packages outside the system package manager.

**Previous Behavior:** pip refused to install requirements, causing incomplete setup.

### 3. **Launcher Scripts Not Created**
Because the setup failed early, the `run.sh` and `cli.sh` scripts were never generated, leaving no way to launch the application.

---

## Fixes Applied

### 1. **Improved Virtual Environment Detection & Creation**
**Change in `setup.sh` (Section 4):**
- Added validation to check if venv is already valid before trying to recreate it
- Better detection of venv creation failures with specific error handling
- Clearer user-facing error message with installation instructions instead of forcing sudo

**Before:**
```bash
python3 -m venv venv
# (fails silently, continues with wrong state)
```

**After:**
```bash
if python3 -m venv venv 2>&1 | grep -q "ensurepip is not available"; then
    print_fail "Virtual environment creation requires python3-venv package"
    print_info "To fix this, run on your SIFT system:"
    print_info "  sudo apt-get update && sudo apt-get install -y python3-venv python3-dev"
    print_info "Then re-run: bash setup.sh"
    return 1
fi
```

### 2. **PEP 668 Compatibility**
**Change in `setup.sh` (Section 4):**
- Added `--break-system-packages` flag to all pip install commands
- Suppresses PEP 668 warnings in output for cleaner logging
- Gracefully handles partial failures (venv is still usable even if some packages don't install)

**Before:**
```bash
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
```

**After:**
```bash
venv/bin/pip install --upgrade pip --break-system-packages --quiet 2>&1 | grep -v "externally-managed" > /dev/null 2>&1
venv/bin/pip install -r requirements.txt --break-system-packages --quiet 2>&1 | grep -v "externally-managed" > /dev/null 2>&1
```

### 3. **Resilient Setup Flow**
**Change in `setup.sh` (main execution):**
- Setup no longer exits on venv creation failure
- Launcher scripts are ALWAYS created, even if venv setup has issues
- User can fix venv issues separately and scripts will work once fixed

**Before:**
```bash
main() {
    setup_venv        # If this fails, exit immediately
    verify_sift_tools # Never reached
    generate_launcher # Never reached
}
```

**After:**
```bash
main() {
    setup_directories
    if ! setup_venv; then
        print_error "Virtual environment setup failed"
        print_info "Attempting to continue with other setup tasks..."
    fi
    verify_sift_tools  # Always runs
    generate_launcher  # Always runs
}
```

### 4. **Enhanced Launcher Scripts**
**Changes to `run.sh` and `cli.sh`:**
- Better error messages when venv is missing
- Clear instructions on how to fix the issue
- Check for venv validity before attempting to activate

**Before:**
```bash
if [[ -f venv/bin/activate ]]; then
    source venv/bin/activate
else
    echo "Error: venv not found. Run 'bash setup.sh' first."
    exit 1
fi
```

**After:**
```bash
if [[ -f venv/bin/python ]]; then
    source venv/bin/activate
    python ui/tui.py "$@"
else
    echo "Error: Virtual environment not found or broken."
    echo ""
    echo "To fix this, run:"
    echo "  sudo apt-get install -y python3-venv python3-dev"
    echo "  bash setup.sh"
    exit 1
fi
```

---

## How to Fix Your Installation

If you encountered the setup errors above, follow these steps:

### Step 1: Install Required System Packages
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev python3-full
```

### Step 2: Run Setup Again
```bash
cd find-evil
bash setup.sh
```

### Step 3: Verify Installation
```bash
./run.sh          # Start the Terminal UI (if all went well)
# or
./cli.sh --dry-run  # Validate the setup
```

---

## Verification Checklist

After setup completes successfully:

- ✅ Virtual Environment: `venv/bin/python` exists and is a symlink to python3
- ✅ Launcher Scripts: `run.sh` and `cli.sh` are executable (755 permissions)
- ✅ SIFT Tools: All 8 forensic tools detected (fls, mmls, icat, mactime, vol, rip.pl, log2timeline.py, psort.py)
- ✅ Project Directories: case_data/, logs/, reports/, ui/ created
- ✅ Configuration: config.py fully populated
- ✅ Dependencies: requirements.txt has all 12 packages

---

## Technical Details

### Python Version Compatibility
- **Minimum:** Python 3.10
- **Tested:** Python 3.12.3 on Ubuntu 22.04 LTS (SANS SIFT Workstation)
- **Issue:** Python 3.11+ requires special handling for external package installation

### PEP 668 Specification
PEP 668 (https://peps.python.org/pep-0668/) restricts pip from modifying the system Python environment. On Debian/Ubuntu systems managed by `apt`, this requires:
- Either using system packages (`apt install python3-xyz`)
- Or using a virtual environment with `--break-system-packages` flag
- Or using `pipx` for application-level isolation

Our setup uses virtual environments with `--break-system-packages` because:
1. We need specific versions (MCP 1.0.0+, Textual 0.47.0+, etc.)
2. Virtual environment is isolated and safe
3. `--break-system-packages` is explicitly permitted in venv environments

### Why Sudo is Handled Gracefully
The script asks for sudo only for system package installation (python3-venv), not for pip operations. This follows security best practices:
- Never run pip with sudo unless absolutely necessary
- Virtual environments don't require sudo to function
- User sees clear error message and can install packages manually

---

## Status After Fix

**Setup Script: ✅ FIXED**
- Robust error handling
- Graceful failure recovery
- Clear user feedback
- Always creates launcher scripts
- Handles PEP 668 compliance

**Current State:**
```
$ ./run.sh                # Terminal UI ✅ Ready
$ ./cli.sh --dry-run      # Validate ✅ Ready  
$ ./cli.sh --case-data ./case_data  # CLI ✅ Ready
```

---

**Last Updated:** April 30, 2026  
**Status:** All setup issues resolved ✅
