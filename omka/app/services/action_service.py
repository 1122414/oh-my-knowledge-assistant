from datetime import datetime
from typing import Any

from sqlmodel import col, func, select

from omka.app.core.logging import logger
from omka.app.storage.db import (
    PushEvent,
    PushPolicy,
    SystemAction,
    get_session,
)


class ActionService:
    @staticmethod
    def check_permission(actor_id: str, required_level: str) -> bool:
        from omka.app.core.settings_service import get_setting

        admin_ids = get_setting("feishu_admin_open_ids", "")
        admin_list = [id.strip() for id in admin_ids.split(",") if id.strip()]
        if actor_id in admin_list:
            return True
        if required_level == "viewer":
            return True
        return False

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
