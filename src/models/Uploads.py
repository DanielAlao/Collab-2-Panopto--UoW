from distutils.command import config
import os
import re
import time
from config import Config
from src.views import Logger
from src.models.PanoptoFolders import PanoptoFolders
from src.models.PanoptoOAuth2 import PanoptoOAuth2
from src.models.PanoptoUploader import PanoptoUploader
from src.models.PanoptoSessions import PanoptoSessions
from src.models.Discover import Discover
from src.models import Utilities as Utils
from src.views import Logger
from config import globalConfig

LOGGER = Logger.init_logger(__name__)


class Uploads:
    def __init__(self) -> None:
        self.__ppto_server = Config.credentials["ppto_server"]
        self.__ppto_client_id = Config.credentials["ppto_client_id"]
        self.__ppto_client_secret = Config.credentials["ppto_client_secret"]
        self.__ppto_username = Config.credentials["ppto_username"]
        self.__ppto_password = Config.credentials["ppto_password"]
        self.__ssl_verify = True

        self.oauth2 = PanoptoOAuth2(
            self.__ppto_server,
            self.__ppto_client_id,
            self.__ppto_client_secret,
            self.__ssl_verify,
        )
        self.uploader = PanoptoUploader(
            self.__ppto_server,
            self.__ssl_verify,
            self.oauth2,
            self.__ppto_username,
            self.__ppto_password,
        )
        self.folders = PanoptoFolders(
            self.__ppto_server,
            self.__ssl_verify,
            self.oauth2,
            self.__ppto_username,
            self.__ppto_password,
        )
        self.sessions = PanoptoSessions(
            self.__ppto_server,
            self.__ssl_verify,
            self.oauth2,
            self.__ppto_username,
            self.__ppto_password,
        )
        self.Discover = Discover(
            self.__ppto_server,
            self.__ssl_verify,
            self.oauth2,
            self.__ppto_username,
            self.__ppto_password,
        )

    def upload_video(
        self, file_path: str, date_created: str, ppto_folder_id: str
    ) -> dict:
        """Uploads video to given folder in Panopto
        
        Args:
            file_path (str): Path to file that will be uploaded
            ppto_folder_id (str): Upload destination folder ID in Panopto
        Returns:
            dict: Upload status {int: 'Status'}
        """
        LOGGER.debug("")
        Utils.handle_types([(file_path, ""), (ppto_folder_id, "")])
        file_name = os.path.basename(file_path)
        LOGGER.info(f"Uploading {file_name} => {ppto_folder_id}")

        return self.uploader.upload(file_path, date_created, ppto_folder_id)

    def get_folder_id_from_course_info(self, course_label: str, course_name: str) -> str:
        """Retrieves folder ID in PPTO from given course name or course label.
            If none is found found, match to the default PPTO folder
            -- eff5f998-ecd4-476c-ac56-ae1a014af674 : Unmapped_Collaborate_Recordings
        Args:
            course_label (str): Course Label as found in Collaborate
            course_name (str): Course Name as found in Collaborate
        Returns:
            str: Folder ID in PPTO corresponding to given Course Label
        """
        LOGGER.debug("")
        Utils.handle_types([(course_name, ""), (course_label, "")])

        result = self.folders.search_folders(course_name)
        if len(result) == 1:
            return result[0]["Id"]
        if len(result) > 1:
            # select first of several
            return result[0]["Id"]
        if len(result) == 0:
            truncated_course_name = (course_name[:26]) if len(course_name) >= 26 else course_name
            result = self.folders.search_folders(truncated_course_name)
            if len(result) == 1:
                return result[0]["Id"]
            if len(result) > 1:
                # select first of several
                return result[0]["Id"] 
            if len(result) == 0:
                result = self.folders.search_folders(course_label)
                if len(result) == 1:
                    return result[0]["Id"]
                if len(result) > 1:
                    # select first of several
                    return result[0]["Id"]   
                if len(result) == 0:
                    msg = f"No Panopto folder found for: {course_label}"
                    LOGGER.warning(msg)
                    return Config.default_ppto_folder["folder_id"]


    def check_recordings_on_panopto(
        self, list_of_recordings: list, ppto_folder_id: str, check: str
    ):
        """Retrieves all sessions (aka recordings) in panopto folder
           Compares with given list of recordings to upload
           Tells you which ones from list_of_recordings:
            -- are already on PPTO
            -- are not yet on PPTO 
        Args:
            folder_id (str): folder id to search for sessions in
            list_of_recordings (list): recordings file paths to be compared to those online
            check (str): 'Duplicate' for first check, 'Discover' for second check
        Returns:
            lists: list of sessions not on PPTO + list of sessions on PPTO + list of unrenamed sessions on PPTO
        """
        LOGGER.debug(f"Panopto folder: {ppto_folder_id} -- {list_of_recordings}") 
        Utils.handle_types([(list_of_recordings, []), (ppto_folder_id, ""),(check, "")])

        sessions_result = self.sessions.search_sessions(ppto_folder_id)
        present_on_ppto = []
        [present_on_ppto.append({s["Name"]: s["Id"]}) for s in sessions_result]
        
        # Go through downloaded Collab recordings and check if present on Panopto
        absent, present, present_unrenamed = Utils.return_absent_present(
            present_on_ppto, list_of_recordings, check
        )

        return absent, present, present_unrenamed

    def check_unrenamed_recordings_on_panopto(self, unrenamed_on_ppto:list):
        """ Check if recording is either unrenamed+processed or unrenamed+unprocessed
        Args:
        unrenamed_on_ppto: list of dicts - {recording filename : ppto session_id}
        Returns:
        list of dicts: unrenamed_successfulUploads - [{recording filename : ppto session_id}]
        list of dicts: unrenamed_failedUploads - [{recording filename : ppto session_id}]
        """
        unrenamed_successfulUploads, unrenamed_failedUploads = [],[]
        for rec in unrenamed_on_ppto:
            for rec_long_name in rec.keys():
                res = self.sessions.search_sessions(rec_long_name)
                if res != []:
                    if res[0]['Duration'] != None:
                        unrenamed_successfulUploads.append(rec)
                    else:
                        unrenamed_failedUploads.append(rec)

        return unrenamed_successfulUploads, unrenamed_failedUploads

    def delete_unprocessed_recordings_on_panopto(self, unrenamed_failedUploads:list):
        """Delete unprocessed (unrenamed) recordings left on ppto
        Args:
        unrenamed_failedUploads: list of dicts - {recording filename : ppto session_id}
        Returns:
        unrenamed_failed_ppto_deletions: list of recording filenames
        """
        unrenamed_failed_ppto_deletions = []
        for rec in unrenamed_failedUploads:
            for rec_long_name in rec.keys():
                try:
                    failed_session_id = self.sessions.search_sessions(
                        rec_long_name
                    )[0]["Id"]
                                
                    if self.sessions.delete_session(failed_session_id) == True:
                        print("  Unrenamed failed upload - deleted")
                        LOGGER.warning(" Unrenamed failed upload - deleted")    
                    else:
                        unrenamed_failed_ppto_deletions.append(rec_long_name)
                        print("  Unrenamed failed upload - could not be deleted ")
                        LOGGER.warning("Unrenamed failed upload - could not be deleted ")   
                except:
                    unrenamed_failed_ppto_deletions.append(rec_long_name)
                    print("  Unrenamed failed upload - could not be deleted ")
                    LOGGER.warning("Unrenamed failed upload - could not be deleted ") 

        return unrenamed_failed_ppto_deletions


    def upload_list_of_recordings(self, recording_paths: list, rec_ids_date_created: dict, ppto_folder_id: str):
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug(f"Panopto folder: {ppto_folder_id} -- {recording_paths}")
        else:
            LOGGER.debug("")
            
        unsuccessful_uploads, successful_uploads, failed_ppto_deletions = [], [], []
        controlled_stop = False
        for path in recording_paths:
            if globalConfig.ScheduledRun == 'Yes' and Utils.time_of_day() >= globalConfig.ControlledStopTime:
                controlled_stop = True
                break 
            else:
                date_created = Utils.get_recording_date_created(path, rec_ids_date_created)
                upload_status = self.upload_video(path, date_created, ppto_folder_id)
                print("Status value: ",upload_status)
                if upload_status["Status_Value"] != 4:
                    msg = f"Something went wrong during upload. {upload_status['Status_Value']}: {upload_status['Status_Name']}"
                    LOGGER.error(msg)
                    unsuccessful_uploads.append(path)
                    # Try to delete failed session
                    print("  Something went wrong, deleting failed upload...")
                    LOGGER.warning("Attempting to delete failed upload")
                    print("time sleep before deletion")
                    secs = globalConfig.PanoptoTimeSleep
                    time.sleep(secs)
                    time.sleep(secs)
                    try:
                        failed_session_id = self.sessions.search_sessions(
                            os.path.basename(path)
                        )[0]["Id"]
                        
                        if self.sessions.delete_session(failed_session_id) == True:
                            print("  Failed upload - deleted")
                            LOGGER.warning("Failed upload - deleted")    
                        else:
                            failed_ppto_deletions.append(path)
                            print("  Failed upload - could not be deleted ")
                            LOGGER.warning("Failed upload - could not be deleted ")        
                        
                        os.unlink(path)
                        print("  Failed upload deleted locally")
                        LOGGER.warning("Failed upload deleted locally")
                    except Exception as e:
                        failed_ppto_deletions.append(path)
                        print("Deletion failed. {0}".format(e))
                        LOGGER.error("Deletion failed. {0}".format(e))
                        
                        os.unlink(path)
                        print("  Failed upload deleted locally")
                        LOGGER.warning("Failed upload deleted locally")
                else:
                    successful_uploads.append(path)
                    LOGGER.info("Upload successful!")

        return unsuccessful_uploads, successful_uploads, failed_ppto_deletions, controlled_stop
