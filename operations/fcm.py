from __future__ import annotations

from datetime import timedelta

import firebase_admin
from django.conf import settings
from django.utils import timezone
from firebase_admin import credentials, messaging

from operations.models import Notification, PushDevice


def _build_firebase_credential() -> credentials.Certificate:
    private_key = (getattr(settings, 'FCM_PRIVATE_KEY', '') or '').replace('\\n', '\n')
    payload = {
        'type': 'service_account',
        'project_id': getattr(settings, 'FCM_PROJECT_ID', ''),
        'private_key': private_key,
        'client_email': getattr(settings, 'FCM_CLIENT_EMAIL', ''),
        'token_uri': 'https://oauth2.googleapis.com/token',
    }

    missing = [k for k, v in payload.items() if not v and k in {'project_id', 'private_key', 'client_email'}]
    if missing:
        raise ValueError(f'Missing FCM credential fields: {", ".join(missing)}')

    return credentials.Certificate(payload)


def get_firebase_app() -> firebase_admin.App:
    if firebase_admin._apps:  # noqa: SLF001
        return firebase_admin.get_app()
    return firebase_admin.initialize_app(_build_firebase_credential())


def send_push_to_user_ids(*, user_ids: list[str], title: str, body: str, data: dict | None = None, order=None) -> None:
    if not user_ids:
        return

    app = get_firebase_app()
    devices = PushDevice.objects.filter(user_id__in=user_ids, is_active=True)

    notifications = {
        user_id: Notification.objects.create(
            user_id=user_id,
            order=order,
            title=title,
            body=body,
            channel=Notification.Channel.PUSH,
            delivery_state=Notification.DeliveryState.QUEUED,
            payload=data or {},
        )
        for user_id in user_ids
    }

    grouped_tokens: dict[str, list[str]] = {user_id: [] for user_id in user_ids}
    for device in devices:
        grouped_tokens.setdefault(str(device.user_id), []).append(device.token)

    for user_id, notification in notifications.items():
        tokens = grouped_tokens.get(user_id, [])
        if not tokens:
            notification.delivery_state = Notification.DeliveryState.FAILED
            notification.failure_reason = 'No active push devices registered.'
            notification.last_attempt_at = timezone.now()
            notification.retry_count += 1
            notification.save(update_fields=['delivery_state', 'failure_reason', 'last_attempt_at', 'retry_count', 'updated_at'])
            continue

        sent = False
        first_error = ''
        for token in tokens:
            message = messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                android=messaging.AndroidConfig(ttl=timedelta(hours=2)),
                apns=messaging.APNSConfig(headers={'apns-priority': '10'}),
            )
            try:
                messaging.send(message, app=app)
                sent = True
            except Exception as exc:  # noqa: BLE001
                if not first_error:
                    first_error = str(exc)

        notification.last_attempt_at = timezone.now()
        if sent:
            notification.delivery_state = Notification.DeliveryState.SENT
            notification.sent_at = timezone.now()
            notification.failure_reason = ''
        else:
            notification.delivery_state = Notification.DeliveryState.FAILED
            notification.retry_count += 1
            notification.failure_reason = first_error or 'Unknown FCM send error.'

        notification.save(
            update_fields=[
                'delivery_state',
                'last_attempt_at',
                'sent_at',
                'retry_count',
                'failure_reason',
                'updated_at',
            ]
        )
