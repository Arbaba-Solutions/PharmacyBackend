from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions

from accounts.models import User


@dataclass
class _RoleHint:
    role: str | None = None


def _extract_role(payload: dict[str, Any]) -> str:
    app_meta = payload.get('app_metadata') or {}
    user_meta = payload.get('user_metadata') or {}
    role = app_meta.get('role') or user_meta.get('role') or 'customer'
    allowed = {choice for choice, _ in User.Role.choices}
    return role if role in allowed else User.Role.CUSTOMER


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    """Validates Supabase JWTs using the project's JWKS endpoint."""

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode('utf-8')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid Authorization header format.')

        token = parts[1]
        jwks_url = settings.SUPABASE_JWKS_URL
        if not jwks_url:
            raise exceptions.AuthenticationFailed('SUPABASE_JWKS_URL is not configured.')

        try:
            signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['RS256'],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options={'verify_exp': True},
            )
        except Exception as exc:  # noqa: BLE001
            raise exceptions.AuthenticationFailed(f'Invalid token: {exc}') from exc

        sub = payload.get('sub')
        if not sub:
            raise exceptions.AuthenticationFailed('Token missing sub claim.')

        role = _extract_role(payload)
        user, _ = User.objects.update_or_create(
            id=sub,
            defaults={
                'email': payload.get('email', ''),
                'phone': payload.get('phone', ''),
                'full_name': (payload.get('user_metadata') or {}).get('full_name', ''),
                'role': role,
                'is_active': True,
            },
        )
        return (user, payload)
