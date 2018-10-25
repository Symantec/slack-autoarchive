#!/usr/bin/python3.6

from datetime import timedelta, datetime
import logging
import os
import requests
import sys
import time
import json

log_file = 'audit.log'
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#
# This will archive inactive channels. The inactive period is in days as 'self.days_inactive'
# You can put this in a cron job to run daily to do slack cleanup.
#


class ChannelReaper(object):
  def __init__(self):
    self.admin_channel      = os.getenv('ADMIN_CHANNEL')
    self.days_inactive      = int(os.getenv('DAYS_INACTIVE', 60))
    # set MIN_MEMBERS and any channels larger than this in people
    # are exempt from archiving. 0 is no limit.
    self.min_members        = int(os.getenv('MIN_MEMBERS', 0))
    self.dry_run            = (os.getenv('DRY_RUN', 'true') == 'true')
    self.slack_token        = os.getenv('SLACK_TOKEN')
    self.too_old_datetime   = datetime.now() - timedelta(days=self.days_inactive)
    self.whitelist_keywords = os.getenv('WHITELIST_KEYWORDS')
    self.skip_subtypes      = {'channel_leave', 'channel_join'}  # 'bot_message'
    # note, if the channel purpose has this string in it, we'll skip archiving this channel.
    self.skip_channel_str   = os.getenv('SLACK_SKIP_PURPOSE', '%noarchive')

  def get_whitelist_keywords(self):
    keywords = []
    if os.path.isfile('whitelist.txt'):
      with open('whitelist.txt') as f:
        keywords = f.readlines()

    # remove whitespace characters like `\n` at the end of each line
    keywords = map(lambda x: x.strip(), keywords)
    if self.whitelist_keywords:
      keywords = keywords + self.whitelist_keywords.split(',')
    return keywords

  def get_channel_alerts(self):
    alerts = {
      'channel_template': 'This channel has had no activity for %s days. It is being auto-archived. If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point. In the future, you can add "%noarchive" to your channel topic or purpose to avoid being archived. This script was run from this repo: https://github.com/Symantec/slack-autoarchive'
    }
    if os.path.isfile('templates.json'):
      with open('templates.json') as f:
        alerts = json.load(f)
    return alerts

  # api_endpoint is a string, and payload is a dict
  def slack_api_http(self, api_endpoint=None, payload=None, method='GET', retry=True, retry_delay=0):

    uri = 'https://slack.com/api/' + api_endpoint
    payload['token'] = self.slack_token
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
        return self.slack_api_http(api_endpoint, payload, method, False, retry_timeout)
      else:
        raise
    except Exception as error_msg:
      raise Exception(error_msg)

  # too_old_datetime is a datetime object
  def get_all_channels(self):
    payload  = {'exclude_archived': 1}
    api_endpoint = 'channels.list'
    channels = self.slack_api_http(api_endpoint=api_endpoint, payload=payload)['channels']
    all_channels = []
    for channel in channels:
      all_channels.append({'id': channel['id'], 'name': channel['name'], 'created': channel['created'], 'num_members': channel['num_members']})
    return all_channels

  def get_last_message_timestamp(self, channel_history, too_old_datetime):
    last_message_datetime = too_old_datetime
    last_bot_message_datetime = too_old_datetime

    if 'messages' not in channel_history:
      return (last_message_datetime, False)  # no messages

    for message in channel_history['messages']:
      if 'subtype' in message and message['subtype'] in self.skip_subtypes:
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

  def is_channel_disused(self, channel, too_old_datetime):
    num_members = channel['num_members']
    payload  = {'inclusive': 0, 'oldest': 0, 'count': 50}
    api_endpoint = 'channels.history'

    payload['channel'] = channel['id']
    channel_history = self.slack_api_http(api_endpoint=api_endpoint, payload=payload)
    (last_message_datetime, is_user) = self.get_last_message_timestamp(channel_history, datetime.fromtimestamp(float(channel['created'])))
    # mark inactive if last message is too old, but don't
    # if there have been bot messages and the channel has
    # at least the minimum number of members
    has_min_users = (self.min_members == 0 or self.min_members > num_members)
    return last_message_datetime <= too_old_datetime and (not is_user or has_min_users)

  # If you add channels to the WHITELIST_KEYWORDS constant they will be exempt from archiving.
  def is_channel_whitelisted(self, channel, white_listed_channels):
    # self.skip_channel_str
    # if the channel purpose contains the string self.skip_channel_str, we'll skip it.
    info_payload = {'channel': channel['id']}
    channel_info = self.slack_api_http(api_endpoint='channels.info', payload=info_payload, method='GET')
    channel_purpose = channel_info['channel']['purpose']['value']
    channel_topic = channel_info['channel']['topic']['value']
    if self.skip_channel_str in channel_purpose or self.skip_channel_str in channel_topic:
        return True

    # check the white listed channels (file / env)
    for white_listed_channel in white_listed_channels:
      wl_channel_name = white_listed_channel.strip('#')
      if wl_channel_name in channel['name']:
        return True
    return False

  def send_channel_message(self, channel_id, message):
    payload  = {'channel': channel_id, 'username': 'channel_reaper', 'icon_emoji': ':ghost:', 'text': message}
    api_endpoint = 'chat.postMessage'
    self.slack_api_http(api_endpoint=api_endpoint, payload=payload, method='POST')

  def archive_channel(self, channel, alert):
    api_endpoint = 'channels.archive'
    stdout_message = 'Archiving channel... %s' % channel['name']
    print(stdout_message)

    if not self.dry_run:
      channel_message = alert % self.days_inactive
      self.send_channel_message(channel['id'], channel_message)
      payload        = {'channel': channel['id']}
      self.slack_api_http(api_endpoint=api_endpoint, payload=payload)
      logging.info(stdout_message)

  def send_admin_report(self, channels):
    if self.admin_channel:
      channel_names = ', '.join('#' + channel['name'] for channel in channels)
      admin_msg = 'Archiving %d channels: %s' % (len(channels), channel_names)
      if self.dry_run:
        admin_msg = '[DRY RUN] %s' % admin_msg
      self.send_channel_message(self.admin_channel, admin_msg)

  def main(self):

    if self.dry_run:
      print('THIS IS A DRY RUN. NO CHANNELS ARE ACTUALLY ARCHIVED.')

    whitelist_keywords = self.get_whitelist_keywords()
    alert_templates = self.get_channel_alerts()
    archived_channels = []

    for channel in self.get_all_channels():
      sys.stdout.write('.')
      sys.stdout.flush()

      if (not self.is_channel_whitelisted(channel, whitelist_keywords) and
        self.is_channel_disused(channel, self.too_old_datetime)):
        archived_channels.append(channel)
        self.archive_channel(channel, alert_templates['channel_template'])

    self.send_admin_report(archived_channels)


if __name__ == '__main__':
  channel_reaper = ChannelReaper()
  channel_reaper.main()
