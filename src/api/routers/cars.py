from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import CarORM, CarCreate, CarResponse
from sqlalchemy import func
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[CarResponse])
async def get_cars(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    manufacturer: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    state: Optional[str] = None,
    has_installments: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get a list of cars with optional filtering parameters."""
    try:
        query = db.query(CarORM)

        if manufacturer:
            query = query.filter(CarORM.manufacturer.ilike(f"%{manufacturer}%"))
        if min_price is not None:
            query = query.filter(CarORM.price >= min_price)
        if max_price is not None:
            query = query.filter(CarORM.price <= max_price)
        if min_year is not None:
            query = query.filter(CarORM.year >= min_year)
        if max_year is not None:
            query = query.filter(CarORM.year <= max_year)
        if state:
            query = query.filter(CarORM.state.ilike(f"%{state}%"))
        if has_installments is not None:
            query = query.filter(CarORM.has_installments == has_installments)

        return query.offset(skip).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting cars: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving cars")


@router.get("/{car_id}", response_model=CarResponse)
async def get_car(car_id: int, db: Session = Depends(get_db)):
    """Get a specific car by ID."""
    try:
        car = db.query(CarORM).filter(CarORM.id == car_id).first()
        if car is None:
            raise HTTPException(status_code=404, detail="Car not found")
        return car
    except Exception as e:
        logger.error(f"Error getting car {car_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving car")


@router.get("/stats/price_ranges")
async def get_price_ranges(db: Session = Depends(get_db)):
    """Get statistics about car price ranges."""
    try:
        ranges = [
            (0, 10000),
            (10000, 20000),
            (20000, 30000),
            (30000, 50000),
            (50000, float('inf')),
        ]

        stats = []
        for min_price, max_price in ranges:
            query = db.query(func.count(CarORM.id))
            query = query.filter(CarORM.price >= min_price)
            if max_price != float('inf'):
                query = query.filter(CarORM.price < max_price)

            count = query.scalar()
            stats.append({
                "range": f"${min_price:,.0f} - ${max_price if max_price != float('inf') else 'inf'}",
                "count": count,
            })

        return stats
    except Exception as e:
        logger.error(f"Error getting price range stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving price range statistics")


@router.get("/stats/financing")
async def get_financing_stats(
    manufacturer: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get financing statistics for cars."""
    try:
        query = db.query(
            func.count(CarORM.id).label("total_cars"),
            func.count(CarORM.id).filter(CarORM.has_installments == True).label("total_financed"),
            func.avg(CarORM.monthly_payment).filter(CarORM.has_installments == True).label("avg_monthly_payment"),
            func.avg(CarORM.down_payment).filter(CarORM.has_installments == True).label("avg_down_payment"),
            func.avg(CarORM.installments).filter(CarORM.has_installments == True).label("avg_installments"),
        )

        if manufacturer:
            query = query.filter(CarORM.manufacturer.ilike(f"%{manufacturer}%"))
        if state:
            query = query.filter(CarORM.state.ilike(f"%{state}%"))

        result = query.first()

        return {
            "total_cars": result.total_cars,
            "total_financed": result.total_financed,
            "financing_percentage": (result.total_financed / result.total_cars * 100) if result.total_cars > 0 else 0,
            "avg_monthly_payment": float(result.avg_monthly_payment) if result.avg_monthly_payment else 0,
            "avg_down_payment": float(result.avg_down_payment) if result.avg_down_payment else 0,
            "avg_installments": float(result.avg_installments) if result.avg_installments else 0,
        }
    except Exception as e:
        logger.error(f"Error getting financing stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving financing statistics") 