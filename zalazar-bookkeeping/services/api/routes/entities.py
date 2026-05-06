from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from zalazar.db import get_db

router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("/")
async def get_entities(session: AsyncSession = Depends(get_db)):
    """Fetch all entities."""
    query = text("SELECT id, name, entity_type FROM entities ORDER BY name ASC")
    result = await session.execute(query)
    return {"data": [dict(row._mapping) for row in result.fetchall()]}
