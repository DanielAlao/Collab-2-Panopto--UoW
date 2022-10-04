import requests
from tqdm import tqdm

import os
from src.models import CollabWebService as Ws
from src.models import Utilities as Utils
from src.views import Reports
from src.views import Logger
import os.path
from config import globalConfig

WEBSERVICE = Ws.WebService()
LOGGER = Logger.init_logger(__name__)
PATH = "./downloads/"

g_expected_uploads = []

##### DATA SOURCE - API OPTION
def get_recordings_list_by_id(id: str, start_date: str, end_date: str):
    """Obtains json of data associated with each recording.
    Args:
        id (str): Course ID
        start_date (str): date in "%Y-%m-%dT%H:%M:%SZ" format 
        end_date (str): date in "%Y-%m-%dT%H:%M:%SZ" format 
    Returns:
        list[dict]: None, or list of dicts containing recording objects 
    """
    LOGGER.debug(f"course_id = {id}")
    Utils.handle_types([(id, ""), (start_date, "")])
    recs_json = WEBSERVICE.get_recordings_by_id(id, start_date)
    if len(recs_json["results"]) != 0:
        return list_of_recordings(recs_json, end_date)
    return None

##### DATA SOURCE - API OPTION
def list_of_recordings(recs_json: dict, end_date):
    """Goes through given recordings, parses json and returns full list of details for each recording
       Filtering recordings falling within the date range defined by user input
    Args:
        recs_json (dict): dict of public and private recordings for a specific course
    Returns:
        list[dicts]: contains the recordings (as entered in the download reports) found for download
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"COLLAB:SEARCH RESULT -- {recs_json}")
    else:
        LOGGER.debug("")

    Utils.handle_types([recs_json, {}])
    Utils.handle_res_content("results", recs_json)
    
    eligible_recordings_list = []
    failed_pre_downloads_list = []
    
    results = recs_json["results"] 
    for i in range(len(results)):
        if results[i]["created"] <= end_date:
            rec_data = WEBSERVICE.get_public_recording(results[i]["id"])
            if rec_data != None:
                # Data attribute returned means public recording
                result, failed_pre_download = Utils.create_list_entry(results[i], recording_type = 1)
            else:
                # No data attribute returned means private recording
                result, failed_pre_download = Utils.create_list_entry(results[i], recording_type = 2)
            if result != {}:
                eligible_recordings_list.append(result)
            if failed_pre_download != "":
                failed_pre_downloads_list.append(failed_pre_download)

    return eligible_recordings_list, failed_pre_downloads_list

##### DATA SOURCE - DB OPTION
def list_of_recordings_db(rec_objects: list):
    """Goes through given recordings, parses json and returns full list of details for each recording
    Args:
        rec_objects: list of public and private recordings for a specific course
    Returns:
        list[dicts]: contains the recordings (as entered in the download reports) found for download
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"COLLAB:SEARCH RESULT -- {rec_objects}")
    else:
        LOGGER.debug("")

    Utils.handle_types([rec_objects, []])
    
    eligible_recordings_list = []
    failed_pre_downloads_list = []
 
    for i in range(len(rec_objects)):
        # db snapshot one-day lag - case when deleted on collab
        if rec_objects[i].get('errorKey') == 'resource_not_found':
            continue
        else: 
            rec_data = WEBSERVICE.get_public_recording(rec_objects[i]["id"])
            # Data attribute only present for public recording not for private recording
            if rec_data != None:
                result, failed_pre_download = Utils.create_list_entry(rec_objects[i], recording_type = 1)
            else:
                result, failed_pre_download = Utils.create_list_entry(rec_objects[i], recording_type = 2)
            # either result or failed_pre_download has a value
            if result != {}:
                eligible_recordings_list.append(result)
            if failed_pre_download != "":
                failed_pre_downloads_list.append(failed_pre_download)
    return eligible_recordings_list, failed_pre_downloads_list


def get_recordings_for_course(rec_objects: list, course_label: str):
    """Calls functions to:
        - download relevant public and private recordings per course (creates mp4 recording file). 
        - add entry to public or private download report for each recording
    Args:
        rec_objects (list of dicts): List of eligible recordings
        course_label (str)
    Returns:
        failed downloads, failed_download_ids
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"-- {rec_objects}") 
    else:
        LOGGER.debug("")

    Utils.handle_types([(rec_objects, []), (course_label, "")])

    failed_downloads, failed_download_ids = [],[]

    for rec in rec_objects:
        if "403_msg" in rec: # private recording data is forbidden
            failed_download, failed_download_id = download_private_recording_from_collab(rec, course_label)
            Reports.append_report_private_entry(course_label, rec)
        else:
            failed_download, failed_download_id = download_public_recording_from_collab(rec, course_label)
            Reports.append_report_public_entry(course_label, rec)
        
        if failed_download != '':
            failed_downloads.append(failed_download)
        
        if failed_download_id != '':
            failed_download_ids.append(failed_download_id)

    return failed_downloads, failed_download_ids


def download_public_recording_from_collab(recording: dict, course_label: str):
    """Downloads public recording for given course label, writes it to file
    Args:
        recording (dict): dict from parsed recording json
        course_label (str)
    Result:
        Newly created file containing recording (.mp4) 
    Returns:
    failed_download, failed_download_id
    """
    LOGGER.debug(f"Downloading public recording for {course_label} -- {recording}")
    Utils.handle_types([(recording, {}), (course_label, "")])
    Utils.handle_res_content("recording_id", recording)

    failed_download, failed_download_id = '',''

    rec_public_data = WEBSERVICE.get_public_recording(recording["recording_id"])
    if rec_public_data != None:
        filename = Utils.return_download_filename(course_label, recording, ".mp4")
        if filename != '':
            print(f"Downloading: {filename}")
            failed_download = download_stream(rec_public_data["extStreams"][0]["streamUrl"], f"{PATH}{filename}")
            if check_local_downloaded_file(filename) == True:
                g_expected_uploads.append(filename)
            else:
                failed_download = filename
                failed_download_id = recording["recording_id"]
        else:
            failed_download = failed_download_id = recording["recording_id"]
    
    return failed_download, failed_download_id


def download_private_recording_from_collab(recording: dict, course_label: str,):
    """Downloads private recording for given course label, writes it to file
    Args:
        recording (dict): dict from parsed recording json
        course_label (str)
    Result:
        Newly created file containing recording (.mp4) 
    Returns:
    failed_download, failed_download_id    
    """
    LOGGER.debug(f"Downloading private recording for {course_label} -- {recording}")

    failed_download, failed_download_id = '', ''

    rec_private_url = WEBSERVICE.get_private_recording(recording["recording_id"])
    if rec_private_url != None:
        filename = Utils.return_download_filename(course_label, recording, ".mp4")
        if filename != '':
            print(f"Downloading: {filename}")
            failed_download = download_stream(rec_private_url, f"{PATH}{filename}")
            if check_local_downloaded_file(filename) == True:
                g_expected_uploads.append(filename)
            else:
                failed_download = filename
                failed_download_id = recording["recording_id"]
        else:
            failed_download = failed_download_id = recording["recording_id"]
    
    return failed_download, failed_download_id


def download_stream(url: str, fname: str):
    """Download recording stream from url and write to file
    Args:
        url (str): recording url
        fname (str): file path to write recording to
    Result:
        Newly created file containing recording data (usually .mp4)
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"Download from => {url} -- Save to => {fname}") 
    else:
        LOGGER.debug("")

    Utils.handle_types([(url, ""), (fname, "")])

    failed_download = ''

    try:
        resp = requests_get_stream(url, True)
    except:
        failed_download = fname
        LOGGER.error(str(e))

    total = int(resp.headers.get("content-length", 0))
    progress_bar = tqdm(total=total, unit="iB", unit_scale=True, unit_divisor=1024)
    try:
        with open(fname, "wb") as file:
            for data in resp.iter_content(chunk_size=1024):
                size = file.write(data)
                progress_bar.update(size)
        progress_bar.close()
    except FileNotFoundError as fe:
        failed_download = fname
        print("Error downloading file. ")
        print(str(fe))
        LOGGER.debug("Error downloading file. ")
        LOGGER.error(str(fe))
    except Exception as e:
        failed_download = fname
        LOGGER.error(str(e))    
    return failed_download


def requests_get_stream(url, stream=True):
    return requests.get(url, stream=stream)


def check_local_downloaded_file(fname:str):
    # check if file exists in local downloads folder
    # print("Local file path: ", f"{PATH}{fname}")
    if os.path.isfile(f"{PATH}{fname}"):
       # print("File exists")
        file_size = os.path.getsize(f"{PATH}{fname}")
        # print("Local file size: ", file_size)
        if file_size > 0:
           # print("File is greater than 0 ")
            return True
        else:
           # print("File is 0")
            return False
    else:
      #  print("file not found")
        return False


def expected_uploads_list():
    return g_expected_uploads


def delete_local_downloads(downloads, unsuccessful_uploads_paths):
        for rec in downloads:
            if not rec in unsuccessful_uploads_paths:
                os.unlink(rec)

            
def delete_successful_uploads_from_collab(
successful_uploads_sessionIds: dict, recordingIds_date_created: dict):
    delete_result = True
    for ele in successful_uploads_sessionIds:
        for path, session_id in ele.items():
            if len(recordingIds_date_created) > 0:
                if remove_from_collab(path, recordingIds_date_created) != True:
                    delete_result = False
    return delete_result


def remove_from_collab(path, recordingIds_date_created):
    delete_result = True
    for pair in recordingIds_date_created:
        for rec_id, date in pair.items():
            if rec_id in path: 
                if WEBSERVICE.delete_recording_from_collab(rec_id) != True:
                    delete_result = False
    return delete_result

