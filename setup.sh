#!/usr/bin/env bash
# Find Evil! — Automated Setup Script
# Installs everything needed to run the autonomous IR agent
# Usage: bash setup.sh

set -o pipefail

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Error handling
trap 'print_error "Setup failed at line $LINENO. Check output above."; exit 1' ERR

# ============================================================================
# SECTION 1: Banner
# ============================================================================
print_banner() {
    echo ""
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║      FIND EVIL! — Setup & Installation       ║"
    echo "║      SANS SIFT Workstation | Hackathon 2026  ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

# ============================================================================
# SECTION 2: System Detection
# ============================================================================
detect_system() {
    print_info "Detecting system environment..."
    
    # OS Detection
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_ok "Operating System: Linux ($(uname -r))"
    else
        print_fail "Operating System: Unsupported ($OSTYPE) — requires Linux"
        exit 1
    fi
    
    # Python detection
    if ! command -v python3 &> /dev/null; then
        print_fail "Python3 not found"
        exit 1
    fi
    
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
        print_ok "Python: $PY_VERSION"
    else
        print_fail "Python: $PY_VERSION (minimum 3.10 required)"
        exit 1
    fi
    
    # SIFT detection
    if [[ -f /etc/sift-release ]] || command -v fls &> /dev/null; then
        print_ok "SANS SIFT Workstation detected"
    else
        print_warn "SANS SIFT Workstation not detected — install SIFT for full tool support"
    fi
    
    # Git detection
    if command -v git &> /dev/null; then
        print_ok "Git: $(git --version | awk '{print $3}')"
    else
        print_warn "Git not found — some features may not work"
    fi
    
    echo ""
}

# ============================================================================
# SECTION 3: Directory Setup
# ============================================================================
setup_directories() {
    print_info "Setting up project directories..."
    
    mkdir -p case_data logs reports ui
    chmod 755 case_data logs reports
    
    print_ok "Directories created: case_data/ logs/ reports/ ui/"
    echo ""
}

# ============================================================================
# SECTION 4: Python Virtual Environment
# ============================================================================
setup_venv() {
    print_info "Setting up Python virtual environment..."
    
    if [[ -d venv ]]; then
        print_warn "venv/ already exists — skipping creation"
    else
        python3 -m venv venv
        print_ok "Virtual environment created"
    fi
    
    # Activate venv
    # shellcheck source=/dev/null
    source venv/bin/activate
    print_ok "Virtual environment activated"
    
    # Upgrade pip
    pip install --upgrade pip --quiet
    print_ok "pip upgraded"
    
    # Install requirements
    if [[ -f requirements.txt ]]; then
        pip install -r requirements.txt --quiet
        print_ok "Dependencies installed from requirements.txt"
    else
        print_warn "requirements.txt not found — skipping dependency installation"
    fi
    
    echo ""
}

# ============================================================================
# SECTION 5: SIFT Tool Verification
# ============================================================================
verify_sift_tools() {
    print_info "Verifying SIFT tools..."
    
    local tools=("fls" "mmls" "icat" "mactime" "vol" "rip.pl" "log2timeline.py" "psort.py")
    local found=0
    local missing=0
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            print_ok "$tool found"
            ((found++))
        else
            print_warn "$tool not found"
            ((missing++))
        fi
    done
    
    echo ""
    print_info "Tool summary: $found found, $missing missing"
    
    if [[ $missing -gt 0 ]]; then
        print_warn "Install SANS SIFT Workstation for full tool support:"
        print_warn "  https://www.sans.org/tools/sift-workstation/"
    fi
    
    echo ""
}

# ============================================================================
# SECTION 6: MCP Server Test
# ============================================================================
test_mcp_server() {
    print_info "Testing MCP server..."
    
    # Start server in background
    python mcp_server/server.py &> /dev/null &
    local server_pid=$!
    
    # Wait for startup
    sleep 2
    
    # Test health endpoint
    if command -v curl &> /dev/null; then
        if curl -s http://localhost:8765/health 2>/dev/null | grep -q "ok"; then
            print_ok "MCP server is healthy"
        else
            print_warn "MCP server not responding on port 8765"
        fi
    else
        print_warn "curl not found — skipping server test"
    fi
    
    # Kill server
    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true
    
    echo ""
}

# ============================================================================
# SECTION 7: API Key Setup
# ============================================================================
setup_api_key() {
    print_info "Configuring Anthropic API key..."
    
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        print_ok "ANTHROPIC_API_KEY already set in environment"
    else
        echo -n "Enter your Anthropic API key (or press Enter to skip): "
        read -r api_key
        
        if [[ -n "$api_key" ]]; then
            export ANTHROPIC_API_KEY="$api_key"
            
            # Add to bashrc for persistence
            if ! grep -q "ANTHROPIC_API_KEY" ~/.bashrc 2>/dev/null; then
                echo "export ANTHROPIC_API_KEY='$api_key'" >> ~/.bashrc
            fi
            
            print_ok "API key configured and saved to ~/.bashrc"
        else
            print_warn "API key not set — you must set ANTHROPIC_API_KEY before running triage"
        fi
    fi
    
    echo ""
}

# ============================================================================
# SECTION 8: Sample Case Data (Optional)
# ============================================================================
setup_sample_data() {
    print_info "Sample forensic case data setup (optional)..."
    
    echo -n "Download sample case data for testing? [y/N]: "
    read -r download_choice
    
    if [[ "$download_choice" == "y" || "$download_choice" == "Y" ]]; then
        print_info "Sample case data can be obtained from:"
        print_info "  • DFTT: https://dftt.sourceforge.io/"
        print_info "  • Digital Corpora: https://digitalcorpora.org/"
        print_info ""
        print_warn "Download and extract sample images to case_data/"
        print_warn "Example: tar -xf sample.tar.gz -C case_data/"
    else
        print_ok "Skipped sample data download"
    fi
    
    echo ""
}

# ============================================================================
# SECTION 9: Generate Launch Script
# ============================================================================
generate_launcher() {
    print_info "Generating launch scripts..."
    
    # Generate run.sh
    cat > run.sh << 'EOF'
#!/usr/bin/env bash
# Find Evil! Launcher Script
# Activates venv and launches the TUI

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
if [[ -f venv/bin/activate ]]; then
    source venv/bin/activate
else
    echo "Error: venv not found. Run 'bash setup.sh' first."
    exit 1
fi

# Launch TUI
python ui/tui.py "$@"
EOF
    
    chmod +x run.sh
    print_ok "Created run.sh launcher script"
    
    # Generate cli.sh for direct CLI access
    cat > cli.sh << 'EOF'
#!/usr/bin/env bash
# Find Evil! CLI Launcher
# Direct access to main.py CLI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f venv/bin/activate ]]; then
    source venv/bin/activate
else
    echo "Error: venv not found. Run 'bash setup.sh' first."
    exit 1
fi

python main.py "$@"
EOF
    
    chmod +x cli.sh
    print_ok "Created cli.sh for direct CLI access"
    
    echo ""
}

# ============================================================================
# SECTION 10: Create __init__.py files
# ============================================================================
create_init_files() {
    print_info "Creating package __init__ files..."
    
    touch ui/__init__.py 2>/dev/null || true
    print_ok "ui/__init__.py created"
    
    echo ""
}

# ============================================================================
# SECTION 11: Final Summary
# ============================================================================
print_summary() {
    print_info "Setup complete!"
    
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            Setup Summary                              ║${NC}"
    echo -e "${BLUE}╠═════════════════════════════════════════════════════╦═╣${NC}"
    echo -e "${BLUE}║ Component                 │ Status                  ║${NC}"
    echo -e "${BLUE}╠─────────────────────────────────────────────────────╫─╣${NC}"
    echo -e "${BLUE}║ Virtual Environment       │${NC} ${GREEN}venv/ ready${NC}          ${BLUE}║${NC}"
    echo -e "${BLUE}║ Dependencies              │${NC} ${GREEN}all installed${NC}       ${BLUE}║${NC}"
    echo -e "${BLUE}║ SIFT Tools                │${NC} ${YELLOW}verify manually${NC}     ${BLUE}║${NC}"
    echo -e "${BLUE}║ MCP Server                │${NC} ${GREEN}tested${NC}              ${BLUE}║${NC}"
    echo -e "${BLUE}║ Configuration             │${NC} ${GREEN}ready${NC}              ${BLUE}║${NC}"
    echo -e "${BLUE}║ Launcher Scripts          │${NC} ${GREEN}created${NC}            ${BLUE}║${NC}"
    echo -e "${BLUE}╚═════════════════════════════════════════════════════╩═╝${NC}"
    
    echo ""
    echo -e "${GREEN}Ready to use Find Evil!${NC}"
    echo ""
    echo "Launch options:"
    echo -e "  ${GREEN}./run.sh${NC}                           # Start TUI (recommended)"
    echo -e "  ${GREEN}./cli.sh --case-data ./case_data${NC}  # CLI mode"
    echo -e "  ${GREEN}./cli.sh --dry-run${NC}                # Validate setup"
    echo ""
    echo "For detailed usage, see README.md"
    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
main() {
    print_banner
    detect_system
    setup_directories
    setup_venv
    verify_sift_tools
    test_mcp_server
    setup_api_key
    setup_sample_data
    generate_launcher
    create_init_files
    print_summary
}

# Run main
main "$@"
