import json
import requests
from tqdm import tqdm
from config import Config as Conf
from config import globalConfig
from src.models import CollabJWT as Jwt
from src.models import CollabSessions as Session
from src.views import Logger

LOGGER = Logger.init_logger(__name__)


class WebService:
    def __init__(self):
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug("")
        self.collab_key = Conf.credentials["collab_key"]
        self.collab_secret = Conf.credentials["collab_secret"]
        self.collab_domain = Conf.credentials["collab_base_url"]
        self.jsession = None
        self.cert = True if Conf.credentials["verify_certs"] == "True" else False
        #self.path = "/learn/api/public/v1/courses/contents/"

    def get_context(self):
        try:
            self.jsession = Jwt.CollabJWT(
                self.collab_domain, self.collab_key, self.collab_secret, self.cert
            )
            token = self.jsession.refresh_JWT()
            return token 
        except Exception as e:
            raise e

    ##### DATA SOURCE - API OPTION
    def courses_data_from_collab(self,course_filter):
        LOGGER.info("Contacting Collab API")
        json_pages = []
        token = self.get_context()
        if globalConfig.LogDetail == "Verbose":
            LOGGER.info(token)
        else:
            LOGGER.debug("")

        def get_courses_from_collab(offset=0):
            if course_filter == "":
                url = f"https://{self.collab_domain}contexts?offset={offset}"
            else:
                url = f"https://{self.collab_domain}contexts?offset={offset}&name={course_filter}"

            r = requests.get(url, headers={"Authorization": "Bearer " + token})           
            res = json.loads(r.text)
            if globalConfig.LogDetail == "Verbose":
                LOGGER.info(res) 
            else:
                LOGGER.debug("")
            if bool(res["results"]) == True:
                json_pages.append(res)
                #breakpoint()
                #offset += 1000
                #get_courses_from_collab(offset)
        if bool(json_pages) == False:
            get_courses_from_collab()
        return json_pages

    ##### DATA SOURCE - API OPTION
    def get_recordings_by_id(self, course_id, search_from):
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        recordings = session.get_recordings(course_id, search_from) # Response from collab api call
        return recordings

    ##### DATA SOURCE - DB OPTION
    def get_recording_db(self, recording_id):
        """Only used in preview mode (find recording)
        Returns:
        rec json object as dict
        """
        rec = {}
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        rec = session.get_recording_object_db(recording_id)
        return rec

    ##### DATA SOURCE - DB OPTION
    def get_recordings_db(self, rec_id_list):
        """Only used in actual mode (find recordings)
        Returns:
        recs as list of dicts
        """
        recs = []
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        for rec_id in rec_id_list:
            rec = session.get_recording_object_db(rec_id)
            recs.append(rec)
        return recs


    def get_public_recording(self, recording_id):
        """get recording data for download report + action
        Returns:
        json dict
        """
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        rec_data = session.get_public_recording_data(recording_id)
        return rec_data
    
    def get_private_recording(self, recording_id):
        """get download url for private recording
        Returns:
        recording url string
        """
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        rec_private_url = session.get_private_recording_url(recording_id)
        return rec_private_url


    def delete_recording_from_collab(self, recording_id):
        """Used to delete recording
        Returns:
        True, False
        """
        session = Session.CollabSessions(
            self.collab_domain, self.get_context(), self.cert
        )
        delete_result = session.delete_recording(recording_id)
        return delete_result
