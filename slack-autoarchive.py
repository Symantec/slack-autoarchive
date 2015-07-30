#!/usr/local/bin/python

from datetime import timedelta, datetime
import os
import requests

#
# This will archive inactive channels. The inactive period is in days as 'DAYS_INACTIVE'
# You can put this in a cron job to run daily to do slack cleanup.
#

SLACK_TOKEN      = os.environ.get('SLACK_TOKEN')
DAYS_INACTIVE    = 60
TOO_OLD_DATETIME = datetime.now() - timedelta(days=DAYS_INACTIVE)


# api_endpoint is a string, and payload is a dict
def slack_api_http_get(api_endpoint=None, payload=None):
  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    response = requests.get(uri, params=payload)
    if response.status_code == requests.codes.ok:
      return response.json()
    else:
      raise Exception(response.content)
  except Exception as e:
    raise Exception(e)


# too_old_datetime is a datetime object
def get_all_channels():
  payload  = {'exclude_archived': 1}
  api_endpoint = 'channels.list'
  channels = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)['channels']
  all_channels = []
  for channel in channels:
    all_channels.append({'id': channel['id'], 'name': channel['name']})
  return all_channels


def get_last_message_timestamp(channel_history, too_old_datetime):
  last_message_datetime = too_old_datetime
  for message in channel_history['messages']:
    if 'subtype' not in message:
      last_message_datetime = datetime.fromtimestamp(float(message['ts']))
      break
  return last_message_datetime


def get_inactive_channels(all_unarchived_channels, too_old_datetime):
  payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
  api_endpoint = 'channels.history'
  inactive_channels = []
  for channel in all_unarchived_channels:
    payload['channel'] = channel['id']
    channel_history = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
    last_message_datetime = get_last_message_timestamp(channel_history, too_old_datetime)
    if last_message_datetime < too_old_datetime:
      inactive_channels.append(channel)
  return inactive_channels


def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http_get(api_endpoint=api_endpoint, payload=payload)


def archive_inactive_channels(channels):
  api_endpoint = 'channels.archive'
  for channel in channels:
    message = "This channel has had no activity for %s days. It is being auto-archived." % DAYS_INACTIVE
    message += "If you feel this is a mistake you an unarchive this channel to bring it back at any point."
    message += " ( https://github.com/Symantec/slack-autoarchive.git )"
    send_channel_message(channel['id'], message)
    payload = {'channel': channel['id']}
    slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
    print "Archiving channel... %s" % channel['name']


all_unarchived_channels = get_all_channels()
inactive_channels       = get_inactive_channels(all_unarchived_channels, TOO_OLD_DATETIME)
archive_inactive_channels(inactive_channels)

