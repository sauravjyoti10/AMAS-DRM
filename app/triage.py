"""Triage Module: SOS parsing and spatial resolution."""
import re
from typing import Optional
from geopy.geocoders import Nominatim
from google import genai
from google.genai import types

from app.schemas import ParsedIncident
from app.config import get_settings

def clean_location_query(location_str: str) -> str:
    """Remove landmark phrases like 'near SBI ATM' or 'behind station' for OSM geocoding."""
    if not location_str:
        return "Guwahati"
    
    cleaned = re.sub(
        r'\b(near|opp|opposite|behind|beside|next to|close to)\b.*$', 
        '', 
        location_str, 
        flags=re.IGNORECASE
    ).strip()
    
    return cleaned if len(cleaned) > 2 else location_str

def resolve_location(incident: ParsedIncident) -> ParsedIncident:
    """Validate lat/lon against Guwahati bounds; geocode or set default fallback if missing."""
    settings = get_settings()
    
    # Safely get attributes (works whether your schema uses 'location' or 'location_name')
    lat = getattr(incident, "latitude", None)
    lon = getattr(incident, "longitude", None)
    
    valid_lat = lat and (settings.bbox_south <= lat <= settings.bbox_north)
    valid_lon = lon and (settings.bbox_west <= lon <= settings.bbox_east)

    if valid_lat and valid_lon:
        return incident

    # Safely get the location text
    raw_name = getattr(incident, "location", None) or getattr(incident, "location_name", None) or "Guwahati"
    cleaned_name = clean_location_query(raw_name)
    query = f"{cleaned_name}, Guwahati, Assam, India"

    geolocator = Nominatim(user_agent="amas_drm_geocoder")
    
    try:
        location = geolocator.geocode(query, timeout=5)
        if location and (settings.bbox_south <= location.latitude <= settings.bbox_north):
            incident.latitude = location.latitude
            incident.longitude = location.longitude
        else:
            incident.latitude = 26.1750
            incident.longitude = 91.7750
    except Exception:
        incident.latitude = 26.1750
        incident.longitude = 91.7750

    return incident

def run_triage(raw_sos: str) -> ParsedIncident:
    """MOCK TRIAGE: Bypasses Gemini API for local UI testing."""
    raw = raw_sos.lower()
    
    severity = "LOW"
    if "critical" in raw or "collapse" in raw or "landslide" in raw:
        severity = "CRITICAL"
    elif "waterlogging" in raw or "flood" in raw:
        severity = "HIGH"
    elif "electricity" in raw or "knee-deep" in raw:
        severity = "MODERATE"
        
    loc = "Guwahati"
    if "chandmari" in raw: loc = "Chandmari"
    elif "ganeshguri" in raw: loc = "Ganeshguri"
    elif "zoo road" in raw: loc = "Zoo Road"
    elif "rajgarh" in raw: loc = "Rajgarh"
    
    mock_parsed = ParsedIncident(
        summary=f"Mocked emergency response for {loc}",
        severity=severity,
        location=loc,
        casualties=5 if severity == "CRITICAL" else 0,
        needed_resources=[{
            "item_name": "First Aid Kits",
            "resource_type": "medical_kit", 
            "quantity": 3
        }]
    )
    
    return resolve_location(mock_parsed)