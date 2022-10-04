from distutils.command.config import config
from distutils.log import debug
import os
from time import sleep
from src.views import Logger
from src.models import CollabWebService as Ws
from src.models import DatabaseFeed as Dbfeed
from src.models import Discover
from src.models import Courses, Downloads, Utilities
from src.models.Uploads import Uploads
from src.views import Reports
from src.models import Emails
from src.models import Blacklist
import time
import traceback
import csv
from config import globalConfig
from config import Config

BASE = os.getcwd()
LOGS = Utilities.create_dir_if_not_exists(f"{BASE}/.logs")
LOGGER = Logger.init_logger(__name__)
WEBSERVICE = Ws.WebService()
DBFEED = Dbfeed.DatabaseFeed()

g_start_date = ''
g_end_date = ''
g_course_filter = ''
g_controlled_stop = False


##### DRY RUN OPTION
def run_preview(start_date: str, end_date: str, course_filter):
    global g_start_date
    g_start_date = start_date
    global g_end_date
    g_end_date = end_date
    global g_course_filter
    g_course_filter = course_filter

    LOGGER.info(f"Starting PREVIEW -- from {g_start_date} until {g_end_date}")
    print(f"\n\nPreview - for period: {g_start_date} -> {g_end_date}")
    
    Utilities.pre_run_reset()

    Blacklist.clean_downloads()

    id_label_names = ()
    label_names = ()
    id_label_names, label_names = apply_data_source_option()

    # add the download step of all recordings in preview mode (preview + download mode)
    if globalConfig.PreviewWithDownloads == "Yes":
            print('\nPreview - with downloads\n')
            id_label_pairs = {}
            failed_downloads_list = []
            for item in id_label_names:
                id_label_pairs[item[0]] = (item[1])
            eligible_recordings, failed_downloads = download_from_collab(course_id_labels = id_label_pairs)
            for failed in failed_downloads:
                failed_downloads_list.append(failed)
                # print("failed_downloads_list: ",failed_downloads_list)
            expected_uploads = Downloads.expected_uploads_list()
            print("expected uploads: ", len(expected_uploads))
            # print("expected uploads list: ", expected_uploads)
    else:
        print('\nPreview - no downloads\n')

    print("#########################")
    print("### COURSES ON COLLAB ###")
    print("#########################")
    print("┌───────────────────────┐")
    print("│ COURSE LABEL          │")
    print("└───────────────────────┘")
    if globalConfig.DataSource == 'DB':
        for item in label_names:
            print(f"{item[0]}")
    else:
        for item in id_label_names:
            print(f"{item[1]}")

    print("\n")

    print("#############################")
    print("### RECORDINGS PER COURSE ###")
    print("#############################")

    courses_with_recordings = []

    if globalConfig.DataSource == 'DB':
        course_recordings_db = ()
        course_recordings_db = DBFEED.get_recs_per_course_db(g_start_date, g_end_date, g_course_filter)
        if course_recordings_db == ():
            print(f"\n## No Recordings found")
        else:
            totalcount = 0
            for label, name, rec_id_list in course_recordings_db:
                courses_with_recordings.append([label,name])
                count = len(rec_id_list)
                totalcount += count
                print(f"\n## {count} Recordings expected for  {label}: ")
                for rec_id in rec_id_list:
                    rec = WEBSERVICE.get_recording_db(rec_id)
                    if rec.get('errorKey') == 'resource_not_found':  # db lag - case when deleted on collab
                        print(f"  + <recording not found on collab>")
                    else: 
                        filename = Utilities.return_download_filename_db(label, rec_id, rec, ".mp4")
                        print(f"  + {filename}")             
            print(f"\n\n{totalcount} Recordings expected for the selected period")
    else:
        recordings_found = []
        totalcount = 0
        for id,label,name in id_label_names:
            recordings_found = Downloads.get_recordings_list_by_id(id, g_start_date, g_end_date)
            # Filter courses with recordings
            if recordings_found == [] or recordings_found is None:
                print(f"\n## No Recordings found for: {label}")
            else:
                courses_with_recordings.append([label,name])
                count = len(recordings_found)
                totalcount += count
                print(f"\n## {count} Recordings found for  {label}: ")
                for rec in recordings_found:
                    filename = Utilities.return_download_filename(label, rec, ".mp4")
                    print(f"  + {filename}")
        print(f"\n\n{totalcount} Recordings found for the selected period")
 
    print("\n")
    print("########################################")
    print("### CORRESPONDING FOLDERS ON PANOPTO ###")
    print("########################################")

    # course_label and folder_id are returned
    courseLabels_folderIds, missing_folders_list = Utilities.get_courseLabel_folderId_pairs(
        courses_with_recordings
    )

    # folder names contain course labels by default
    print("\n## course labels and their corresponding folder Ids in Panopto:")

    for course_label, folder_id in courseLabels_folderIds.items():
        print(f"  + {course_label} \t> {folder_id}")

    print("\n## Missing folders in Panopto:")
    for missing_folder_id in missing_folders_list:
        print(f"  + {missing_folder_id}")

    print("\n")

    print("#######################")
    print("### PLANNED UPLOADS ###")
    print("#######################")
    print("")

    downloads_list = Utilities.get_downloads_list(f"{BASE}/downloads")
    folderId_downloads = Utilities.get_folder_download_matches(
        courseLabels_folderIds, downloads_list
    )
    # print("downloads_list: ", downloads_list)
    # print("folderId_downloads: ", folderId_downloads)

    if len(folderId_downloads) > 0:
        print("┌──────────────────────┬───────────────────────────────┬────────────┐")
        print("│ FILE NAME            │ COURSE LABEL (in folder name) │ FOLDER ID  │")
        print("└──────────────────────┴───────────────────────────────┴────────────┘")

        for folder_id, downloads in folderId_downloads.items():
            # Find course label corresponding to this folder_id
            course_label = list(courseLabels_folderIds.keys())[
                list(courseLabels_folderIds.values()).index(folder_id)
            ]
            for download in downloads:
                if folder_id == Config.default_ppto_folder["folder_id"]:
                    print(f"{os.path.basename(download)} > {Config.default_ppto_folder['folder_name']} ({folder_id})")
                else:
                    print(f"{os.path.basename(download)} > {course_label} ({folder_id})")
    else:
        print("  + <None>")


##### ACTUAL RUN OPTION
def run_application(start_date: str, end_date: str, course_filter):
    global g_start_date
    g_start_date = start_date
    global g_end_date
    g_end_date = end_date
    global g_course_filter
    g_course_filter = course_filter

    LOGGER.info(f"Starting ACTUAL RUN -- from {g_start_date} until {g_end_date}")

    try:
        
        Utilities.pre_run_reset()

        def upload_eligible_recordings(label_name: list, eligible_recordings: list):
            for failed in failed_pre_downloads:
                    failed_downloads_list.append(failed)
            if eligible_recordings != []:
                failed_uploads, undiscovered_uploads, successful_uploads, already_on_ppto, unrenamed_failed_ppto_deletions, failed_ppto_deletions = [],[],[],[],[],[]
                failed_uploads, undiscovered_uploads, successful_uploads, already_on_ppto, unrenamed_failed_ppto_deletions, failed_ppto_deletions = upload_to_panopto(
                label_name, eligible_recordings
                )
                for failed in failed_downloads:
                    failed_downloads_list.append(failed)
                for failed in failed_uploads:
                    failed_uploads_list.append(failed)
                for success in successful_uploads:
                    successful_uploads_list.append(success)
                for on_ppto in already_on_ppto:
                    already_on_ppto_list.append(on_ppto) 
                for failed in undiscovered_uploads:
                    undiscovered_uploads_list.append(failed)  
                for failed in failed_ppto_deletions:
                    failed_ppto_deletions_list.append(failed)     
                for failed in unrenamed_failed_ppto_deletions:
                    failed_ppto_deletions_list.append(failed)

        ## DOWNLOAD + UPLOAD ELIGIBLE RECORDINGS
        failed_downloads_list, failed_uploads_list, undiscovered_uploads_list, successful_uploads_list, already_on_ppto_list, failed_ppto_deletions_list = [], [], [], [], [], []

        def get_undiscovered_uploads():
            return undiscovered_uploads_list
        
        def get_failed_ppto_deletions():
            return failed_ppto_deletions_list

        id_label_names = () 
        label_names = ()
        id_label_names, label_names = apply_data_source_option()

        if globalConfig.DataSource == 'DB':
            for label,name in label_names:
                if globalConfig.ScheduledRun == 'Yes' and Utilities.time_of_day() >= globalConfig.ControlledStopTime:
                    set_controlled_stop()
                    break 
                else:
                    print(f"--------------------------------------------------------------------------------------------")
                    print(f"COLLAB:SEARCHING -- {label}")
                    print(f"--------------------------------------------------------------------------------------------")
                    LOGGER.debug(
                    "\n--------------------------------------------------------------------------------------------" +
                    f"\nCOLLAB:SEARCHING -- {label}" +
                    "\n--------------------------------------------------------------------------------------------")
                    eligible_recordings, failed_pre_downloads, failed_downloads = download_from_collab(label = label)
                    upload_eligible_recordings([label,name], eligible_recordings)            
        else:
            for id, label, name in id_label_names:
                    print(f"--------------------------------------------------------------------------------------------")
                    print(f"COLLAB:SEARCHING -- {label}")
                    print(f"--------------------------------------------------------------------------------------------")
                    LOGGER.debug(
                    "\n--------------------------------------------------------------------------------------------" +
                    f"\nCOLLAB:SEARCHING -- {label}" +
                    "\n--------------------------------------------------------------------------------------------")
                    eligible_recordings, failed_downloads = download_from_collab(course_id_labels = {id:label})
                    upload_eligible_recordings([label,name], eligible_recordings)

        successful_downloads_count = 0
        public_downloads_count, private_downloads_count = Reports.get_downloads_totals()
        successful_downloads_count = public_downloads_count + private_downloads_count
        
        log_info_msg = ''
        rediscover_msg = ''
        redelete_msg = ''

        if g_controlled_stop is True:
            log_info_msg = f"\n--- CONTROLLED STOP ---"

        log_info_msg += (f"\n--- END OF RUN SUMMARY ---" +
        f"\n----------------------------------------" +
        f"\nsuccessful downloads count: {successful_downloads_count}" +
        f"\n\nsuccessful uploads count: {len(successful_uploads_list)}" +
        f"\n\nfailed_downloads_list: {len(failed_downloads_list)} - {failed_downloads_list}" +
        f"\n\nfailed_uploads_list: {len(failed_uploads_list)} - {failed_uploads_list}" +
        f"\n\nalready_on_ppto_list: {len(already_on_ppto_list)} - {already_on_ppto_list}" +
        f"\n\nundiscovered_uploads_list: {len(undiscovered_uploads_list)} - {undiscovered_uploads_list}" +
        f"\n\nfailed_ppto_deletions_list: {len(failed_ppto_deletions_list)} - {failed_ppto_deletions_list}")
        print(log_info_msg)
        LOGGER.info(log_info_msg)

        # RE-DISCOVER 1 (to reduce undiscovered uploads)
        undiscovered_uploads_list_final_1 = []
        if len(undiscovered_uploads_list) > 0:
            uploader = Uploads()
            undiscovered_uploads_list_final_1 = uploader.Discover.re_discover(undiscovered_uploads_list)
            rediscover_msg = f"\n\nundiscovered_uploads_list_final_1: {len(undiscovered_uploads_list_final_1)} - {undiscovered_uploads_list_final_1}"
            print(rediscover_msg)
            LOGGER.info(rediscover_msg)

        # RE-DISCOVER 2 (to reduce undiscovered uploads)
        undiscovered_uploads_list_final_2 = []
        if len(undiscovered_uploads_list_final_1) > 0:
            uploader = Uploads()
            undiscovered_uploads_list_final_2 = uploader.Discover.re_discover(undiscovered_uploads_list_final_1)
            rediscover_msg = f"\n\nundiscovered_uploads_list_final_2: {len(undiscovered_uploads_list_final_2)} - {undiscovered_uploads_list_final_2}"
            print(rediscover_msg)
            LOGGER.info(rediscover_msg)

        # RE-DELETE 1 (to reduce failed ppto deletions)
        failed_ppto_deletions_list_final_1 = []
        if len(failed_ppto_deletions_list) > 0:
            uploader = Uploads()
            failed_ppto_deletions_list_final_1 = uploader.Discover.re_delete(failed_ppto_deletions_list)
            redelete_msg = f"\n\nfailed_ppto_deletions_list_final_1: {len(failed_ppto_deletions_list_final_1)} - {failed_ppto_deletions_list_final_1}"
            print(redelete_msg)
            LOGGER.info(redelete_msg)

        # RE-DELETE 2 (to reduce failed ppto deletions)
        failed_ppto_deletions_list_final_2 = []
        if len(failed_ppto_deletions_list_final_1) > 0:
            uploader = Uploads()
            failed_ppto_deletions_list_final_2 = uploader.Discover.re_delete(failed_ppto_deletions_list_final_1)
            redelete_msg = f"\n\nfailed_ppto_deletions_list_final_2: {len(failed_ppto_deletions_list_final_2)} - {failed_ppto_deletions_list_final_2}"
            print(redelete_msg)
            LOGGER.info(redelete_msg)

        log_info_msg += rediscover_msg
        log_info_msg += redelete_msg
        
       # Send email notification about run outcome
        if globalConfig.EmailNotification == 'Yes':
            message = Emails.create_info_email(log_info_msg, g_controlled_stop)
            # email = Emails.attach_notification_excel(
            #     message, failed_downloads_list, failed_uploads_list, undiscovered_uploads_list_final_2,
            #     failed_ppto_deletions_list_final_2
            # )
            Emails.send_info_email(message)

        LOGGER.info("TRANSFER COMPLETE")
        print("\n -- Completed: exiting program -- \n")

        done = True

        if done:
            sleep(10)
            os._exit(0)

    except Exception as e:
        LOGGER.error(str(e))
        if globalConfig.EmailNotification == 'Yes':
            trace_back = traceback.format_exc()
            message = Emails.create_alert_message(trace_back)
            Emails.send_alert_email(message)
        print("Exception: ", e)
        
        # mitigate: handling pending issues up to point of failure
        undiscovered_uploads = get_undiscovered_uploads()
        failed_ppto_deletions = get_failed_ppto_deletions()
        uploader = Uploads()
        uploader.Discover.mitigate(undiscovered_uploads,failed_ppto_deletions)

        Utilities.run_restart()
             

def apply_data_source_option():
    """ returns 
        id_label_names: tuple
        label_names: tuple
    """
    id_label_names = ()
    label_names = ()
    if globalConfig.DataSource == "DB":
        label_names = get_course_pairs_db()
    # elif globalConfig.DataSource == "API":
    #     id_label_names = get_course_pairs_api()
    # elif globalConfig.DataSource == "CSV":
    #     id_label_names = get_course_pairs_csv()
    elif globalConfig.DataSource == 'INLINE':
        id_label_names = get_course_pairs_inline()

    return id_label_names, label_names


##### DATA SOURCE - DB OPTION
def get_course_pairs_db():
    """Search for recordings via database connection from start to end dates
        Using global variables: g_start_date, g_end_date as strings
        g_course_filter optional search parameter
        start and end dates are strings in "%Y-%m-%dT%H:%M:%SZ" format
    Return: 
        tuple of course labels + names 
    """
    LOGGER.debug(f"Searching database for recordings from date: {g_start_date} to date: {g_end_date}")

    label_names = DBFEED.get_distinct_label_names_db(g_start_date, g_end_date, g_course_filter)
    
    return label_names

##### DATA SOURCE - API OPTION
def get_course_pairs_api():
    """ Get dict of {course id:label} pairs
        Search for recordings from start to end dates
        start and end dates are strings in "%Y-%m-%dT%H:%M:%SZ" format
    """
    LOGGER.debug(f"Searching courses for recordings from date: {g_start_date} to date: {g_end_date}")

    # We get to the recordings via the course id:label pairs

    # ENTER FILTER FOR SEARCH ON COURSE NAME
    # Returns the course id:label pairs from the api
    # NOTE This option will return all courses if course year filter (uow adhoc filter) is blank
    course_pairs = WEBSERVICE.courses_data_from_collab(g_course_filter) # Search term on name
    id_label_pairs, courses_without_labels = Courses.get_id_label_pairs(course_pairs)

    # First filter excluding the labels that are blacklisted
    blacklisted_courses = Blacklist.get_blacklisted_courses()
    course_pairs = {}
    for id, label in id_label_pairs.items():
        if not label in blacklisted_courses:
            course_pairs[id] = label

    return course_pairs

##### DATA SOURCE - CSV OPTION
def get_course_pairs_csv():
    with open(f"{BASE}/data/manual_customer_list.csv", mode='r', encoding='utf-8-sig') as infile:
        reader = csv.reader(infile)
        course_pairs = {rows[0]:rows[1] for rows in reader}

    return course_pairs

##### DATA SOURCE - INLINE OPTION
def get_course_pairs_inline():
    # Manually add the (course id,label,name)
    # NOTE This option is used for test runs mostly
    course_id_label_names = (
        # ("", "", ""),
        # ("", "", "")  
    )

    return course_id_label_names

def set_controlled_stop():
    global g_controlled_stop
    g_controlled_stop = True

##### COLLAB DOWNLOAD PHASE
def download_from_collab(course_id_labels = {}, label = ''):
    """Calls function to download recordings from BB Collab, using global variables
        g_start_date (datetime): start of search range
        g_end_date (datetime): end of search range
        g_course_filter (str): optional
     Calls function to generate download reports
    Args:
        course_id_labels (dict): {id:label} - optional (API route only)
        label (str): optional (DB route only)
    Return:
        eligible_recordings: list of dicts (part of recording objects)
        failed_downloads: list of #filenames
    """
    eligible_recordings, failed_pre_downloads, failed_downloads = [], [], []
    recordings_found = {}

    # DB actual run: label value required
    # DB preview run: no label value but global course filter possible/optional
    label = g_course_filter if label == '' else label

    if globalConfig.DataSource == 'DB':
        course_recordings_db = DBFEED.get_recs_per_course_db(g_start_date, g_end_date, label)
        if course_recordings_db == ():
            LOGGER.info(f"\n## No Recordings found for period {g_start_date} to {g_end_date}")
        else:
            for label, name, rec_id_list in course_recordings_db:
                LOGGER.info(f"{len(rec_id_list)} Recordings found for {label}")
                rec_objects = WEBSERVICE.get_recordings_db(rec_id_list)
                if len(rec_objects) != 0:
                    # getting list of downloadable recordings                    
                    recordings_found, failed_pre_downloads =  Downloads.list_of_recordings_db(rec_objects)
                    # actual download action     
                    failed_downloads, failed_download_ids = Downloads.get_recordings_for_course(recordings_found, label)

                for r in recordings_found:
                    if r["recording_id"] not in failed_download_ids:
                        # getting list of uploadable recordings
                        eligible_recordings.append(
                            {r["recording_id"]: r.get("created")}
                        )            
    else:
        for id, label in course_id_labels.items():
            recordings_found, failed_pre_downloads = Downloads.get_recordings_list_by_id(id, g_start_date, g_end_date)

            if recordings_found is None:
                LOGGER.info(f"No recordings found for: {label}")
            else:
                LOGGER.info(f"{len(recordings_found)} Recordings found for {label}")
                [
                    eligible_recordings.append(
                        {r["recording_id"]: r.get("created")}
                    )
                    for r in recordings_found
                ]
                failed_downloads = Downloads.get_recordings_for_course(recordings_found, label)

    Reports.generate_download_reports()

    return eligible_recordings, failed_pre_downloads, failed_downloads


##### PANOPTO UPLOAD PHASE
def upload_to_panopto(course_label_name: list, eligible_recordings: list):
    """Only applies to eligible courses, i.e. with eligible recordings
        Step 1: Find PPTO folder match
        Step 2: Upload (includes processing on ppto)
        Step 3: Rename
        Step 4: Delete BB
        Step 5: Delete Local
    """
    def rename(uploaded: list):
        print("Renaming uploaded recording(s)")
        LOGGER.debug("Renaming uploaded recording(s)")        
        if uploader.sessions.rename_successful_uploads(uploaded) == True:
            print("Renamed")
            LOGGER.debug("Renamed")   
        else:
            print("PPTO rename issue")
            LOGGER.debug("PPTO rename issue")      

    def delete_bb(uploaded: list):
        print("Deleting BB recording(s)")
        LOGGER.debug("Deleting BB recording(s)")
        if globalConfig.DeleteBBRecordings == "Yes":
            if folder_id != Config.default_ppto_folder["folder_id"]:
                if Downloads.delete_successful_uploads_from_collab(uploaded, eligible_recordings) == True:
                    print("BB deleted")
                    LOGGER.debug("BB deleted")
                else:
                    print("BB deletion issue")
                    LOGGER.debug("BB deletion issue")
            else: # unmapped recordings in the default folder
                if globalConfig.DeleteUnmappedBBRecordings == "Yes":
                    if Downloads.delete_successful_uploads_from_collab( uploaded, eligible_recordings) == True:
                        print("BB deleted")
                        LOGGER.debug("BB deleted")
                    else:
                        print("BB deletion issue")
                        LOGGER.debug("BB deletion issue")                        
                else:
                    print("No BB delete")
                    LOGGER.debug("No BB delete")
        else:
            print("No BB delete")
            LOGGER.debug("No BB delete")

    LOGGER.debug("PANOPTO:SEARCHING")
    print("Getting PPTO folder ID for the upload")
    uploader = Uploads()
    course_label_name_list = []
    course_label_name_list.append(course_label_name)
    courseLabels_folderIds, missing_folders_list = Utilities.get_courseLabel_folderId_pairs(
        course_label_name_list
    )

    Blacklist.clean_downloads()

    downloads_list = Utilities.get_downloads_list(f"{BASE}/downloads") # mp4 file paths
    folderId_downloads = Utilities.get_folder_download_matches(
        courseLabels_folderIds, downloads_list
    )

    already_on_ppto, successful_uploads, undiscovered_sessions, unrenamed_failed_ppto_deletions, failed_uploads, failed_ppto_deletions = [], [], [], [], [], []
    
    for folder_id, downloads in folderId_downloads.items():
        print("Duplicate check")
        LOGGER.debug("Check for duplicates on Panopto")
        # list of mp4 file paths + list of dictionaries with Name:Id
        recs_to_upload, already_on_ppto, unrenamed_on_ppto  = uploader.check_recordings_on_panopto(
            downloads, folder_id, check = 'Duplicate'
        )
        time.sleep(globalConfig.PanoptoTimeSleep)
        recs_to_upload, already_on_ppto, unrenamed_on_ppto  = uploader.check_recordings_on_panopto(
            downloads, folder_id, check = 'Duplicate'
        )        
        print('already_on_ppto: ', already_on_ppto) # list of dictionaries with Name:Id

        # If there are unrenamed recordings (undiscovered from previous runs)
        # - skip upload + discover
        # - If recording has been processed : apply rename on PPTO + delete on BB 
        # - If recording has not been processed : apply delete on PPTO 
        if len(unrenamed_on_ppto) > 0:
            unrenamed_successfulUploads, unrenamed_failedUploads =  uploader.check_unrenamed_recordings_on_panopto(
                unrenamed_on_ppto)        
            if len (unrenamed_successfulUploads) > 0:
                rename(unrenamed_successfulUploads)
                delete_bb(unrenamed_successfulUploads)

            if len (unrenamed_failedUploads) > 0:
                unrenamed_failed_ppto_deletions = uploader.delete_unprocessed_recordings_on_panopto(
                    unrenamed_failedUploads)
            

        if len(downloads) != len(already_on_ppto): 
            LOGGER.debug("Uploading recordings to Panopto folder")
            controlled_stop = False
            failed_uploads, successful_uploads, failed_ppto_deletions, controlled_stop = uploader.upload_list_of_recordings(
                recs_to_upload, eligible_recordings, folder_id
            )
            if controlled_stop is True:
                set_controlled_stop()

            # I wish we had a better solution.
            # Unfortunately it takes a little while for the session to be fully uploaded and present on ppto once recording is uploaded
            # If we check too quickly we won't see the session because it is still processing
            print("time sleep before discovery")
            secs = globalConfig.PanoptoTimeSleep
            time.sleep(secs)

            print("Discover on PPTO") # Double checking uploaded files are discoverable on Panopto
            LOGGER.debug("Discover uploaded recordings on Panopto")
            # 1 list of filepaths, 2 lists of dicts {recording #filename : ppto sessionId}
            (undiscovered_sessions, discovered_sessions, unrenamed_sessions) = uploader.check_recordings_on_panopto(
                successful_uploads, folder_id, check='Discover')

            LOGGER.debug("Check upload results")
            Utilities.check_upload_results(failed_uploads, undiscovered_sessions)

            if len(discovered_sessions) > 0:
                for ele in discovered_sessions:
                    print("Successful upload ", ele)
            else:
                print("Successful upload {}")

            if len(discovered_sessions) > 0:
                rename(discovered_sessions)
                delete_bb(discovered_sessions)

        print("Deleting Local recording(s)")
        LOGGER.debug("Deleting Local recording(s)")
        if globalConfig.DeleteLocalRecordings == "Yes":
            Downloads.delete_local_downloads(downloads, failed_uploads)
            print("Local deleted")
            LOGGER.debug("Local deleted")
        else:
            print("No Local delete")
            LOGGER.debug("No Local delete")


    return failed_uploads, undiscovered_sessions, successful_uploads, already_on_ppto, unrenamed_failed_ppto_deletions, failed_ppto_deletions



