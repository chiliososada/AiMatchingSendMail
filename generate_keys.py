#!/usr/bin/env python3
# generate_keys.py - 安全密钥生成工具

import secrets
import string
from cryptography.fernet import Fernet
import base64
import os


def generate_secret_key(length=64):
    """生成安全的随机字符串作为SECRET_KEY"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_fernet_key():
    """生成Fernet加密密钥"""
    return Fernet.generate_key().decode()


def generate_uuid():
    """生成UUID作为租户ID示例"""
    import uuid

    return str(uuid.uuid4())


def main():
    print("=" * 60)
    print("          邮件API系统 - 密钥生成工具")
    print("=" * 60)
    print()

    # 生成SECRET_KEY
    secret_key = generate_secret_key()
    print("1. SECRET_KEY (应用密钥):")
    print("   用途：JWT签名、会话管理、一般加密")
    print(f'   SECRET_KEY="{secret_key}"')
    print()

    # 生成ENCRYPTION_KEY
    encryption_key = generate_fernet_key()
    print("2. ENCRYPTION_KEY (Fernet加密密钥):")
    print("   用途：SMTP密码加密存储")
    print(f'   ENCRYPTION_KEY="{encryption_key}"')
    print()

    # 生成示例租户ID
    tenant_id = generate_uuid()
    print("3. 示例租户ID:")
    print("   用途：多租户系统中的租户标识")
    print(f'   TENANT_ID="{tenant_id}"')
    print()

    # 生成完整的.env配置
    print("4. 完整的.env配置文件内容:")
    print("-" * 50)

    env_content = f"""# ==========================================
# 安全配置 - 自动生成
# ==========================================
SECRET_KEY="{secret_key}"
ENCRYPTION_KEY="{encryption_key}"

# ==========================================
# 数据库配置
# ==========================================
DATABASE_URL="postgresql://emailapi:emailapi123@localhost:5432/email_api_db"

# ==========================================
# 应用配置
# ==========================================
PROJECT_NAME="Email API"
API_V1_STR="/api/v1"
ENVIRONMENT="development"
DEBUG=true

# ==========================================
# 文件上传配置
# ==========================================
UPLOAD_DIR="uploads"
ATTACHMENT_DIR="uploads/attachments"
TEMP_DIR="uploads/temp"
MAX_FILE_SIZE=26214400
MAX_FILES_PER_REQUEST=10

# ==========================================
# 邮件配置
# ==========================================
MAX_RECIPIENTS_PER_EMAIL=100
MAX_BULK_EMAILS=1000
EMAIL_TIMEOUT_SECONDS=60

# ==========================================
# CORS配置
# ==========================================
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# ==========================================
# Redis配置（可选）
# ==========================================
REDIS_ENABLED=false

# ==========================================
# 示例租户ID（用于测试）
# ==========================================
EXAMPLE_TENANT_ID="{tenant_id}"
"""

    print(env_content)

    # 保存到文件
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ 配置已保存到 .env 文件")
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        print("请手动复制上面的配置到 .env 文件")

    print()
    print("=" * 60)
    print("                   重要提醒")
    print("=" * 60)
    print("🔒 这些密钥非常重要，请：")
    print("   1. 不要提交到版本控制系统（Git）")
    print("   2. 生产环境使用不同的密钥")
    print("   3. 定期更换密钥")
    print("   4. 备份密钥到安全位置")
    print()
    print("🚀 下一步：")
    print("   1. 启动数据库：docker-compose up -d db")
    print("   2. 启动应用：uvicorn app.main:app --reload")
    print("   3. 访问文档：http://localhost:8000/docs")


def test_keys():
    """测试生成的密钥是否有效"""
    print("\n🧪 测试密钥有效性...")

    try:
        # 测试SECRET_KEY
        secret = generate_secret_key()
        print(f"✅ SECRET_KEY 生成成功: {len(secret)} 字符")

        # 测试ENCRYPTION_KEY
        key = generate_fernet_key()
        f = Fernet(key.encode())

        # 测试加密解密
        test_data = "test_password_123"
        encrypted = f.encrypt(test_data.encode())
        decrypted = f.decrypt(encrypted).decode()

        if decrypted == test_data:
            print("✅ ENCRYPTION_KEY 加密解密测试通过")
        else:
            print("❌ ENCRYPTION_KEY 测试失败")

    except Exception as e:
        print(f"❌ 密钥测试失败: {e}")


if __name__ == "__main__":
    main()
    test_keys()
