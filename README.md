# Autoarchive unused slack channels

## Requirements

- python2.7/python3
- Install requirements.txt ( `pip install -r requirements.txt` )
- Slack API token (https://api.slack.com/docs/oauth-test-tokens)

## Example Usages

The `SLACK_TOKEN` must be exposed as a environment variable before running your script. By default, the script will do a `DRY_RUN`. To perform a non-dry run, specify `DRY_RUN=false` as an environment variable as well. See sample usages below.
```
# Run the script in dry run archive mode...This will output a list of channels that will be archived.
SLACK_TOKEN=<TOKEN> python slack-autoarchive.py

# Run the script in active archive mode...THIS WILL ARCHIVE CHANNELS!
DRY_RUN=false SLACK_TOKEN=<TOKEN> python slack-autoarchive.py
```

## What Channels Will Be Archived

A channel will be archived by this script is it doesn't meet any of the following criteria:

- Has non-bot messages in the past 60 days.
- Is whitelisted. A channel is considered to be whitelisted if the channel name contains keywords in the WHITELIST_KEYWORDS environment variable. Multiple keywords can be provided, separated by comma.

## What Happens When A Channel Is Archived By This Script

- *Don't panic! It can be unarchived from https://slack.com/archives/archived* However all previous members would be kicked out of the channel and not be automatically invited back.
- A message will be dropped into the channel saying the channel is being auto archived because of low activity
- You can always whitelist a channel if it indeed needs to be kept despite meeting the auto-archive criteria.

## Custom Archive Messages

Just before a channel is archived, a message will be sent with information about the archive process. The default message is:

  This channel has had no activity for %s days. It is being auto-archived. If you feel this is a mistake you can <https://slack.com/archives/archived|unarchive this channel> to bring it back at any point.'

To provide a custom message, simply edit `messages.json`.

## Known Issues

- When piping or redirecting Python 2 output, the interpreter defaults to 8-bit/ASCII output. This will cause a crash if your channel names have unicode characters. A workaround is to set this environment variable `PYTHONIOENCODING=UTF-8` prior to executing Python.
