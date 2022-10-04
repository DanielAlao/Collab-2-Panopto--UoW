# Allow deletion of local downloaded recordings to occur in actual mode
# possible values: Yes or No
DeleteLocalRecordings = 'Yes'

# Allow deletion of BB recordings to occur in actual mode
# possible values: Yes or No
DeleteBBRecordings = 'No'

# Allow deletion of unmapped BB recordings to occur in actual mode
# possible values: Yes or No
DeleteUnmappedBBRecordings = 'No'

# Allow downloading of the recordings in preview mode
# possible values: Yes or No
PreviewWithDownloads = 'No'

# Specify environment in which the app is running
# possible values: Local, Server01 (test server), Server02 (live server), Server03, Server04, Server05
Environment = 'Local'

# Select a data source to get the eligible recordings
# possible values: DB, API, CSV, INLINE
DataSource = 'DB'

# Select logging detail level
# possible values: Verbose, Brief
LogDetail = 'Brief'

# Allow sending email notifications (info or alert)
# possible values: Yes or No
EmailNotification = 'Yes'

# Set time sleep (in seconds) before accessing recordings on Panopto
PanoptoTimeSleep = 50

# Set time sleep (in seconds) before restarting the app
RestartTimeSleep = 3600

# Enable scheduled automated run
# possible values: Yes, No
ScheduledRun = 'Yes'

# set time to stop automated run before 24-hour limit
ControlledStopTime = '23:00:00'

# set a countdown timer (in hours) for Panopto processing duration
PanoptoCountdown = 2
