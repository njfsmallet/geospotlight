#!/usr/bin/env python3
"""
GeoSpotlight - Professional Real Estate Geospatial Analysis Tool

This tool provides comprehensive real estate property analysis by combining
proximity data (OSM) and transactional data (DVF).

Author: GeoSpotlight Team
Version: 2.0.0
License: MIT
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from functools import lru_cache

try:
    import requests
    from geopy.geocoders import Nominatim
    from tabulate import tabulate
except ImportError as e:
    print(f"Error: Missing dependency - {e}")
    print("Please install dependencies: pip install requests geopy tabulate")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Constants
OVERPASS_API_URL = "http://overpass-api.de/api/interpreter"
DVF_API_BASE_URL = "https://apidf-preprod.cerema.fr/dvf_opendata/mutations/"
NOMINATIM_USER_AGENT = "GeoSpotlight/2.0"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
SEARCH_RADIUS = 350

@dataclass
class PropertyTransaction:
    """Data structure for a real estate transaction."""
    mutation_id: str
    mutation_date: Optional[str]
    mutation_year: int
    land_value: float
    built_area: float
    land_area: float
    price_per_m2: Optional[float]
    property_type: Optional[str]
    department_code: Optional[str]
    insee_codes: List[str]
    is_vefa: bool = False

    def __post_init__(self):
        """Calculate price per m² if possible."""
        if self.built_area > 0 and self.land_value > 0:
            self.price_per_m2 = self.land_value / self.built_area


class GeoSpotlightError(Exception):
    """Base class for GeoSpotlight errors."""
    pass


class APIError(GeoSpotlightError):
    """API-related errors."""
    pass


class ValidationError(GeoSpotlightError):
    """Data validation errors."""
    pass

@lru_cache(maxsize=128)
def get_coordinates(address: str) -> Tuple[float, float]:
    """Get geographical coordinates for an address.

    Args:
        address: Address to geocode

    Returns:
        Tuple (latitude, longitude)

    Raises:
        ValidationError: If address cannot be geocoded
    """
    try:
        geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=DEFAULT_TIMEOUT)
        location = geolocator.geocode(address)

        if location is None:
            raise ValidationError(f"Unable to geocode address: {address}")

        logger.info(f"Coordinates found for '{address}': {location.latitude}, {location.longitude}")
        return (location.latitude, location.longitude)

    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        raise ValidationError(f"Geocoding error: {e}")

def request_overpass_api(query: str) -> Dict[str, Any]:
    """Make a request to the Overpass API and return the JSON result.

    Args:
        query: Overpass QL query string

    Returns:
        JSON response from Overpass API

    Raises:
        APIError: If the API request fails
    """
    try:
        response = requests.get(
            OVERPASS_API_URL,
            params={'data': query},
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Overpass API request failed: {e}")
        raise APIError(f"Overpass API error: {e}")

def construct_overpass_query(amenities: List[Tuple[str, str]], coordinates: Tuple[float, float], radius: int) -> str:
    """Build an Overpass API query for the given amenities, coordinates, and radius.

    Args:
        amenities: List of (key, value) tuples for OSM tags
        coordinates: (latitude, longitude) tuple
        radius: Search radius in meters

    Returns:
        Overpass QL query string
    """
    if not amenities:
        raise ValidationError("Amenities list cannot be empty")

    query_parts = ["[out:json];", "("]

    for key, value in amenities:
        query_parts.append(f'node["{key}"="{value}"](around:{radius},{coordinates[0]},{coordinates[1]});')

    query_parts.extend([");", "out;"])
    return "\n".join(query_parts)

def search_places(amenities: List[Tuple[str, str]], coordinates: Tuple[float, float], radius: int = 2000) -> Dict[str, Any]:
    """Find places of specified amenities around the given coordinates within the specified radius.

    Args:
        amenities: List of (key, value) tuples for OSM tags
        coordinates: (latitude, longitude) tuple
        radius: Search radius in meters

    Returns:
        Dictionary containing search results
    """
    query = construct_overpass_query(amenities, coordinates, radius)
    return request_overpass_api(query)

def sort_places_by_category(places):
    """Categorize places by their type and return a dictionary."""
    categorized_places = {}
    for place in places['elements']:
        name = place.get("tags", {}).get("name")
        if name:  # Only add the place if it has a name
            # Extend the list of keys to include all possible categories
            for key in ['amenity', 'shop', 'office', 'healthcare', 'highway', 'railway', 'aeroway']:
                category = place.get("tags", {}).get(key)
                if category:
                    # Create a unique key for the category by combining the key and the value
                    unique_category_key = f"{key}:{category}"
                    if unique_category_key not in categorized_places:
                        categorized_places[unique_category_key] = set()
                    categorized_places[unique_category_key].add(name)
                    break
    return categorized_places

def retrieve_places_data(places_by_category, category):
    """Get the categorized places data for tabulation."""
    data = []
    for unique_category_key, names in places_by_category.items():
        key, subcategory = unique_category_key.split(':', 1)
        for name in sorted(names):  # Sort names for better readability
            if name:  # Only include the name if it is not None
                data.append([category, subcategory.capitalize(), name])
    return data

def display_amenities_table(amenities_data):
    """Print the amenities data in a table format."""
    headers = ['Category', 'Subcategory', 'Name']

    if amenities_data:
        print(f"\n🎯 Found {len(amenities_data)} amenities and services within {350}m radius:")
        print(tabulate(amenities_data, headers=headers, tablefmt='fancy_grid'))
    else:
        print(f"\n⚠️  No amenities found within {350}m radius of this location.")


def generate_bbox(center_coordinates: Tuple[float, float], radius_meters: int = 1000) -> str:
    """
    Create a bounding box around the center coordinates.
    Hard coded to always generate a 0.005° × 0.005° bounding box for micro-neighborhood analysis.

    Args:
        center_coordinates: Tuple of (latitude, longitude)
        radius_meters: Radius in meters (ignored, kept for compatibility)

    Returns:
        String representing the bounding box 'lon_min,lat_min,lon_max,lat_max'
    """
    lat, lon = center_coordinates

    # Hard coded to always use 0.0025° delta for 0.005° × 0.005° bounding box (micro-neighborhood scale)
    lat_delta = 0.0025
    lon_delta = 0.0025

    lat_min = round(lat - lat_delta, 6)
    lat_max = round(lat + lat_delta, 6)
    lon_min = round(lon - lon_delta, 6)
    lon_max = round(lon + lon_delta, 6)

    logger.info(f"Generated bounding box: {lon_min},{lat_min},{lon_max},{lat_max}")
    logger.info(f"Bounding box dimensions: 0.005000° × 0.005000°")

    return f"{lon_min},{lat_min},{lon_max},{lat_max}"

def fetch_all_pages_dvf_api(bbox: str, min_year: str) -> List[Dict[str, Any]]:
    """
    Query the DVF API for all pages of results within the given bounding box and minimum mutation year.
    Uses precise filters to improve data quality.
    Implements timeout and retry mechanism with exponential backoff.

    Args:
        bbox: String representing the bounding box 'lon_min,lat_min,lon_max,lat_max'
        min_year: String representing the minimum year for mutations

    Returns:
        List of all results from the DVF API

    Raises:
        APIError: If the API request fails after all retries
    """
    if not bbox or not min_year:
        raise ValidationError("Bounding box and minimum year are required")

    api_url = DVF_API_BASE_URL
    params = {
        'in_bbox': bbox,
        'anneemut_min': min_year,
        'fields': 'all',  # Get all available fields
        'format': 'json',  # JSON format for precision
        'valeurfonc_min': 10000,  # Exclude very low values (likely errors)
        'sbati_min': 10,  # Exclude very small surfaces (likely errors)
        'ordering': '-anneemut,-datemut'  # Sort by year and date descending
    }

    results = []
    page_count = 0
    max_retries = 3
    
    while True:
        retries = max_retries
        while retries > 0:
            try:
                logger.info(f"Fetching DVF data page {page_count + 1}...")
                response = requests.get(api_url, params=params, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                page_results = data.get('results', [])

                results.extend(page_results)
                page_count += 1
                logger.info(f"Successfully fetched {len(page_results)} entries from page {page_count}")

                next_url = data.get('next')
                if not next_url:
                    logger.info(f"Completed fetching all pages. Total entries: {len(results)}")
                    return results

                # Update the API URL with the next URL for the subsequent request
                api_url = next_url
                # Clear params since the next URL will include them
                params = {}
                break
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    logger.error("Area too large for DVF API (max 0.02° × 0.02°)")
                    raise APIError(f"Area too large for DVF API: {e.response.text}")
                else:
                    retries -= 1
                    if retries > 0:
                        wait_time = 2 ** (MAX_RETRIES - retries)
                        logger.warning(f"HTTP error {e.response.status_code}. Retrying in {wait_time}s... ({retries} left)")
                        time.sleep(wait_time)
                    else:
                        raise APIError(f"HTTP error after {MAX_RETRIES} attempts: {e}")

            except requests.exceptions.RequestException as e:
                retries -= 1
                if retries > 0:
                    wait_time = 2 ** (MAX_RETRIES - retries)
                    logger.warning(f"Request failed: {e}. Retrying in {wait_time}s... ({retries} left)")
                    time.sleep(wait_time)
                else:
                    raise APIError(f"Request failed after {MAX_RETRIES} attempts: {e}")
    
    return results

def get_location_info_by_mutation_id(mutation_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve location information for a specific mutation ID.
    Returns parcels, municipalities, and cadastral sections (no complete address available in DVF).

    Args:
        mutation_id: Mutation identifier to search for

    Returns:
        Available location information or None if not found

    Raises:
        APIError: If the API request fails
    """
    if not mutation_id:
        raise ValidationError("Mutation ID cannot be empty")

    api_url = f"{DVF_API_BASE_URL}{mutation_id}/"
    retries = MAX_RETRIES

    while retries > 0:
        try:
            logger.info(f"Searching for location info of mutation ID: {mutation_id}...")
            response = requests.get(api_url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            mutation = response.json()
            return {
                'mutation_id': mutation.get('idmutation'),
                'parcel_ids': mutation.get('l_idpar', []),
                'mutated_parcel_ids': mutation.get('l_idparmut', []),
                'cadastral_sections': mutation.get('l_section', []),
                'mutation_date': mutation.get('datemut'),
                'mutation_year': mutation.get('anneemut'),
                'department_code': mutation.get('coddep'),
                'insee_codes': mutation.get('l_codinsee', []),
                'property_type': mutation.get('libtypbien'),
                'land_value': mutation.get('valeurfonc'),
                'built_area': mutation.get('sbati'),
                'land_area': mutation.get('sterr')
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Mutation ID {mutation_id} not found")
                return None
            retries -= 1
            if retries > 0:
                wait_time = 2 ** (MAX_RETRIES - retries)
                logger.warning(f"HTTP error. Retrying in {wait_time}s... ({retries} left)")
                time.sleep(wait_time)
            else:
                raise APIError(f"HTTP error after {MAX_RETRIES} attempts: {e}")

        except requests.exceptions.RequestException as e:
            retries -= 1
            if retries > 0:
                wait_time = 2 ** (MAX_RETRIES - retries)
                logger.warning(f"Request failed: {e}. Retrying in {wait_time}s... ({retries} left)")
                time.sleep(wait_time)
            else:
                raise APIError(f"Request failed after {MAX_RETRIES} attempts: {e}")

    return None

def refine_dvf_data(dvf_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Refine DVF data by exploiting ALL available schema fields.
    Returns precise and detailed raw data.

    Args:
        dvf_entries: List of raw DVF entries

    Returns:
        List of refined entries with calculated fields
    """
    if not dvf_entries:
        return []
    refined_entries = []

    for entry in dvf_entries:
        # Extract all available fields
        try:
            mutation_id = entry.get('idmutation', '')
            mutation_date = entry.get('datemut')  # Exact mutation date
            mutation_year = int(entry.get('anneemut', 0))
            department_code = entry.get('coddep')
            insee_codes = entry.get('l_codinsee', [])

            # Financial information
            land_value = float(entry.get('valeurfonc') or 0.0)
            land_area = float(entry.get('sterr') or 0.0)
            built_area = float(entry.get('sbati') or 0.0)
        except (ValueError, TypeError) as e:
            logger.warning(f"Data conversion error for entry {entry.get('idmutation', 'unknown')}: {e}")
            continue
        
        # Property type (code and label)
        property_type_code = entry.get('codtypbien')
        property_type_label = entry.get('libtypbien')

        # Mutation nature
        mutation_nature = entry.get('libnatmut')

        # VEFA (Sale in future state of completion)
        is_vefa = bool(entry.get('vefa', False))

        # Parcel information
        nb_parcels = int(entry.get('nbpar', 0))
        nb_parcels_mutated = int(entry.get('nbparmut', 0))
        parcel_ids = entry.get('l_idpar', [])
        mutated_parcel_ids = entry.get('l_idparmut', [])

        # Volume and property information
        nb_volumes_mutated = int(entry.get('nbvolmut', 0))
        nb_locals_mutated = int(entry.get('nblocmut', 0))
        local_ids = entry.get('l_idlocmut', [])

        # Number of municipalities
        nb_communes = int(entry.get('nbcomm', 0))
        
        # Calculate price per m² only if surface > 0
        price_per_m2 = None
        if built_area > 0 and land_value > 0:
            price_per_m2 = round(land_value / built_area, 2)

        # Calculate land price per m² if land > 0
        price_per_m2_land = None
        if land_area > 0 and land_value > 0:
            price_per_m2_land = round(land_value / land_area, 2)
        
        # Création de l'entrée raffinée avec TOUTES les données
        refined_entry = {
            # Identifiants
            'mutation_id': mutation_id,
            'mutation_date': mutation_date,
            'mutation_year': mutation_year,
            
            # Géographie
            'department_code': department_code,
            'insee_codes': insee_codes,
            'nb_communes': nb_communes,
            
            # Financier
            'land_value': land_value,
            'land_area': land_area,
            'built_area': built_area,
            'price_per_m2': price_per_m2,
            'price_per_m2_land': price_per_m2_land,
            
            # Type de bien
            'property_type_code': property_type_code,
            'property_type_label': property_type_label,
            
            # Nature de mutation
            'mutation_nature': mutation_nature,
            'is_vefa': is_vefa,
            
            # Parcelles
            'nb_parcels': nb_parcels,
            'nb_parcels_mutated': nb_parcels_mutated,
            'parcel_ids': parcel_ids,
            'mutated_parcel_ids': mutated_parcel_ids,
            
            # Volumes et locaux
            'nb_volumes_mutated': nb_volumes_mutated,
            'nb_locals_mutated': nb_locals_mutated,
            'local_ids': local_ids,
            
            # Métadonnées
            'raw_entry': entry  # Conservation de l'entrée brute pour référence
        }
        
        refined_entries.append(refined_entry)
    
    return refined_entries

def calculate_comprehensive_statistics(refined_entries):
    """
    Calcule des statistiques agrégées robustes basées sur toutes les données disponibles.
    """
    if not refined_entries:
        return {}
    
    # Filtrage des données valides pour les calculs de prix
    valid_price_data = [e for e in refined_entries if e['price_per_m2'] is not None and e['price_per_m2'] > 0]
    valid_land_price_data = [e for e in refined_entries if e['price_per_m2_land'] is not None and e['price_per_m2_land'] > 0]
    
    stats = {
        # Métadonnées générales
        'total_transactions': len(refined_entries),
        'valid_price_transactions': len(valid_price_data),
        'valid_land_price_transactions': len(valid_land_price_data),
        
        # Période d'analyse
        'year_range': {
            'min': min(e['mutation_year'] for e in refined_entries) if refined_entries else None,
            'max': max(e['mutation_year'] for e in refined_entries) if refined_entries else None
        },
        
        # Statistiques financières globales
        'financial_stats': {},
        
        # Statistiques par type de bien
        'by_property_type': {},
        
        # Statistiques par nature de mutation
        'by_mutation_nature': {},
        
        # Statistiques VEFA vs classique
        'vefa_vs_classic': {},
        
        # Statistiques géographiques
        'geographic_stats': {}
    }
    
    # Statistiques financières globales
    if valid_price_data:
        prices = [e['price_per_m2'] for e in valid_price_data]
        land_values = [e['land_value'] for e in valid_price_data]
        built_areas = [e['built_area'] for e in valid_price_data]
        
        stats['financial_stats'] = {
            'price_per_m2': {
                'mean': sum(prices) / len(prices),
                'median': sorted(prices)[len(prices)//2] if prices else 0,
                'min': min(prices),
                'max': max(prices),
                'std_dev': (sum((p - sum(prices)/len(prices))**2 for p in prices) / len(prices))**0.5 if len(prices) > 1 else 0
            },
            'land_value': {
                'mean': sum(land_values) / len(land_values),
                'median': sorted(land_values)[len(land_values)//2] if land_values else 0,
                'min': min(land_values),
                'max': max(land_values),
                'total': sum(land_values)
            },
            'built_area': {
                'mean': sum(built_areas) / len(built_areas),
                'median': sorted(built_areas)[len(built_areas)//2] if built_areas else 0,
                'min': min(built_areas),
                'max': max(built_areas),
                'total': sum(built_areas)
            }
        }
    
    # Statistiques par type de bien
    property_types = {}
    for entry in refined_entries:
        prop_type = entry['property_type_label']
        if prop_type not in property_types:
            property_types[prop_type] = []
        property_types[prop_type].append(entry)
    
    for prop_type, entries in property_types.items():
        valid_entries = [e for e in entries if e['price_per_m2'] is not None and e['price_per_m2'] > 0]
        if valid_entries:
            prices = [e['price_per_m2'] for e in valid_entries]
            stats['by_property_type'][prop_type] = {
                'count': len(entries),
                'valid_price_count': len(valid_entries),
                'price_per_m2': {
                    'mean': sum(prices) / len(prices),
                    'median': sorted(prices)[len(prices)//2],
                    'min': min(prices),
                    'max': max(prices)
                },
                'avg_built_area': sum(e['built_area'] for e in valid_entries) / len(valid_entries),
                'avg_land_value': sum(e['land_value'] for e in valid_entries) / len(valid_entries)
            }
    
    # Statistiques par nature de mutation
    mutation_natures = {}
    for entry in refined_entries:
        nature = entry['mutation_nature']
        if nature not in mutation_natures:
            mutation_natures[nature] = []
        mutation_natures[nature].append(entry)
    
    for nature, entries in mutation_natures.items():
        valid_entries = [e for e in entries if e['price_per_m2'] is not None and e['price_per_m2'] > 0]
        if valid_entries:
            prices = [e['price_per_m2'] for e in valid_entries]
            stats['by_mutation_nature'][nature] = {
                'count': len(entries),
                'valid_price_count': len(valid_entries),
                'avg_price_per_m2': sum(prices) / len(prices),
                'avg_land_value': sum(e['land_value'] for e in valid_entries) / len(valid_entries)
            }
    
    # Statistiques VEFA vs classique
    vefa_entries = [e for e in refined_entries if e['is_vefa']]
    classic_entries = [e for e in refined_entries if not e['is_vefa']]
    
    if vefa_entries:
        valid_vefa = [e for e in vefa_entries if e['price_per_m2'] is not None and e['price_per_m2'] > 0]
        if valid_vefa:
            vefa_prices = [e['price_per_m2'] for e in valid_vefa]
            stats['vefa_vs_classic']['vefa'] = {
                'count': len(vefa_entries),
                'valid_price_count': len(valid_vefa),
                'avg_price_per_m2': sum(vefa_prices) / len(vefa_prices),
                'avg_land_value': sum(e['land_value'] for e in valid_vefa) / len(valid_vefa)
            }
    
    if classic_entries:
        valid_classic = [e for e in classic_entries if e['price_per_m2'] is not None and e['price_per_m2'] > 0]
        if valid_classic:
            classic_prices = [e['price_per_m2'] for e in valid_classic]
            stats['vefa_vs_classic']['classic'] = {
                'count': len(classic_entries),
                'valid_price_count': len(valid_classic),
                'avg_price_per_m2': sum(classic_prices) / len(classic_prices),
                'avg_land_value': sum(e['land_value'] for e in valid_classic) / len(valid_classic)
            }
    
    # Statistiques géographiques
    departments = {}
    communes = {}
    for entry in refined_entries:
        dept = entry['department_code']
        if dept not in departments:
            departments[dept] = []
        departments[dept].append(entry)
        
        for insee_code in entry['insee_codes']:
            if insee_code not in communes:
                communes[insee_code] = []
            communes[insee_code].append(entry)
    
    stats['geographic_stats'] = {
        'departments': {dept: len(entries) for dept, entries in departments.items()},
        'communes': {commune: len(entries) for commune, entries in communes.items()},
        'nb_unique_departments': len(departments),
        'nb_unique_communes': len(communes)
    }
    
    return stats

def print_comprehensive_data_table(refined_entries, period_months=24):
    """
    Display a detailed table with all available raw data.
    """
    if not refined_entries:
        print("Aucune donnée disponible.")
        return
    
    # Tri par date de mutation décroissante
    sorted_entries = sorted(refined_entries, 
                          key=lambda x: (x['mutation_year'], x['mutation_date'] or ''), 
                          reverse=True)
    
    # Préparation des données pour le tableau
    table_data = []
    for entry in sorted_entries:
        # Formatage des données pour l'affichage
        mutation_date_str = entry['mutation_date'] or f"{entry['mutation_year']}"
        insee_str = ', '.join(entry['insee_codes']) if entry['insee_codes'] else 'N/A'
        # Création d'une adresse approximative à partir des données disponibles
        parcel_str = ', '.join(entry['parcel_ids'][:2]) if entry['parcel_ids'] else 'N/A'
        
        price_per_m2_str = f"{entry['price_per_m2']:,.0f}" if entry['price_per_m2'] else "N/A"
        price_per_m2_land_str = f"{entry['price_per_m2_land']:,.0f}" if entry['price_per_m2_land'] else "N/A"
        
        vefa_str = "Oui" if entry['is_vefa'] else "Non"
        
        table_data.append([
            mutation_date_str,
            f"{entry['land_value']:,.0f}",
            f"{entry['land_area']:.0f}",
            f"{entry['built_area']:.0f}",
            price_per_m2_str,
            price_per_m2_land_str,
            entry['property_type_label'] or 'N/A',
            entry['nb_parcels'],
            entry['nb_locals_mutated']
        ])
    
    # En-têtes du tableau
    headers = [
        'Date', 'Valeur (€)', 'Surface Terrain (m²)', 'Surface Bâtie (m²)',
        'Prix/m² Bâti (€)', 'Prix/m² Terrain (€)', 'Type Bien',
        'Nb Parcelles', 'Nb Locaux'
    ]
    
    if table_data:
        actual_min_year = min(e['mutation_year'] for e in refined_entries)
        actual_max_year = max(e['mutation_year'] for e in refined_entries)
        current_date = datetime.now()
        requested_start = current_date - timedelta(days=period_months * 30.44)

        # Get actual date range from data
        all_dates = [e['mutation_date'] for e in refined_entries if e['mutation_date']]
        if all_dates:
            actual_start = min(all_dates)
            actual_end = max(all_dates)
            data_coverage = f"{actual_start} to {actual_end}"
        else:
            data_coverage = f"{actual_min_year} - {actual_max_year}"

        print(f"\n📋 Property transactions found: {len(table_data)} records")
        print(f"📅 Data coverage: {data_coverage}")
        print(f"🎯 Analysis period: {period_months} months back")
        print("\n" + "="*120)
        print(tabulate(table_data, headers=headers, tablefmt='fancy_grid'))
        print("="*120)
    else:
        print(f"\n⚠️  No property transaction data found for this location.")
        print(f"🎯 Analysis period: {period_months} months back")

def print_comprehensive_statistics(stats):
    """
    Display comprehensive aggregated statistics in English.
    """
    if not stats or stats['total_transactions'] == 0:
        print("\n⚠️  No statistical data available for analysis.")
        return

    print(f"\n📊 MARKET OVERVIEW")
    print(f"• Total transactions analyzed: {stats['total_transactions']}")
    print(f"• Valid price data points: {stats['valid_price_transactions']}")

    if stats['year_range']['min'] and stats['year_range']['max']:
        print(f"• Analysis period: {stats['year_range']['min']} - {stats['year_range']['max']}")

    # Financial statistics
    if stats['financial_stats']:
        fs = stats['financial_stats']
        print(f"\n💰 FINANCIAL ANALYSIS")
        print(f"• Average price per m²: €{fs['price_per_m2']['mean']:,.0f}")
        print(f"• Median price per m²: €{fs['price_per_m2']['median']:,.0f}")
        print(f"• Price range: €{fs['price_per_m2']['min']:,.0f} - €{fs['price_per_m2']['max']:,.0f}")
        print(f"• Average property value: €{fs['land_value']['mean']:,.0f}")
        print(f"• Average built area: {fs['built_area']['mean']:.0f}m²")

    # Property type breakdown
    if stats['by_property_type']:
        print(f"\n🏠 PROPERTY TYPE BREAKDOWN")
        for prop_type, data in stats['by_property_type'].items():
            percentage = (data['count'] / stats['total_transactions']) * 100
            print(f"• {prop_type}: {data['count']} transactions ({percentage:.1f}%)")
            print(f"  - Average price: €{data['price_per_m2']['mean']:,.0f}/m²")
            print(f"  - Average size: {data['avg_built_area']:.0f}m²")

    # Geographic distribution
    if stats['geographic_stats']:
        gs = stats['geographic_stats']
        print(f"\n🗺️ GEOGRAPHIC DISTRIBUTION")
        print(f"• Departments covered: {gs['nb_unique_departments']} ({', '.join(gs['departments'].keys())})")
        print(f"• Municipalities involved: {gs['nb_unique_communes']}")

    # Transaction types
    if stats['by_mutation_nature']:
        print(f"\n📋 TRANSACTION TYPES")
        for nature, data in stats['by_mutation_nature'].items():
            print(f"• {nature}: {data['count']} transactions (avg: €{data['avg_price_per_m2']:,.0f}/m²)")

    print("\n" + "="*80)

def calculate_average_price_by_type(data, property_type):
    # Filter data by property type and ensure that the area and price are positive
    filtered_entries = [
        entry for entry in data
        if entry['property_type'] == property_type and entry['built_area'] > 0 and entry['land_value'] > 0
    ]

    # Check if the filtered list is empty
    if not filtered_entries:
        return None

    # Calculate the total price and total area for the specified property type
    total_price = sum(entry['land_value'] for entry in filtered_entries)
    total_area = sum(entry['built_area'] for entry in filtered_entries)

    # Calculate the average price per m2
    average_price_per_m2 = total_price / total_area if total_area > 0 else None

    return average_price_per_m2

def calculate_median_price_by_type(data, property_type):
    # Filter data by property type and ensure that the area and price are positive
    filtered_entries = [
        entry for entry in data
        if entry['property_type'] == property_type and entry['built_area'] > 0 and entry['land_value'] > 0
    ]

    # Extract the prices per m2 for the specified property type
    prices_per_m2_list = [entry['price_per_m2'] for entry in filtered_entries]

    # Check if the list of prices is empty
    if not prices_per_m2_list:
        return None

    # Calculate the median price per m2
    prices_per_m2_list.sort()
    mid = len(prices_per_m2_list) // 2
    if len(prices_per_m2_list) % 2:
        # If odd, take the middle element
        median_price_per_m2 = prices_per_m2_list[mid]
    else:
        # If even, take the average of the two middle elements
        median_price_per_m2 = (prices_per_m2_list[mid - 1] + prices_per_m2_list[mid]) / 2

    return median_price_per_m2

def print_average_and_median_prices_table(average_price_per_m2_apartments, average_price_per_m2_houses, median_price_per_m2_apartments, median_price_per_m2_houses):
    # Define the headers for the table
    headers = ['Property Type', 'Average Price per m2 (€)', 'Median Price per m2 (€)']

    # Create a list of data rows for the table
    table_data = [
        ['Apartments', f"{round(average_price_per_m2_apartments):,.0f}" if average_price_per_m2_apartments is not None else "N/A",
         f"{round(median_price_per_m2_apartments):,.0f}" if median_price_per_m2_apartments is not None else "N/A"],
        ['Houses', f"{round(average_price_per_m2_houses):,.0f}" if average_price_per_m2_houses is not None else "N/A",
         f"{round(median_price_per_m2_houses):,.0f}" if median_price_per_m2_houses is not None else "N/A"]
    ]

    # Print the table
    print(tabulate(table_data, headers=headers, tablefmt='fancy_grid'))

def calculate_average_price_by_type(data, property_type):
    # Filter data by property type and ensure that the area and price are positive
    filtered_entries = [
        entry for entry in data
        if entry['property_type_label'] == property_type and entry['built_area'] > 0 and entry['land_value'] > 0
    ]

    # Check if the filtered list is empty
    if not filtered_entries:
        return None

    # Calculate the total price and total area for the specified property type
    total_price = sum(entry['land_value'] for entry in filtered_entries)
    total_area = sum(entry['built_area'] for entry in filtered_entries)

    # Calculate the average price per m2
    average_price_per_m2 = total_price / total_area if total_area > 0 else None

    return average_price_per_m2

def calculate_median_price_by_type(data, property_type):
    # Filter data by property type and ensure that the area and price are positive
    filtered_entries = [
        entry for entry in data
        if entry['property_type_label'] == property_type and entry['built_area'] > 0 and entry['land_value'] > 0
    ]

    # Extract the prices per m2 for the specified property type
    prices_per_m2_list = [entry['price_per_m2'] for entry in filtered_entries]

    # Check if the list of prices is empty
    if not prices_per_m2_list:
        return None

    # Calculate the median price per m2
    prices_per_m2_list.sort()
    mid = len(prices_per_m2_list) // 2
    if len(prices_per_m2_list) % 2:
        # If odd, take the middle element
        median_price_per_m2 = prices_per_m2_list[mid]
    else:
        # If even, take the average of the two middle elements
        median_price_per_m2 = (prices_per_m2_list[mid - 1] + prices_per_m2_list[mid]) / 2

    return median_price_per_m2

def print_average_and_median_prices_table(average_price_per_m2_apartments, average_price_per_m2_houses, median_price_per_m2_apartments, median_price_per_m2_houses):
    # Define the headers for the table
    headers = ['Property Type', 'Average Price per m2 (€)', 'Median Price per m2 (€)']

    # Create a list of data rows for the table
    table_data = [
        ['Apartments', f"{round(average_price_per_m2_apartments):,.0f}" if average_price_per_m2_apartments is not None else "N/A",
         f"{round(median_price_per_m2_apartments):,.0f}" if median_price_per_m2_apartments is not None else "N/A"],
        ['Houses', f"{round(average_price_per_m2_houses):,.0f}" if average_price_per_m2_houses is not None else "N/A",
         f"{round(median_price_per_m2_houses):,.0f}" if median_price_per_m2_houses is not None else "N/A"]
    ]

    # Print the table
    print(tabulate(table_data, headers=headers, tablefmt='fancy_grid'))

# Define the amenities for each category
CULTURAL_AND_EDUCATIONAL_AMENITIES = [
    ("amenity", "school"), ("amenity", "college"), ("amenity", "university"),
    ("amenity", "training"), ("amenity", "library"), ("amenity", "music_school"),
    ("amenity", "arts_centre"), ("amenity", "theatre"), ("amenity", "cinema"),
    ("amenity", "community_centre"), ("amenity", "public_bookcase"),
    ("amenity", "concert_hall"), ("amenity", "gymnasium"), ("amenity", "sports_centre"),
    ("amenity", "stadium"), ("amenity", "dance"), ("amenity", "planetarium"),
    ("amenity", "museum"), ("amenity", "gallery")
]

TRANSPORT_AMENITIES = [
    ("amenity", "bus_station"), ("highway", "bus_stop"), ("amenity", "taxi"),
    ("amenity", "ferry_terminal"), ("amenity", "parking"), ("amenity", "bicycle_parking"),
    ("amenity", "bicycle_rental"), ("amenity", "car_rental"), ("amenity", "car_sharing"),
    ("amenity", "charging_station"), ("amenity", "fuel"), ("railway", "station"),
    ("railway", "tram_stop"), ("railway", "halt"), ("railway", "subway_entrance"),
    ("railway", "light_rail"), ("aeroway", "aerodrome"), ("aeroway", "helipad")
]

FOOD_AND_DRINK_AMENITIES = [
    ("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food"),
    ("amenity", "pub"), ("amenity", "bar"), ("amenity", "biergarten"),
    ("amenity", "food_court"), ("amenity", "ice_cream"), ("amenity", "juice_bar"),
    ("shop", "bakery"), ("shop", "butcher"), ("shop", "cheese"),
    ("shop", "chocolate"), ("shop", "confectionery"), ("shop", "deli"),
    ("shop", "greengrocer"), ("shop", "pastry"), ("shop", "seafood"),
    ("shop", "tea"), ("shop", "wine"), ("amenity", "nightclub"), ("amenity", "caterer")
]

HEALTHCARE_AMENITIES = [
    ("amenity", "hospital"), ("amenity", "clinic"), ("amenity", "pharmacy"),
    ("amenity", "laboratory"), ("amenity", "doctors"), ("amenity", "medical_centre"),
    ("amenity", "dentist"), ("amenity", "veterinary"), ("amenity", "optician"),
    ("amenity", "physiotherapist"), ("healthcare", "blood_donation"),
    ("healthcare", "alternative"), ("healthcare", "audiologist"),
    ("healthcare", "speech_therapist"), ("healthcare", "psychotherapist"),
    ("healthcare", "nutrition_counselling"), ("healthcare", "podiatrist")
]

BUSINESS_AND_FINANCE_AMENITIES = [
    ("amenity", "bank"), ("amenity", "atm"), ("amenity", "bureau_de_change"),
    ("office", "company"), ("office", "financial"), ("office", "insurance"),
    ("amenity", "conference_centre"), ("amenity", "business_centre"), ("amenity", "marketplace")
]

# Parse command-line arguments
parser = argparse.ArgumentParser(description='GeoSpotlight - Analyse géospatiale des quartiers')
parser.add_argument('--period', type=int, default=24,
                   help='Période d\'analyse en mois (défaut: 24)')
parser.add_argument('--test-mutation-id', type=str,
                   help='Tester la récupération d\'informations pour un ID de mutation spécifique')
args = parser.parse_args()

# Calculate minimum year from period in months (24 months by default)
current_date = datetime.now()
min_date = current_date - timedelta(days=args.period * 30.44)  # Average days per month
min_year = str(min_date.year)

# Calculate minimum year from period in months (24 months by default)

def main():
    """Main function of the script."""
    address = input("Please enter the address: ")
    coordinates = get_coordinates(address)
    search_radius = 350  # Fixed radius of 350 meters

    print(f"\n🏠 GEOSPOTLIGHT REAL ESTATE ANALYSIS")
    print(f"📍 Location: {address}")
    print(f"🌐 Coordinates: {coordinates[0]:.6f}, {coordinates[1]:.6f}")
    print(f"📏 Search radius: {search_radius} meters")

    # =============================================================================
    # SECTION 1: NEARBY AMENITIES & SERVICES ANALYSIS
    # =============================================================================
    print("\n" + "="*80)
    print("🏪 SECTION 1: NEARBY AMENITIES & SERVICES")
    print("="*80)

    all_amenities_data = []
    for category_name, amenities in [
        ("Cultural and Educational", CULTURAL_AND_EDUCATIONAL_AMENITIES),
        ("Transport", TRANSPORT_AMENITIES),
        ("Food and Drink", FOOD_AND_DRINK_AMENITIES),
        ("Healthcare", HEALTHCARE_AMENITIES),
        ("Business and Finance", BUSINESS_AND_FINANCE_AMENITIES)
    ]:
        places = search_places(amenities, coordinates, search_radius)
        places_by_category = sort_places_by_category(places)
        category_data = retrieve_places_data(places_by_category, category_name)
        all_amenities_data.extend(category_data)

    display_amenities_table(all_amenities_data)

    # =============================================================================
    # SECTION 2: RAW PROPERTY TRANSACTION DATA
    # =============================================================================
    print("\n" + "="*80)
    print("📊 SECTION 2: PROPERTY TRANSACTION DATA")
    print("="*80)

    bbox = generate_bbox(coordinates, search_radius)
    dvf_entries = fetch_all_pages_dvf_api(bbox, min_year)
    refined_entries = refine_dvf_data(dvf_entries)

    # Display raw transaction data table
    print_comprehensive_data_table(refined_entries, args.period)

    # =============================================================================
    # SECTION 3: STATISTICAL ANALYSIS & MARKET INSIGHTS
    # =============================================================================
    print("\n" + "="*80)
    print("📈 SECTION 3: STATISTICAL ANALYSIS & MARKET INSIGHTS")
    print("="*80)

    # Calculate and display comprehensive statistics
    comprehensive_stats = calculate_comprehensive_statistics(refined_entries)
    print_comprehensive_statistics(comprehensive_stats)

if __name__ == "__main__":
    # Test de la fonction get_location_info_by_mutation_id si un ID est fourni en argument
    if args.test_mutation_id:
        mutation_id = args.test_mutation_id
        result = get_location_info_by_mutation_id(mutation_id)
        if result:
            print(f"\n✅ Test réussi pour l'ID mutation {mutation_id}:")
            print(f"   Parcelles: {', '.join(result['parcel_ids']) if result['parcel_ids'] else 'N/A'}")
            print(f"   Sections: {', '.join(result['cadastral_sections']) if result['cadastral_sections'] else 'N/A'}")
            print(f"   Date: {result['mutation_date']} ({result['mutation_year']})")
            print(f"   Département: {result['department_code']}")
            print(f"   INSEE: {', '.join(result['insee_codes']) if result['insee_codes'] else 'N/A'}")
            print(f"   Type bien: {result['property_type']}")
            print(f"   Valeur: {result['land_value']}€")
            print(f"   Surface bâtie: {result['built_area']}m²")
        else:
            print(f"❌ Aucune information trouvée pour l'ID mutation {mutation_id}")
    else:
        main()
