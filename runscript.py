from concurrent.futures import thread
from threading import Thread
from time import sleep
from config import globalConfig
from src.models import Utilities as Utils
from src.controllers import ApplicationController as App
from src.views import Logger
from src.models import Emails
import pid
import os
import traceback
import psutil


is_active = True


def start(timer:thread, user:thread):
    timer.start()
    user.start()
    join(timer, user)


def join(timer:thread, user:thread):
    timer.join()
    user.join()


def initiate_auto_run(count:int):
    """auto run initiated following countdown
    """
    global is_active
    while is_active:
        m, s = divmod(count, 60)
        min_sec_format = "{:02d}:{:02d}".format(m, s)
        print(min_sec_format, end="\r")
        sleep(1)
        count -= 1
        if count < 0:
            is_active = False
            auto_run_program()
            break


def initiate_manual_run():
    """manual run initiated following user input
    """
    global is_active
    while is_active:
        input("")
        is_active = False
        manual_run_program()
        break


def manual_run_program():
    print("\n -- Manual run initiated -- \n")

    mode = input("\n Enter 'a' for actual run or 'p' for preview: ")
    while (mode != 'a' and mode != 'p') or mode == '':
        mode = input("\n Please try again, entering 'a' or 'p': ")

    course_filter_term = input("\n Enter term to search on course name or press enter:  ")

    period = input("\n Enter 'date' for search with dates or 'day' for search with days: ")
    while (period != 'date' and period != 'day') or period == '':
        period = input("\n Please try again, entering 'date' or 'day': ")
    if period == 'date':
        start_date = input("\n Enter start date (yyyy-mm-dd): ")
        end_date = input("\n Enter end date (yyyy-mm-dd): ")
    elif period == 'day':
        start_of_search_range = int(input("\n Enter number of days for search start: "))
        end_of_search_range = int(input("\n Enter number of days for search end: "))
        start_date = Utils.set_search_start_date(start_of_search_range)
        end_date = Utils.set_search_end_date(end_of_search_range)
    
    if mode == 'a':
        App.run_application(start_date, end_date, course_filter_term)
    elif mode == "p":
        App.run_preview(start_date, end_date, course_filter_term)
        

def auto_run_program():
    print("\n >> Automatic run initiated \n")
    ## SETTING 1
    # This setting should be used for fully automated daily batches migration
    start_date = Utils.set_search_start_date(1)
    end_date = Utils.set_search_end_date(0)
    ## SETTING 2
    # This setting should only be used for historic batches migration (to allow restart to work properly)
    # start_date = "2022-10-03"
    # end_date = "2022-10-02"
    course_filter = ""
    App.run_application(start_date, end_date, course_filter)


if __name__ == "__main__":
    global LOGGER
    try:
        LOGGER = Logger.init_logger(__name__)
        LOGGER.info(
            "\n=========================================================================================================" +
             "\nLAUNCHING APPLICATION" +
            "\n=========================================================================================================" 
            )
        
        pidfile = None

        userhome = os.path.expanduser('~')
        username = os.path.split(userhome)[-1]  
        pid_file_name = "runscript.py.pid"
        pid_dir = f"/home/{username}/tmp/"
        pid_file_path = os.path.join(pid_dir, pid_file_name)

        if os.path.isfile(pid_file_path):
            pid_number = int(open(pid_file_path, "r").readline().strip())                  
            if psutil.pid_exists(pid_number):  # pid file and process still running in parallel
                msg = (f"An instance of this program is still running with PID {pid_number}. The locking file is at {pid_file_path}")
                LOGGER.critical(msg)
                raise pid.PidFileAlreadyLockedError(msg)
                
        pidfile = pid.PidFile(
            piddir=pid_dir,
            pidname=pid_file_name,
            register_atexit=False,
            register_term_signal_handler=None,
        )
        with pidfile:
            print("\n -- PRESS ENTER FOR MANUAL RUN -- \n")
            timer = Thread(target=initiate_auto_run, args=(5,), daemon=True)
            user = Thread(target=initiate_manual_run, daemon=True)
            start(timer, user)

    except Exception as e:
        LOGGER.error(str(e))
        if globalConfig.EmailNotification == 'Yes':
            trace_back = traceback.format_exc()
            message = Emails.create_alert_message(trace_back)
            Emails.send_alert_email(message)
        Utils.run_restart()
