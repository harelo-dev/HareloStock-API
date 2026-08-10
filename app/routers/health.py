"""Health check and sample data router."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Health"])


SAMPLE_DATA = [
    {"sku_id": "KR202-209", "demand": [1509,1855,2665,1841,1231,2598,1988,1988,2927,2707,731,2598], "unit_cost": 1001, "lead_time": 2, "retail_price": 5000, "quantity_on_hand": 1003, "backlog": 10},
    {"sku_id": "KR202-210", "demand": [1006,206,2588,670,2768,2809,1475,1537,919,2525,440,2691], "unit_cost": 394, "lead_time": 2, "retail_price": 1300, "quantity_on_hand": 3224, "backlog": 10},
    {"sku_id": "KR202-211", "demand": [1840,2284,850,983,2737,1264,2002,1980,235,1489,218,525], "unit_cost": 434, "lead_time": 4, "retail_price": 1200, "quantity_on_hand": 390, "backlog": 10},
    {"sku_id": "KR202-212", "demand": [104,2262,350,528,2570,1216,1101,2755,2856,2381,1867,2743], "unit_cost": 474, "lead_time": 3, "retail_price": 10, "quantity_on_hand": 390, "backlog": 10},
    {"sku_id": "KR202-213", "demand": [489,954,1112,199,919,330,561,2372,921,1587,1532,1512], "unit_cost": 514, "lead_time": 1, "retail_price": 2000, "quantity_on_hand": 2095, "backlog": 10},
    {"sku_id": "KR202-214", "demand": [2416,2010,2527,1409,1059,890,2837,276,987,2228,1095,1396], "unit_cost": 554, "lead_time": 2, "retail_price": 1800, "quantity_on_hand": 55, "backlog": 10},
    {"sku_id": "KR202-215", "demand": [403,1737,753,1982,2775,380,1561,1230,1262,2249,824,743], "unit_cost": 594, "lead_time": 1, "retail_price": 2500, "quantity_on_hand": 4308, "backlog": 10},
    {"sku_id": "KR202-216", "demand": [2908,929,684,2618,1477,1508,765,43,2550,2157,937,1201], "unit_cost": 634, "lead_time": 3, "retail_price": 3033, "quantity_on_hand": 34, "backlog": 10},
    {"sku_id": "KR202-217", "demand": [2799,2197,1647,2263,224,2987,2366,588,1140,869,1707,1180], "unit_cost": 674, "lead_time": 3, "retail_price": 5433, "quantity_on_hand": 390, "backlog": 10},
    {"sku_id": "KR202-218", "demand": [1333,402,804,318,1408,830,1028,534,1871,2730,2022,94], "unit_cost": 714, "lead_time": 2, "retail_price": 3034, "quantity_on_hand": 3535, "backlog": 10},
]


@router.get("/health", summary="Health Check")
async def health_check():
    """Check that the API is alive and return version info."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@router.get(
    "/api/v1/sample-data",
    summary="Sample Data",
    description=(
        "Returns a pre-loaded sample dataset (10 SKUs × 12 months) from the original "
        "supplychainpy library. Use this data to test any analysis endpoint."
    ),
)
async def get_sample_data():
    """Get sample SKU data for quick testing."""
    return {
        "sku_count": len(SAMPLE_DATA),
        "periods": 12,
        "currency": "USD",
        "skus": SAMPLE_DATA,
    }
