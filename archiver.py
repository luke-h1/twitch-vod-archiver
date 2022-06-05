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