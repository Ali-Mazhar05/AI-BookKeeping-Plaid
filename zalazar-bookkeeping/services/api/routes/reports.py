from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from datetime import date
from zalazar.db import get_db
from zalazar.reports.dscr import calculate_property_dscr
from sqlalchemy import text

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/dscr")
async def get_dscr_report(
    property_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: AsyncSession = Depends(get_db)
):
    """Returns DSCR metrics for a property."""
    report = await calculate_property_dscr(session, property_id, start_date, end_date)
    return report

@router.get("/summary")
async def get_entity_summary(
    entity_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: AsyncSession = Depends(get_db)
):
    """Returns a summary of all properties under an entity."""
    # Fetch properties
    res = await session.execute(
        text("SELECT id, name FROM properties WHERE entity_id = :eid AND is_active = TRUE"),
        {"eid": entity_id}
    )
    properties = res.fetchall()
    
    reports = []
    for p in properties:
        report = await calculate_property_dscr(session, str(p.id), start_date, end_date)
        reports.append({
            "property_name": p.name,
            **report
        })
        
    return {
        "entity_id": entity_id,
        "period": {"start": start_date, "end": end_date},
        "properties": reports
    }
