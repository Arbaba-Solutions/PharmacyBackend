from __future__ import annotations

from decimal import Decimal

import requests
from django.conf import settings

from catalog.models import DeliveryZone


class GoogleDistanceMatrixError(Exception):
    pass


def get_distance_matrix_km(*, origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> dict:
    api_key = getattr(settings, 'GOOGLE_DISTANCE_MATRIX_API_KEY', '')
    if not api_key:
        raise GoogleDistanceMatrixError('GOOGLE_DISTANCE_MATRIX_API_KEY is not configured.')

    endpoint = 'https://maps.googleapis.com/maps/api/distancematrix/json'
    params = {
        'origins': f'{origin_lat},{origin_lng}',
        'destinations': f'{destination_lat},{destination_lng}',
        'key': api_key,
        'units': 'metric',
    }
    response = requests.get(endpoint, params=params, timeout=15)
    response.raise_for_status()

    payload = response.json()
    if payload.get('status') != 'OK':
        raise GoogleDistanceMatrixError(f"Distance Matrix error: {payload.get('status')}")

    rows = payload.get('rows') or []
    if not rows or not rows[0].get('elements'):
        raise GoogleDistanceMatrixError('Distance Matrix response has no route elements.')

    element = rows[0]['elements'][0]
    if element.get('status') != 'OK':
        raise GoogleDistanceMatrixError(f"Route element error: {element.get('status')}")

    distance_meters = element['distance']['value']
    duration_seconds = element['duration']['value']

    return {
        'distance_km': float(distance_meters) / 1000.0,
        'duration_seconds': int(duration_seconds),
        'distance_text': element['distance']['text'],
        'duration_text': element['duration']['text'],
    }


def resolve_delivery_zone(*, distance_km: float, reference_mode: str | None = None) -> DeliveryZone | None:
    zones = DeliveryZone.objects.all().order_by('min_radius_km')
    if reference_mode:
        zones = zones.filter(pricing_reference_mode=reference_mode)

    distance_decimal = Decimal(str(distance_km))
    for zone in zones:
        if zone.min_radius_km <= distance_decimal <= zone.max_radius_km:
            return zone

    return None
