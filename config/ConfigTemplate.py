credentials = {
    "verify_certs": "True",
    "collab_key": "Collab Key",
    "collab_secret": "Collab Secret",
    "collab_base_url": "us.bbcollab.com/collab/api/csa",
    "ppto_server": "panoptoServer",
    "ppto_folder_id": "panoptoFolderId",
    "ppto_client_id": "panoptoClientId",
    "ppto_client_secret": "panoptoClientSecret",
    "ppto_username": "panoptoUserName",
    "ppto_password": "panoptoPassword",
    "email_smtp_tls_port": "587",  # For SSL
    "smtp_server": "smtpServer",
    # NOTE: personal sender and receiver accounts must be different or email will be blocked as spam
    "sender_email": "sender@url.com",
    "receiver_info_email": "receiver_info@url.com",
    "receiver_alert_email": "receiver_alert@url.com",
}

# Unmapped_Collaborate_Recordings folder id
default_ppto_folder = {
    "folder_name": "panoptoFolderName",
    "folder_id": "panoptoFolderId" 
}

db_connection = {
    "Driver": "ODBC Driver",
    "server" : "serverName",
    "database" : "databaseName",
    "username": "databaseUserName",
    "password": "databaseUserPassword",
    "TrustServerCertificate": "yes",
    "Encrypt": "yes",
    "Trusted_Connection": "yes",
}