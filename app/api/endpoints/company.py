from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.db.database import get_db
from app.models.user import User
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyOut, PaginatedCompanies
from app.api.deps import get_current_user, require_superadmin_and_admin
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/", response_model=PaginatedCompanies)
async def list_companies(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
):
    total = (await db.execute(select(func.count()).select_from(Company))).scalar_one()
    result = await db.execute(
        select(Company).order_by(Company.id).offset(skip).limit(limit)
    )
    companies = result.scalars().all()
    return PaginatedCompanies(total=total, skip=skip, limit=limit, items=companies)


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/", response_model=CompanyOut)
async def create_company(
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    company = Company(**company.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.put("/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: int,
    company: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    existing = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    existing.name = company.name
    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/{company_id}")
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await db.delete(company)
    await db.commit()
    return {"message": "Company deleted successfully"}
