from src.models import CollabWebService as Ws
from src.views import Logger
from re import search

WEBSERVICE = Ws.WebService()
LOGGER = Logger.init_logger(__name__)


def get_id_label_pairs(courses: list):
    """Takes list of courses returned from Collab API
        extracts id:label as key:value pair
    Args:
        courses(list): Returned from Collab JWT contexts
    Returns:
        pairs(dict): All id:label pairs on Collab, as dictionary
        ids_for_courses_without_labels(list): Collab courses without labels
    """
    LOGGER.info("Combining id labelId as key:value pairs")
    pairs = {}
    ids_for_courses_without_labels = []
    for x in range(len(courses)):
        for i in range(len(courses[x]["results"])):
            try:
                pairs[courses[x]["results"][i]["id"]] = courses[x]["results"][i]["label"] 
            except: # courses without labels
                ids_for_courses_without_labels.append(courses[x]["results"][i]["id"]) 
    return pairs, ids_for_courses_without_labels


def get_id_label_pairs_this_year(courses: list, this_year: str):
    """Takes list of courses returned from Collab API
        extracts id:label for currenct academic year
    Args:
        courses(list): Returned from Collab JWT contexts
        this_year(str): e.g. "21-21"
    Returns:
        pairs(dict): id:label pairs as dictionary
    """
    LOGGER.info(f"Combining id:label pairs for {this_year}")
    pairs = {}
    for x in range(len(courses)):
        for i in range(len(courses[x]["results"])):
            try:
                course_id = courses[x]["results"][i]["label"]
                if search(f"-{this_year}", course_id):
                    pairs[courses[x]["results"][i]["id"]] = courses[x]["results"][i][
                        "label"
                    ]
            except:
                continue
    return pairs
