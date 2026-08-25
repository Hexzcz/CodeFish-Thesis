"""Request bodies for the routing endpoints.

Shape only. The range and scenario checks stay in the handlers so a bad value
comes back as 400 with a sentence the UI can show, rather than pydantic's 422
validation dump.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    scenario: str = "25yr"
    k: Optional[int] = 3
    penalty_factor: Optional[float] = 3.0
    weights: Optional[Dict[str, float]] = {
        'flood': 0.764,
        'distance': 0.112,
        'road_class': 0.124
    }


class DestinationPoint(BaseModel):
    lat: float
    lon: float


class ShortestDistanceRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destinations: List[DestinationPoint]


class ShortestPathRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    scenario: str = "25yr"
