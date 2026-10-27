"""Huawei Push Kit test-message sender.

This module does not run automatically. Callers must obtain a short-lived JWT
securely and must never persist device tokens or credentials in the public feed.
Server-side registration, delivery tracking and production policy are separate.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


class PushError(Exception):
    """A sanitized error that does not include credentials or response bodies."""


def build_test_request(project_id: str, jwt: str, device_token: str,
                       title: str, body: str, category: str) -> urllib.request.Request:
    """Build one test request; no network call is made by this function."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', project_id):
        raise PushError('Invalid project ID')
    if not jwt or not device_token or not title or not body:
        raise PushError('Missing required push information')
    if category not in {'IM', 'VOIP', 'TRAVEL', 'HEALTH', 'WORK', 'MARKETING'}:
        raise PushError('Invalid notification category')
    payload = {
        'payload': {'notification': {
            'category': category, 'title': title, 'body': body,
            'clickAction': {'actionType': 0}, 'foregroundShow': True,
        }},
        'target': {'token': [device_token]},
        'pushOptions': {'testMessage': True, 'ttl': 3600},
    }
    return urllib.request.Request(
        f'https://push-api.cloud.huawei.com/v3/{project_id}/messages:send',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {jwt}',
                 'push-type': '0'}, method='POST')


def send_test_notification(project_id: str, jwt: str, device_token: str,
                           title: str, body: str, category: str) -> None:
    """Submit a test message. API acceptance does not prove device delivery."""
    request = build_test_request(project_id, jwt, device_token, title, body, category)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read(65536).decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise PushError(f'Huawei Push HTTP {error.code}') from None
    except (urllib.error.URLError, TimeoutError, ValueError, UnicodeError):
        raise PushError('Huawei Push request failed') from None
    if not isinstance(result, dict) or result.get('code') != '80000000':
        raise PushError('Huawei Push did not accept the test request')
