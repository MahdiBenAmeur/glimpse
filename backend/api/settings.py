from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.app_settings_service import load_app_settings, update_app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class AppSettingsResponse(BaseModel):
    rememberLastPage: bool
    confirmDestructiveActions: bool
    doubleClickBehavior: Literal["viewer", "external"]
    includeSubfoldersByDefault: bool
    skipHiddenFolders: bool
    faceDetectionEnabled: bool
    compactSidebar: bool
    thumbnailDensity: Literal["comfortable", "compact"]


class UpdateAppSettingsRequest(BaseModel):
    rememberLastPage: bool | None = None
    confirmDestructiveActions: bool | None = None
    doubleClickBehavior: Literal["viewer", "external"] | None = None
    includeSubfoldersByDefault: bool | None = None
    skipHiddenFolders: bool | None = None
    faceDetectionEnabled: bool | None = None
    compactSidebar: bool | None = None
    thumbnailDensity: Literal["comfortable", "compact"] | None = None


def _to_response_payload(settings: dict) -> dict:
    return {
        "rememberLastPage": bool(settings.get("remember_last_page", True)),
        "confirmDestructiveActions": bool(settings.get("confirm_destructive_actions", True)),
        "doubleClickBehavior": settings.get("double_click_behavior", "viewer"),
        "includeSubfoldersByDefault": bool(settings.get("include_subfolders_by_default", True)),
        "skipHiddenFolders": bool(settings.get("skip_hidden_folders", True)),
        "faceDetectionEnabled": bool(settings.get("face_detection_enabled", True)),
        "compactSidebar": bool(settings.get("compact_sidebar", False)),
        "thumbnailDensity": settings.get("thumbnail_density", "comfortable"),
    }


@router.get("/", response_model=AppSettingsResponse)
def read_settings() -> dict:
    return _to_response_payload(load_app_settings())


@router.patch("/", response_model=AppSettingsResponse)
def patch_settings(payload: UpdateAppSettingsRequest) -> dict:
    updated = update_app_settings({
        "remember_last_page": payload.rememberLastPage,
        "confirm_destructive_actions": payload.confirmDestructiveActions,
        "double_click_behavior": payload.doubleClickBehavior,
        "include_subfolders_by_default": payload.includeSubfoldersByDefault,
        "skip_hidden_folders": payload.skipHiddenFolders,
        "face_detection_enabled": payload.faceDetectionEnabled,
        "compact_sidebar": payload.compactSidebar,
        "thumbnail_density": payload.thumbnailDensity,
    })
    return _to_response_payload(updated)
