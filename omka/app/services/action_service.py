from datetime import datetime
from typing import Any

from sqlmodel import col, func, select

from omka.app.core.logging import logger
from omka.app.storage.db import (
    CandidateItem,
    KnowledgeItem,
    PushEvent,
    PushPolicy,
    SourceConfig,
    SystemAction,
    get_session,
)


class PermissionService:
    """权限服务：检查用户权限级别"""

    LEVELS = {"viewer": 0, "operator": 1, "admin": 2}

    @staticmethod
    def get_user_level(actor_id: str) -> str:
        from omka.app.core.settings_service import get_setting

        admin_ids = get_setting("feishu_admin_open_ids", "")
        admin_list = [id.strip() for id in admin_ids.split(",") if id.strip()]
        if actor_id in admin_list:
            return "admin"

        operator_ids = get_setting("feishu_operator_open_ids", "")
        operator_list = [id.strip() for id in operator_ids.split(",") if id.strip()]
        if actor_id in operator_list:
            return "operator"

        return "viewer"

    @staticmethod
    def check_permission(actor_id: str, required_level: str) -> bool:
        user_level = PermissionService.get_user_level(actor_id)
        user_level_value = PermissionService.LEVELS.get(user_level, 0)
        required_level_value = PermissionService.LEVELS.get(required_level, 0)
        return user_level_value >= required_level_value


class ActionService:
    """系统操作服务：封装可审计的系统操作，所有变更通过 ActionService 执行"""

    @staticmethod
    def create_action(
        action_type: str,
        actor_channel: str,
        actor_external_id: str,
        target_type: str,
        target_id: str | None = None,
        request_text: str | None = None,
        params_json: dict | None = None,
    ) -> SystemAction:
        with get_session() as session:
            action = SystemAction(
                action_type=action_type,
                actor_channel=actor_channel,
                actor_external_id=actor_external_id,
                target_type=target_type,
                target_id=target_id,
                request_text=request_text,
                params_json=params_json or {},
            )
            session.add(action)
            session.commit()
            session.refresh(action)
        logger.info("创建系统操作 | id=%d | type=%s | actor=%s", action.id, action_type, actor_external_id)
        return action

    @staticmethod
    def complete_action(action_id: int, status: str, result_json: dict | None = None, error_message: str | None = None) -> None:
        with get_session() as session:
            action = session.get(SystemAction, action_id)
            if action:
                action.status = status
                action.result_json = result_json or {}
                action.error_message = error_message
                if status == "success":
                    action.confirmed_at = datetime.utcnow()
                session.add(action)
                session.commit()


class SourceActionService:
    """信息源操作服务"""

    @staticmethod
    def list_sources(enabled_only: bool = False) -> list[SourceConfig]:
        with get_session() as session:
            query = select(SourceConfig)
            if enabled_only:
                query = query.where(SourceConfig.enabled == True)
            return list(session.exec(query).all())

    @staticmethod
    def get_source(source_id: str) -> SourceConfig | None:
        with get_session() as session:
            return session.get(SourceConfig, source_id)

    @staticmethod
    def create_source(
        source_id: str,
        name: str,
        source_type: str,
        mode: str,
        repo_full_name: str | None = None,
        query: str | None = None,
        limit: int = 5,
        weight: float = 1.0,
    ) -> SourceConfig:
        config = SourceConfig(
            id=source_id,
            source_type=source_type,
            name=name,
            mode=mode,
            repo_full_name=repo_full_name,
            query=query,
            limit=limit,
            weight=weight,
        )
        with get_session() as session:
            config = session.merge(config)
            session.commit()
            session.refresh(config)
        logger.info("创建信息源 | id=%s | name=%s | mode=%s", source_id, name, mode)
        return config

    @staticmethod
    def delete_source(source_id: str) -> bool:
        with get_session() as session:
            config = session.get(SourceConfig, source_id)
            if not config:
                return False
            session.delete(config)
            session.commit()
        logger.info("删除信息源 | id=%s", source_id)
        return True

    @staticmethod
    def set_source_enabled(source_id: str, enabled: bool) -> bool:
        with get_session() as session:
            config = session.get(SourceConfig, source_id)
            if not config:
                return False
            config.enabled = enabled
            config.updated_at = datetime.utcnow()
            session.add(config)
            session.commit()
        logger.info("更新信息源状态 | id=%s | enabled=%s", source_id, enabled)
        return True


class CandidateActionService:
    """候选知识操作服务"""

    @staticmethod
    def list_candidates(status: str = "pending", limit: int = 20) -> list[CandidateItem]:
        with get_session() as session:
            return list(
                session.exec(
                    select(CandidateItem)
                    .where(CandidateItem.status == status)
                    .order_by(col(CandidateItem.score).desc())
                    .limit(limit)
                ).all()
            )

    @staticmethod
    def get_candidate(candidate_id: str) -> CandidateItem | None:
        with get_session() as session:
            return session.get(CandidateItem, candidate_id)

    @staticmethod
    def confirm_candidate(candidate_id: str) -> bool:
        with get_session() as session:
            candidate = session.get(CandidateItem, candidate_id)
            if not candidate:
                return False
            candidate.status = "confirmed"
            candidate.updated_at = datetime.utcnow()
            session.add(candidate)
            session.commit()

            from omka.app.storage.db import KnowledgeItem
            knowledge = KnowledgeItem(
                id=candidate_id,
                candidate_item_id=candidate_id,
                title=candidate.title,
                url=candidate.url,
                item_type=candidate.item_type,
                content=candidate.summary or "",
                summary=candidate.summary,
                tags=candidate.matched_interests or [],
            )
            session.add(knowledge)
            session.commit()
        logger.info("候选入库 | id=%s", candidate_id)
        return True

    @staticmethod
    def ignore_candidate(candidate_id: str) -> bool:
        with get_session() as session:
            candidate = session.get(CandidateItem, candidate_id)
            if not candidate:
                return False
            candidate.status = "ignored"
            candidate.updated_at = datetime.utcnow()
            session.add(candidate)
            session.commit()
        logger.info("候选忽略 | id=%s", candidate_id)
        return True

    @staticmethod
    def ignore_all_candidates() -> int:
        count = 0
        with get_session() as session:
            candidates = session.exec(
                select(CandidateItem).where(CandidateItem.status == "pending")
            ).all()
            for candidate in candidates:
                candidate.status = "ignored"
                candidate.updated_at = datetime.utcnow()
                session.add(candidate)
                count += 1
            session.commit()
        logger.info("批量忽略候选 | count=%d", count)
        return count

    @staticmethod
    def read_later_candidate(candidate_id: str) -> bool:
        with get_session() as session:
            candidate = session.get(CandidateItem, candidate_id)
            if not candidate:
                return False
            candidate.status = "read_later"
            candidate.updated_at = datetime.utcnow()
            session.add(candidate)
            session.commit()
        logger.info("候选稍后读 | id=%s", candidate_id)
        return True


class KnowledgeActionService:
    """知识库操作服务"""

    @staticmethod
    def list_knowledge(limit: int = 20) -> list[KnowledgeItem]:
        with get_session() as session:
            return list(
                session.exec(
                    select(KnowledgeItem)
                    .order_by(col(KnowledgeItem.created_at).desc())
                    .limit(limit)
                ).all()
            )

    @staticmethod
    def search_knowledge(keyword: str, limit: int = 10) -> list[KnowledgeItem]:
        with get_session() as session:
            query = select(KnowledgeItem).where(
                (KnowledgeItem.title.contains(keyword)) |
                (KnowledgeItem.content.contains(keyword)) |
                (KnowledgeItem.summary.contains(keyword))
            ).limit(limit)
            return list(session.exec(query).all())

    @staticmethod
    def delete_knowledge(knowledge_id: str) -> bool:
        with get_session() as session:
            item = session.get(KnowledgeItem, knowledge_id)
            if not item:
                return False
            session.delete(item)
            session.commit()
        logger.info("删除知识条目 | id=%s", knowledge_id)
        return True


class ConfigActionService:
    """配置操作服务：支持查看和修改非敏感配置"""

    @staticmethod
    def _get_sensitive_keys() -> set[str]:
        from omka.app.core.settings_service import SENSITIVE_KEYS
        return SENSITIVE_KEYS

    @staticmethod
    def list_config(mask_secrets: bool = True) -> dict[str, Any]:
        from omka.app.core.settings_service import get_all_settings
        return get_all_settings(mask_secrets=mask_secrets)

    @staticmethod
    def get_config(key: str) -> Any | None:
        from omka.app.core.settings_service import get_setting
        return get_setting(key)

    @staticmethod
    def set_config(key: str, value: Any) -> tuple[bool, str]:
        if key.lower() in ConfigActionService._get_sensitive_keys():
            return False, f"配置项 {key} 为敏感字段，不允许通过飞书修改"
        from omka.app.core.settings_service import set_setting
        try:
            set_setting(key, value)
            return True, f"配置 {key} 已更新"
        except Exception as e:
            logger.error("更新配置失败 | key=%s | error=%s", key, e)
            return False, f"更新失败: {str(e)}"

    @staticmethod
    def is_sensitive(key: str) -> bool:
        return key.lower() in ConfigActionService._get_sensitive_keys()


class PushService:
    @staticmethod
    def create_policy(
        policy_id: str,
        name: str,
        trigger_type: str,
        threshold: float | None = None,
        max_per_day: int = 5,
    ) -> PushPolicy:
        with get_session() as session:
            policy = PushPolicy(
                id=policy_id,
                name=name,
                trigger_type=trigger_type,
                threshold=threshold,
                max_per_day=max_per_day,
            )
            session.add(policy)
            session.commit()
            session.refresh(policy)
        return policy

    @staticmethod
    def list_policies(enabled_only: bool = True) -> list[PushPolicy]:
        with get_session() as session:
            query = select(PushPolicy)
            if enabled_only:
                query = query.where(PushPolicy.enabled == True)
            return list(session.exec(query).all())

    @staticmethod
    def record_event(
        policy_id: str,
        target_id: str,
        title: str,
        content: str,
        status: str = "pending",
    ) -> PushEvent:
        with get_session() as session:
            event = PushEvent(
                policy_id=policy_id,
                channel="feishu",
                target_id=target_id,
                title=title,
                content=content,
                status=status,
            )
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    @staticmethod
    def count_today_events(policy_id: str | None = None) -> int:
        from datetime import timedelta
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        with get_session() as session:
            query = select(func.count(PushEvent.id)).where(PushEvent.created_at >= today)
            if policy_id:
                query = query.where(PushEvent.policy_id == policy_id)
            return session.exec(query).one()


class AssetService:
    @staticmethod
    def create_asset(
        asset_type: str,
        title: str,
        source_type: str = "upload",
        file_path: str | None = None,
        original_filename: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        content_hash: str = "",
        tags: list[str] | None = None,
    ) -> Any:
        import uuid
        from omka.app.storage.db import KnowledgeAsset

        asset_id = f"asset_{uuid.uuid4().hex[:16]}"
        with get_session() as session:
            asset = KnowledgeAsset(
                id=asset_id,
                asset_type=asset_type,
                title=title,
                source_type=source_type,
                file_path=file_path,
                original_filename=original_filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                content_hash=content_hash,
                tags=tags or [],
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
        logger.info("创建资产 | id=%s | type=%s | title=%s", asset_id, asset_type, title)
        return asset

    @staticmethod
    def list_assets(asset_type: str | None = None, status: str | None = None) -> list[Any]:
        from omka.app.storage.db import KnowledgeAsset

        with get_session() as session:
            query = select(KnowledgeAsset)
            if asset_type:
                query = query.where(KnowledgeAsset.asset_type == asset_type)
            if status:
                query = query.where(KnowledgeAsset.status == status)
            query = query.order_by(col(KnowledgeAsset.created_at).desc())
            return list(session.exec(query).all())

    @staticmethod
    def get_asset(asset_id: str) -> Any | None:
        from omka.app.storage.db import KnowledgeAsset

        with get_session() as session:
            return session.get(KnowledgeAsset, asset_id)

    @staticmethod
    def update_asset_status(asset_id: str, status: str, extracted_text: str | None = None, summary: str | None = None) -> Any | None:
        from omka.app.storage.db import KnowledgeAsset

        with get_session() as session:
            asset = session.get(KnowledgeAsset, asset_id)
            if not asset:
                return None
            asset.status = status
            if extracted_text is not None:
                asset.extracted_text = extracted_text
            if summary is not None:
                asset.summary = summary
            asset.updated_at = datetime.utcnow()
            session.add(asset)
            session.commit()
            session.refresh(asset)
        return asset
