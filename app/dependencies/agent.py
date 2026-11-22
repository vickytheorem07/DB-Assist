from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]