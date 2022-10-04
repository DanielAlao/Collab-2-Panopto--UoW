import smtplib, ssl
import os
import csv
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from mysqlx import Row
from config.Config import credentials as config
from src.views import Logger
import xlsxwriter
from config import globalConfig

smtp_server = config["smtp_server"]
sender_email = config["sender_email"]
# sender_password= config["sender_password"]
receiver_info_email = config["receiver_info_email"]
receiver_alert_email = config["receiver_alert_email"]


BASE = os.getcwd()
LOGGER = Logger.init_logger(__name__)


def create_info_email(log_info_msg:str, controlled_stop:bool):
    message = MIMEMultipart("alternative")
    if controlled_stop is True:
        message["Subject"] = f"BB-PPTO - run controlled stop [{globalConfig.Environment}]"
    else:
        message["Subject"] = f"BB-PPTO - completed run results [{globalConfig.Environment}]"
    body = MIMEText(log_info_msg, "plain","utf-8")
    message.attach(body)
    return message


def create_alert_message(trace_back: str):
    # Create message body
    message = MIMEMultipart("alternative")
    message["Subject"] = f"BB-PPTO - error encountered [{globalConfig.Environment}]"
    part1 = MIMEText(get_html_alert(), "html", "utf-8")
    message.attach(part1)

    # Create traceback file
    f = open("traceback.txt", "w")
    f.write(trace_back)
    f.close()

    # Attach traceback to message
    with open("traceback.txt", "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition", f"attachment; filename= traceback.txt",
    )
    message.attach(part)
    os.unlink("traceback.txt")

    # Attach log to message
    with open(f"{BASE}/.logs/info.log", "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition", f"attachment; filename= info.log",
    )
    message.attach(part)

    # Attach debug log to message
    with open(f"{BASE}/.logs/dbg.log", "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition", f"attachment; filename= dbg.log",
    )
    message.attach(part)

    # Return message
    return message


def get_html_info():
    email = f"{BASE}/data/email_info.html"
    HtmlFile = open(email, "r", encoding="utf-8")
    return HtmlFile.read()


def get_html_alert():
    email = f"{BASE}/data/email_alert.html"
    HtmlFile = open(email, "r", encoding="utf-8")
    return HtmlFile.read()


def send_info_email(message: MIMEMultipart):
    send_email(message, False)


def send_alert_email(message: MIMEMultipart):
    send_email(message, True)


def send_email(message: MIMEMultipart, alert=False):
    if alert == True:
        receiver_email = receiver_alert_email
    else:
        receiver_email = receiver_info_email

    message["From"] = sender_email
    message["To"] = receiver_alert_email

    # Not working with UOW email smtp server
    # Create a secure SSL context
    # context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_server) as server:
            server.ehlo()  # Can be omitted
            # server.starttls(context=context)
            server.starttls()
            # server.login(sender_email,sender_password)
            # server.login(sender_email)
            server.sendmail(sender_email, receiver_email, message.as_string())
            server.quit()
    except Exception as e:
        LOGGER.error(f"Email failed to send: {e}")

def attach_notification_excel(
    message: MIMEMultipart, failed_downloads:list, failed_uploads: list, undiscovered_uploads = [], failed_ppto_deletions = []):
    if len(failed_downloads)!= 0 or len(failed_uploads)!= 0 or len(undiscovered_uploads)!= 0 or len(failed_ppto_deletions)!= 0:

        workbook = xlsxwriter.Workbook('BB-PPTO - run results.xlsx')

        failed_downloads_worksheet = workbook.add_worksheet("failed_dowloads")
        failed_uploads_worksheet = workbook.add_worksheet("failed_uploads")
        undiscovered_uploads_worksheet = workbook.add_worksheet("undiscovered_uploads")
        failed_ppto_deletions_worksheet = workbook.add_worksheet("failed_ppto_deletions")

        # Iterate over the data and write it out row by row.
        for row in range(2,len(failed_downloads)+2):
            failed_downloads_worksheet.write(f'A{row}', failed_downloads[row-2])
        
        for row in range(2,len(failed_uploads)+2):
            failed_uploads_worksheet.write(f'A{row}', failed_uploads[row-2])
        
        for row in range(2,len(undiscovered_uploads)+2):
            undiscovered_uploads_worksheet.write(f'A{row}', undiscovered_uploads[row-2])

        for row in range(2,len(failed_ppto_deletions)+2):
            failed_ppto_deletions_worksheet.write(f'A{row}', failed_ppto_deletions[row-2])

        workbook.close()

        with open('BB-PPTO - run results.xlsx', "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f"attachment; filename= BB-PPTO - run results.xlsx",
        )
        message.attach(part)

        os.unlink("BB-PPTO - run results.xlsx")

    return message

