#!/usr/bin/env python3
# scripts/create_test_data.py
"""
创建AI匹配测试数据

生成具有明确匹配关系的测试项目和简历数据
用于验证AI匹配算法的准确性
"""

import asyncio
import asyncpg
import logging
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, date

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 示例租户ID
TEST_TENANT_ID = "33723dd6-cf28-4dab-975c-f883f5389d04"

# 测试项目数据
TEST_PROJECTS = [
    {
        "title": "React.js Webアプリケーション開発",
        "client_company": "株式会社テックイノベーション",
        "company_type": "自社",
        "description": "新しいECサイトのフロントエンド開発",
        "detail_description": "React.js、TypeScript、Next.jsを使用したモダンなWebアプリケーション開発。レスポンシブデザイン対応、API連携、状態管理(Redux)の実装が必要です。",
        "status": "募集中",
        "priority": "高",
        "skills": [
            "React",
            "TypeScript",
            "JavaScript",
            "Next.js",
            "Redux",
            "CSS",
            "HTML",
        ],
        "key_technologies": "React.js, TypeScript, Next.js, Redux",
        "experience": "React開発経験2年以上、TypeScript経験1年以上",
        "location": "東京都渋谷区",
        "work_type": "常駐",
        "duration": "6ヶ月",
        "budget": "月60万円～80万円",
        "japanese_level": "N2",
        "max_candidates": 3,
        "start_date": date.today(),
    },
    {
        "title": "Python Django バックエンド開発",
        "client_company": "株式会社データサイエンス",
        "company_type": "自社",
        "description": "AIサービスのバックエンドAPI開発",
        "detail_description": "Django REST frameworkを使用したAPIサーバー開発。機械学習モデルとの連携、大量データ処理、高性能なAPI設計が求められます。PostgreSQL、Redis使用。",
        "status": "募集中",
        "priority": "高",
        "skills": [
            "Python",
            "Django",
            "PostgreSQL",
            "Redis",
            "REST API",
            "機械学習",
            "Docker",
        ],
        "key_technologies": "Python, Django, PostgreSQL, Machine Learning",
        "experience": "Python開発経験3年以上、Django経験2年以上、機械学習プロジェクト経験",
        "location": "東京都新宿区",
        "work_type": "リモート可",
        "duration": "12ヶ月",
        "budget": "月70万円～90万円",
        "japanese_level": "N1",
        "max_candidates": 2,
        "start_date": date.today(),
    },
    {
        "title": "Java Spring Boot マイクロサービス開発",
        "client_company": "大手金融機関",
        "company_type": "元請け",
        "description": "銀行システムのマイクロサービス基盤開発",
        "detail_description": "Java Spring Bootを使用したマイクロサービスアーキテクチャの設計・開発。Kubernetes、Docker、AWS環境での開発。高いセキュリティ要件があります。",
        "status": "募集中",
        "priority": "中",
        "skills": [
            "Java",
            "Spring Boot",
            "Kubernetes",
            "Docker",
            "AWS",
            "マイクロサービス",
            "セキュリティ",
        ],
        "key_technologies": "Java, Spring Boot, Kubernetes, AWS",
        "experience": "Java開発経験5年以上、Spring Boot経験3年以上、金融系システム経験優遇",
        "location": "東京都千代田区",
        "work_type": "常駐",
        "duration": "18ヶ月",
        "budget": "月80万円～100万円",
        "japanese_level": "N1",
        "max_candidates": 5,
        "start_date": date.today(),
    },
    {
        "title": "React Native モバイルアプリ開発",
        "client_company": "スタートアップ企業",
        "company_type": "自社",
        "description": "ヘルスケアアプリのモバイル開発",
        "detail_description": "React Nativeを使用したiOS/Androidアプリ開発。Firebaseとの連携、プッシュ通知、位置情報機能の実装。UIXにもこだわりたいプロジェクトです。",
        "status": "募集中",
        "priority": "中",
        "skills": ["React Native", "JavaScript", "Firebase", "iOS", "Android", "UI/UX"],
        "key_technologies": "React Native, Firebase, Mobile Development",
        "experience": "React Native開発経験2年以上、モバイルアプリ公開経験",
        "location": "東京都品川区",
        "work_type": "リモート可",
        "duration": "8ヶ月",
        "budget": "月50万円～70万円",
        "japanese_level": "N3",
        "max_candidates": 2,
        "start_date": date.today(),
    },
    {
        "title": "Vue.js + Node.js フルスタック開発",
        "client_company": "中小IT企業",
        "company_type": "自社",
        "description": "社内管理システムのリニューアル",
        "detail_description": "Vue.js + Node.js (Express)でのフルスタック開発。既存システムからの移行、データベース設計、API設計から実装まで担当。",
        "status": "募集中",
        "priority": "低",
        "skills": [
            "Vue.js",
            "Node.js",
            "Express",
            "MySQL",
            "JavaScript",
            "フルスタック",
        ],
        "key_technologies": "Vue.js, Node.js, Express, MySQL",
        "experience": "Vue.js開発経験1年以上、Node.js経験1年以上、フルスタック開発経験",
        "location": "東京都港区",
        "work_type": "常駐",
        "duration": "4ヶ月",
        "budget": "月45万円～60万円",
        "japanese_level": "N2",
        "max_candidates": 1,
        "start_date": date.today(),
    },
]

# 测试简历数据
TEST_ENGINEERS = [
    {
        "name": "田中太郎",
        "email": "tanaka@example.com",
        "nationality": "日本",
        "age": "28歳",
        "skills": [
            "React",
            "TypeScript",
            "JavaScript",
            "Next.js",
            "Redux",
            "CSS",
            "HTML",
            "Git",
        ],
        "experience": "フロントエンド開発5年",
        "work_experience": "React.jsを使用したWebアプリケーション開発5年。大手ECサイトのフロントエンド開発に3年従事。TypeScriptでの開発経験2年。",
        "japanese_level": "N1",
        "english_level": "日常会話レベル",
        "current_status": "available",
        "company_type": "フリーランス",
        "preferred_locations": ["東京都", "神奈川県"],
        "desired_rate_min": 55,
        "desired_rate_max": 75,
        "self_promotion": "React.jsのエキスパートです。モダンなフロントエンド技術に精通しており、TypeScriptでの型安全な開発を得意としています。",
        "technical_keywords": [
            "SPA",
            "PWA",
            "レスポンシブデザイン",
            "webpack",
            "Babel",
        ],
    },
    {
        "name": "佐藤花子",
        "email": "sato@example.com",
        "nationality": "日本",
        "age": "32歳",
        "skills": [
            "Python",
            "Django",
            "PostgreSQL",
            "Redis",
            "REST API",
            "機械学習",
            "Docker",
            "AWS",
        ],
        "experience": "バックエンド開発7年、機械学習2年",
        "work_experience": "PythonでのWebアプリケーション開発7年。Django REST frameworkでのAPI開発が得意。機械学習プロジェクトでのバックエンド開発経験2年。AWSでのインフラ構築も可能。",
        "japanese_level": "N1",
        "english_level": "ビジネスレベル",
        "current_status": "available",
        "company_type": "正社員",
        "company_name": "株式会社AI開発",
        "preferred_locations": ["東京都", "リモート"],
        "desired_rate_min": 70,
        "desired_rate_max": 90,
        "self_promotion": "Python・Djangoのスペシャリストです。機械学習との連携経験も豊富で、スケーラブルなシステム開発が得意です。",
        "technical_keywords": [
            "scikit-learn",
            "pandas",
            "FastAPI",
            "Celery",
            "Elasticsearch",
        ],
    },
    {
        "name": "リー・ウェイ",
        "email": "li@example.com",
        "nationality": "中国",
        "age": "29歳",
        "skills": [
            "Java",
            "Spring Boot",
            "Kubernetes",
            "Docker",
            "AWS",
            "マイクロサービス",
            "Maven",
            "Git",
        ],
        "experience": "Java開発6年、マイクロサービス3年",
        "work_experience": "Java Spring Bootでの企業システム開発6年。マイクロサービスアーキテクチャでの開発経験3年。金融系システム開発経験2年。AWSでのクラウド開発に精通。",
        "japanese_level": "N1",
        "english_level": "ネイティブレベル",
        "current_status": "available",
        "company_type": "フリーランス",
        "preferred_locations": ["東京都", "大阪府"],
        "desired_rate_min": 75,
        "desired_rate_max": 95,
        "self_promotion": "Java Spring Bootでのマイクロサービス開発のエキスパートです。金融系の高セキュリティシステム開発経験があります。",
        "technical_keywords": [
            "Spring Cloud",
            "Kafka",
            "Redis",
            "Jenkins",
            "Terraform",
        ],
    },
    {
        "name": "山田健",
        "email": "yamada@example.com",
        "nationality": "日本",
        "age": "26歳",
        "skills": [
            "React Native",
            "JavaScript",
            "Firebase",
            "iOS",
            "Android",
            "UI/UX",
            "Swift",
            "Kotlin",
        ],
        "experience": "モバイルアプリ開発4年",
        "work_experience": "React Nativeでのクロスプラットフォーム開発4年。iOS/Androidアプリを複数リリース。ヘルスケア、フィンテック分野でのアプリ開発経験。UI/UXデザインにも対応可能。",
        "japanese_level": "N1",
        "english_level": "日常会話レベル",
        "current_status": "available",
        "company_type": "フリーランス",
        "preferred_locations": ["東京都", "千葉県"],
        "desired_rate_min": 50,
        "desired_rate_max": 70,
        "self_promotion": "React Nativeでのモバイルアプリ開発が専門です。ユーザビリティを重視したアプリ設計・開発を得意としています。",
        "technical_keywords": [
            "Expo",
            "Redux",
            "AsyncStorage",
            "Push通知",
            "App Store",
            "Google Play",
        ],
    },
    {
        "name": "鈴木一郎",
        "email": "suzuki@example.com",
        "nationality": "日本",
        "age": "35歳",
        "skills": [
            "Vue.js",
            "Node.js",
            "Express",
            "MySQL",
            "JavaScript",
            "PHP",
            "Laravel",
        ],
        "experience": "Web開発10年、フルスタック開発5年",
        "work_experience": "Web開発10年の経験。PHP→JavaScriptへの技術移行を経験。Vue.js + Node.jsでのフルスタック開発5年。中小企業の業務システム開発が得意分野。",
        "japanese_level": "N1",
        "english_level": "初級レベル",
        "current_status": "available",
        "company_type": "正社員",
        "company_name": "株式会社ウェブソリューション",
        "preferred_locations": ["東京都"],
        "desired_rate_min": 45,
        "desired_rate_max": 65,
        "self_promotion": "長年のWeb開発経験を活かし、要件定義から運用まで一貫したシステム開発が可能です。中小企業のニーズを理解した開発が得意です。",
        "technical_keywords": [
            "Nuxt.js",
            "Vuex",
            "Sequelize",
            "Socket.io",
            "業務システム",
        ],
    },
    {
        "name": "パク・ミンス",
        "email": "park@example.com",
        "nationality": "韓国",
        "age": "27歳",
        "skills": ["React", "Vue.js", "Angular", "TypeScript", "Node.js", "GraphQL"],
        "experience": "フロントエンド開発4年",
        "work_experience": "React、Vue.js、Angularでのフロントエンド開発4年。SPA開発が得意。GraphQLでのAPI連携経験豊富。多言語サイト開発経験あり。",
        "japanese_level": "N2",
        "english_level": "ビジネスレベル",
        "current_status": "available",
        "company_type": "フリーランス",
        "preferred_locations": ["東京都", "リモート"],
        "desired_rate_min": 55,
        "desired_rate_max": 75,
        "self_promotion": "複数のフロントエンドフレームワークに精通したマルチスキルエンジニアです。国際的なプロジェクト経験も豊富です。",
        "technical_keywords": ["Apollo", "Gatsby", "Storybook", "Jest", "多言語対応"],
    },
]


async def create_test_projects(conn):
    """测试项目数据を作成"""
    logger.info("📁 テストプロジェクトデータを作成中...")

    project_ids = []

    for project_data in TEST_PROJECTS:
        try:
            project_id = await conn.fetchval(
                """
                INSERT INTO projects (
                    tenant_id, title, client_company, company_type, description,
                    detail_description, status, priority, skills, key_technologies,
                    experience, location, work_type, duration, budget,
                    japanese_level, max_candidates, start_date, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                RETURNING id
                """,
                TEST_TENANT_ID,
                project_data["title"],
                project_data["client_company"],
                project_data["company_type"],
                project_data["description"],
                project_data["detail_description"],
                project_data["status"],
                project_data["priority"],
                project_data["skills"],
                project_data["key_technologies"],
                project_data["experience"],
                project_data["location"],
                project_data["work_type"],
                project_data["duration"],
                project_data["budget"],
                project_data["japanese_level"],
                project_data["max_candidates"],
                project_data["start_date"],
                True,
            )

            project_ids.append(project_id)
            logger.info(
                f"✅ プロジェクト作成: {project_data['title']} (ID: {project_id})"
            )

        except Exception as e:
            logger.error(
                f"❌ プロジェクト作成失敗: {project_data['title']}, エラー: {str(e)}"
            )

    logger.info(f"✅ {len(project_ids)} 個のテストプロジェクトを作成しました")
    return project_ids


async def create_test_engineers(conn):
    """测试简历数据を作成"""
    logger.info("👥 テストエンジニアデータを作成中...")

    engineer_ids = []

    for engineer_data in TEST_ENGINEERS:
        try:
            engineer_id = await conn.fetchval(
                """
                INSERT INTO engineers (
                    tenant_id, name, email, nationality, age, skills, experience,
                    work_experience, japanese_level, english_level, current_status,
                    company_type, company_name, preferred_locations, desired_rate_min,
                    desired_rate_max, self_promotion, technical_keywords, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                RETURNING id
                """,
                TEST_TENANT_ID,
                engineer_data["name"],
                engineer_data["email"],
                engineer_data["nationality"],
                engineer_data["age"],
                engineer_data["skills"],
                engineer_data["experience"],
                engineer_data["work_experience"],
                engineer_data["japanese_level"],
                engineer_data["english_level"],
                engineer_data["current_status"],
                engineer_data["company_type"],
                engineer_data.get("company_name"),
                engineer_data["preferred_locations"],
                engineer_data["desired_rate_min"],
                engineer_data["desired_rate_max"],
                engineer_data["self_promotion"],
                engineer_data["technical_keywords"],
                True,
            )

            engineer_ids.append(engineer_id)
            logger.info(
                f"✅ エンジニア作成: {engineer_data['name']} (ID: {engineer_id})"
            )

        except Exception as e:
            logger.error(
                f"❌ エンジニア作成失敗: {engineer_data['name']}, エラー: {str(e)}"
            )

    logger.info(f"✅ {len(engineer_ids)} 人のテストエンジニアを作成しました")
    return engineer_ids


async def clear_existing_test_data(conn):
    """既存のテストデータをクリア"""
    logger.info("🗑️ 既存のテストデータをクリア中...")

    try:
        # マッチング結果をクリア
        await conn.execute(
            "DELETE FROM project_engineer_matches WHERE tenant_id = $1", TEST_TENANT_ID
        )

        # マッチング履歴をクリア
        await conn.execute(
            "DELETE FROM ai_matching_history WHERE tenant_id = $1", TEST_TENANT_ID
        )

        # プロジェクトをクリア
        project_count = await conn.fetchval(
            "DELETE FROM projects WHERE tenant_id = $1 RETURNING COUNT(*)",
            TEST_TENANT_ID,
        )

        # エンジニアをクリア
        engineer_count = await conn.fetchval(
            "DELETE FROM engineers WHERE tenant_id = $1 RETURNING COUNT(*)",
            TEST_TENANT_ID,
        )

        logger.info(
            f"✅ クリア完了: プロジェクト{project_count or 0}件, エンジニア{engineer_count or 0}件"
        )

    except Exception as e:
        logger.error(f"❌ データクリア失敗: {str(e)}")


async def show_test_data_summary(conn):
    """テストデータの概要を表示"""
    logger.info("📊 テストデータ概要を表示中...")

    try:
        # プロジェクト概要
        projects = await conn.fetch(
            "SELECT title, skills FROM projects WHERE tenant_id = $1", TEST_TENANT_ID
        )

        # エンジニア概要
        engineers = await conn.fetch(
            "SELECT name, skills FROM engineers WHERE tenant_id = $1", TEST_TENANT_ID
        )

        print("\n" + "=" * 60)
        print("📁 作成されたテストプロジェクト:")
        print("=" * 60)
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project['title']}")
            print(f"   スキル: {', '.join(project['skills'][:4])}...")
            print()

        print("=" * 60)
        print("👥 作成されたテストエンジニア:")
        print("=" * 60)
        for i, engineer in enumerate(engineers, 1):
            print(f"{i}. {engineer['name']}")
            print(f"   スキル: {', '.join(engineer['skills'][:4])}...")
            print()

        print("=" * 60)
        print("🎯 期待される高マッチング:")
        print("=" * 60)
        print("• 田中太郎 ↔ React.js Webアプリ開発 (React, TypeScript)")
        print("• 佐藤花子 ↔ Python Django バックエンド開発 (Python, Django, ML)")
        print("• リー・ウェイ ↔ Java Spring Boot マイクロサービス (Java, Spring Boot)")
        print("• 山田健 ↔ React Native モバイルアプリ開発 (React Native, Mobile)")
        print("• 鈴木一郎 ↔ Vue.js + Node.js フルスタック開発 (Vue.js, Node.js)")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ 概要表示失敗: {str(e)}")


async def main():
    """メイン処理"""
    print("🧪 AI匹配テストデータ作成ツール")
    print("=" * 50)

    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)

        try:
            # 既存データをクリア
            await clear_existing_test_data(conn)

            # テストデータを作成
            project_ids = await create_test_projects(conn)
            engineer_ids = await create_test_engineers(conn)

            # 概要を表示
            await show_test_data_summary(conn)

            print("\n🎉 テストデータ作成完了!")
            print("\n📝 次のステップ:")
            print("1. python scripts/generate_embeddings.py --type both")
            print("2. python examples/ai_matching_examples.py")
            print("3. APIテストの実行")

            print(f"\n💡 テスト用租户ID: {TEST_TENANT_ID}")
            print("   この租户IDを使用してAPIテストを実行してください")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"❌ テストデータ作成失敗: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
