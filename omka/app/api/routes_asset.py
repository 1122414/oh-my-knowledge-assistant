from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import col, select

from omka.app.core.config import settings
from omka.app.core.logging import logger
from omka.app.services.action_service import AssetService
from omka.app.storage.db import KnowledgeAsset, get_session

router = APIRouter()


class AssetCreateRequest(BaseModel):
    asset_type: str
    title: str
    source_type: str = "upload"
    content_hash: str = ""
    tags: list[str] | None = None


@router.get("")
async def list_assets(asset_type: str | None = None, status: str | None = None):
    assets = AssetService.list_assets(asset_type=asset_type, status=status)
    return {"assets": [a.model_dump() for a in assets]}


@router.post("/upload")
async def upload_asset(file: UploadFile):
    import hashlib
    import uuid
    from pathlib import Path

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()[:32]

    ext = Path(file.filename or "unknown").suffix.lstrip(".")
    asset_type = "image" if ext in settings.asset_allowed_image_types.split(",") else "document"
    if ext in ["pdf"]:
        asset_type = "pdf"

    asset_dir = settings.assets_dir / ("images" if asset_type == "image" else "documents")
    asset_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{uuid.uuid4().hex[:16]}.{ext}"
    file_path = asset_dir / file_name
    file_path.write_bytes(content)

    asset = AssetService.create_asset(
        asset_type=asset_type,
        title=file.filename or "未命名",
        file_path=str(file_path.relative_to(settings.data_dir)),
        original_filename=file.filename,
        mime_type=file.content_type,
        size_bytes=len(content),
        content_hash=content_hash,
    )

    logger.info("上传资产 | id=%s | type=%s | size=%d", asset.id, asset_type, len(content))
    return {"id": asset.id, "status": "uploaded", "asset_type": asset_type}


@router.get("/{asset_id}")
async def get_asset(asset_id: str):
    asset = AssetService.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    return asset.model_dump()


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str):
    with get_session() as session:
        asset = session.get(KnowledgeAsset, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="资产不存在")
        asset.status = "archived"
        session.add(asset)
        session.commit()
    return {"id": asset_id, "message": "资产已归档"}
