#!/usr/local/bin/python

from datetime import timedelta, datetime
import os
import requests
import sys

#
# This will archive inactive channels. The inactive period is in days as 'DAYS_INACTIVE'
# You can put this in a cron job to run daily to do slack cleanup.
#

ADMIN_CHANNEL      = os.getenv('ADMIN_CHANNEL')
AUDIT_LOG          = 'audit.log'
DAYS_INACTIVE      = 60
MIN_MEMBERS        = os.getenv('MIN_MEMBERS')
DRY_RUN            = (os.getenv('DRY_RUN', 'true') == 'true')
SLACK_TOKEN        = os.getenv('SLACK_TOKEN')
TOO_OLD_DATETIME   = datetime.now() - timedelta(days=DAYS_INACTIVE)
WHITELIST_KEYWORDS = os.getenv('WHITELIST_KEYWORDS')


# api_endpoint is a string, and payload is a dict
def slack_api_http(api_endpoint=None, payload=None, method="GET"):
  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    if method == "POST":
      response = requests.post(uri, data=payload)
    else:
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
  channels = slack_api_http(api_endpoint=api_endpoint, payload=payload)['channels']
  all_channels = []
  for channel in channels:
    all_channels.append({'id': channel['id'], 'name': channel['name'], 'created': channel['created'], 'num_members': channel['num_members']})
  return all_channels


def get_last_message_timestamp(channel_history, too_old_datetime):
  last_message_datetime = too_old_datetime
  last_bot_message_datetime = too_old_datetime
  skip_subtypes = {'bot_message', 'channel_leave', 'channel_join' }
  for message in channel_history['messages']:
    if 'subtype' in message and message['subtype'] in skip_subtypes:
      last_bot_message_datetime = datetime.fromtimestamp(float(message['ts']))
      continue
    last_message_datetime = datetime.fromtimestamp(float(message['ts']))
    break

  # return bot message time if there was no user message
  if last_bot_message_datetime > too_old_datetime and last_message_datetime <= too_old_datetime:
    return (last_bot_message_datetime, False)
  else:
    return (last_message_datetime, True)


def get_inactive_channels(all_unarchived_channels, too_old_datetime):
  print('Find inactive channels...')
  payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
  api_endpoint = 'channels.history'
  inactive_channels = []
  cnt = 0
  for channel in all_unarchived_channels:
    sys.stdout.write('.')
    sys.stdout.flush()
    num_members = channel['num_members']
    if num_members == 0:
      inactive_channels.append(channel)
    else:
      payload['channel'] = channel['id']
      channel_history = slack_api_http(api_endpoint=api_endpoint, payload=payload)
      (last_message_datetime, is_user) = get_last_message_timestamp(channel_history, datetime.fromtimestamp(float(channel['created'])))
      # mark inactive if last message is too old, but don't
      # if there have been bot messages and the channel has
      # at least the minimum number of members
      if last_message_datetime <= too_old_datetime and (not is_user or (MIN_MEMBERS is not None and num_members < MIN_MEMBERS)):
        inactive_channels.append(channel)
  return inactive_channels


# If you add channels to the WHITELIST_KEYWORDS constant they will be exempt from archiving.
def filter_out_whitelist_channels(inactive_channels):
    keywords = []
    with open('whitelist.txt') as f:
        keywords = f.readlines()
    # remove whitespace characters like `\n` at the end of each line
    keywords = map(lambda x: x.strip(), keywords)

    if WHITELIST_KEYWORDS:
      keywords.append(WHITELIST_KEYWORDS.split(','))
    
    channels_to_archive = []
    for channel in inactive_channels:
      whitelisted = False
      for kw in keywords:
        if kw in channel['name']:
          whitelisted = True
          break
      if not whitelisted:
        channels_to_archive.append(channel)
    return channels_to_archive


def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http(api_endpoint=api_endpoint, payload=payload, method="POST")


def write_log_entry(file_name, entry):
  with open(file_name, 'a') as logfile:
    logfile.write(entry + '\n')


def archive_inactive_channels(channels):
  print('Archive inactive channels...')
  api_endpoint = 'channels.archive'
  for channel in channels:
    stdout_message = 'Archiving channel... %s' % channel['name']
    if not DRY_RUN:
      channel_message = 'This channel has had no activity for %s days. It is being auto-archived.' % DAYS_INACTIVE
      channel_message += ' If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point.'
      send_channel_message(channel['id'], channel_message)
      payload        = {'channel': channel['id']}
      log_message    = str(datetime.now()) + ' ' + stdout_message
      slack_api_http(api_endpoint=api_endpoint, payload=payload)
      write_log_entry(AUDIT_LOG, log_message)

    print(stdout_message)
  if ADMIN_CHANNEL:
    channel_names = ', '.join('#' + channel['name'] for channel in channels)
    admin_msg = 'Archiving channel: %s' % channel_names
    if DRY_RUN:
      admin_msg = '[DRY RUN] %s' % admin_msg
    send_channel_message(ADMIN_CHANNEL, admin_msg)


if DRY_RUN:
  print('THIS IS A DRY RUN. NO CHANNELS ARE ACTUALLY ARCHIVED.')
all_unarchived_channels = get_all_channels()
inactive_channels       = get_inactive_channels(all_unarchived_channels, TOO_OLD_DATETIME)
channels_to_archive     = filter_out_whitelist_channels(inactive_channels)
archive_inactive_channels(channels_to_archive)
