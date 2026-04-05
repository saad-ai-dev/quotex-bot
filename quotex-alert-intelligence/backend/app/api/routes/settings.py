"""Runtime settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_COLLECTION = "settings"
SETTINGS_DOC_ID = "runtime"


async def _get_or_create_settings(db: AsyncIOMotorDatabase) -> dict:
    """Return the singleton settings document, creating defaults if absent."""
    doc = await db[SETTINGS_COLLECTION].find_one({"_id": SETTINGS_DOC_ID})
    if doc is None:
        defaults = SettingsRead().model_dump()
        defaults["_id"] = SETTINGS_DOC_ID
        await db[SETTINGS_COLLECTION].insert_one(defaults)
        doc = defaults
    return doc


@router.get("", response_model=SettingsRead)
async def get_settings(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Return current runtime settings."""
    doc = await _get_or_create_settings(db)
    doc.pop("_id", None)
    return SettingsRead(**doc)


@router.put("", response_model=SettingsRead)
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Update runtime settings (partial update)."""
    # Ensure the document exists
    await _get_or_create_settings(db)

    # Build update dict from only the fields that were explicitly set
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    await db[SETTINGS_COLLECTION].update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": update_data},
    )

    updated_doc = await db[SETTINGS_COLLECTION].find_one({"_id": SETTINGS_DOC_ID})
    updated_doc.pop("_id", None)
    return SettingsRead(**updated_doc)
