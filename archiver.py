import datetime
import enum
import logging
import os
import subprocess
import sys
import shutil
import time
import requests
from dotenv import load_dotenv


class ResponseStatus(enum.Enum):
  ONLINE = 0
  OFFLINE = 1
  NOT_FOUND = 2
  UNAUTHORIZED = 3
  ERROR = 4

class Archiver:
  def __init__(self):
    load_dotenv('.env')
    requests.urllib3.disable_warnings()
    self.logger = logging.getLogger(__name__)
    self.logger.setLevel(logging.DEBUG)
    self.logger.addHandler(logging.StreamHandler())
    self.root_path = os.path.dirname(os.path.realpath(__file__))

    self.logger.info("Archiver initialized") 
    self.ffmpeg_path = "ffmpeg"
    self.disable_ffmpeg = False
    self.refresh = 15

    # user prefs 
    self.username = os.getenv("USERNAME")
    self.quality = os.getenv('QUALITY')

    # twitch secrets
    self.client_id = os.getenv('CLIENT_ID')
    self.client_secret = os.getenv('CLIENT_SECRET')

    self.token_url = "https://id.twitch.tv/oauth2/token?client_id=" + self.client_id + "&client_secret=" \
                         + self.client_secret + "&grant_type=client_credentials"
    self.url = "https://api.twitch.tv/helix/streams"
    self.access_token = self.fetch_access_token()

  def fetch_access_token(self):
    self.logger.info("Fetching access token")
    resp = requests.post(self.token_url, timeout=15, verify=False)
    if resp.status_code == 200:
      self.logger.info("Access token fetched")
      return resp.json()['access_token']
    else:
      self.logger.error("Error fetching access token")
      return None

  def run(self):
    # path to recorded stream 
    recorded_path = os.path.join(self.root_path, 'recorded', self.username)

    # path to finished stream with errors removed 
    processed_path = os.path.join(self.root_path, "processed", self.username)

    # create relevant directories if they don't exist
    if not os.path.exists(recorded_path):
      os.makedirs(recorded_path)

    if not os.path.exists(processed_path):
      os.makedirs(processed_path)

    # make sure the interval to check user availability is not less than 15 seconds
    if self.refresh < 15:
      self.logger.warning("Refresh interval is less than 15 seconds. Setting to 15 seconds")
      self.refresh = 15

    # attempt to fix videos from previous runs
    try:
      self.logger.info("Attempting to fix videos from previous runs")
      video_list = [f for f in os.listdir(recorded_path) if os.path.isfile(os.path.join(recorded_path, f))]

      if len(video_list) > 0:
        self.logger.info("Found %d videos from previous runs in recorded directory", len(video_list))

      for video in video_list:
        self.logger.info("Attempting to fix video %s", video)      

        recorded_filename = os.path.join(recorded_path, video)
        processed_filename = os.path.join(processed_path, video)
        self.process_recorded_file(recorded_filename, processed_filename)

    except Exception as e:
      self.logger.error("Error fixing videos from previous runs", e)

    # check if user is online
    self.logger.info("checking for %s every %s seconds, recording with %s quality",
                     self.username, self.refresh, self.quality)
    self.loop_check(recorded_path, processed_path)

  def process_recorded_file(self, recorded_filename, processed_filename):
    if self.disabled_ffmpeg:
      self.logger.info("Skipping ffmpeg processing")
      logging.info("moving %s to %s", recorded_filename, processed_filename)
      shutil.move(recorded_filename, processed_filename)
    else:
      self.logger.info("fixing %s", recorded_filename)
      self.ffmpeg_copy_and_fix_errors(recorded_filename, processed_filename)

  def ffmpeg_copy_and_fix_errors(self, recorded_filename, processed_filename):
    self.logger.info("Running ffmpeg on %s", recorded_filename)
    try:
      subprocess.call([self.ffmpeg_path, '-err_detect', 'ignore_err', '-i', recorded_filename, '-c', 'copy', processed_filename])      

      os.remove(recorded_filename)

    except Exception as e:
      self.logger.error("Error fixing videos %s", recorded_filename, e)

  def check_user(self):
    info = None
    status = ResponseStatus.ERROR

    try:
      headers = {"Client-ID": self.client_id, "Authorization": "Bearer " + self.access_token}

      resp = requests.get(self.url + "?user_login=" + self.username, headers=headers, timeout=15)
      resp.raise_for_status()
      info = resp.json()

      if info is None or not info["data"]:
        # user is offline
        status = ResponseStatus.OFFLINE

      else:
        # user is online
        status = ResponseStatus.ONLINE

    except requests.exceptions.HTTPError:
      if resp.status_code == 404:
        status = ResponseStatus.NOT_FOUND

      elif resp.status_code == 401:
        status = ResponseStatus.UNAUTHORIZED

      else:
        status = ResponseStatus.ERROR
    return status, info

  def loop_check(self, recorded_path, processed_path):
    while True:
      status, info = self.check_user()
        
      if status == ResponseStatus.NOT_FOUND:
        self.logger.error("User %s not found", self.username)
        time.sleep(self.refresh)

      elif status == ResponseStatus.ERROR:
        self.logger.error("Error checking user %s", self.username)
        self.logger.info("Retrying in 5 minutes", datetime.datetime.now().strftime("%Hh%Mm%Ss"))
        time.sleep(300)

      elif status == ResponseStatus.OFFLINE:
        logging.info("User %s currently offline, checking again in %s seconds", self.username, self.refresh)
        time.sleep(self.refresh)

      elif status == ResponseStatus.UNAUTHORIZED:
        logging.info("unauthorized, attempting to reauthenticate immediately")
        self.access_token = self.fetch_access_token()

      elif status == ResponseStatus.ONLINE:
        logging.info("User %s currently online, recording", self.username)
        channels = info["data"]                 
        channel = next(iter(channels), None)
        filename = self.username + " - " + datetime.datetime.now() \
                    .strftime("%Y-%m-%d %Hh%Mm%Ss") + " - " + channel.get("title") + ".mp4"

        # cleanup filename from unwanted characters
        # filename = re.sub(r'[^\w\-_\. ]', '', filename)
        filename = "".join(x for x in filename if x.isalnum() or x in [" ", "-", "_", "."])

        recorded_filename = os.path.join(recorded_path, filename)
        processed_filename = os.path.join(processed_path, filename)

        # start streamlink process
        subprocess.call(
          ["streamlink", "--twitch-disable-ads", "twitch.tv/" + self.username, self.quality,
            "-o", recorded_filename])

        logging.info("Recording complete, processing file")
        if os.path.exists(recorded_filename):
          self.process_recorded_file(recorded_filename, processed_filename)
        else:
          logging.error("Recording file not found, skipping")
        
        logging.info("Processing complete, checking again in %s seconds", self.refresh)
        time.sleep(self.refresh)

def main():
  archiver = Archiver()

  username = os.getenv('USERNAME')
  assert username, 'username is a required environment variable'

  quality = os.getenv('QUALITY')
  assert quality, 'quality is a required environment variable'

  refresh = os.getenv('REFRESH')
  assert refresh, 'refresh is a required environment variable'

  disable_ffmpeg = os.getenv('DISABLE_FFMPEG') or False

  archiver.username = username
  archiver.quality = quality
  archiver.refresh = int(refresh)
  archiver.disable_ffmpeg = disable_ffmpeg

  archiver.run()

if __name__ == "__main__":
  main()
  