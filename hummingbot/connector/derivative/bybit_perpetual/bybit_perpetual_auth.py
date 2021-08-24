import hashlib
import hmac
import time
from typing import Dict, Any


class BybitPerpetualAuth():
    """
    Auth class required by Bybit API
    """

    def __init__(self, api_key: str, secret_key: str):
        self._api_key: str = api_key
        self._secret_key: str = secret_key

    def get_expiration_timestamp(self):
        return str(int((round(time.time()) + 1) * 1e3))

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generates a dictionary with all required information for the authentication process
        :return: a dictionary of authentication info including the request signature
        """
        expires = self.get_expiration_timestamp()
        raw_signature = 'GET/realtime' + expires
        signature = hmac.new(self._secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
        auth_info = [self._api_key, expires, signature]

        return auth_info

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """
        return {
            "Content-Type": 'application/json',
        }

    def extend_params_with_authentication_info(self, params: Dict[str, Any]):
        params["timestamp"] = self.get_expiration_timestamp()
        params["api_key"] = self._api_key
        raw_signature = '&'.join([str(key) + "=" + str(value) for key, value in sorted(params.items())])
        signature = hmac.new(self._secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
        params["sign"] = signature
        return params
