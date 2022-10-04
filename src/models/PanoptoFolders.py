from src.models.Limiter import RateLimiter
from src.models.PanoptoSessions import PanoptoSessions
import requests
import urllib.parse
import time
from src.views import Logger
from config import globalConfig

LOGGER = Logger.init_logger(__name__)

class PanoptoFolders:
    def __init__(self, server, ssl_verify, oauth2, username, password):
        """
        Constructor of folders API handler instance.
        This goes through authorization step of the target server.
        """
        self.server = server
        self.ssl_verify = ssl_verify
        self.oauth2 = oauth2
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
        access_token = self.oauth2.get_access_token_resource_owner_grant(
            self.username, self.password
        )
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
        
    @RateLimiter(max_calls=5, period=1)
    def search_folders(self, course_label_name):
        """ Calls GET /api/v1/folders/search on course_label or course_name 
            and returns Panopto folder/s.
        Args:
            course_label_name (str): Collab contextIdentifier or contextName
        Returns:
            [list]: returns Panopto folder/s linked to course_label_name
        """
        result = []
        page_number = 0
        while True:
            url = (
                f"https://{self.server}/Panopto/api/v1/folders/search?searchQuery="
                f"{urllib.parse.quote_plus(course_label_name)}&pageNumber={page_number}"
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
