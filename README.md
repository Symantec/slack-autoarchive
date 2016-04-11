#Autoarchive unused slack channels

##How to use

- Install python-requests dependency ( pip install requests )
- Set your slack token environment variable ( SLACK_TOKEN=somekey )
- Run the script, python slack-autoarchive.py

##What Channels Will Be Archived

A channel will be archived by this script is it doesn't meet any of the following criteria:

- Has non-bot messages in the past 60 days.
- Has bot messags in the past 60 days and has more than 5 members.
- Is whitelisted. A channel is considered to be whitelisted if the channel name contains keywords in the WHITELIST_KEYWORDS environment variable. Multiple keywords can be provided, separated by comma.
