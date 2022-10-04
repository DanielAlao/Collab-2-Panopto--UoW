import json
from urllib import response
import requests
from src.views import Logger
from src.models import Utilities as Utils
import json 
from config import globalConfig

LOGGER = Logger.init_logger(__name__)


class CollabSessions:
    def __init__(self, url, token, cert):
        LOGGER.debug("")
        self.url = url
        self.token = token
        self.cert = cert

    ##### DATA SOURCE - API OPTION
    def get_recordings(self, course_id, start_time):
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug(f"for course ID {course_id} from {start_time}")
        else:
            LOGGER.debug("")
        endpoint = (
            "https://"
            + self.url
            + "/recordings"
            + "?contextId="
            + course_id
            + "&startTime="
            + str(start_time) # This spans from the start time to the present
        )
        bearer = "Bearer " + self.token
        rheaders = Utils.get_headers(bearer)
        r = requests.get(endpoint, headers=rheaders, verify=self.cert)
        return Utils.handle_response(r)

    ##### DATA SOURCE - DB OPTION
    def get_recording_object_db(self, recording_id):
        """returns rec json dict
        """
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug("")
        auth_str = "Bearer " + self.token
        url = "https://" + self.url + "/recordings/" + recording_id 
        response = requests.get(url,
            headers={'Authorization': auth_str, 'Content-Type': 'application/json',
                'Accept': 'application/json'}, verify=self.cert)
        data = json.loads(response.text)
        return data



    def get_public_recording_data(self, recording_id):
        """Getting recording json data and defining if recording is public or private: 
            If public, we get a 200 response with recording json data 
            If private, we get a 403 response
        Returns:
        json dict
        """
        LOGGER.debug("")
        auth_str = "Bearer " + self.token
        url = "https://" + self.url + "/recordings/" + recording_id + "/data"
        headers = Utils.get_headers(auth_str)
        r = requests.get(url, headers, verify=self.cert)
        rec_data = Utils.handle_response(r)
        return rec_data


    def get_private_recording_url(self,recording_id):
        LOGGER.debug("")
        auth_str = "Bearer " + self.token
        url = "https://" + self.url + "/recordings/" + recording_id + "/url?validHours=1&disposition=download"
        r = requests.get(url,
                         headers={'Authorization': auth_str, 'Content-Type': 'application/json',
                                  'Accept': 'application/json'}, verify=self.cert)
        json_data = json.loads(r.text)
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug(json_data)
        else:
            LOGGER.debug("")
        return json_data['url']


    def delete_recording(self, recording_id):
        """Returns: True, False
        """
        LOGGER.debug(f"recording_id = {recording_id}")
        auth_str = "Bearer " + self.token
        url = f"https://{self.url}/recordings/{recording_id}"
        try:
            headers = Utils.get_headers(auth_str)
            r = requests.delete(url,headers={'Authorization': auth_str, 'Content-Type': 'application/json',
                                  'Accept': 'application/json'},verify=self.cert,)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                LOGGER.warning(f"404 => {recording_id} not found on Collab.") 
                return True
        except requests.exceptions.HTTPError as e:
            LOGGER.error(str(e))
            return False
    