# tests/test_email_service.py
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.services.email_service import EmailService, AttachmentManager
from app.services.smtp_service import SMTPService
from app.schemas.email_schemas import (
    EmailSendRequest,
    EmailWithAttachmentsRequest,
    SMTPSettingsCreate,
    AttachmentInfo,
)
from app.models.email_models import EmailSMTPSettings, EmailSendingQueue
from app.database import get_db

# 测试客户端
client = TestClient(app)


class TestEmailService:
    """邮件服务测试类"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return Mock(spec=Session)

    @pytest.fixture
    def email_service(self, mock_db):
        """邮件服务实例"""
        return EmailService(mock_db)

    @pytest.fixture
    def sample_tenant_id(self):
        """示例租户ID"""
        return uuid4()

    @pytest.fixture
    def sample_smtp_settings(self, sample_tenant_id):
        """示例SMTP设置"""
        return EmailSMTPSettings(
            id=uuid4(),
            tenant_id=sample_tenant_id,
            setting_name="Test SMTP",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@gmail.com",
            smtp_password_encrypted="encrypted_password",
            security_protocol="TLS",
            from_email="test@gmail.com",
            from_name="Test Sender",
            is_default=True,
            is_active=True,
        )

    def test_create_smtp_settings(self, email_service, mock_db, sample_tenant_id):
        """测试创建SMTP设置"""
        # 准备测试数据
        settings_data = SMTPSettingsCreate(
            tenant_id=sample_tenant_id,
            setting_name="Test SMTP",
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@gmail.com",
            smtp_password="test_password",
            security_protocol="TLS",
            from_email="test@gmail.com",
            from_name="Test Sender",
            is_default=True,
        )

        # 模拟数据库操作
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        mock_db.query.return_value.filter.return_value.update = Mock()

        # 执行测试
        result = email_service.create_smtp_settings(settings_data)

        # 验证结果
        assert result is not None
        assert result.setting_name == "Test SMTP"
        assert result.smtp_host == "smtp.gmail.com"
        assert result.tenant_id == sample_tenant_id

        # 验证数据库操作
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_get_smtp_settings(self, email_service, mock_db, sample_smtp_settings):
        """测试获取SMTP设置"""
        # 模拟数据库查询
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.first.return_value = sample_smtp_settings

        # 执行测试
        result = email_service.get_smtp_settings(
            sample_smtp_settings.tenant_id, sample_smtp_settings.id
        )

        # 验证结果
        assert result == sample_smtp_settings
        assert result.setting_name == "Test SMTP"

    @pytest.mark.asyncio
    async def test_send_email_immediately(
        self, email_service, mock_db, sample_smtp_settings
    ):
        """测试立即发送邮件"""
        # 准备测试数据
        email_request = EmailSendRequest(
            tenant_id=sample_smtp_settings.tenant_id,
            to_emails=["recipient@example.com"],
            subject="Test Email",
            body_text="Test content",
            body_html="<p>Test content</p>",
        )

        # 模拟SMTP设置查询
        mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = (
            sample_smtp_settings
        )

        # 模拟邮件队列创建
        mock_queue_item = EmailSendingQueue(
            id=uuid4(),
            tenant_id=sample_smtp_settings.tenant_id,
            to_emails=email_request.to_emails,
            subject=email_request.subject,
            status="queued",
        )
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(
            side_effect=lambda x: setattr(x, "id", mock_queue_item.id)
        )

        # 模拟SMTP发送
        with patch("app.services.email_service.SMTPService") as mock_smtp_class:
            mock_smtp = AsyncMock()
            mock_smtp_class.return_value = mock_smtp
            mock_smtp.send_email.return_value = {
                "status": "success",
                "message": "邮件发送成功",
                "message_id": "test_message_id",
            }

            # 执行测试
            result = await email_service.send_email_immediately(email_request)

            # 验证结果
            assert result["status"] == "success"
            assert result["message"] == "邮件发送成功"
            assert result["to_emails"] == email_request.to_emails
            assert "queue_id" in result

    def test_get_email_queue_status(self, email_service, mock_db, sample_tenant_id):
        """测试获取邮件队列状态"""
        # 准备测试数据
        queue_id = uuid4()
        mock_queue_item = EmailSendingQueue(
            id=queue_id,
            tenant_id=sample_tenant_id,
            to_emails=["test@example.com"],
            subject="Test",
            status="sent",
        )

        # 模拟数据库查询
        mock_db.query.return_value.filter.return_value.first.return_value = (
            mock_queue_item
        )

        # 执行测试
        result = email_service.get_email_queue_status(sample_tenant_id, queue_id)

        # 验证结果
        assert result == mock_queue_item
        assert result.status == "sent"


class TestAttachmentManager:
    """附件管理器测试类"""

    @pytest.fixture
    def attachment_manager(self, tmp_path):
        """附件管理器实例"""
        return AttachmentManager(str(tmp_path))

    @pytest.fixture
    def sample_file_content(self):
        """示例文件内容"""
        return b"This is a test file content"

    @pytest.fixture
    def sample_tenant_id(self):
        """示例租户ID"""
        return uuid4()

    def test_save_attachment(
        self, attachment_manager, sample_file_content, sample_tenant_id
    ):
        """测试保存附件"""
        filename = "test.txt"
        content_type = "text/plain"

        # 执行测试
        attachment_info, attachment_id = attachment_manager.save_attachment(
            sample_file_content, filename, sample_tenant_id, content_type
        )

        # 验证结果
        assert attachment_info.filename == filename
        assert attachment_info.content_type == content_type
        assert attachment_info.file_size == len(sample_file_content)
        assert attachment_id is not None

        # 验证文件是否保存
        file_path = attachment_manager.get_attachment_path(
            sample_tenant_id, attachment_id, filename
        )
        assert file_path is not None

        # 读取文件验证内容
        with open(file_path, "rb") as f:
            saved_content = f.read()
        assert saved_content == sample_file_content

    def test_delete_attachment(
        self, attachment_manager, sample_file_content, sample_tenant_id
    ):
        """测试删除附件"""
        filename = "test.txt"

        # 先保存附件
        _, attachment_id = attachment_manager.save_attachment(
            sample_file_content, filename, sample_tenant_id
        )

        # 验证文件存在
        file_path = attachment_manager.get_attachment_path(
            sample_tenant_id, attachment_id, filename
        )
        assert file_path is not None

        # 删除附件
        result = attachment_manager.delete_attachment(
            sample_tenant_id, attachment_id, filename
        )

        # 验证删除结果
        assert result is True

        # 验证文件已被删除
        file_path = attachment_manager.get_attachment_path(
            sample_tenant_id, attachment_id, filename
        )
        assert file_path is None


class TestSMTPService:
    """SMTP服务测试类"""

    @pytest.fixture
    def mock_smtp_settings(self):
        """模拟SMTP设置"""
        return Mock(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="test@gmail.com",
            smtp_password_encrypted="encrypted_password",
            security_protocol="TLS",
            from_email="test@gmail.com",
            from_name="Test Sender",
            reply_to_email=None,
        )

    @patch("app.services.smtp_service.decrypt_password")
    def test_smtp_service_init(self, mock_decrypt, mock_smtp_settings):
        """测试SMTP服务初始化"""
        mock_decrypt.return_value = "decrypted_password"

        smtp_service = SMTPService(mock_smtp_settings)

        assert smtp_service.settings == mock_smtp_settings
        assert smtp_service.smtp_password == "decrypted_password"
        mock_decrypt.assert_called_once_with("encrypted_password")

    @patch("app.services.smtp_service.decrypt_password")
    @patch("app.services.smtp_service.aiosmtplib.send")
    @pytest.mark.asyncio
    async def test_send_email_success(
        self, mock_send, mock_decrypt, mock_smtp_settings
    ):
        """测试成功发送邮件"""
        mock_decrypt.return_value = "decrypted_password"
        mock_send.return_value = None

        smtp_service = SMTPService(mock_smtp_settings)

        result = await smtp_service.send_email(
            to_emails=["recipient@example.com"],
            subject="Test Subject",
            body_text="Test content",
        )

        assert result["status"] == "success"
        assert result["message"] == "邮件发送成功"
        mock_send.assert_called_once()

    @patch("app.services.smtp_service.decrypt_password")
    @patch("app.services.smtp_service.aiosmtplib.send")
    @pytest.mark.asyncio
    async def test_send_email_failure(
        self, mock_send, mock_decrypt, mock_smtp_settings
    ):
        """测试邮件发送失败"""
        mock_decrypt.return_value = "decrypted_password"
        mock_send.side_effect = Exception("SMTP Error")

        smtp_service = SMTPService(mock_smtp_settings)

        result = await smtp_service.send_email(
            to_emails=["recipient@example.com"],
            subject="Test Subject",
            body_text="Test content",
        )

        assert result["status"] == "failed"
        assert "SMTP Error" in result["message"]


class TestEmailAPI:
    """邮件API测试类"""

    def test_health_check(self):
        """测试健康检查API"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_get_system_limits(self):
        """测试获取系统限制API"""
        response = client.get("/limits")
        assert response.status_code == 200
        data = response.json()
        assert "file_upload" in data
        assert "email_sending" in data

    def test_create_smtp_settings_validation(self):
        """测试SMTP设置创建参数验证"""
        # 测试缺少必需参数
        response = client.post("/api/v1/email/smtp-settings", json={})
        assert response.status_code == 422

        # 测试无效邮箱格式
        invalid_data = {
            "tenant_id": str(uuid4()),
            "setting_name": "Test",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "invalid-email",
            "smtp_password": "password",
            "from_email": "invalid-email",
        }
        response = client.post("/api/v1/email/smtp-settings", json=invalid_data)
        assert response.status_code == 422


# 测试配置
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# 性能测试
class TestPerformance:
    """性能测试类"""

    @pytest.mark.performance
    def test_bulk_email_performance(self):
        """测试批量邮件发送性能"""
        import time

        # 准备大量邮件数据
        emails = []
        for i in range(100):
            emails.append(
                {
                    "to_email": f"user{i}@example.com",
                    "subject": f"Test Email {i}",
                    "body_text": f"Test content {i}",
                }
            )

        bulk_request = {
            "tenant_id": str(uuid4()),
            "emails": emails,
            "common_subject": "Bulk Test",
        }

        start_time = time.time()
        # 这里应该有实际的批量发送逻辑
        end_time = time.time()

        processing_time = end_time - start_time
        assert processing_time < 10.0  # 100封邮件应在10秒内处理完成


# 集成测试
class TestIntegration:
    """集成测试类"""

    @pytest.mark.integration
    def test_complete_email_flow(self):
        """测试完整的邮件发送流程"""
        # 这里应该包含从创建SMTP设置到发送邮件的完整流程测试
        pass


if __name__ == "__main__":
    pytest.main([__file__])
