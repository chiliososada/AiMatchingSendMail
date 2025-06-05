# supabase_diagnostic.py - Supabase数据库连接诊断工具
import asyncio
import asyncpg
import socket
import ssl
import subprocess
import requests
import time
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
import logging
import json
import os
import dns.resolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SupabaseDiagnostic:
    """Supabase数据库连接诊断工具"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.parsed_url = urlparse(database_url)
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or 5432
        self.username = self.parsed_url.username
        self.password = self.parsed_url.password
        self.database = self.parsed_url.path[1:] if self.parsed_url.path else "postgres"

        logger.info(f"Supabase连接信息:")
        logger.info(f"  主机: {self.host}")
        logger.info(f"  端口: {self.port}")
        logger.info(f"  用户: {self.username}")
        logger.info(f"  数据库: {self.database}")

    def check_internet_connectivity(self) -> Dict[str, Any]:
        """检查互联网连接"""
        print("🌐 检查互联网连接...")

        test_sites = [
            "https://google.com",
            "https://supabase.com",
            "https://aws.amazon.com",
            "https://cloudflare.com",
        ]

        results = {}
        working_sites = 0

        for site in test_sites:
            try:
                response = requests.get(site, timeout=10)
                if response.status_code == 200:
                    results[site] = "✅ 连接正常"
                    working_sites += 1
                else:
                    results[site] = f"⚠️ HTTP {response.status_code}"
            except requests.exceptions.RequestException as e:
                results[site] = f"❌ 连接失败: {str(e)}"

        if working_sites > 0:
            print("✅ 互联网连接正常")
            return {"status": "success", "details": results}
        else:
            print("❌ 互联网连接异常")
            return {"status": "error", "details": results}

    def check_dns_resolution(self) -> Dict[str, Any]:
        """检查DNS解析"""
        print(f"🔍 检查DNS解析: {self.host}")

        results = {
            "hostname": self.host,
            "ip_addresses": [],
            "dns_servers": [],
            "resolution_time": 0,
            "status": "unknown",
        }

        try:
            # 获取系统DNS服务器
            try:
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            dns_server = line.split()[1]
                            results["dns_servers"].append(dns_server)
            except:
                pass

            # 测试DNS解析时间
            start_time = time.time()
            ip_addresses = socket.gethostbyname_ex(self.host)[2]
            end_time = time.time()

            results["ip_addresses"] = ip_addresses
            results["resolution_time"] = round((end_time - start_time) * 1000, 2)
            results["status"] = "success"

            print(f"✅ DNS解析成功:")
            print(f"  IP地址: {', '.join(ip_addresses)}")
            print(f"  解析时间: {results['resolution_time']}ms")

            return results

        except socket.gaierror as e:
            print(f"❌ DNS解析失败: {e}")
            results["status"] = "error"
            results["error"] = str(e)

            # 尝试使用不同的DNS服务器
            alternative_dns = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]
            print("🔄 尝试使用公共DNS服务器...")

            for dns_server in alternative_dns:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = [dns_server]
                    answer = resolver.resolve(self.host, "A")

                    ips = [str(rdata) for rdata in answer]
                    print(f"✅ 使用 {dns_server} 解析成功: {', '.join(ips)}")
                    results["alternative_resolution"] = {
                        "dns_server": dns_server,
                        "ip_addresses": ips,
                    }
                    break
                except Exception as dns_e:
                    print(f"❌ 使用 {dns_server} 解析失败: {dns_e}")

            return results

    def check_network_connectivity(self) -> Dict[str, Any]:
        """检查网络连通性"""
        print(f"🔌 检查网络连通性: {self.host}:{self.port}")

        results = {
            "host": self.host,
            "port": self.port,
            "tcp_connect": False,
            "ssl_connect": False,
            "ping_result": None,
            "traceroute_result": None,
            "connection_time": 0,
        }

        # 1. TCP连接测试
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((self.host, self.port))
            end_time = time.time()
            sock.close()

            if result == 0:
                results["tcp_connect"] = True
                results["connection_time"] = round((end_time - start_time) * 1000, 2)
                print(f"✅ TCP连接成功 ({results['connection_time']}ms)")
            else:
                print(f"❌ TCP连接失败 (错误码: {result})")

        except Exception as e:
            print(f"❌ TCP连接测试失败: {e}")

        # 2. SSL连接测试（Supabase使用SSL）
        if results["tcp_connect"]:
            try:
                context = ssl.create_default_context()
                with socket.create_connection(
                    (self.host, self.port), timeout=10
                ) as sock:
                    with context.wrap_socket(sock, server_hostname=self.host) as ssock:
                        cert = ssock.getpeercert()
                        results["ssl_connect"] = True
                        results["ssl_cert_subject"] = cert.get("subject", "")
                        print("✅ SSL连接成功")
            except Exception as e:
                print(f"❌ SSL连接失败: {e}")

        # 3. Ping测试
        try:
            ping_result = subprocess.run(
                ["ping", "-c", "3", self.host],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if ping_result.returncode == 0:
                # 提取平均延迟
                output = ping_result.stdout
                if "avg" in output:
                    avg_line = [line for line in output.split("\n") if "avg" in line]
                    if avg_line:
                        results["ping_result"] = avg_line[0].strip()
                        print(f"✅ Ping成功: {results['ping_result']}")
                else:
                    results["ping_result"] = "成功"
                    print("✅ Ping成功")
            else:
                print("❌ Ping失败")
        except Exception as e:
            print(f"❌ Ping测试失败: {e}")

        return results

    def check_supabase_status(self) -> Dict[str, Any]:
        """检查Supabase服务状态"""
        print("📊 检查Supabase服务状态...")

        results = {"status_page": None, "api_health": None, "region_status": None}

        # 1. 检查Supabase状态页面
        try:
            response = requests.get(
                "https://status.supabase.com/api/v2/status.json", timeout=10
            )
            if response.status_code == 200:
                status_data = response.json()
                results["status_page"] = status_data.get("status", {})
                print(
                    f"✅ Supabase整体状态: {status_data.get('status', {}).get('description', '未知')}"
                )
            else:
                print("⚠️ 无法获取Supabase状态")
        except Exception as e:
            print(f"❌ 检查Supabase状态失败: {e}")

        # 2. 检查区域状态（从主机名推断区域）
        if "ap-northeast-1" in self.host:
            region = "亚太东北1区 (东京)"
        elif "us-east-1" in self.host:
            region = "美国东部1区"
        elif "eu-west-1" in self.host:
            region = "欧洲西部1区"
        else:
            region = "未知区域"

        results["region"] = region
        print(f"📍 数据库区域: {region}")

        # 3. 尝试访问Supabase管理API
        try:
            # 提取项目ID（如果可能）
            if "utkxuvldiveojhnzfsca" in self.host:
                project_id = "utkxuvldiveojhnzfsca"
                print(f"📋 项目ID: {project_id}")
                results["project_id"] = project_id
        except:
            pass

        return results

    async def test_database_connection(self) -> Dict[str, Any]:
        """测试数据库连接"""
        print("🗄️ 测试Supabase数据库连接...")

        results = {
            "connection_success": False,
            "connection_time": 0,
            "server_version": None,
            "database_info": None,
            "error": None,
        }

        try:
            start_time = time.time()

            # 尝试连接数据库
            conn = await asyncpg.connect(
                self.database_url, timeout=30, command_timeout=10  # 增加超时时间
            )

            end_time = time.time()
            results["connection_time"] = round((end_time - start_time) * 1000, 2)

            # 获取服务器信息
            version = await conn.fetchval("SELECT version()")
            results["server_version"] = version

            # 获取数据库信息
            db_info = await conn.fetchrow(
                """
                SELECT 
                    current_database() as database_name,
                    current_user as current_user,
                    inet_server_addr() as server_ip,
                    inet_server_port() as server_port
            """
            )

            results["database_info"] = dict(db_info)
            results["connection_success"] = True

            await conn.close()

            print("✅ 数据库连接成功!")
            print(f"  连接时间: {results['connection_time']}ms")
            print(f"  服务器版本: {version}")
            print(f"  数据库: {db_info['database_name']}")
            print(f"  当前用户: {db_info['current_user']}")

            return results

        except asyncpg.InvalidAuthorizationSpecificationError as e:
            error_msg = "认证失败 - 用户名或密码错误"
            print(f"❌ {error_msg}: {e}")
            results["error"] = error_msg
            results["error_detail"] = str(e)

        except asyncpg.InvalidCatalogNameError as e:
            error_msg = "数据库不存在"
            print(f"❌ {error_msg}: {e}")
            results["error"] = error_msg
            results["error_detail"] = str(e)

        except asyncpg.ConnectionDoesNotExistError as e:
            error_msg = "连接不存在或已断开"
            print(f"❌ {error_msg}: {e}")
            results["error"] = error_msg
            results["error_detail"] = str(e)

        except Exception as e:
            error_msg = f"连接失败: {str(e)}"
            print(f"❌ {error_msg}")
            results["error"] = error_msg
            results["error_detail"] = str(e)

        return results

    def test_alternative_connections(self) -> List[Dict[str, Any]]:
        """测试备用连接方式"""
        print("🔄 测试备用连接方式...")

        # 生成不同的连接URL
        alternative_urls = []

        # 1. 使用IP地址而不是域名（如果DNS解析成功）
        dns_result = self.check_dns_resolution()
        if dns_result.get("status") == "success" and dns_result.get("ip_addresses"):
            for ip in dns_result["ip_addresses"]:
                alt_url = self.database_url.replace(self.host, ip)
                alternative_urls.append(
                    {
                        "name": f"直接IP连接 ({ip})",
                        "url": alt_url,
                        "description": "使用IP地址绕过DNS解析",
                    }
                )

        # 2. 使用不同的连接参数
        base_url = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

        connection_options = [
            {
                "name": "增加超时时间",
                "url": base_url + "?connect_timeout=30&command_timeout=30",
                "description": "增加连接和命令超时时间",
            },
            {
                "name": "SSL模式调整",
                "url": base_url + "?sslmode=require",
                "description": "明确要求SSL连接",
            },
            {
                "name": "应用名称设置",
                "url": base_url + "?application_name=EmailAPI&connect_timeout=30",
                "description": "设置应用名称和超时",
            },
        ]

        alternative_urls.extend(connection_options)

        return alternative_urls

    def generate_fix_suggestions(self, diagnostic_results: Dict[str, Any]) -> List[str]:
        """生成修复建议"""
        suggestions = []

        # 检查互联网连接
        if diagnostic_results.get("internet", {}).get("status") == "error":
            suggestions.extend(
                [
                    "🌐 网络连接问题:",
                    "  1. 检查网络连接是否正常",
                    "  2. 检查防火墙设置",
                    "  3. 检查代理配置",
                    "  4. 尝试使用移动热点测试",
                ]
            )

        # 检查DNS解析
        dns_result = diagnostic_results.get("dns", {})
        if dns_result.get("status") == "error":
            suggestions.extend(
                [
                    "🔍 DNS解析问题:",
                    "  1. 更换DNS服务器 (8.8.8.8, 1.1.1.1)",
                    "  2. 清空DNS缓存: sudo dscacheutil -flushcache (macOS)",
                    "  3. 或: sudo systemctl restart systemd-resolved (Linux)",
                    "  4. 检查网络防火墙和路由器设置",
                ]
            )

            # 如果有备用DNS解析成功，建议使用IP
            if dns_result.get("alternative_resolution"):
                ip_addresses = dns_result["alternative_resolution"]["ip_addresses"]
                suggestions.append(f"  5. 临时使用IP地址: {', '.join(ip_addresses)}")

        # 检查网络连通性
        network_result = diagnostic_results.get("network", {})
        if not network_result.get("tcp_connect"):
            suggestions.extend(
                [
                    "🔌 网络连通性问题:",
                    "  1. 检查防火墙是否阻止5432端口",
                    "  2. 检查公司网络是否限制外部数据库连接",
                    "  3. 尝试使用VPN或不同网络环境",
                    "  4. 联系网络管理员",
                ]
            )

        # 检查数据库连接
        db_result = diagnostic_results.get("database", {})
        if not db_result.get("connection_success"):
            error = db_result.get("error", "")
            if "认证失败" in error:
                suggestions.extend(
                    [
                        "🔐 认证问题:",
                        "  1. 检查Supabase项目设置中的数据库密码",
                        "  2. 重置数据库密码",
                        "  3. 确认用户名是否正确 (通常是postgres)",
                        "  4. 检查URL中的特殊字符是否需要编码",
                    ]
                )
            elif "数据库不存在" in error:
                suggestions.extend(
                    [
                        "🗄️ 数据库问题:",
                        "  1. 检查数据库名称是否正确",
                        "  2. 确认Supabase项目是否正常",
                        "  3. 检查项目是否被暂停或删除",
                    ]
                )

        # Supabase特定建议
        supabase_result = diagnostic_results.get("supabase", {})
        suggestions.extend(
            [
                "🚀 Supabase特定建议:",
                "  1. 检查Supabase控制台项目状态",
                "  2. 确认项目没有被暂停",
                "  3. 检查数据库连接字符串是否最新",
                "  4. 考虑使用连接池模式 (pooler)",
                "  5. 访问 https://app.supabase.com 检查项目状态",
            ]
        )

        # 环境变量建议
        suggestions.extend(
            [
                "⚙️ 配置建议:",
                "  1. 检查.env文件中DATABASE_URL格式",
                "  2. 确认没有多余的空格或换行符",
                "  3. 考虑设置连接池参数",
                "  4. 增加连接超时时间",
            ]
        )

        return suggestions

    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """运行完整诊断"""
        print("=" * 70)
        print("🔍 Supabase数据库连接诊断开始")
        print(f"📋 目标: {self.host}")
        print("=" * 70)

        results = {
            "database_url": self.database_url,
            "host": self.host,
            "timestamp": time.time(),
            "checks": {},
        }

        # 1. 互联网连接检查
        print("\n1️⃣ 检查互联网连接...")
        results["checks"]["internet"] = self.check_internet_connectivity()

        # 2. DNS解析检查
        print("\n2️⃣ 检查DNS解析...")
        results["checks"]["dns"] = self.check_dns_resolution()

        # 3. 网络连通性检查
        print("\n3️⃣ 检查网络连通性...")
        results["checks"]["network"] = self.check_network_connectivity()

        # 4. Supabase状态检查
        print("\n4️⃣ 检查Supabase服务状态...")
        results["checks"]["supabase"] = self.check_supabase_status()

        # 5. 数据库连接测试
        print("\n5️⃣ 测试数据库连接...")
        results["checks"]["database"] = await self.test_database_connection()

        # 6. 生成备用连接方案
        print("\n6️⃣ 生成备用连接方案...")
        results["alternatives"] = self.test_alternative_connections()

        # 7. 生成修复建议
        print("\n7️⃣ 生成修复建议...")
        results["suggestions"] = self.generate_fix_suggestions(results["checks"])

        return results

    def print_results(self, results: Dict[str, Any]):
        """打印诊断结果"""
        print("\n" + "=" * 70)
        print("📊 Supabase诊断结果总结")
        print("=" * 70)

        checks = results.get("checks", {})

        # 状态总览
        print("\n📋 检查状态:")
        for check_name, check_result in checks.items():
            if isinstance(check_result, dict):
                if check_result.get("status") == "success" or check_result.get(
                    "connection_success"
                ):
                    print(f"  ✅ {check_name}: 正常")
                elif check_result.get("status") == "error" or check_result.get("error"):
                    print(f"  ❌ {check_name}: 异常")
                else:
                    print(f"  ⚠️ {check_name}: 部分异常")

        # 备用方案
        alternatives = results.get("alternatives", [])
        if alternatives:
            print("\n🔄 备用连接方案:")
            for i, alt in enumerate(alternatives, 1):
                print(f"  {i}. {alt['name']}")
                print(f"     {alt['description']}")

        # 修复建议
        print("\n💡 修复建议:")
        for suggestion in results.get("suggestions", []):
            print(suggestion)

        print("\n" + "=" * 70)


async def main():
    """主函数"""
    # Supabase数据库URL
    database_url = "postgresql://postgres.utkxuvldiveojhnzfsca:1994Lzy.@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

    print("🚀 Supabase数据库连接诊断工具")
    print(f"🎯 目标数据库: {urlparse(database_url).hostname}")

    diagnostic = SupabaseDiagnostic(database_url)
    results = await diagnostic.run_full_diagnostic()
    diagnostic.print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
