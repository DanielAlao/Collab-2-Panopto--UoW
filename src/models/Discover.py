from ast import While
import requests
import urllib.parse
import time
import os
from src.models import Utilities as Utils
from src.models import Emails
import traceback
from src.views import Logger
from config import globalConfig
from config import Config
from src.models.PanoptoSessions import PanoptoSessions 
from src.models import CollabWebService as Ws


LOGGER = Logger.init_logger(__name__)

WEBSERVICE = Ws.WebService()

class Discover:
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

        self.sessions = PanoptoSessions(
            self.server,
            self.ssl_verify,
            self.oauth2,
            self.username,
            self.password,
        )

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


    def mitigate(self,undiscovered_uploads_list = [], failed_ppto_deletions_list = []):
        """Mitigation process to re-discover + re-delete 
            any undiscovered and failed uploads deletions up to the point of failure 
            before app restart
        """
        msg = f"\n--- MITIGATE BEFORE RESTART ---"
        print(msg)
        LOGGER.info(msg)
        undiscovered_uploads_list_final = []
        failed_ppto_deletions_list_final = []

        if len(undiscovered_uploads_list) > 0:
            undiscovered_uploads_list_final = self.re_discover(undiscovered_uploads_list)

        if len(failed_ppto_deletions_list) > 0:
            failed_ppto_deletions_list_final = self.re_delete(failed_ppto_deletions_list)

        # RE-DISCOVER 2
        if len(undiscovered_uploads_list_final) > 0:
            self.re_discover(undiscovered_uploads_list_final)

        # RE-DELETE 2
        if len(failed_ppto_deletions_list_final) > 0:
            self.re_delete(failed_ppto_deletions_list_final)

    def re_discover(self, undiscovered_uploads_list: list):
        """Re-discover: Rename + Delete undiscovered recordings

        Args: 
            undiscovered_uploads_list: list of filepaths - after first discover round
        Returns:
            undiscovered_uploads_list_final: refreshed list of filepaths - after second discover round
        """
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep)

        msg = (f"\n-----------------------------------------------------" +
        f"\nRE-DISCOVER:")
        print(msg)
        LOGGER.info(msg)

        undiscovered_uploads_list_final = undiscovered_uploads_list
        undiscovered = Utils.undiscovered_course_folders()
        for courseLabel, folderId in undiscovered.items():
            for ele in undiscovered_uploads_list[:]:
                try:
                    filename = os.path.basename(ele)                    
                    url = f"https://{self.server}/Panopto/api/v1/folders/{folderId}/sessions"
                    resp = self.requests_session.get(url=url)
                    if self.__check_retry_needed(resp):
                        continue                    
                    data = resp.json()
                    entries = data['Results']
                    for rec in entries:
                        # RE-DISCOVER
                        if rec['Name'] == filename:
                            # RENAME STEP
                            ppto_name = Utils.rename_recording(filename, courseLabel)
                            url = f"https://{self.server}/Panopto/api/v1/sessions/{rec['Id']}" 
                            payload = {"Name": ppto_name}
                            headers = {"content-type": "application/json"}
                            resp = self.requests_session.put(
                                url=url, json=payload, headers=headers
                            )
                            if self.__check_retry_needed(resp):
                                continue
                            msg = f"Renamed: {filename}"
                            print(msg)
                            LOGGER.info(msg)
                    
                            # DELETE STEP
                            if globalConfig.DeleteBBRecordings == "Yes":
                                if folderId != Config.default_ppto_folder["folder_id"]:
                                    split_filename = filename.split("#")
                                    rec_id = split_filename[1]
                                    if WEBSERVICE.delete_recording_from_collab(rec_id) == True:
                                        print('BB deleted')
                                        LOGGER.info("BB deleted")
                                    else:
                                        print("BB deletion issue")
                                        LOGGER.debug("BB deletion issue")  
                                else: 
                                    if globalConfig.DeleteUnmappedBBRecordings == "Yes":
                                        split_filename = filename.split("#")
                                        rec_id = split_filename[1]
                                        if WEBSERVICE.delete_recording_from_collab(rec_id) == True:
                                            print('BB deleted')
                                            LOGGER.info("BB deleted")
                                        else:
                                            print("BB deletion issue")
                                            LOGGER.debug("BB deletion issue")  
                                    else:
                                        print("No BB delete")
                                        LOGGER.info("No BB delete")
                            else:
                                print("No BB delete")
                                LOGGER.debug("No BB delete") 
                                                       
                            # REFRESH UNDISCOVERED LIST
                            if ele in undiscovered_uploads_list_final:
                                undiscovered_uploads_list_final.remove(ele)
                
                except Exception as e:
                    LOGGER.debug(f"Re-discover failed: {e}")
                    print(f"Re-discover failed: {e}")

        return undiscovered_uploads_list_final

    def re_delete(self, failed_ppto_deletions_list: list):
        """Re-delete: Delete failed uploads

        Args: 
            failed_ppto_deletions_list: list of filepaths - after first discover round
        Returns:
            failed_ppto_deletions_list_final: refreshed list of filepaths - after second discover round
        """   
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep)
        time.sleep(globalConfig.PanoptoTimeSleep) 

        msg = (f"\n-----------------------------------------------------" +
        f"\nRE-DELETE:")
        print(msg)
        LOGGER.info(msg)

        failed_ppto_deletions_list_final = failed_ppto_deletions_list
        for ele in failed_ppto_deletions_list[:]:
            try:
                # RE-DELETE STEP
                failed_session_id = self.sessions.search_sessions(
                    os.path.basename(ele)
                    )[0]["Id"] 

                if self.sessions.delete_session(failed_session_id) == True:
                    msg = f" Failed upload deleted: {os.path.basename(ele)}"
                    print(msg)
                    LOGGER.warning(msg)    

                    # REFRESH FAILED PPTO DELETIONS LIST
                    if ele in failed_ppto_deletions_list_final:
                        failed_ppto_deletions_list_final.remove(ele) 
                else:
                    msg = f" Deletion failed."
                    print(msg)
                    LOGGER.error(msg)

            except Exception as e:
                msg = f" Deletion failed. {format(e)}"
                print(msg)
                LOGGER.error(msg)

        return failed_ppto_deletions_list_final   
