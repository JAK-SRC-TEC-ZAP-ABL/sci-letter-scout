import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src.harmony_push import PushError, build_test_request, send_test_notification


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return json.dumps(self.payload).encode()


class HarmonyPushTests(unittest.TestCase):
    def test_request_uses_test_mode_and_no_secrets_in_url(self):
        request = build_test_request('project123', 'jwt-secret', 'device-secret', 'title', 'body', 'WORK')
        payload = json.loads(request.data)
        self.assertTrue(payload['pushOptions']['testMessage'])
        self.assertEqual(payload['target']['token'], ['device-secret'])
        self.assertNotIn('jwt-secret', request.full_url)
        self.assertNotIn('device-secret', request.full_url)

    def test_accepted_response_is_not_a_delivery_receipt(self):
        with patch('src.harmony_push.urllib.request.urlopen', return_value=FakeResponse({'code': '80000000'})):
            self.assertIsNone(send_test_notification('123', 'jwt', 'token', 'title', 'body', 'WORK'))

    def test_rejected_response_does_not_echo_server_body(self):
        with patch('src.harmony_push.urllib.request.urlopen', return_value=FakeResponse({'code': 'fail', 'msg': 'device-secret'})):
            with self.assertRaises(PushError) as error:
                send_test_notification('123', 'jwt', 'device-secret', 'title', 'body', 'WORK')
        self.assertNotIn('device-secret', str(error.exception))

    def test_http_error_is_sanitized(self):
        with patch('src.harmony_push.urllib.request.urlopen', side_effect=HTTPError('https://example.com', 403, 'jwt-secret', {}, None)):
            with self.assertRaises(PushError) as error:
                send_test_notification('123', 'jwt-secret', 'token', 'title', 'body', 'WORK')
        self.assertEqual(str(error.exception), 'Huawei Push HTTP 403')


if __name__ == '__main__':
    unittest.main()
