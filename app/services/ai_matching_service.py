# app/services/ai_matching_service.py
"""
AIマッチングサービス - 簡易版
データベースデフォルトのembedding類似度マッチングのみを使用し、すべてのカスタムビジネス重みを削除
"""

import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from fastapi import HTTPException

from .ai_matching_database import AIMatchingDatabase
from .embedding_generator_service import embedding_service
from ..schemas.ai_matching_schemas import (
    ProjectToEngineersMatchRequest,
    EngineerToProjectsMatchRequest,
    BulkMatchingRequest,
    MatchResult,
    MatchingHistoryResponse,
    ProjectToEngineersResponse,
    EngineerToProjectsResponse,
    BulkMatchingResponse,
)

logger = logging.getLogger(__name__)


class AIMatchingService:
    """AIマッチングサービス - 簡易版（データベースデフォルト類似度のみ）"""

    def __init__(self):
        self.db = AIMatchingDatabase()
        self.model_version = "pgvector_database_similarity"
        # 簡易版はAIモデルのロードが不要、データベース計算を直接使用
        logger.info(
            "AIマッチングサービスの初期化が完了しました（簡易版-データベース類似度のみ）"
        )

    def _validate_similarity_score(self, score: float, context: str = "") -> float:
        """類似度スコアの検証と修正"""
        if score is None or not isinstance(score, (int, float)):
            logger.warning(
                f"無効な類似度スコア {context}: {score}, デフォルト値 0.5 を使用"
            )
            return 0.5

        # スコアが[0,1]範囲内であることを確認
        if not (0 <= score <= 1):
            logger.warning(
                f"類似度スコアが範囲を超えています {context}: {score}, 修正します"
            )
            score = max(0, min(1, float(score)))

        return float(score)

    def _clean_skills_array(self, skills) -> List[str]:
        """清洗技能数组（全角→半角）"""
        if not skills:
            return []
        
        if isinstance(skills, str):
            # 如果是字符串，按逗号分割
            skills_str = skills.replace('，', ',')  # 全角逗号转半角
            skills_list = [s.strip() for s in skills_str.split(',') if s.strip()]
        elif isinstance(skills, list):
            # 如果已经是列表，直接使用
            skills_list = [str(s).strip() for s in skills if s]
        else:
            return []
        
        return skills_list

    def _calculate_overlapping_skills(self, project_skills: List[str], engineer_skills: List[str]) -> List[str]:
        """计算重叠技能"""
        if not project_skills or not engineer_skills:
            return []
        
        # 转换为集合进行交集运算
        project_skills_set = set(skill.strip().lower() for skill in project_skills if skill.strip())
        engineer_skills_set = set(skill.strip().lower() for skill in engineer_skills if skill.strip())
        
        # 计算交集
        overlapping = project_skills_set.intersection(engineer_skills_set)
        
        # 返回原始格式的技能（保持大小写）
        result = []
        for skill in project_skills:
            if skill.strip().lower() in overlapping:
                result.append(skill.strip())
        
        return result

    async def _create_match_results_from_db_results(
        self,
        similarity_results: List[Dict[str, Any]],
        target_info: Dict[str, Any],
        target_type: str,  # 'project' または 'engineer'
        max_matches: int,
        tenant_id: UUID,
    ) -> List[MatchResult]:
        """
        データベース類似度結果からMatchResultオブジェクトを作成

        Args:
            similarity_results: データベースが返した類似度結果
            target_info: ターゲットオブジェクト情報（プロジェクトまたはエンジニア）
            target_type: ターゲットタイプ
            max_matches: 最大マッチ数
        """
        matches = []

        for result in similarity_results[:max_matches]:
            try:
                similarity_score = self._validate_similarity_score(
                    result.get("similarity_score", 0), f"{target_type} matching"
                )

                if target_type == "project":
                    # プロジェクトマッチングエンジニア
                    project_id = target_info["id"]
                    engineer_id = result["id"]
                    project_title = target_info.get("title", "")
                    engineer_name = result.get("name", "")
                    # 担当者情報はターゲットプロジェクト情報から取得
                    project_manager_name = target_info.get("manager_name", "")
                    project_manager_email = target_info.get("manager_email", "")
                    project_created_by = (
                        str(target_info.get("created_by"))
                        if target_info.get("created_by")
                        else None
                    )
                    # エンジニアの会社と担当者情報はマッチング結果から取得
                    engineer_company_name = result.get(
                        "company_name", ""
                    )  # company_nameから取得に変更
                    engineer_company_type = result.get("company_type", "")
                    engineer_manager_name = result.get("manager_name", "")
                    engineer_manager_email = result.get("manager_email", "")
                else:
                    # エンジニアマッチングプロジェクト
                    project_id = result["id"]
                    engineer_id = target_info["id"]
                    # データベースからプロジェクト情報を取得する必要があります
                    project_info = await self.db.get_project_info(project_id, tenant_id)
                    project_title = (
                        project_info.get("title", "") if project_info else ""
                    )
                    engineer_name = target_info.get("name", "")
                    # 担当者情報は取得したプロジェクト情報から抽出
                    project_manager_name = (
                        project_info.get("manager_name", "") if project_info else ""
                    )
                    project_manager_email = (
                        project_info.get("manager_email", "") if project_info else ""
                    )
                    project_created_by = (
                        str(project_info.get("created_by"))
                        if project_info and project_info.get("created_by")
                        else None
                    )
                    # エンジニアの会社と担当者情報はターゲットエンジニア情報から取得
                    engineer_company_name = target_info.get(
                        "company_name", ""
                    )  # company_nameから取得に変更
                    engineer_company_type = target_info.get("company_type", "")
                    engineer_manager_name = target_info.get("manager_name", "")
                    engineer_manager_email = target_info.get("manager_email", "")

                # 技能分析
                if target_type == "project":
                    project_skills = target_info.get("skills", [])
                    engineer_skills = result.get("skills", [])
                else:
                    project_skills = project_info.get("skills", []) if 'project_info' in locals() and project_info else []
                    engineer_skills = target_info.get("skills", [])

                # 清洗技能数组
                project_skills_cleaned = self._clean_skills_array(project_skills)
                engineer_skills_cleaned = self._clean_skills_array(engineer_skills)
                
                # 计算重叠技能
                overlapping_skills = self._calculate_overlapping_skills(
                    project_skills_cleaned, engineer_skills_cleaned
                )

                # 簡易版：類似度スコアをマッチングスコアとして直接使用
                match_score = similarity_score
                confidence_score = (
                    similarity_score  # 簡易版：信頼度スコアはマッチングスコアと同じ
                )

                match = MatchResult(
                    id=uuid4(),
                    project_id=project_id,
                    engineer_id=engineer_id,
                    match_score=round(match_score, 3),
                    confidence_score=round(confidence_score, 3),
                    # 簡易版：詳細スコアは使用しない
                    skill_match_score=None,
                    experience_match_score=None,
                    project_experience_match_score=None,
                    japanese_level_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    # 簡易版：詳細スキルマッチングは分析しない
                    matched_skills=[],
                    missing_skills=[],
                    matched_experiences=[],
                    missing_experiences=[],
                    project_experience_match=[],
                    missing_project_experience=[],
                    # 簡易的なマッチング理由
                    match_reasons=[f"AIによるマッチ率: {similarity_score * 100:.1f}%"],
                    concerns=[],
                    project_title=project_title,
                    engineer_name=engineer_name,
                    status="未保存",
                    created_at=datetime.now(timezone.utc),
                    # 担当者情報
                    project_manager_name=project_manager_name,
                    project_manager_email=project_manager_email,
                    project_created_by=project_created_by,
                    # エンジニア会社情報
                    engineer_company_name=engineer_company_name,
                    engineer_company_type=engineer_company_type,
                    engineer_manager_name=engineer_manager_name,
                    engineer_manager_email=engineer_manager_email,
                    # 技能详细分析
                    project_skills_cleaned=project_skills_cleaned,
                    engineer_skills_cleaned=engineer_skills_cleaned,
                    overlapping_skills=overlapping_skills,
                )

                matches.append(match)

            except Exception as e:
                logger.error(f"マッチング結果の作成に失敗しました: {str(e)}")
                continue

        # マッチングスコア順に並び替え
        matches.sort(key=lambda x: x.match_score, reverse=True)

        logger.info(f"{len(matches)} 個のマッチング結果を作成しました")
        if matches:
            scores = [m.match_score for m in matches]
            logger.info(f"スコア範囲: {min(scores):.3f} - {max(scores):.3f}")

        return matches

    # ========== ベクトル生成関連メソッド ==========

    async def _ensure_project_embeddings(
        self, project_ids: List[UUID], tenant_id: UUID
    ) -> None:
        """
        欠落したプロジェクトベクトルのチェックと生成

        Args:
            project_ids: プロジェクトIDリスト
            tenant_id: テナントID
        """
        try:
            # ベクトルが缺落しているプロジェクトを取得
            projects_missing = await self.db.get_projects_with_embeddings(
                project_ids, tenant_id
            )

            if not projects_missing:
                logger.debug(
                    "すべてのプロジェクトに既にベクトルがあり、生成の必要はありません"
                )
                return

            logger.info(
                f"{len(projects_missing)} 個のプロジェクトのベクトルが欠落していることを発見、生成を開始..."
            )

            # バッチ処理
            project_data_list = list(projects_missing.values())
            batches = self._batch_items(project_data_list)

            total_updated = 0

            for batch_idx, batch in enumerate(batches):
                logger.info(
                    f"プロジェクトベクトル生成バッチ {batch_idx + 1}/{len(batches)} ({len(batch)} 個のプロジェクト)を処理"
                )

                # paraphraseテキストの生成
                paraphrases = []
                for project in batch:
                    paraphrase = embedding_service.create_project_paraphrase(project)
                    paraphrases.append(paraphrase)

                # ベクトルの生成
                embeddings = embedding_service.generate_embeddings(paraphrases)

                # 更新データの準備
                update_data = []
                for project, paraphrase, embedding in zip(
                    batch, paraphrases, embeddings
                ):
                    update_data.append(
                        {
                            "id": project["id"],
                            "paraphrase": paraphrase,
                            "embedding": embedding,
                        }
                    )

                # データベースの一括更新
                updated_count = await self.db.update_project_embeddings(update_data)
                total_updated += updated_count

                logger.info(
                    f"バッチ {batch_idx + 1} 完了、{updated_count} 個のプロジェクトベクトルを更新"
                )

            logger.info(
                f"✅ プロジェクトベクトル生成完了、合計更新: {total_updated}/{len(projects_missing)}"
            )

        except Exception as e:
            logger.error(f"❌ プロジェクトベクトル生成に失敗しました: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"プロジェクトベクトル生成に失敗しました: {str(e)}",
            )

    async def _ensure_engineer_embeddings(
        self, engineer_ids: List[UUID], tenant_id: UUID
    ) -> None:
        """
        缺落したエンジニアベクトルのチェックと生成

        Args:
            engineer_ids: エンジニアIDリスト
            tenant_id: テナントID
        """
        try:
            # ベクトルが缺落しているエンジニアを取得
            engineers_missing = await self.db.get_engineers_with_embeddings(
                engineer_ids, tenant_id
            )

            if not engineers_missing:
                logger.debug(
                    "すべてのエンジニアに既にベクトルがあり、生成の必要はありません"
                )
                return

            logger.info(
                f"{len(engineers_missing)} 個のエンジニアのベクトルが欠落していることを発見、生成を開始..."
            )

            # バッチ処理
            engineer_data_list = list(engineers_missing.values())
            batches = self._batch_items(engineer_data_list)

            total_updated = 0

            for batch_idx, batch in enumerate(batches):
                logger.info(
                    f"エンジニアベクトル生成バッチ {batch_idx + 1}/{len(batches)} ({len(batch)} 個のエンジニア)を処理"
                )

                # paraphraseテキストの生成
                paraphrases = []
                for engineer in batch:
                    paraphrase = embedding_service.create_engineer_paraphrase(engineer)
                    paraphrases.append(paraphrase)

                # ベクトルの生成
                embeddings = embedding_service.generate_embeddings(paraphrases)

                # 更新データの準備
                update_data = []
                for engineer, paraphrase, embedding in zip(
                    batch, paraphrases, embeddings
                ):
                    update_data.append(
                        {
                            "id": engineer["id"],
                            "paraphrase": paraphrase,
                            "embedding": embedding,
                        }
                    )

                # データベースの一括更新
                updated_count = await self.db.update_engineer_embeddings(update_data)
                total_updated += updated_count

                logger.info(
                    f"バッチ {batch_idx + 1} 完了、{updated_count} 個のエンジニアベクトルを更新"
                )

            logger.info(
                f"✅ エンジニアベクトル生成完了、合計更新: {total_updated}/{len(engineers_missing)}"
            )

        except Exception as e:
            logger.error(f"❌ エンジニアベクトル生成に失敗しました: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"エンジニアベクトル生成に失敗しました: {str(e)}",
            )

    def _batch_items(self, items: List[Any], batch_size: int = 32) -> List[List[Any]]:
        """
        リストのバッチ処理

        Args:
            items: バッチ化するアイテムリスト
            batch_size: バッチサイズ、デフォルトは32

        Returns:
            List[List[Any]]: バッチ化されたリスト
        """
        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i : i + batch_size])
        return batches

    # ========== メインAPIメソッド ==========

    async def match_project_to_engineers(
        self, request: ProjectToEngineersMatchRequest
    ) -> ProjectToEngineersResponse:
        """プロジェクトマッチングエンジニア（簡易版）"""
        start_time = time.time()

        try:
            logger.info(
                f"プロジェクトマッチングエンジニアを開始: project_id={request.project_id}"
            )

            # マッチング履歴の作成
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="project_to_engineers",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=[request.project_id],
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # ステップ1: プロジェクト情報を取得し、ベクトルがあることを確認
                project_info = await self.db.get_project_info(
                    request.project_id, request.tenant_id
                )
                if not project_info:
                    raise ValueError(
                        f"プロジェクトが存在しません: {request.project_id}"
                    )

                # 自動でプロジェクトベクトルをチェックして生成
                await self._ensure_project_embeddings(
                    [request.project_id], request.tenant_id
                )

                # プロジェクト情報を再取得（現在はベクトルがあるはず）
                project_info = await self.db.get_project_info(
                    request.project_id, request.tenant_id
                )

                if not project_info.get("ai_match_embedding"):
                    raise ValueError(
                        f"プロジェクトベクトルの生成に失敗しました: {request.project_id}"
                    )

                # まずすべてのアクティブエンジニアIDを取得してembeddingsを生成
                all_engineers = await self.db.get_all_active_engineers(
                    request.tenant_id
                )
                if all_engineers:
                    all_engineer_ids = [e["id"] for e in all_engineers]
                    await self._ensure_engineer_embeddings(
                        all_engineer_ids, request.tenant_id
                    )

                # 候補エンジニアを取得（現在すべてのアクティブエンジニアにembeddingsがあるはず）
                candidate_engineers = await self.db.get_candidate_engineers(
                    request.tenant_id, request.filters or {}
                )

                logger.info(
                    f"{len(candidate_engineers)} 個の候補エンジニアが見つかりました"
                )

                if not candidate_engineers:
                    logger.warning("候補エンジニアが見つかりませんでした")
                    matches = []
                else:
                    # ステップ4: 候補エンジニアIDリストを取得し、ベクトルがあることを確認
                    engineer_ids = [e["id"] for e in candidate_engineers]

                    # 自動でエンジニアベクトルをチェックして生成
                    await self._ensure_engineer_embeddings(
                        engineer_ids, request.tenant_id
                    )

                    # データベースで直接類似度を計算
                    similarity_results = (
                        await self.db.calculate_similarities_by_database(
                            target_embedding=project_info["ai_match_embedding"],
                            candidate_ids=engineer_ids,
                            table_type="engineers",
                            max_matches=request.max_matches,
                            min_score=request.min_score,
                        )
                    )

                    # マッチング結果を作成
                    matches = await self._create_match_results_from_db_results(
                        similarity_results=similarity_results,
                        target_info=project_info,
                        target_type="project",
                        max_matches=request.max_matches,
                        tenant_id=request.tenant_id,
                    )

                # マッチング結果を保存
                saved_matches = await self.db.save_matches(
                    matches, matching_history["id"]
                )

                # 統計情報を計算
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # マッチング履歴を更新
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    engineer_ids=[e["id"] for e in candidate_engineers],
                )

                logger.info(
                    f"プロジェクトマッチング完了: {len(saved_matches)} 個のマッチングを生成"
                )

                return ProjectToEngineersResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    project_info=self.db.format_project_info(project_info),
                    matched_engineers=saved_matches,
                    recommendations=self._generate_simple_recommendations(
                        "project", len(saved_matches), high_quality_matches
                    ),
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"プロジェクトマッチングエンジニアに失敗しました: {str(e)}")
            raise Exception(f"マッチングに失敗しました: {str(e)}")

    async def match_engineer_to_projects(
        self, request: EngineerToProjectsMatchRequest
    ) -> EngineerToProjectsResponse:
        """エンジニアマッチングプロジェクト（簡易版）"""
        start_time = time.time()

        try:
            logger.info(
                f"エンジニアマッチングプロジェクトを開始: engineer_id={request.engineer_id}"
            )

            # マッチング履歴の作成
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="engineer_to_projects",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                engineer_ids=[request.engineer_id],
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # ステップ1: エンジニア情報を取得し、ベクトルがあることを確認
                engineer_info = await self.db.get_engineer_info(
                    request.engineer_id, request.tenant_id
                )
                if not engineer_info:
                    raise ValueError(f"エンジニアが存在しません: {request.engineer_id}")

                # 自動でエンジニアベクトルをチェックして生成
                await self._ensure_engineer_embeddings(
                    [request.engineer_id], request.tenant_id
                )

                # エンジニア情報を再取得（現在はベクトルがあるはず）
                engineer_info = await self.db.get_engineer_info(
                    request.engineer_id, request.tenant_id
                )

                if not engineer_info.get("ai_match_embedding"):
                    raise ValueError(
                        f"エンジニアベクトルの生成に失敗しました: {request.engineer_id}"
                    )

                # まずすべてのアクティブプロジェクトIDを取得してembeddingsを生成
                all_projects = await self.db.get_all_active_projects(request.tenant_id)
                if all_projects:
                    all_project_ids = [p["id"] for p in all_projects]
                    await self._ensure_project_embeddings(
                        all_project_ids, request.tenant_id
                    )

                # 候補プロジェクトを取得（現在すべてのアクティブプロジェクトにembeddingsがあるはず）
                candidate_projects = await self.db.get_candidate_projects(
                    request.tenant_id, request.filters or {}
                )

                logger.info(
                    f"{len(candidate_projects)} 個の候補プロジェクトが見つかりました"
                )

                if not candidate_projects:
                    logger.warning("候補プロジェクトが見つかりませんでした")
                    matches = []
                else:
                    # ステップ4: 候補プロジェクトIDリストを取得し、ベクトルがあることを確認
                    project_ids = [p["id"] for p in candidate_projects]

                    # 自動でプロジェクトベクトルをチェックして生成
                    await self._ensure_project_embeddings(
                        project_ids, request.tenant_id
                    )

                    # データベースで直接類似度を計算
                    similarity_results = (
                        await self.db.calculate_similarities_by_database(
                            target_embedding=engineer_info["ai_match_embedding"],
                            candidate_ids=project_ids,
                            table_type="projects",
                            max_matches=request.max_matches,
                            min_score=request.min_score,
                        )
                    )

                    # マッチング結果を作成
                    matches = await self._create_match_results_from_db_results(
                        similarity_results=similarity_results,
                        target_info=engineer_info,
                        target_type="engineer",
                        max_matches=request.max_matches,
                        tenant_id=request.tenant_id,
                    )

                # マッチング結果を保存
                saved_matches = await self.db.save_matches(
                    matches, matching_history["id"]
                )

                # 統計情報を計算
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # マッチング履歴を更新
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    project_ids=[p["id"] for p in candidate_projects],
                )

                logger.info(
                    f"エンジニアマッチング完了: {len(saved_matches)} 個のマッチングを生成"
                )

                return EngineerToProjectsResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    engineer_info=self.db.format_engineer_info(engineer_info),
                    matched_projects=saved_matches,
                    recommendations=self._generate_simple_recommendations(
                        "engineer", len(saved_matches), high_quality_matches
                    ),
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"エンジニアマッチングプロジェクトに失敗しました: {str(e)}")
            raise Exception(f"マッチングに失敗しました: {str(e)}")

    async def bulk_matching(self, request: BulkMatchingRequest) -> BulkMatchingResponse:
        """バッチマッチング（簡易版）"""
        start_time = time.time()

        try:
            logger.info("バッチマッチングを開始")

            # マッチング履歴の作成
            matching_history = await self.db.create_matching_history(
                tenant_id=request.tenant_id,
                matching_type="bulk_matching",
                trigger_type=request.trigger_type,
                executed_by=request.executed_by,
                project_ids=request.project_ids,
                engineer_ids=request.engineer_ids,
                filters=request.filters or {},
                ai_model_version=self.model_version,
            )

            try:
                # 新しいフィルターパラメータを含むフィルター条件を構築
                filters = dict(request.filters or {})
                if request.project_company_type is not None:
                    filters["project_company_type"] = request.project_company_type
                if request.engineer_company_type is not None:
                    filters["engineer_company_type"] = request.engineer_company_type
                if request.project_start_date is not None:
                    filters["project_start_date"] = request.project_start_date

                # プロジェクトとエンジニアデータを取得
                if request.project_ids:
                    candidate_projects = []
                    for project_id in request.project_ids:
                        project = await self.db.get_project_info(
                            project_id, request.tenant_id
                        )
                        if project:
                            candidate_projects.append(project)
                else:
                    candidate_projects = await self.db.get_candidate_projects(
                        request.tenant_id, filters
                    )

                if request.engineer_ids:
                    candidate_engineers = []
                    for engineer_id in request.engineer_ids:
                        engineer = await self.db.get_engineer_info(
                            engineer_id, request.tenant_id
                        )
                        if engineer:
                            candidate_engineers.append(engineer)
                else:
                    candidate_engineers = await self.db.get_candidate_engineers(
                        request.tenant_id, filters
                    )

                # すべてのプロジェクトとエンジニアにベクトルがあることを確認
                if candidate_projects:
                    project_ids = [p["id"] for p in candidate_projects]
                    await self._ensure_project_embeddings(
                        project_ids, request.tenant_id
                    )

                    # プロジェクトデータを再取得（現在すべてにベクトルがあるはず）
                    candidate_projects = []
                    for project_id in project_ids:
                        project = await self.db.get_project_info(
                            project_id, request.tenant_id
                        )
                        if project and project.get("ai_match_embedding"):
                            candidate_projects.append(project)

                if candidate_engineers:
                    engineer_ids = [e["id"] for e in candidate_engineers]
                    await self._ensure_engineer_embeddings(
                        engineer_ids, request.tenant_id
                    )

                    # エンジニアデータを再取得（現在すべてにベクトルがあるはず）
                    candidate_engineers = []
                    for engineer_id in engineer_ids:
                        engineer = await self.db.get_engineer_info(
                            engineer_id, request.tenant_id
                        )
                        if engineer and engineer.get("ai_match_embedding"):
                            candidate_engineers.append(engineer)

                logger.info(
                    f"バッチマッチング：{len(candidate_projects)} 個のプロジェクト × {len(candidate_engineers)} 個のエンジニア"
                )

                all_matches = []
                top_matches_by_project = {}

                # すべての候補プロジェクトを処理
                max_projects = len(candidate_projects)

                for i, project in enumerate(candidate_projects):
                    logger.info(
                        f"プロジェクト処理 {i+1}/{max_projects}: {project.get('title', '')}"
                    )

                    try:
                        # エンジニアIDリストを取得
                        engineer_ids = [e["id"] for e in candidate_engineers]

                        # データベースで類似度を計算
                        similarity_results = (
                            await self.db.calculate_similarities_by_database(
                                target_embedding=project["ai_match_embedding"],
                                candidate_ids=engineer_ids,
                                table_type="engineers",
                                max_matches=request.max_matches,
                                min_score=request.min_score,
                            )
                        )

                        # マッチング結果を作成
                        project_matches = (
                            await self._create_match_results_from_db_results(
                                similarity_results=similarity_results,
                                target_info=project,
                                target_type="project",
                                max_matches=request.max_matches,
                                tenant_id=request.tenant_id,
                            )
                        )

                        if project_matches:
                            all_matches.extend(project_matches)
                            top_matches_by_project[str(project["id"])] = (
                                project_matches[:3]
                            )

                    except Exception as e:
                        logger.error(
                            f"プロジェクト処理に失敗しました {project['id']}: {str(e)}"
                        )
                        continue

                # すべてのマッチングを保存
                saved_matches = await self.db.save_matches(
                    all_matches, matching_history["id"]
                )

                # 統計情報を計算
                processing_time = int(time.time() - start_time)
                high_quality_matches = len(
                    [m for m in saved_matches if m.match_score >= 0.8]
                )

                # マッチング履歴を更新
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="completed",
                    total_projects_input=len(candidate_projects),
                    total_engineers_input=len(candidate_engineers),
                    total_matches_generated=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    ai_config={
                        "algorithm": "database_pgvector_similarity",
                        "batch_size": 32,  # 固定バッチサイズ
                        "model_version": self.model_version,
                        "use_custom_weights": False,
                    },
                    project_ids=[p["id"] for p in candidate_projects],
                    engineer_ids=[e["id"] for e in candidate_engineers],
                )

                logger.info(
                    f"バッチマッチング完了: {len(saved_matches)} 個のマッチングを生成"
                )

                return BulkMatchingResponse(
                    matching_history=MatchingHistoryResponse(**matching_history),
                    matches=saved_matches,
                    total_matches=len(saved_matches),
                    high_quality_matches=high_quality_matches,
                    processing_time_seconds=processing_time,
                    batch_summary={
                        "total_projects": len(candidate_projects),
                        "total_engineers": len(candidate_engineers),
                        "processed_projects": max_projects,
                        "average_match_score": (
                            sum(m.match_score for m in saved_matches)
                            / len(saved_matches)
                            if saved_matches
                            else 0
                        ),
                        "algorithm": "database_pgvector_similarity",
                    },
                    top_matches_by_project=top_matches_by_project,
                    top_matches_by_engineer={},  # 簡易版は一時的に実装しない
                    recommendations=self._generate_simple_recommendations(
                        "bulk", len(saved_matches), high_quality_matches
                    ),
                    warnings=(
                        []
                        if len(saved_matches) > 0
                        else ["条件に合致するマッチングが見つかりません"]
                    ),
                )

            except Exception as e:
                await self.db.update_matching_history(
                    matching_history["id"],
                    execution_status="failed",
                    error_message=str(e),
                )
                raise

        except Exception as e:
            logger.error(f"バッチマッチングに失敗しました: {str(e)}")
            raise Exception(f"バッチマッチングに失敗しました: {str(e)}")

    # ========== クエリメソッド（データベース層への委譲） ==========

    async def get_matching_history(
        self, tenant_id: UUID, history_id: Optional[UUID] = None, limit: int = 20
    ) -> List[MatchingHistoryResponse]:
        """マッチング履歴を取得"""
        try:
            histories_data = await self.db.get_matching_history(
                tenant_id, history_id, limit
            )
            return [MatchingHistoryResponse(**data) for data in histories_data]
        except Exception as e:
            logger.error(f"マッチング履歴の取得に失敗しました: {str(e)}")
            return []

    async def get_matches_by_history(
        self, history_id: UUID, tenant_id: UUID, limit: int = 100
    ) -> List[MatchResult]:
        """履歴IDに基づいてマッチング結果を取得"""
        try:
            matches_data = await self.db.get_matches_by_history(
                history_id, tenant_id, limit
            )

            matches = []
            for data in matches_data:
                match = MatchResult(
                    id=data["id"],
                    project_id=data["project_id"],
                    engineer_id=data["engineer_id"],
                    match_score=(
                        float(data["match_score"]) if data["match_score"] else 0.0
                    ),
                    confidence_score=(
                        float(data["confidence_score"])
                        if data["confidence_score"]
                        else 0.0
                    ),
                    # 簡易版：詳細スコアは使用しない
                    skill_match_score=None,
                    experience_match_score=None,
                    project_experience_match_score=None,
                    japanese_level_match_score=None,
                    budget_match_score=None,
                    location_match_score=None,
                    matched_skills=[],
                    missing_skills=[],
                    matched_experiences=[],
                    missing_experiences=[],
                    project_experience_match=[],
                    missing_project_experience=[],
                    match_reasons=data["match_reasons"] or ["embedding類似度に基づく"],
                    concerns=[],
                    project_title=data["project_title"],
                    engineer_name=data["engineer_name"],
                    status=data["status"],
                    created_at=data["created_at"],
                )
                matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"履歴によるマッチング結果の取得に失敗しました: {str(e)}")
            return []

    async def update_match_status(
        self,
        match_id: UUID,
        tenant_id: UUID,
        status: str,
        comment: Optional[str] = None,
        reviewed_by: Optional[UUID] = None,
    ) -> bool:
        """マッチングステータスを更新"""
        return await self.db.update_match_status(
            match_id, tenant_id, status, comment, reviewed_by
        )

    # ========== ユーティリティメソッド ==========

    def _generate_simple_recommendations(
        self, match_type: str, total_matches: int, high_quality_matches: int
    ) -> List[str]:
        """簡易化された推奨提案を生成"""
        recommendations = []

        if total_matches == 0:
            recommendations.append(
                "マッチング結果が見つかりません、フィルター条件を調整するか最小スコア要件を下げることをお勧めします"
            )
        elif high_quality_matches == 0:
            recommendations.append(
                "高品質なマッチング（0.8+）がありません、より低いスコアのマッチングを確認することをお勧めします"
            )
        elif high_quality_matches >= 5:
            recommendations.append(
                "複数の高品質マッチングがあります、最初の数個を優先的に注目することをお勧めします"
            )
        else:
            recommendations.append(
                f"{high_quality_matches} 個の高品質マッチングが見つかりました"
            )

        if match_type == "bulk":
            recommendations.append(
                "バッチマッチングはAIベクトル類似度に基づいており、人工的なビジネスルールの介入はありません"
            )
        else:
            recommendations.append(
                "マッチング結果はAIベクトル類似度計算に基づいており、スコアが高いほど類似度が高いことを表します"
            )

        return recommendations
