from config import Config as Conf
from config import globalConfig
from src.views import Logger
from mysqlx import RowResult
import pyodbc 

LOGGER = Logger.init_logger(__name__)


class DatabaseFeed:
    def __init__(self):
        if globalConfig.LogDetail == "Verbose":
            LOGGER.debug("")
        self.db_driver = Conf.db_connection["Driver"]
        self.db_server = Conf.db_connection["server"]
        self.database = Conf.db_connection["database"]
        self.username = Conf.db_connection['username']
        self.password = Conf.db_connection['password']
        self.con = Conf.db_connection["TrustServerCertificate"]
        self.encrypt = Conf.db_connection["Encrypt"]
        self.trusted_connection = Conf.db_connection["Trusted_Connection"]


    def db_connect(self):
        try:
            if globalConfig.LogDetail == "Verbose":
                LOGGER.debug("connecting to db")
            cnxn = pyodbc.connect(f'DRIVER={self.db_driver};SERVER={self.db_server};DATABASE={self.database};UID={self.username};PWD={self.password};TrustServerCertificate={self.con};Encrypt={self.encrypt};TRUSTED_CONNECTION = {self.trusted_connection}')
            cursor = cnxn.cursor()
            return cursor
        except Exception as e:
            LOGGER.error(str(e))
            raise e
            

    def get_eligible_recordings_db(self, start_date, end_date, course_label):
        """DB call to get recordings in rows including course_label, recording_id, creation_date and course_name
            row[0] = course_label
            row[1] = recording_id
            row[2] = creation_date (used for troubleshooting only)
            row[3] = course_name
        Returns:
            list of tuples [(row[0],row[1],row[2],row[3])]
        """
        cursor = self.db_connect()
        # print("-- execute stored proc eligible recordings --")
        if course_label == '':
            sql_string = "execute [dbo].[get_eligible_recordings] @startDate = '" + start_date + "', @endDate = '" + end_date + "'"
        else:
            sql_string = "execute [dbo].[get_eligible_recordings] @courseLabel = '" + course_label + "', @startDate = '" + start_date + "', @endDate = '" + end_date + "'"
        # print("sql_string: ",sql_string)
        cursor.execute(sql_string)
        rows = cursor.fetchall()
        return rows

    def get_distinct_label_names_db(self,start_date, end_date, course_label):
        """Extracting from db rows (tuple of tuples)
        Returns:
            tuple of tuples ((course_label, course_name)) 
        """
        distinct_label_names = []
        rows = self.get_eligible_recordings_db(start_date, end_date, course_label)
        # row[0] is course_label
        # row[3] is course_name
        for row in rows:
            if (row[0],row[3]) not in distinct_label_names:
                distinct_label_names.append((row[0],row[3]))
        return tuple(distinct_label_names)


    def get_recs_per_course_db(self, start_date, end_date, course_label):
        """Extracting from db rows dict of {(course_label,course_name):[rec_id_list]}
        Returns:
            tuple of tuples ((course_label,course_name,[rec_id list]))
        """
        course_recs = {}
        rows = self.get_eligible_recordings_db(start_date, end_date, course_label)
        # row[0] is course_label
        # row[1] is recording_id
        # row[3] is course_name
        for row in rows:
            if (row[0],row[3]) in course_recs:
                course_recs[row[0],row[3]].append((row[1]))
            else:
                course_recs[row[0],row[3]] = [(row[1])]
        recs_per_course = []
        # dict key: label_name = tuple
        # dict value: rec_id_list = list
        for label_name, rec_id_list in course_recs.items():
            recs_per_course.append((label_name[0],label_name[1],rec_id_list))

        return tuple(recs_per_course)