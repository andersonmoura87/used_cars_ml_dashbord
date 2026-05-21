from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import CarORM, ManufacturerStats, StateStats, YearStats
from sqlalchemy import func
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/manufacturer-stats")
async def get_manufacturer_stats(
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Get market statistics by manufacturer.
    """
    try:
        query = db.query(ManufacturerStats)
        
        if min_year or max_year or min_price or max_price:
            # If filters are applied, we need to calculate stats dynamically
            subquery = db.query(
                CarORM.manufacturer,
                func.count(CarORM.id).label("total_listings"),
                func.avg(CarORM.price).label("avg_price"),
                func.min(CarORM.price).label("min_price"),
                func.max(CarORM.price).label("max_price"),
                func.avg(CarORM.year).label("avg_year"),
                func.count(CarORM.id).filter(CarORM.has_installments == True).label("total_financed"),
                func.avg(CarORM.monthly_payment).filter(CarORM.has_installments == True).label("avg_monthly_payment"),
                func.avg(CarORM.down_payment).filter(CarORM.has_installments == True).label("avg_down_payment"),
                func.avg(CarORM.installments).filter(CarORM.has_installments == True).label("avg_installments")
            )
            
            if min_year:
                subquery = subquery.filter(CarORM.year >= min_year)
            if max_year:
                subquery = subquery.filter(CarORM.year <= max_year)
            if min_price:
                subquery = subquery.filter(CarORM.price >= min_price)
            if max_price:
                subquery = subquery.filter(CarORM.price <= max_price)
                
            results = subquery.group_by(CarORM.manufacturer).all()
            
            return [{
                "manufacturer": result.manufacturer,
                "total_listings": result.total_listings,
                "avg_price": float(result.avg_price) if result.avg_price else 0,
                "min_price": float(result.min_price) if result.min_price else 0,
                "max_price": float(result.max_price) if result.max_price else 0,
                "avg_year": float(result.avg_year) if result.avg_year else 0,
                "total_financed": result.total_financed,
                "avg_monthly_payment": float(result.avg_monthly_payment) if result.avg_monthly_payment else 0,
                "avg_down_payment": float(result.avg_down_payment) if result.avg_down_payment else 0,
                "avg_installments": float(result.avg_installments) if result.avg_installments else 0
            } for result in results]
        else:
            # If no filters, use pre-calculated stats
            return query.all()
    except Exception as e:
        logger.error(f"Error getting manufacturer stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving manufacturer statistics")

@router.get("/state-stats")
async def get_state_stats(
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    manufacturer: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get market statistics by state.
    """
    try:
        query = db.query(StateStats)
        
        if min_year or max_year or manufacturer:
            # If filters are applied, calculate stats dynamically
            subquery = db.query(
                CarORM.state,
                func.count(CarORM.id).label("total_listings"),
                func.avg(CarORM.price).label("avg_price"),
                func.min(CarORM.price).label("min_price"),
                func.max(CarORM.price).label("max_price"),
                func.count(CarORM.id).filter(CarORM.has_installments == True).label("total_financed"),
                func.avg(CarORM.monthly_payment).filter(CarORM.has_installments == True).label("avg_monthly_payment"),
                func.avg(CarORM.down_payment).filter(CarORM.has_installments == True).label("avg_down_payment"),
                func.avg(CarORM.installments).filter(CarORM.has_installments == True).label("avg_installments")
            )
            
            if min_year:
                subquery = subquery.filter(CarORM.year >= min_year)
            if max_year:
                subquery = subquery.filter(CarORM.year <= max_year)
            if manufacturer:
                subquery = subquery.filter(CarORM.manufacturer.ilike(f"%{manufacturer}%"))
                
            results = subquery.group_by(CarORM.state).all()
            
            return [{
                "state": result.state,
                "total_listings": result.total_listings,
                "avg_price": float(result.avg_price) if result.avg_price else 0,
                "min_price": float(result.min_price) if result.min_price else 0,
                "max_price": float(result.max_price) if result.max_price else 0,
                "total_financed": result.total_financed,
                "avg_monthly_payment": float(result.avg_monthly_payment) if result.avg_monthly_payment else 0,
                "avg_down_payment": float(result.avg_down_payment) if result.avg_down_payment else 0,
                "avg_installments": float(result.avg_installments) if result.avg_installments else 0
            } for result in results]
        else:
            # If no filters, use pre-calculated stats
            return query.all()
    except Exception as e:
        logger.error(f"Error getting state stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving state statistics")

@router.get("/year-stats")
async def get_year_stats(
    manufacturer: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get market statistics by year.
    """
    try:
        query = db.query(YearStats)
        
        if manufacturer or state:
            # If filters are applied, calculate stats dynamically
            subquery = db.query(
                CarORM.year,
                func.count(CarORM.id).label("total_listings"),
                func.avg(CarORM.price).label("avg_price"),
                func.min(CarORM.price).label("min_price"),
                func.max(CarORM.price).label("max_price"),
                func.count(CarORM.id).filter(CarORM.has_installments == True).label("total_financed"),
                func.avg(CarORM.monthly_payment).filter(CarORM.has_installments == True).label("avg_monthly_payment"),
                func.avg(CarORM.down_payment).filter(CarORM.has_installments == True).label("avg_down_payment"),
                func.avg(CarORM.installments).filter(CarORM.has_installments == True).label("avg_installments")
            )
            
            if manufacturer:
                subquery = subquery.filter(CarORM.manufacturer.ilike(f"%{manufacturer}%"))
            if state:
                subquery = subquery.filter(CarORM.state.ilike(f"%{state}%"))
                
            results = subquery.group_by(CarORM.year).order_by(CarORM.year.desc()).all()
            
            return [{
                "year": result.year,
                "total_listings": result.total_listings,
                "avg_price": float(result.avg_price) if result.avg_price else 0,
                "min_price": float(result.min_price) if result.min_price else 0,
                "max_price": float(result.max_price) if result.max_price else 0,
                "total_financed": result.total_financed,
                "avg_monthly_payment": float(result.avg_monthly_payment) if result.avg_monthly_payment else 0,
                "avg_down_payment": float(result.avg_down_payment) if result.avg_down_payment else 0,
                "avg_installments": float(result.avg_installments) if result.avg_installments else 0
            } for result in results]
        else:
            # If no filters, use pre-calculated stats
            return query.order_by(YearStats.year.desc()).all()
    except Exception as e:
        logger.error(f"Error getting year stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving year statistics") 