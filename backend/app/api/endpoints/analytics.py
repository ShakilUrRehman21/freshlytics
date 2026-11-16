from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.scan import Scan
from app.models.user import User

router = APIRouter()

STAGE_ORDER = ["Fresh", "Good", "Use Soon", "Spoiled"]
LEGACY_STAGE_MAP = {"Ripe": "Good", "Overripe": "Use Soon", "Rotten": "Spoiled"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("")
@router.get("/", include_in_schema=False)
async def get_analytics(
    days: int = Query(14, ge=7, le=90),
    tz_offset: int = Query(0, ge=-840, le=840, description="Browser getTimezoneOffset() in minutes"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id
    base = select(Scan).where(Scan.user_id == uid)

    total = (await db.execute(select(func.count(Scan.id)).where(Scan.user_id == uid))).scalar() or 0
    avg = (await db.execute(select(func.avg(Scan.freshness_score)).where(Scan.user_id == uid))).scalar()
    high_risk = (await db.execute(
        select(func.count(Scan.id)).where(Scan.user_id == uid, Scan.shelf_life_hours < 24.0)
    )).scalar() or 0

    dist_rows = (await db.execute(
        select(Scan.fruit_type, func.count(Scan.id)).where(Scan.user_id == uid).group_by(Scan.fruit_type)
    )).all()
    stage_rows = (await db.execute(
        select(Scan.freshness_stage, func.count(Scan.id)).where(Scan.user_id == uid).group_by(Scan.freshness_stage)
    )).all()

    # Local-day bucketing for the trend
    local = timezone(timedelta(minutes=-tz_offset))
    now_local = datetime.now(local)
    start_local = (now_local - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    prev_start = start_local - timedelta(days=days)

    recent_rows = (await db.execute(
        select(Scan.created_at, Scan.freshness_score, Scan.shelf_life_hours)
        .where(Scan.user_id == uid, Scan.created_at >= prev_start.astimezone(timezone.utc))
    )).all()

    buckets: dict[str, list[int]] = defaultdict(list)
    cur_scores, prev_scores = [], []
    today_key = now_local.date().isoformat()
    scans_today = 0
    for created, score, _shelf in recent_rows:
        if created is None:
            continue
        lt = _aware(created).astimezone(local)
        if lt >= start_local:
            buckets[lt.date().isoformat()].append(score)
            cur_scores.append(score)
            if lt.date().isoformat() == today_key:
                scans_today += 1
        else:
            prev_scores.append(score)

    trend = []
    for i in range(days):
        d = (start_local + timedelta(days=i)).date()
        vals = buckets.get(d.isoformat(), [])
        trend.append({
            "date": d.isoformat(),
            "label": d.strftime("%b %d").replace(" 0", " "),
            "scans": len(vals),
            "avg_freshness": round(sum(vals) / len(vals), 1) if vals else None,
        })

    change = None
    if cur_scores and prev_scores:
        change = round(sum(cur_scores) / len(cur_scores) - sum(prev_scores) / len(prev_scores), 1)

    stages = Counter()
    for stage, n in stage_rows:
        stages[LEGACY_STAGE_MAP.get(stage, stage)] += n

    recent = (await db.execute(base.order_by(Scan.created_at.desc(), Scan.id.desc()).limit(6))).scalars().all()
    at_risk = (await db.execute(
        base.where(Scan.shelf_life_hours < 48.0).order_by(Scan.created_at.desc()).limit(5)
    )).scalars().all()

    def brief(s: Scan) -> dict:
        return {
            "id": s.id, "fruit_type": s.fruit_type, "freshness_stage": LEGACY_STAGE_MAP.get(s.freshness_stage, s.freshness_stage),
            "freshness_score": s.freshness_score, "shelf_life_hours": s.shelf_life_hours,
            "thumbnail": s.thumbnail, "created_at": _aware(s.created_at) if s.created_at else None,
        }

    return {
        "total_scans": total,
        "scans_today": scans_today,
        "avg_freshness": round(float(avg), 1) if avg is not None else 0.0,
        "high_risk_count": high_risk,
        "freshness_change": change,
        "period_days": days,
        "fruit_distribution": sorted(
            [{"name": r[0], "value": r[1]} for r in dist_rows if r[0]], key=lambda x: -x["value"]
        ),
        "stage_distribution": [{"name": s, "value": stages.get(s, 0)} for s in STAGE_ORDER],
        "trend": trend,
        "recent_scans": [brief(s) for s in recent],
        "at_risk": [brief(s) for s in at_risk],
    }
