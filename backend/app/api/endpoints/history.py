from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.scan import Scan
from app.models.user import User
from app.schemas.scan import ScanDetail, ScanResponse, ScanUpdate

router = APIRouter()


def _filtered(user_id: int, fruit: Optional[str], stage: Optional[str]):
    q = select(Scan).where(Scan.user_id == user_id)
    if fruit:
        q = q.where(Scan.fruit_type == fruit.lower())
    if stage:
        q = q.where(Scan.freshness_stage == stage)
    return q


@router.get("", response_model=list[ScanResponse])
@router.get("/", response_model=list[ScanResponse], include_in_schema=False)
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    fruit: Optional[str] = None,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _filtered(current_user.id, fruit, stage).order_by(Scan.created_at.desc(), Scan.id.desc()).offset(skip).limit(limit)
    return (await db.execute(q)).scalars().all()


@router.get("/count")
async def count_history(
    fruit: Optional[str] = None,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = _filtered(current_user.id, fruit, stage).subquery()
    return {"count": (await db.execute(select(func.count()).select_from(sub))).scalar() or 0}


async def _get_owned(scan_id: int, db: AsyncSession, user: User) -> Scan:
    scan = (await db.execute(select(Scan).where(Scan.id == scan_id, Scan.user_id == user.id))).scalars().first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.get("/{scan_id}", response_model=ScanDetail)
async def get_scan(scan_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _get_owned(scan_id, db, current_user)


@router.patch("/{scan_id}", response_model=ScanResponse)
async def update_scan(scan_id: int, data: ScanUpdate, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    scan = await _get_owned(scan_id, db, current_user)
    scan.notes = data.notes
    await db.commit()
    await db.refresh(scan)
    return scan


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(scan_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    scan = await _get_owned(scan_id, db, current_user)
    await db.delete(scan)
    await db.commit()


@router.delete("", status_code=204)
@router.delete("/", status_code=204, include_in_schema=False)
async def clear_history(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(delete(Scan).where(Scan.user_id == current_user.id))
    await db.commit()
