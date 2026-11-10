"""Triage Module: SOS parsing and spatial resolution."""
import re
import json
import time
from typing import Optional
from geopy.geocoders import Nominatim
from google import genai
from google.genai import types
from pydantic import ValidationError

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
    
    lat = getattr(incident, "latitude", None)
    lon = getattr(incident, "longitude", None)
    
    valid_lat = lat and (settings.bbox_south <= lat <= settings.bbox_north)
    valid_lon = lon and (settings.bbox_west <= lon <= settings.bbox_east)

    if valid_lat and valid_lon:
        return incident

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
    """REAL TRIAGE: Uses Gemini API to parse natural language distress feeds."""
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    
    prompt = f"""
    You are an emergency disaster response AI. Extract the emergency details from the following distress feed 
    and format it exactly according to the strict JSON schema provided.
    
    Raw SOS Message: "{raw_sos}"
    """
    
    # 3-Attempt Retry Logic for API timeouts or hallucination recovery
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ParsedIncident,
                    temperature=0.1, 
                ),
            )
            
            data = json.loads(response.text)
            parsed = ParsedIncident(**data)
            return resolve_location(parsed)
            
        except (ValidationError, json.JSONDecodeError, Exception) as e:
            if attempt == 2:
                raise RuntimeError(f"Triage failed after 3 attempts: {str(e)}")
            time.sleep(1) # Brief pause before retry