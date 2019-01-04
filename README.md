# Autoarchive unused slack channels

## Requirements

- python3
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

## How can I exempt my channel from being archived?

You can add the string '%noarchive' to your channel purpose or topic. (There is also a whitelist file or env variable if you prefer.)

## What Channels Will Be Archived

A channel will be archived by this script is it doesn't meet any of the following criteria:

- Has non-bot messages in the past 60 days.
- Is whitelisted. A channel is considered to be whitelisted if the channel name contains keywords in the WHITELIST_KEYWORDS environment variable. Multiple keywords can be provided, separated by comma.

## What Happens When A Channel Is Archived By This Script

- *Don't panic! It can be unarchived by following [these instructions](https://get.slack.help/hc/en-us/articles/201563847-Archive-a-channel#unarchive-a-channel) However all previous members would be kicked out of the channel and not be automatically invited back.
- A message will be dropped into the channel saying the channel is being auto archived because of low activity
- You can always whitelist a channel if it indeed needs to be kept despite meeting the auto-archive criteria.

## Custom Archive Messages

Just before a channel is archived, a message will be sent with information about the archive process. The default message is:

  This channel has had no activity for %s days. It is being auto-archived. If you feel this is a mistake you can <https://get.slack.help/hc/en-us/articles/201563847-Archive-a-channel#unarchive-a-channel|unarchive this channel> to bring it back at any point.'

To provide a custom message, simply edit `messages.json`.

## Known Issues

- Since slack doesn't have a batch API, we have to hit the api a couple times for each channel. This makes the performance of this script slow. If you have thousands of channels (which some people do), get some coffee and be patient.
