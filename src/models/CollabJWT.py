from logging import exception
import jwt
import requests
import datetime
import json
from cachetools import TTLCache
from src.models import Utilities
from src.views import Logger
import sys

LOGGER = Logger.init_logger(__name__)


class CollabJWT:
    def __init__(self, domain, key, secret, cert):
        LOGGER.debug("")
        self.domain = domain
        self.key = key
        self.secret = secret
        self.cert = cert
        exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=5.0)
        header = {"alg": "RS256", "typ": "JWT"}
        claims = {"iss": self.key, "sub": self.key, "exp": exp}
        self.assertion = jwt.encode(claims, self.secret)
        self.grant_type = "urn:ietf:params:oauth:grant-type:jwt-bearer"
        self.payload = {"grant_type": self.grant_type, "assertion": self.assertion}
        self.verify_cert = cert
        self.jcache = None

    def get_key(self):
        return self.key

    def get_secret(self):
        return self.secret


    def refresh_JWT(self):
        # Create request with header, payload, signature
        if self.jcache != None:
            try:
                token = self.jcache["jwtoken"]
                return token
            except KeyError as e:
                LOGGER.error(str(e))
                token = self.create_session()
                return token
        else:
            token = self.create_session()
            return token

    def create_session(self):
        try:
            endpoint = "https://" + self.domain + "/token"
            r = requests.post(
                endpoint, data=self.payload, auth=(self.key, self.secret), verify=self.cert
            )

            if r.status_code == 200:
                json_data = json.loads(r.text)
                self.jcache = TTLCache(maxsize=1, ttl=json_data["expires_in"])
                token = self.jcache["jwtoken"] = json_data["access_token"]
                return token
            else:
                r.raise_for_status()           
        except requests.exceptions.HTTPError as e:
            raise e