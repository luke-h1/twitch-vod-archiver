# twitch vod archiver 

This is a simple wrapper around streamlink to download live Twitch streams. It is designed to be used with a cron job to download the latest stream.

## Prerequisites 🔧

* [Python3.10](https://www.python.org/downloads/release/python-3100/)
* [streamlink](https://streamlink.github.io/)
* [ffmpeg](https://www.ffmpeg.org/)


## Getting started 👷

* check if you have streamlink installed 

```bash 
streamlink --version
```

* create a `.env` file in the root of the project (see [.env.example](.env.example) for required variables)
* Go to twitch.tv and register for an account if you don't have one already 
* Go to the settings page and click on the "Security" tab
* Enable 2FA (this is required by Twitch in order to generate a twitch application which will allow you to generate secret keys)
* visit the [twitch developer portal](https://dev.twitch.tv/dashboard/apps) and create an application
* Click on the "Create New Application" button
* Fill out the form and click on "Create Application"
* Copy the client ID and secret into the `CLIENT_ID` and `CLIENT_SECRET` fields in the `.env` file
* Enter the username who you want to start recording in the `.env` file


## Usage:

```bash 
# install dependencies 
pipenv install 

# run script 
pipenv run python archiver.py
```

