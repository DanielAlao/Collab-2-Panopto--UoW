import datetime
import time
from logging import exception
import requests
import json
import re
import os,sys
import csv
from src.models.Uploads import Uploads
from src.models import Emails as Email
from src.views import Logger
from config import Config
from config import globalConfig

BASE = os.getcwd()
LOGGER = Logger.init_logger(__name__)

g_current_course_label = ''

g_undiscovered_course_folders = {}


def logger_msg(*vars):
    return [str(type(var)) for var in vars]

def get_headers(auth_or_bearer):
    """Helper function - template for returning headers to make API calls depending on auth or bearer being required
    Args:
        auth_or_bearer (str): String variable for header
    Returns:
        [dict]: Header for making requests
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{auth_or_bearer}")
    else:
        LOGGER.debug("")
    handle_types(*[(auth_or_bearer, "")])

    return {
        "Authorization": auth_or_bearer,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

def handle_response(r):
    """Generic function for API response handling and error logging.
    Args:
        r (res): Response from API call
    Returns: 
        Parsed json or None, depending on status_code
    """
    if r.status_code == 200:
        res = json.loads(r.text)
        return res
    elif r.status_code == 403:
        LOGGER.debug(f"Private recording - {str(r)}") 
        return None
    elif r.status_code == 404:
        LOGGER.debug(f"Not Found - {str(r)}")
        return None
    else:
        LOGGER.debug(f"Unknown response for: {str(r)}")
        return None

def handle_types(*received_expected):
    """Generic helper function for handling TypeErrors
    Args:
        rec_exp (list(tuples)): Unpackable list of (rec, exp) tuples of arbitrary length
    Raises:
        TypeError: if type(rec) != type(exp)
    """
    for pair in received_expected:
        if not type(pair[0]) is type(pair[1]):
            msg = f"Type {type(pair[1])} expected, received: {type(pair[0])}"
            LOGGER.error(msg)
            raise TypeError(msg)

def handle_res_content(key, json):
    if not key in json:
        raise KeyError(f"Expected key {key} in response json")


def calculate_time(secs: int):
    """Converts given number of seconds into "%H:%M:%S" format
    Args:
        secs (int): number of seconds
    Returns:
        str: "%H:%M:%S" time format
    """
    handle_types(*[(secs, 0)])
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    time_in_session = datetime.time(hours, mins, secs)
    return time_in_session.strftime("%H:%M:%S")

def convert_date(date: str):
    """Converts given date to "%b %d,%Y" format. Example : Sep 03,2021
    Args:
        date (str): date
    Returns:
        str: date in "%b %d,%Y" format
    """
    handle_types(*[(date, "")])
    try:
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        msg = "Incorrect data format, should be %Y-%m-%dT%H:%M:%S.%fZ"
        LOGGER.error(msg)
        raise ValueError(msg)
    return date_obj.strftime("%b %d,%Y")

def set_search_start_date(days: int):
    """Returns date {days} from now
    Args:
        days (int): number of weeks to go back
    Returns:
        str: date in "%Y-%m-%d" format
    """
    LOGGER.debug(f"Search from {days} days ago")
    handle_types(*[(days, 0)])

    start_date = datetime.datetime.now() - datetime.timedelta(days=int(days)) # Check start date
    return start_date.strftime("%Y-%m-%d")

def set_search_end_date(days: int):
    """Returns date {days} from now
    Args:
        days (int): number of weeks to go back
    Returns:
        str: date in "%Y-%m-%d" format
    """
    LOGGER.debug(f"Search until {days} days ago")
    handle_types(*[(days, 0)])

    end_date = datetime.datetime.now() - datetime.timedelta(days=int(days)) # Check end date
    return end_date.strftime("%Y-%m-%d")


def clean_name(name: str):
    """Conditions given file or course label name for windows os compliance:
        - removing undesired punctuation and special characters (forbidden in windows explorer)
        - reducing filename maximum size allowed (to comply with windows explorer max size of 255 characters)
    Args:
        name (str): name to clean up
    Returns:
        str: cleaned name
    """
    handle_types(*[(name, "")])

    # recondition step1 and step2
    name1 = re.sub(r"[^\w\s]", "", name)
    name2 = re.sub('\s+',' ',name1)
    name3 = name2.rstrip().replace(" ", "-")
    # bug fix: reduced length from 160 to 120 in order to be able to create the file
    name4 = (name3[:120] + '...') if len(name3) > 120 else name3
    return name4

def return_download_filename(course_label, rec, filetype):
    """NOTE checking against live API data - recordings are in sync
        Builds filename for recording to be downloaded:
        filename is made up of course_label + recording_id + recording_name + file extension
        - course_label length: 3-43 characters (as of 18/03/22)
        - recording_id length: 32 characters
        - file extension: 4 characters
        - recording_name length possible: 255-(43+32+4): varies between 176 and 216
        >> recording_name truncated after 120 with '...' suffix = 123
    Args:
        course_label : str
        rec : dict
        filetype: str
    Returns:
        filename : str
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{course_label} -- {rec}")
    else:
        LOGGER.debug("")
    handle_types(*[(course_label, ""), (rec, {}), (filetype, "")])
    
    # assigning value to module-scope variable
    global g_current_course_label
    g_current_course_label = course_label

    filename = ''
    try:
        filename = (
            f"{clean_name(course_label)}#{rec['recording_id']}#"
            f"{clean_name(rec['recording_name'])}"
            f"{filetype}"
        )
    except KeyError as ke:
        LOGGER.debug(KeyError(f"Expected key in dict: {ke}"))
    except Exception as e:
        LOGGER.error(str(e))

    return filename

def return_download_filename_db(course_label, rec_id, rec, filetype):
    """NOTE checking for null recordings (from daily DBSNAPSHOT - delay - recordings are not in sync)
        Builds filename for recording to be downloaded:
        filename is made up of course_label + recording_id + recording_name + file extension
        - course_label length: 3-43 characters (as of 18/03/22)
        - recording_id length: 32 characters
        - file extension: 4 characters
        - recording_name length possible: 255-(43+32+4): varies between 176 and 216
        >> recording_name truncated after 120 with '...' suffix = 123
    Args:
        course_label : str
        rec_id : str
        rec : dict
        filetype: str
    Returns:
        filename : str
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{course_label} -- {rec}")
    else:
        LOGGER.debug("")
    handle_types(*[(course_label, ""),(rec_id, ""), (rec,{}), (filetype, "")])
    
    # assigning value to module-scope variable
    global g_current_course_label
    g_current_course_label = course_label

    filename = ''
    try:
        filename = (
        f"{clean_name(course_label)}#{rec_id}#"
        f"{clean_name(rec.get('name'))}"
        f"{filetype}"
        )

    except KeyError as ke:
        LOGGER.debug(KeyError(f"Expected key in dict: {ke}"))
    except Exception as e:
        LOGGER.error(str(e))

    return filename


def rename_recording(composed_name, courseLabel = ''): 
    """ Recordings are renamed on PPTO after being uploaded and discovered.
        If recording is in default PPTO folder, add label to recording name as prefix
        to avoid duplicate recording names.
    Args:
        composed_name (downloaded file name): str
        courseLabel : optional, used in re-discover function
    Returns:
        recording_renamed: str
    """
    recording_renamed = ''

    if '#' in composed_name:
        course_label = g_current_course_label if courseLabel == '' else courseLabel
        courseLabel_folderId_pairs = check_json_courselabel_folderid_pairs()

        if course_label in courseLabel_folderId_pairs.keys():
            if courseLabel_folderId_pairs[course_label] == Config.default_ppto_folder["folder_id"]:
                recording_renamed = course_label + "-" + composed_name.split("#")[2] 
            else:
                recording_renamed = composed_name.split("#")[2] 

        # PPTO recording name excludes file extension
        p = recording_renamed.find(".mp4")
        recording_renamed = recording_renamed[:p]
    else:
        recording_renamed = composed_name
    
    return recording_renamed

# in preview mode, get one or more labels (function called once)
# in actual mode, get one label at a time (function called in loop)
def get_courseLabel_folderId_pairs(course_label_names: list):
    """Uses the course label and course name to search for corresponding PPTO folder 
        as course labels or course names are contained in PPTO folder name by default.

        Looking up a local json file and updating the file if required for future lookup.
    Args:
        [list]: course_name_labels (list of lists)
    Returns:
        [dict]: course label and PPTO folder id pairs
    """
    uploader = Uploads()
    courseLabel_folderId_pairs = check_json_courselabel_folderid_pairs()

    missing_folders_list = []
    for courseLabel, courseName in course_label_names:
        if courseLabel in courseLabel_folderId_pairs.keys():
            continue
        else:
            folderId = uploader.get_folder_id_from_course_info(courseLabel,courseName)
            # Each course will have a single PPTO folder match
            # Thanks to the addition of the default PPTO folder
            if folderId is not None:
                # Adding missing pairs to json file
                courseLabel_folderId_pairs[courseLabel] = folderId
            else:
                # This will only be the case if the default PPTO folder is deleted
                missing_folders_list.append(courseLabel)

    save_json_courselabel_folderid_pairs(courseLabel_folderId_pairs, f"{BASE}/data")

    return courseLabel_folderId_pairs, missing_folders_list

def save_json_courselabel_folderid_pairs(courseLabel_folderId_pairs, json_dir_path):
    """Saves or updates courseLabel_folderId_pairs as json to /data folder
    Args:
        courseLabel_folderId_pairs (dict): Dict of Collab course_label to Panopto folder_id mappings
        json_dir_path (path): Path to /data folder
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{json_dir_path} -- {courseLabel_folderId_pairs}")
    else:
        LOGGER.debug("")
    handle_types(*[(courseLabel_folderId_pairs, {}), (json_dir_path, "")])
    dir = create_dir_if_not_exists(json_dir_path)
    with open(f"{dir}/courseLabel_folderId_pairs.json", "w") as fp:
        json.dump(courseLabel_folderId_pairs, fp, indent=4)

    return courseLabel_folderId_pairs

def create_dir_if_not_exists(path: str):
    """Creates directory if it doesn't exist already
    Args:
        path (str): path to directory
    Returns:
        str: path to directory
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{path}")
    handle_types(*[(path, "")])
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except Exception as e:
        msg = str(e)
        LOGGER.error(msg)
        raise e

    return path

def check_json_courselabel_folderid_pairs():
    """Loads courseLabel_folderId_pairs.json as dict if exists, returns empty dict if not
    Returns:
        [dict]: dict(courseLabel_folderId_pairs)
    """
    try:
        with open(f"{BASE}/data/courseLabel_folderId_pairs.json") as f:
            courseLabel_folderId_pairs = json.load(f)
    except:
        courseLabel_folderId_pairs = {}

    return courseLabel_folderId_pairs


def create_list_entry(results, recording_type = 0):
    """Generates entry data for either the private or the public download report
    Returns:
        Recording data dictionary (distinct dictionary for private or public entry) 
        Recording id of incomplete data dictionary
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"Download Report Entry -- {results}, {recording_type}")
    else:
        LOGGER.debug("for Download Report")
    handle_types(*[(results, {}), (recording_type, 0)])

    entry_data = {}
    failed_pre_download = ""
    try:
        if recording_type == 1: 
            # attributes required for the public report
            entry_data = {
                "recording_id": results["id"],
                "recording_name": results["name"],
                "duration": results["duration"],
                "storage_size": results["storageSize"],
                "created": results["created"],
            }
        elif recording_type == 2:
            # attributes required for the private report
            entry_data = {
                "recording_id": results["id"],
                "recording_name": results["name"],
                "duration": results["duration"],
                "storage_size": results["storageSize"],
                "created": results["created"],
                "403_msg": 403, # private recording data is forbidden
            }
    except KeyError as ke:
        LOGGER.error(f"Expected key in dict: {ke}")
        failed_pre_download = results["id"]

    return entry_data, failed_pre_download

def recording_storage_size(url: str):
    """Returns content length for given recording url
    Args:
        url (str): recording url
    Returns:
        int: size of content length
    """
    handle_types(*[(url, "")])

    try:
        r = requests.get(url, stream=True, headers={"Accept-Encoding": None})
    except requests.exceptions.MissingSchema as e:
        LOGGER.error(str(e))
        raise requests.exceptions.MissingSchema(str(e))

    return int(r.headers.get("content-length", 0))

def get_downloads_list(downloads_path: str):
    """Gets list of mp4 files in Collab /downloads folder 
    Args:
        downloads_path (string): Path to Collab downloads folder
    Returns:
        [list]: List of paths to each mp4 download file
    """
    handle_types(*[(downloads_path, "")])

    downloads_list = []
    for file in os.scandir(downloads_path):
        if file.path.endswith(".mp4"):
            downloads_list.append(file.path)

    return downloads_list

def get_folder_download_matches(courseLabels_folderIds: dict, downloads_list: list):
    """ Matches course_label extracted from mp4 file name in Collab /downloads to Panopto folder_id
        Adds {folder_id: [download]} to matches dict. 
        If the folder_id is already in the matches dict, append the download
    Args:
        courseLabels_folderIds (dict): Dict of course_label:folder_id mappings
        downloads_list (list(mp4)): List of mp4 recordings in Collab /downloads 
    Returns:
        [dict]: Mapping of course downloads to corresponding Panopto folder_id
    """
    if globalConfig.LogDetail == "Verbose":
        LOGGER.debug(f"{courseLabels_folderIds} -- {downloads_list}")
    else:
        LOGGER.debug("")
    handle_types(*[(courseLabels_folderIds, {}), (downloads_list, [])])

    matches = {}
    for download in downloads_list:
        for course_label, folder_id in courseLabels_folderIds.items():
            # case for real course labels, which are always included in recording name
            if clean_name(course_label) in download:
                if folder_id in matches:
                    matches[folder_id].append(download)
                else:
                    matches[folder_id] = [download]
    return matches

def return_absent_present(present_on_ppto: list, list_of_recordings: list, check: str):
    """The function is called twice by check_recordings_on_panopto() at different points of the upload process:
       1) first check (before uploading): dealing with previously uploaded recordings (previous runs)
        > already renamed (using short name)
       2) second check (after uploading and time sleep): dealing with just uploaded recordings (current run)
        > not yet renamed (using long name)
    Args: 
        present_on_ppto : list of dicts
        list_of_recordings : list of download paths
        check: 'Duplicate' for first check, 'Discover' for second check
    Returns: 
        absent, present, present_unrenamed : lists
    """
    absent, present, present_unrenamed = [], [], []

    # Turn list of dicts into a single dict
    dict_present_recordings = {}
    for item in present_on_ppto:
        dict_present_recordings[list(item.keys())[0]] = list(item.values())[0]

    # Check if recording is already present on PPTO
    for rec in list_of_recordings:
        rec_long_name = os.path.basename(rec)
        rec_short_name = rename_recording(rec_long_name)
        
        # Short name will be on PPTO when we are checking before uploading - first duplicate check
        # Full name will be on PPTO when we are checking before renaming   - second discover check
        if not rec_short_name in list(dict_present_recordings.keys()) and not rec_long_name in list(dict_present_recordings.keys()):
            # Neither were found, the recording is absent on PPTO
            absent.append(rec)
            if check == 'Discover':
                build_undiscovered() 
        else:
            # Present with short name
            if rec_short_name in dict_present_recordings:
                present.append({rec_short_name: dict_present_recordings[rec_short_name]})
            # Present with long name
            elif rec_long_name in dict_present_recordings:
                present.append({rec_long_name: dict_present_recordings[rec_long_name]})
                if check == 'Duplicate':
                    present_unrenamed.append({rec_long_name: dict_present_recordings[rec_long_name]})
    return absent, present, present_unrenamed

def build_undiscovered():
    courseLabel_folderId_pairs = check_json_courselabel_folderid_pairs()
    for courseLabel, folderId in courseLabel_folderId_pairs.items():
        if courseLabel == g_current_course_label:
            global g_undiscovered_course_folders
            g_undiscovered_course_folders[courseLabel] = folderId

def undiscovered_course_folders():
    return g_undiscovered_course_folders
        
def get_recording_date_created(path, rec_ids_date_created):
    """extracting date part from datetime value
    """
    for ele in rec_ids_date_created:
        for id, date in ele.items():
            if id in path:
                return date.rsplit("T", 1)

def check_upload_results(failed_uploads:list, recordings_not_discovered:list):
    """genuine failed_uploads returned from actual upload operation
        recordings_not_discovered is the result of the second check (discovery on PPTO)
    """
    if len(failed_uploads) > 0:
        LOGGER.warning(
            f"Some recordings weren't uploaded properly : {failed_uploads}"
        )
    if len(recordings_not_discovered) > 0:
        LOGGER.warning(
             f"Some uploaded recordings remain undiscovered on PPTO"
        )


def clean_chat_message(message):
    """Removes unwanted whitespace and characters from Collab chat entries prior to saving
    Args:
        message (str): Chat message on given recording
    Returns:
        [str]: Cleaned message
    """
    LOGGER.debug(f"{message}")
    handle_types(*[(message, "")])
    clean = re.compile("<.*?>")
    return re.sub(clean, "", message)

def save_chatfile_as_csv(fname, json_info, header):
    file = open(fname, "w", encoding="utf-8")
    writer = csv.writer(file)
    writer.writerow(header)
    for json_row in json_info:
        writer.writerow(
            [
                json_row["userName"],
                clean_chat_message(json_row["body"]),
                json_row["relativeEventTime"],
                json_row["id"],
            ]
        )
    file.close()


def pre_run_reset():
    """Procedure to remove json lookup file + remove .mp4 files from downloads folder 
        before starting a new run
    """
    json_filepath = "./data/courseLabel_folderId_pairs.json"
    downloads_dir = "./downloads/"
    
    # remove json file
    try:
        if os.path.exists(json_filepath):
            os.remove(json_filepath)
    except OSError as e:
        LOGGER.error(str(e))

    # remove .mp4 files from downloads folder
    try:
        for file in os.listdir(downloads_dir):
            os.remove(os.path.join(downloads_dir, file))
    except OSError as e:
        LOGGER.error(str(e))


def run_restart():
    """Procedure to restart application for unexpected crashes such as network issues
    """
    try:
        msg = f"\n--- RESTARTING THE RUN ---"
        print(msg)
        LOGGER.info(msg)
        time.sleep(globalConfig.RestartTimeSleep)
        python = sys.executable
        os.execl(python, python, * sys.argv)
    except Exception as e:
        LOGGER.error(str(e))

def time_of_day():
    return time.strftime("%H:%M:%S")
