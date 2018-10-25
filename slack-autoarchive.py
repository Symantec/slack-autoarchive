#!/usr/bin/python3.6

from datetime import timedelta, datetime
import logging
import os
import requests
import sys
import time
import json

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
SKIP_SUBTYPES      = {'channel_leave', 'channel_join'}  # 'bot_message'

logging.basicConfig(filename=AUDIT_LOG, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_whitelist_keywords():
  keywords = []
  if os.path.isfile('whitelist.txt'):
    with open('whitelist.txt') as f:
      keywords = f.readlines()

  # remove whitespace characters like `\n` at the end of each line
  keywords = map(lambda x: x.strip(), keywords)
  if WHITELIST_KEYWORDS:
    keywords = keywords + WHITELIST_KEYWORDS.split(',')
  return keywords


def get_channel_alerts():
  alerts = {
    'channel_template': 'This channel has had no activity for %s days. It is being auto-archived. If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point.'
  }
  if os.path.isfile('templates.json'):
    with open('templates.json') as f:
      alerts = json.load(f)
  return alerts


# api_endpoint is a string, and payload is a dict
def slack_api_http(api_endpoint=None, payload=None, method='GET', retry=True, retry_delay=0):

  uri = 'https://slack.com/api/' + api_endpoint
  payload['token'] = SLACK_TOKEN
  try:
    # Force request to take at least 1 second. Slack docs state:
    # > In general we allow applications that integrate with Slack to send
    # > no more than one message per second. We allow bursts over that
    # > limit for short periods.
    if retry_delay > 0:
      time.sleep(retry_delay)

    if method == 'POST':
      response = requests.post(uri, data=payload)
    else:
      response = requests.get(uri, params=payload)

    if response.status_code == requests.codes.ok and 'error' in response.json() and response.json()['error'] == 'not_authed':
      print('Need to setup auth. eg, SLACK_TOKEN=<secret token> python slack-autoarchive.py')
      sys.exit(1)
    elif response.status_code == requests.codes.ok and response.json()['ok']:
      return response.json()
    elif response.status_code == requests.codes.too_many_requests:
      retry_timeout = float(response.headers['Retry-After'])
      return slack_api_http(api_endpoint, payload, method, False, retry_timeout)
    else:
      raise
  except Exception as error_msg:
    raise Exception(error_msg)


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
def is_channel_whitelisted(channel, white_listed_channels):
  for white_listed_channel in white_listed_channels:
    wl_channel_name = white_listed_channel.strip('#')
    if wl_channel_name in channel['name']:
      return True
  return False


def send_channel_message(channel_id, message):
  payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
  api_endpoint = 'chat.postMessage'
  slack_api_http(api_endpoint=api_endpoint, payload=payload, method='POST')


def archive_channel(channel, alert):
  api_endpoint = 'channels.archive'
  stdout_message = 'Archiving channel... %s' % channel['name']
  print(stdout_message)

  if not DRY_RUN:
    channel_message = alert % DAYS_INACTIVE
    send_channel_message(channel['id'], channel_message)
    payload        = {'channel': channel['id']}
    slack_api_http(api_endpoint=api_endpoint, payload=payload)
    logging.info(stdout_message)


def send_admin_report(channels):
  if ADMIN_CHANNEL:
    channel_names = ', '.join('#' + channel['name'] for channel in channels)
    admin_msg = 'Archiving %d channels: %s' % (len(channels), channel_names)
    if DRY_RUN:
      admin_msg = '[DRY RUN] %s' % admin_msg
    send_channel_message(ADMIN_CHANNEL, admin_msg)


if DRY_RUN:
  print('THIS IS A DRY RUN. NO CHANNELS ARE ACTUALLY ARCHIVED.')

whitelist_keywords = get_whitelist_keywords()
alert_templates = get_channel_alerts()
archived_channels = []

for channel in get_all_channels():
  sys.stdout.write('.')
  sys.stdout.flush()

  if (not is_channel_whitelisted(channel, whitelist_keywords) and
    is_channel_disused(channel, TOO_OLD_DATETIME)):
    archived_channels.append(channel)
    archive_channel(channel, alert_templates['channel_template'])

send_admin_report(archived_channels)
