# app/api/diagnostic_routes.py - 邮件诊断API
from fastapi import APIRouter, HTTPException, status
from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
from datetime import datetime, timedelta
import socket
import dns.resolver

from ..database import fetch_one, fetch_all
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/email-delivery/{queue_id}")
async def get_email_delivery_details(queue_id: UUID, tenant_id: UUID):
    """获取邮件投递详情"""
    try:
        # 查询队列信息
        queue_info = await fetch_one(
            """
            SELECT q.*, s.smtp_host, s.smtp_port, s.from_email, s.security_protocol
            FROM email_sending_queue q
            LEFT JOIN email_smtp_settings s ON q.smtp_setting_id = s.id
            WHERE q.id = $1 AND q.tenant_id = $2
            """,
            queue_id,
            tenant_id,
        )

        if not queue_info:
            raise HTTPException(status_code=404, detail="邮件记录不存在")

        # 查询日志信息
        logs = await fetch_all(
            """
            SELECT * FROM email_sending_logs 
            WHERE queue_id = $1 
            ORDER BY logged_at DESC
            """,
            queue_id,
        )

        # 分析投递状态
        delivery_analysis = await analyze_delivery_issues(queue_info, logs)

        return {
            "queue_info": dict(queue_info),
            "logs": [dict(log) for log in logs],
            "delivery_analysis": delivery_analysis,
            "troubleshooting": get_troubleshooting_steps(queue_info),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件投递详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email-health-check")
async def email_health_check(tenant_id: UUID):
    """邮件系统健康检查"""
    try:
        # 检查最近24小时的发送情况
        yesterday = datetime.utcnow() - timedelta(hours=24)

        stats = await fetch_one(
            """
            SELECT 
                COUNT(*) as total_sent,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status IN ('queued', 'sending') THEN 1 ELSE 0 END) as pending
            FROM email_sending_queue 
            WHERE tenant_id = $1 AND created_at >= $2
            """,
            tenant_id,
            yesterday,
        )

        # 检查SMTP设置
        smtp_settings = await fetch_all(
            """
            SELECT setting_name, smtp_host, connection_status, last_test_at, is_active
            FROM email_smtp_settings 
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY is_default DESC
            """,
            tenant_id,
        )

        # 检查常见问题
        common_issues = await check_common_issues(tenant_id)

        return {
            "stats": dict(stats) if stats else {},
            "smtp_settings": [dict(s) for s in smtp_settings],
            "common_issues": common_issues,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"邮件健康检查失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-delivery/{email}")
async def test_email_delivery(email: str, tenant_id: UUID):
    """测试邮件投递能力"""
    try:
        # 分析目标邮箱
        domain = email.split("@")[1]
        domain_analysis = await analyze_email_domain(domain)

        # 发送测试邮件
        email_service = EmailService()

        # 获取默认SMTP设置
        smtp_settings = await email_service.get_smtp_settings(tenant_id)
        if not smtp_settings:
            raise HTTPException(status_code=400, detail="未找到可用的SMTP设置")

        # 发送优化的测试邮件
        result = await send_optimized_test_email(
            email_service, smtp_settings, email, tenant_id
        )

        return {
            "test_result": result,
            "domain_analysis": domain_analysis,
            "recommendations": get_delivery_recommendations(domain, result),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试邮件投递失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def analyze_delivery_issues(queue_info: Dict, logs: List[Dict]) -> Dict[str, Any]:
    """分析投递问题"""
    issues = []
    recommendations = []

    # 检查发送时间
    if queue_info.get("sent_at"):
        sent_time = queue_info["sent_at"]
        if isinstance(sent_time, str):
            sent_time = datetime.fromisoformat(sent_time.replace("Z", "+00:00"))

        time_since_sent = (
            datetime.utcnow() - sent_time.replace(tzinfo=None)
        ).total_seconds()

        if time_since_sent < 300:  # 5分钟内
            issues.append("邮件刚发送，可能还在投递中")
            recommendations.append("等待5-10分钟后再检查")
        elif time_since_sent > 3600:  # 1小时后还没收到
            issues.append("邮件发送超过1小时，可能被拦截")
            recommendations.append("检查垃圾邮件文件夹")

    # 检查收件人域名
    to_emails = queue_info.get("to_emails", [])
    if to_emails:
        domain = to_emails[0].split("@")[1] if "@" in to_emails[0] else ""
        if domain in ["gmail.com", "googlemail.com"]:
            issues.append("Gmail有严格的垃圾邮件过滤")
            recommendations.extend(
                [
                    "检查Gmail的垃圾邮件文件夹",
                    "检查推广邮件选项卡",
                    "将发件人添加到联系人",
                ]
            )
        elif domain in ["qq.com", "163.com", "126.com"]:
            issues.append("国内邮箱服务商过滤较严")
            recommendations.extend(["检查垃圾邮件文件夹", "检查拦截邮件设置"])

    # 检查SMTP配置
    if queue_info.get("smtp_host"):
        if "gmail.com" in queue_info["smtp_host"]:
            recommendations.append("使用Gmail SMTP时确保使用应用专用密码")

    return {
        "issues_found": issues,
        "recommendations": recommendations,
        "severity": "high" if len(issues) > 2 else "medium" if issues else "low",
    }


async def analyze_email_domain(domain: str) -> Dict[str, Any]:
    """分析邮箱域名配置"""
    analysis = {
        "domain": domain,
        "mx_records": [],
        "has_spf": False,
        "has_dmarc": False,
        "reputation": "unknown",
    }

    try:
        # 查询MX记录
        mx_records = dns.resolver.resolve(domain, "MX")
        analysis["mx_records"] = [str(mx) for mx in mx_records]

        # 检查SPF记录
        try:
            txt_records = dns.resolver.resolve(domain, "TXT")
            for record in txt_records:
                if "v=spf1" in str(record):
                    analysis["has_spf"] = True
                if "v=DMARC1" in str(record):
                    analysis["has_dmarc"] = True
        except:
            pass

        # 判断邮件服务商类型
        mx_str = " ".join(analysis["mx_records"]).lower()
        if "google" in mx_str:
            analysis["provider"] = "Google Workspace/Gmail"
            analysis["reputation"] = "strict_filtering"
        elif "outlook" in mx_str or "microsoft" in mx_str:
            analysis["provider"] = "Microsoft 365/Outlook"
            analysis["reputation"] = "moderate_filtering"
        elif "qq.com" in mx_str:
            analysis["provider"] = "QQ邮箱"
            analysis["reputation"] = "strict_filtering"
        else:
            analysis["provider"] = "其他"

    except Exception as e:
        analysis["error"] = str(e)

    return analysis


async def send_optimized_test_email(
    email_service, smtp_settings, test_email: str, tenant_id: UUID
) -> Dict:
    """发送优化的测试邮件"""

    # 创建SMTP服务实例
    class SMTPSettingsObj:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)

    smtp_settings_obj = SMTPSettingsObj(smtp_settings)

    from ..services.smtp_service import SMTPService

    smtp_service = SMTPService(smtp_settings_obj)

    # 优化的邮件内容
    subject = "📧 邮件系统投递测试"

    body_html = f"""
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">✅ 投递测试成功！</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">您的邮件系统配置正常</p>
    </div>
    
    <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
        <h3 style="color: #495057; margin-top: 0;">📊 测试信息</h3>
        <ul style="color: #6c757d; line-height: 1.6;">
            <li>发送时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</li>
            <li>SMTP服务器: {smtp_settings.get('smtp_host', '')}</li>
            <li>安全协议: {smtp_settings.get('security_protocol', '')}</li>
            <li>收件邮箱: {test_email}</li>
        </ul>
    </div>
    
    <div style="background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>💡 提示:</strong> 如果您收到此邮件，说明邮件投递功能正常工作。
    </div>
    
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6;">
        <p style="color: #6c757d; font-size: 14px; margin: 0;">
            此邮件由邮件系统自动发送<br>
            <span style="color: #28a745;">🔐 安全 • 🚀 快速 • 📈 可靠</span>
        </p>
    </div>
</body>
</html>
"""

    body_text = f"""
✅ 邮件系统投递测试成功！

📊 测试信息:
- 发送时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
- SMTP服务器: {smtp_settings.get('smtp_host', '')}
- 安全协议: {smtp_settings.get('security_protocol', '')}
- 收件邮箱: {test_email}

💡 如果您收到此邮件，说明邮件投递功能正常工作。

此邮件由邮件系统自动发送，请勿回复。
"""

    return await smtp_service.send_email(
        to_emails=[test_email],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


async def check_common_issues(tenant_id: UUID) -> List[Dict]:
    """检查常见问题"""
    issues = []

    # 检查是否有大量失败的邮件
    failed_count = await fetch_one(
        """
        SELECT COUNT(*) as count
        FROM email_sending_queue 
        WHERE tenant_id = $1 
        AND status = 'failed' 
        AND created_at >= NOW() - INTERVAL '24 hours'
        """,
        tenant_id,
    )

    if failed_count and failed_count["count"] > 10:
        issues.append(
            {
                "type": "high_failure_rate",
                "message": f"24小时内有{failed_count['count']}封邮件发送失败",
                "severity": "high",
            }
        )

    # 检查是否有长时间未测试的SMTP设置
    untested_smtp = await fetch_all(
        """
        SELECT setting_name, smtp_host 
        FROM email_smtp_settings 
        WHERE tenant_id = $1 
        AND is_active = true 
        AND (last_test_at IS NULL OR last_test_at < NOW() - INTERVAL '7 days')
        """,
        tenant_id,
    )

    for smtp in untested_smtp:
        issues.append(
            {
                "type": "untested_smtp",
                "message": f"SMTP设置 '{smtp['setting_name']}' 超过7天未测试",
                "severity": "medium",
            }
        )

    return issues


def get_troubleshooting_steps(queue_info: Dict) -> List[str]:
    """获取故障排除步骤"""
    steps = [
        "检查收件人的垃圾邮件文件夹",
        "确认收件人邮箱地址正确",
        "等待5-10分钟，邮件可能有延迟",
    ]

    if queue_info.get("to_emails"):
        email = queue_info["to_emails"][0]
        domain = email.split("@")[1] if "@" in email else ""

        if "gmail.com" in domain:
            steps.extend(
                [
                    "检查Gmail的推广邮件和社交邮件选项卡",
                    "将发件人邮箱添加到Gmail联系人",
                    "检查Gmail的过滤器设置",
                ]
            )
        elif domain in ["qq.com", "163.com", "126.com"]:
            steps.extend(
                [
                    "检查邮箱的拦截邮件设置",
                    "将发件人添加到白名单",
                    "检查邮箱的反垃圾邮件设置",
                ]
            )

    steps.extend(
        [
            "使用不同的邮箱地址测试（如163、Gmail等）",
            "检查邮件内容是否包含敏感词汇",
            "联系邮件服务商确认投递状态",
        ]
    )

    return steps


def get_delivery_recommendations(domain: str, test_result: Dict) -> List[str]:
    """获取投递优化建议"""
    recommendations = []

    if "gmail.com" in domain:
        recommendations.extend(
            [
                "配置SPF记录提高发件人信誉",
                "使用DKIM签名验证邮件真实性",
                "避免在邮件内容中使用过多营销词汇",
                "建立良好的发送历史记录",
            ]
        )

    if test_result.get("status") == "success":
        recommendations.extend(
            [
                "SMTP发送正常，关注邮件内容优化",
                "建议设置邮件追踪以监控投递状态",
                "定期清理无效邮箱地址",
            ]
        )
    else:
        recommendations.extend(
            [
                "检查SMTP设置和认证信息",
                "验证网络连接和防火墙设置",
                "联系SMTP服务商确认服务状态",
            ]
        )

    return recommendations
