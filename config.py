"""
All settings you can change for running slack channel reaper will live in this file.
"""

import os
from datetime import datetime, timedelta


def get_channel_reaper_settings():
    """ This returns a dictionary of all settings. """
    days_inactive = int(os.environ.get('DAYS_INACTIVE', 60))
    return {
        'admin_channel': os.environ.get('ADMIN_CHANNEL', ''),
        'days_inactive': days_inactive,
        # set MIN_MEMBERS and any channels larger than this in people
        # are exempt from archiving. 0 is no limit.
        'min_members': int(os.environ.get('MIN_MEMBERS', 0)),
        'dry_run': (os.environ.get('DRY_RUN', 'true') == 'true'),
        'slack_token': os.environ.get('SLACK_TOKEN', ''),
        'too_old_datetime': (datetime.now() - timedelta(days=days_inactive)),
        'whitelist_keywords': os.environ.get('WHITELIST_KEYWORDS', ''),
        'skip_subtypes': {'channel_leave', 'channel_join'},
        'skip_channel_str': os.environ.get('SLACK_SKIP_PURPOSE', '%noarchive'),
    }
