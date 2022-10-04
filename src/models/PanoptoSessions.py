from ast import While
import requests
import urllib.parse
import time
from src.models import Utilities as Utils
from src.views import Logger
from config import globalConfig


LOGGER = Logger.init_logger(__name__)


class PanoptoSessions:
    def __init__(self, server, ssl_verify, oauth2, username, password):
        """
        Constructor of sessions API handler instance.
        This goes through authorization step of the target server.
        """
        self.server = server
        self.ssl_verify = ssl_verify
        self.oauth2 = oauth2

        # Use requests module's Session object in this example.
        # ref. https://2.python-requests.org/en/master/user/advanced/#session-objects
        self.requests_session = requests.Session()
        self.requests_session.verify = self.ssl_verify
        # self.__setup_or_refresh_access_token()

        # NEW - JBRUYLANT 230621
        self.username = username
        self.password = password
        self.__setup_or_refresh_access_token()

    def __setup_or_refresh_access_token(self,):
        """
        This method invokes OAuth2 Authorization Code Resource Owner Grant authorization flow.
        It refreshes the access token with no browser required.
        This is called at the initialization of the class, as well as when 401 (Unaurhotized) is returend.
        """
        # Changed OAuth2 method from get_access_token_authorization_code_grant to get_access_token_resource_owner_grant
        # This is to resolve "unauthorized.Refresh access token"
        access_token = self.oauth2.get_access_token_resource_owner_grant(self.username,self.password)
        self.requests_session.headers.update(
            {"Authorization": "Bearer " + access_token}
        )
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug(access_token) 
        else:
            LOGGER.debug("")

    def __check_retry_needed(self, response):
        """
        Inspect the response of a requets' call.
        True indicates retry is needed, False indicates success. Otherwise an exception is thrown.
        Reference: https://stackoverflow.com/a/24519419

        This method detects
            - 401 (Unauthorized), refresh the access token, and return as "is retry needed"
            - 429 (Too many requests) which means API throttling by the server, wait 10 secs and return as "is retry needed"
            - 500 (Internal server error), wait 50 secs and return as "is retry needed"

        Production code should handle other failure cases and errors as appropriate.
        """
        if response.status_code // 100 == 2:
            # Success on 2xx responses.
            return False

        if response.status_code == 401:
            print("Unauthorized. Refresh access token.")
            LOGGER.debug("Unauthorized. Refresh access token.")
            self.__setup_or_refresh_access_token()
            return True

        if response.status_code == 429:
            print("Too many requests. Wait 10 secs, and retry.")
            LOGGER.debug("Too many requests. Wait 10 secs, and retry.")
            time.sleep(10)
            return True
        
        if response.status_code == 500:
            print("Internal Server Error. Wait 50 secs and retry.")
            LOGGER.debug("Internal Server Error. Wait 50 secs and retry.")
            time.sleep(50)
            return True

        # Throw unhandled cases.
        response.raise_for_status()

    def get_session(self, session_id):
        """
        Call GET /api/v1/sessions/{id} API
        
        Returns:
            the jason response
        """
        while True:
            url = "https://{0}/Panopto/api/v1/sessions/{1}".format(
                self.server, session_id
            )
            resp = self.requests_session.get(url=url)
            if self.__check_retry_needed(resp):
                continue
            data = resp.json()
            break
        return data

    def search_sessions(self, query):
        """
        Call GET /api/v1/sessions/search API

        Returns: 
            the list of entries
        """
        result = []
        page_number = 0
        while True:
            url = "https://{0}/Panopto/api/v1/sessions/search?searchQuery={1}&pageNumber={2}".format(
                self.server, urllib.parse.quote_plus(query), page_number
            )
            resp = self.requests_session.get(url=url)
            if self.__check_retry_needed(resp):
                continue
            data = resp.json()
            entries = data["Results"]
            if len(entries) == 0:
                break
            for entry in entries:
                result.append(entry)
            page_number += 1
        return result

    def rename_successful_uploads(self, successful_uploads: list):
        """
        Call PUT /api/v1/sessions/{id} API to update the name
         -- session_id is PPTO given recording id
        Returns: 
            True if it succeeds, False if it fails.
        """
        for ele in successful_uploads:
            try:
                for downloads_name, session_id in ele.items():  # loop used to easily extract key and value from dictionary
                    ppto_name = Utils.rename_recording(downloads_name)
                    url = f"https://{self.server}/Panopto/api/v1/sessions/{session_id}"
                    payload = {"Name": ppto_name}
                    headers = {"content-type": "application/json"}
                    resp = self.requests_session.put(
                        url=url, json=payload, headers=headers
                    )
                    if self.__check_retry_needed(resp):
                        continue
            except Exception as e:
                LOGGER.debug(f"Renaming failed: {e}")
                print(f"Renaming failed: {e}")
                return False
        return True

    def delete_session(self, session_id):
        """
        Call DELETE /api/v1/sessions/{id} API to delete a session

        Returns:
          True if it succeeds, False if it fails
        """
        try:
            while True:
                url = "https://{0}/Panopto/api/v1/sessions/{1}".format(
                    self.server, session_id
                )
                resp = self.requests_session.delete(url=url)
                if self.__check_retry_needed(resp):
                    continue
                return True
        except Exception as e:
            print("Deletion failed. {0}".format(e))
            return False