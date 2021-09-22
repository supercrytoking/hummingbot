import hashlib
import hmac
import time

from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth


class BybitPerpetualAuthTests(TestCase):

    @property
    def api_key(self):
        return 'test_api_key'

    @property
    def secret_key(self):
        return 'test_secret_key'

    def _get_timestamp(self):
        return str(int(time.time() * 1e3))

    def test_no_authentication_headers(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)
        headers = auth.get_headers()

        self.assertEqual(1, len(headers))
        self.assertEqual('application/json', headers.get('Content-Type'))

    def test_authentication_headers(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

        timestamp = self._get_timestamp()
        headers = {}

        with patch.object(auth, 'get_timestamp') as get_timestamp_mock:
            get_timestamp_mock.return_value = timestamp
            headers = auth.extend_params_with_authentication_info(headers)

        raw_signature = "api_key=" + self.api_key + "&timestamp=" + timestamp
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(3, len(headers))
        self.assertEqual(timestamp, headers.get('timestamp'))
        self.assertEqual(self.api_key, headers.get('api_key'))
        self.assertEqual(expected_signature, headers.get('sign'))

    def test_ws_auth_payload(self):
        auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

        timestamp = self._get_timestamp()

        with patch.object(auth, 'get_timestamp') as get_timestamp_mock:
            get_timestamp_mock.return_value = timestamp
            payload = auth.get_ws_auth_payload()

        raw_signature = 'GET/realtime' + timestamp
        expected_signature = hmac.new(self.secret_key.encode('utf-8'),
                                      raw_signature.encode('utf-8'),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(3, len(payload))
        self.assertEqual(self.api_key, payload[0])
        self.assertEqual(timestamp, payload[1])
        self.assertEqual(expected_signature, payload[2])
