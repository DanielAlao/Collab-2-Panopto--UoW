from src.models import Utilities as Utils
from prettytable import PrettyTable
from src.views import Logger

LOGGER = Logger.init_logger(__name__)
REPORT_PUBLIC = []
REPORT_PRIVATE = []

# TODO Make sure we have a list of lists : https://stackoverflow.com/a/56427043
# TODO Check our lists have the expected size at very least. Maybe also data types for expected values


def create_download_public_report(report_public: list[list]):
    """Creates tabular output report detailing public recordings downloads for current run.
        Reports number of downloads in logs. 
    Args:
        report (list[list]): raw data from each downloaded recording 
    """

    Utils.create_dir_if_not_exists("./reports")
    filename = "./reports/collab_download_public_report.txt"

    table = PrettyTable(
        [
            "Course Label",
            "Collab Recording ID",
            "Recording Name",
            "Duration",
            "Storage Size (MB)",
            "Created Date",
        ]
    )
    for i in range(len(report_public)):
        entry = report_public[i]
        table.add_row(
            [
                entry[0],
                entry[1],
                entry[2],
                Utils.calculate_time(int(entry[3] / 1000)),
                str(round(float(entry[4]) / 1000000, 2)),
                Utils.convert_date(entry[5]),
            ]
        )
    try:
        with open(filename, "w") as f:
            f.write(table.get_string())
    except:
        LOGGER.info(f"Unable to create download report.")


def create_download_private_report(report_private: list[list]):
    """Creates download report for private recordings
    Args:
        report (list[list]): raw data from each downloaded recording
    """
    filename = "./reports/collab_download_private_report.txt"

    table = PrettyTable(
        [
            "Course Label",
            "Collab Recording ID",
            "Recording Name",
            "Duration",
            "Storage Size (MB)",
            "Created Date",
            "Recording Type"
        ]
    )
    for i in range(len(report_private)):
        entry = report_private[i]
        table.add_row(
            [
                entry[0],
                entry[1],
                entry[2],
                Utils.calculate_time(int(entry[3] / 1000)),
                str(round(float(entry[4]) / 1000000, 2)),
                Utils.convert_date(entry[5]),
                entry[6]
            ]
        )
    try:
        with open(filename, "w") as f:
            f.write(table.get_string())
    except:
        assert TypeError


def append_report_public_entry(course_label, recording_data):
    REPORT_PUBLIC.append(report_public_entry(course_label, recording_data))


def append_report_private_entry(course_label, recording_data):
    REPORT_PRIVATE.append(report_private_entry(course_label, recording_data))


def report_public_entry(course_label, recording_data):
    """[summary] Creates entry for recording download report, for given course.
    Args:
        course_label (str)
        recording_data (dict): Data for a given recording
    Returns:
        [array]: A entry for the recording download report, with details for a particular uuid.
    """
    return [
        course_label,
        recording_data["recording_id"],
        recording_data["recording_name"],
        recording_data["duration"],
        recording_data["storage_size"],
        recording_data["created"],
    ]


def report_private_entry(course_label, recording_data):
    return [
        course_label,
        recording_data["recording_id"],
        recording_data["recording_name"],
        recording_data["duration"],
        recording_data["storage_size"],
        recording_data["created"],
        "403 - private recording",
    ]


def generate_download_reports():
    LOGGER.info(f"Total public downloads so far: {len(REPORT_PUBLIC)}")
    LOGGER.info(f"Total private downloads so far: {len(REPORT_PRIVATE)}")
    create_download_public_report(REPORT_PUBLIC) 
    create_download_private_report(REPORT_PRIVATE) 


def get_downloads_totals():
    return len(REPORT_PUBLIC), len(REPORT_PRIVATE)
