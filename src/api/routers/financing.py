from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models import Car
from sqlalchemy import func
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/installment-analysis")
async def get_installment_analysis(
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    manufacturer: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get detailed analysis of installment patterns.
    """
    try:
        query = db.query(
            func.avg(Car.monthly_payment).label("avg_monthly"),
            func.min(Car.monthly_payment).label("min_monthly"),
            func.max(Car.monthly_payment).label("max_monthly"),
            func.avg(Car.down_payment).label("avg_down"),
            func.min(Car.down_payment).label("min_down"),
            func.max(Car.down_payment).label("max_down"),
            func.avg(Car.installments).label("avg_term"),
            func.min(Car.installments).label("min_term"),
            func.max(Car.installments).label("max_term")
        ).filter(Car.has_installments == True)

        if min_price:
            query = query.filter(Car.price >= min_price)
        if max_price:
            query = query.filter(Car.price <= max_price)
        if manufacturer:
            query = query.filter(Car.manufacturer.ilike(f"%{manufacturer}%"))
        if state:
            query = query.filter(Car.state.ilike(f"%{state}%"))

        result = query.first()

        return {
            "monthly_payment": {
                "average": float(result.avg_monthly) if result.avg_monthly else 0,
                "minimum": float(result.min_monthly) if result.min_monthly else 0,
                "maximum": float(result.max_monthly) if result.max_monthly else 0
            },
            "down_payment": {
                "average": float(result.avg_down) if result.avg_down else 0,
                "minimum": float(result.min_down) if result.min_down else 0,
                "maximum": float(result.max_down) if result.max_down else 0
            },
            "term_months": {
                "average": float(result.avg_term) if result.avg_term else 0,
                "minimum": int(result.min_term) if result.min_term else 0,
                "maximum": int(result.max_term) if result.max_term else 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting installment analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving installment analysis")

@router.get("/manufacturer-comparison")
async def get_manufacturer_financing_comparison(
    manufacturers: List[str] = Query(None),
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Compare financing options between different manufacturers.
    """
    try:
        query = db.query(
            Car.manufacturer,
            func.count(Car.id).label("total_cars"),
            func.count(Car.id).filter(Car.has_installments == True).label("financed_cars"),
            func.avg(Car.monthly_payment).filter(Car.has_installments == True).label("avg_monthly"),
            func.avg(Car.down_payment).filter(Car.has_installments == True).label("avg_down"),
            func.avg(Car.installments).filter(Car.has_installments == True).label("avg_term")
        ).group_by(Car.manufacturer)

        if manufacturers:
            query = query.filter(Car.manufacturer.in_(manufacturers))
        if min_year:
            query = query.filter(Car.year >= min_year)
        if max_year:
            query = query.filter(Car.year <= max_year)

        results = query.all()
        
        return [{
            "manufacturer": result.manufacturer,
            "total_cars": result.total_cars,
            "financed_cars": result.financed_cars,
            "financing_percentage": (result.financed_cars / result.total_cars * 100) if result.total_cars > 0 else 0,
            "avg_monthly_payment": float(result.avg_monthly) if result.avg_monthly else 0,
            "avg_down_payment": float(result.avg_down) if result.avg_down else 0,
            "avg_term_months": float(result.avg_term) if result.avg_term else 0
        } for result in results]
    except Exception as e:
        logger.error(f"Error getting manufacturer comparison: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving manufacturer comparison")

@router.get("/price-range-analysis")
async def get_price_range_financing_analysis(db: Session = Depends(get_db)):
    """
    Analyze financing patterns across different price ranges.
    """
    try:
        ranges = [
            (0, 10000, "Under $10k"),
            (10000, 20000, "$10k-$20k"),
            (20000, 30000, "$20k-$30k"),
            (30000, 50000, "$30k-$50k"),
            (50000, float('inf'), "Over $50k")
        ]
        
        results = []
        for min_price, max_price, range_label in ranges:
            query = db.query(
                func.count(Car.id).label("total_cars"),
                func.count(Car.id).filter(Car.has_installments == True).label("financed_cars"),
                func.avg(Car.monthly_payment).filter(Car.has_installments == True).label("avg_monthly"),
                func.avg(Car.down_payment).filter(Car.has_installments == True).label("avg_down"),
                func.avg(Car.installments).filter(Car.has_installments == True).label("avg_term")
            ).filter(Car.price >= min_price)
            
            if max_price != float('inf'):
                query = query.filter(Car.price < max_price)
                
            result = query.first()
            
            results.append({
                "price_range": range_label,
                "total_cars": result.total_cars,
                "financed_cars": result.financed_cars,
                "financing_percentage": (result.financed_cars / result.total_cars * 100) if result.total_cars > 0 else 0,
                "avg_monthly_payment": float(result.avg_monthly) if result.avg_monthly else 0,
                "avg_down_payment": float(result.avg_down) if result.avg_down else 0,
                "avg_term_months": float(result.avg_term) if result.avg_term else 0
            })
            
        return results
    except Exception as e:
        logger.error(f"Error getting price range analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving price range analysis") 