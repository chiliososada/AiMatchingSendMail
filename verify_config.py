#!/usr/bin/env python3
# verify_config.py - 配置验证工具

import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet


def verify_config():
    """验证.env配置文件"""
    print("🔍 验证配置文件...")

    # 加载.env文件
    if not os.path.exists(".env"):
        print("❌ .env 文件不存在，请先运行 generate_keys.py")
        return False

    load_dotenv()

    # 检查必需的配置
    required_configs = {
        "SECRET_KEY": "应用密钥",
        "ENCRYPTION_KEY": "Fernet加密密钥",
        "DATABASE_URL": "数据库连接字符串",
    }

    all_good = True

    for key, description in required_configs.items():
        value = os.getenv(key)
        if not value:
            print(f"❌ 缺少配置: {key} ({description})")
            all_good = False
        else:
            print(f"✅ {key}: {description} - 已配置")

    # 验证 SECRET_KEY
    secret_key = os.getenv("SECRET_KEY")
    if secret_key:
        if len(secret_key) < 32:
            print("⚠️  SECRET_KEY 长度较短，建议至少32字符")
        else:
            print(f"✅ SECRET_KEY 长度: {len(secret_key)} 字符 - 良好")

    # 验证 ENCRYPTION_KEY
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if encryption_key:
        try:
            fernet = Fernet(encryption_key.encode())
            # 测试加密解密
            test_data = "test_smtp_password"
            encrypted = fernet.encrypt(test_data.encode())
            decrypted = fernet.decrypt(encrypted).decode()

            if decrypted == test_data:
                print("✅ ENCRYPTION_KEY 格式正确，加密测试通过")
            else:
                print("❌ ENCRYPTION_KEY 加密测试失败")
                all_good = False

        except Exception as e:
            print(f"❌ ENCRYPTION_KEY 格式错误: {e}")
            all_good = False

    # 检查可选配置
    optional_configs = {
        "MAX_FILE_SIZE": "26214400",  # 25MB
        "MAX_RECIPIENTS_PER_EMAIL": "100",
        "EMAIL_TIMEOUT_SECONDS": "60",
    }

    print("\n📋 可选配置检查:")
    for key, default_value in optional_configs.items():
        value = os.getenv(key, default_value)
        print(f"   {key}: {value}")

    if all_good:
        print("\n🎉 配置验证通过！系统可以正常启动")
        print("\n🚀 下一步操作:")
        print("   1. 启动数据库: docker-compose up -d db")
        print("   2. 启动应用: uvicorn app.main:app --reload")
        print("   3. 访问API文档: http://localhost:8000/docs")
        print("   4. 健康检查: http://localhost:8000/health")
    else:
        print("\n❌ 配置验证失败，请检查上述问题")

    return all_good


def show_sample_usage():
    """显示使用示例"""
    print("\n📖 SMTP配置示例 (Gmail):")
    print(
        """
    {
        "tenant_id": "your-tenant-uuid",
        "setting_name": "Gmail SMTP",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "your-email@gmail.com",
        "smtp_password": "your-app-password",
        "security_protocol": "TLS",
        "from_email": "your-email@gmail.com",
        "from_name": "Your Name",
        "is_default": true
    }
    """
    )

    print("📧 Gmail设置步骤:")
    print("   1. 启用2FA (两步验证)")
    print("   2. 生成应用密码")
    print("   3. 使用应用密码而不是账户密码")


if __name__ == "__main__":
    if verify_config():
        show_sample_usage()
