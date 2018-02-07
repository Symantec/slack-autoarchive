#!/usr/local/bin/python

from datetime import timedelta, datetime
import os
import requests
import sys
import time

#
# This will archive inactive channels. The inactive period is in days as 'DAYS_INACTIVE'
# You can put this in a cron job to run daily to do slack cleanup.
#

ADMIN_CHANNEL      = os.getenv('ADMIN_CHANNEL')
AUDIT_LOG          = 'audit.log'
DAYS_INACTIVE      = int(os.getenv('DAYS_INACTIVE', 60))
# set MIN_MEMBERS and any channels larger than this in people
# are exempt from archiving. 0 is no limit.
MIN_MEMBERS        = int(os.getenv('MIN_MEMBERS', 0))
DRY_RUN            = (os.getenv('DRY_RUN', 'true') == 'true')
SLACK_TOKEN        = os.getenv('SLACK_TOKEN')
TOO_OLD_DATETIME   = datetime.now() - timedelta(days=DAYS_INACTIVE)
WHITELIST_KEYWORDS = os.getenv('WHITELIST_KEYWORDS')
THROTTLE_REQUESTS  = False
SKIP_SUBTYPES      = {'channel_leave', 'channel_join'}  # 'bot_message'


def get_whitelist_keywords():
  keywords = []
  if os.path.isfile('whitelist.txt'):
    with open('whitelist.txt') as f:
      keywords = f.readlines()

  # remove whitespace characters like `\n` at the end of each line
  keywords = map(lambda x: x.strip(), keywords)

  if WHITELIST_KEYWORDS:
    keywords.append(WHITELIST_KEYWORDS.split(','))
  return keywords


# api_endpoint is a string, and payload is a dict
def slack_api_http(api_endpoint=None, payload=None, method="GET", retry=True):
  global THROTTLE_REQUESTS

  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    if method == "POST":
      response = requests.post(uri, data=payload)
    else:
      response = requests.get(uri, params=payload)

    # Force request to take at least 1 second. Slack docs state:
    # > In general we allow applications that integrate with Slack to send
    # > no more than one message per second. We allow bursts over that
    # > limit for short periods.
    if THROTTLE_REQUESTS:
      time.sleep(1.0)

    if response.status_code == requests.codes.ok and response.json()['ok']:
      return response.json()
    elif retry and response.status_code == requests.codes.too_many_requests:
      THROTTLE_REQUESTS = True
      retry_timeout = 1.2 * float(response.headers['Retry-After'])
      print('Rate-limited. Retrying after ' + str(retry_timeout) + 'ms')
      time.sleep(retry_timeout)
      return slack_api_http(api_endpoint, payload, method, False)
    else:
      print(response.json())
      sys.exit(1)

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

  if 'messages' not in channel_history:
    return (last_message_datetime, False)  # no messages

  for message in channel_history['messages']:
    if 'subtype' in message and message['subtype'] in SKIP_SUBTYPES:
      continue
    last_message_datetime = datetime.fromtimestamp(float(message['ts']))
    break
  # for folks with the free plan, sometimes there is no last message,
  # then just set last_message_datetime to epoch
  if not last_message_datetime:
    last_bot_message_datetime = datetime.utcfromtimestamp(0)
  # return bot message time if there was no user message
  if last_bot_message_datetime > too_old_datetime and last_message_datetime <= too_old_datetime:
    return (last_bot_message_datetime, False)
  else:
    return (last_message_datetime, True)


def is_channel_disused(channel, too_old_datetime):
  num_members = channel['num_members']
  payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
  api_endpoint = 'channels.history'

  payload['channel'] = channel['id']
  channel_history = slack_api_http(api_endpoint=api_endpoint, payload=payload)
  (last_message_datetime, is_user) = get_last_message_timestamp(channel_history, datetime.fromtimestamp(float(channel['created'])))
  # mark inactive if last message is too old, but don't
  # if there have been bot messages and the channel has
  # at least the minimum number of members
  has_min_users = (MIN_MEMBERS == 0 or MIN_MEMBERS > num_members)
  return last_message_datetime <= too_old_datetime and (not is_user or has_min_users)


# If you add channels to the WHITELIST_KEYWORDS constant they will be exempt from archiving.
def is_channel_whitelisted(channel, keywords):
  for kw in keywords:
    if kw in channel['name']:
      return True
  return False


def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http(api_endpoint=api_endpoint, payload=payload, method="POST")


def write_log_entry(file_name, entry):
  with open(file_name, 'a') as logfile:
    logfile.write(decode(entry) + '\n')


def archive_channel(channel):
  api_endpoint = 'channels.archive'
  stdout_message = 'Archiving channel... %s' % decode(channel['name'])
  print(stdout_message)

  if not DRY_RUN:
    channel_message = 'This channel has had no activity for %s days. It is being auto-archived.' % DAYS_INACTIVE
    channel_message += ' If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point.'
    send_channel_message(channel['id'], channel_message)
    payload        = {'channel': channel['id']}
    log_message    = str(datetime.now()) + ' ' + stdout_message
    slack_api_http(api_endpoint=api_endpoint, payload=payload)
    write_log_entry(AUDIT_LOG, log_message)


def send_admin_report(channels):
  if ADMIN_CHANNEL:
    channel_names = ', '.join('#' + decode(channel['name']) for channel in channels)
    admin_msg = 'Archiving %d channels: %s' % (len(channels), channel_names)
    if DRY_RUN:
      admin_msg = '[DRY RUN] %s' % admin_msg
    send_channel_message(ADMIN_CHANNEL, admin_msg)

def decode(text):
  try:
    text = unicode(text, 'utf-8')
  except TypeError:
    return text


if DRY_RUN:
  print('THIS IS A DRY RUN. NO CHANNELS ARE ACTUALLY ARCHIVED.')

whitelist_keywords = get_whitelist_keywords()
archived_channels = []

for channel in get_all_channels():
  sys.stdout.write('.')
  sys.stdout.flush()

  if (not is_channel_whitelisted(channel, whitelist_keywords) and
    is_channel_disused(channel, TOO_OLD_DATETIME)):
    archived_channels.append(channel)
    archive_channel(channel)

send_admin_report(archived_channels)
