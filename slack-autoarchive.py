#!/usr/local/bin/python

from datetime import timedelta, datetime
import os
import requests
import re

#
# This will archive inactive channels. The inactive period is in days as 'DAYS_INACTIVE'
# You can put this in a cron job to run daily to do slack cleanup.
#

SLACK_TOKEN      = os.environ.get('SLACK_TOKEN')
DAYS_INACTIVE    = 60
TOO_OLD_DATETIME = datetime.now() - timedelta(days=DAYS_INACTIVE)
DRY_RUN = os.environ.get('DRY_RUN')
ADMIN_CHANNEL = os.environ.get('ADMIN_CHANNEL')
WHITELIST_KEYWORDS = os.environ.get('WHITELIST_KEYWORDS')


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
    all_channels.append({'id': channel['id'], 'name': channel['name'], 'created': channel['created'], 'members': channel['members']})
  return all_channels


def get_last_message_timestamp(channel_history, too_old_datetime):
  last_message_datetime = too_old_datetime
  for message in channel_history['messages']:
    if 'subtype' not in message or message['subtype'] == 'file_share' or message['subtype'] == 'file_comment':
      last_message_datetime = datetime.fromtimestamp(float(message['ts']))
      break
  return last_message_datetime


def get_inactive_channels(all_unarchived_channels, too_old_datetime):
  print "Find inactive channels..."
  payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
  api_endpoint = 'channels.history'
  inactive_channels = []
  for channel in all_unarchived_channels:
    payload['channel'] = channel['id']
    channel_history = slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
    last_message_datetime = get_last_message_timestamp(channel_history, datetime.fromtimestamp(float(channel['created'])))
    if last_message_datetime <= too_old_datetime:
      if not (len(channel_history['messages']) > 30 and len(channel['members']) > 5):
        inactive_channels.append(channel)
  return inactive_channels

def filter_out_whitelist_channels(inactive_channels):
    channels_to_archive = []
    for channel in inactive_channels:
      whitelisted = False
      if WHITELIST_KEYWORDS
        for kw in WHITELIST_KEYWORDS.split(","):
          if kw in channel['name']:
            whitelisted = True
      if not whitelisted:
        channels_to_archive.append(channel)
    return channels_to_archive

def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http_get(api_endpoint=api_endpoint, payload=payload)


def archive_inactive_channels(channels):
  print "Archive inactive channels..."
  api_endpoint = 'channels.archive'
  for channel in channels:
    if not DRY_RUN:
      message = "This channel has had no activity for %s days. It is being auto-archived." % DAYS_INACTIVE
      message += " If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point."
      send_channel_message(channel['id'], message)
      if ADMIN_CHANNEL:
        send_channel_message(ADMIN_CHANNEL, "Archiving channel... %s" % channel['name'])
      payload = {'channel': channel['id']}
      slack_api_http_get(api_endpoint=api_endpoint, payload=payload)
    print "Archiving channel... %s" % channel['name']


all_unarchived_channels = get_all_channels()
inactive_channels       = get_inactive_channels(all_unarchived_channels, TOO_OLD_DATETIME)
channels_to_archive = filter_out_whitelist_channels(inactive_channels)
archive_inactive_channels(channels_to_archive)

