#------------------------------------------------------------------------------------------------#
# Learning a bit in Python, so expect errors or code that is completely wrong
# Sends a Pushover when any POTA activators are from a given location
# Only spots that happened less than 2 minutes ago are included
# as well as we are restricted to just FT4 and FT8
# NOTE: You need to create an .env file in the root of your project that contains two variables:
# PUSHOVER_TOKEN and PUSHOVER_USER
#------------------------------------------------------------------------------------------------#

import json
import requests
import ssl
import http.client
import urllib
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os


load_dotenv()  # Load variables from .env file

# Rough conversion from frequency to band, cast the net very wide
def getBand(value):
    frequency = float(value)
    if frequency >= 1800 and frequency <= 2000:
     return "160m"
    elif frequency >= 3500 and frequency <= 4000:
     return "80m"
    elif frequency >= 5300 and frequency <= 5500:
     return "60m" # Note: One ham band with channels plus can only transmit a maximum of 100w
    elif frequency >= 7000 and frequency <= 7300:
     return "40m"
    elif frequency >= 10100 and frequency <= 10150:
     return "30m"
    elif frequency >= 14000 and frequency <= 14350:
     return "20m"
    elif frequency >= 18000 and frequency <= 18200:
     return "17m"
    elif frequency >= 21000 and frequency <= 21450:
     return "15m"
    elif frequency >= 24800 and frequency <= 25000:
     return "12m"
    elif frequency >= 28000 and frequency <= 29700:
     return "10m"
    else:
     return " [ERROR: Not Mapped]: "+ str(frequency)

# Our POTA API
response = requests.get("https://api.pota.app/spot/activator")
spots = json.loads(response.text)

# Locations of interest
locations = ["US-FL", "US-HI", "US-RI", "US-LA", "US-SC", "US-CA", "CA-ON", "US-VT", "US-NH","GB-ENG"]

# An array to hold our notification text per spot
notify = []

# Current time in utc
now = datetime.now(pytz.utc)

# Over the spots we shall go
for spot in spots:
  # Only interested in digital modes: FT4 and FT8
  if 1==1: #spot["mode"] == "FT8" or spot["mode"] == "FT4":
    # Check if it is a location we are interested in
    if spot["locationDesc"] in locations:

      # Make sure our datetime objects in UTC
      # We are only interested in spots that occurred less than 2 minutes ago
      spot_datetime = datetime.fromisoformat(spot["spotTime"]+'+00:00')
      difference = now - spot_datetime
      seconds = difference.seconds
      hours, seconds = divmod(seconds, 3600)
      minutes, seconds = divmod(seconds, 60)

      # Our fancy formatting for how long ago the signal was heard
      if( minutes == 0 or minutes ==1 ):
       heard = ''
       if( minutes==1):
        heard = '  (1 minute and ' + str(seconds) + ' seconds ago)'
       else:
        heard = ' (' + str(seconds) + ' seconds ago)'

       # Scarf up our signals that were heard and make it somewhat readable for Pushover
       notify.append('[' + spot["mode"] + ':' + spot["locationDesc"] + '] ' + spot["activator"] + ' was at ' + spot["name"] + ' on ' + getBand(spot["frequency"]) + heard)

# Only send a Pushover IF there are elements in the array
if notify:
  ssl._create_default_https_context = ssl._create_unverified_context

  # Time to send a pushover out: We'll just join the notify array split by a carriage return
  conn = http.client.HTTPSConnection("api.pushover.net:443")
  conn.request("POST",
                   "/1/messages.json",
                       urllib.parse.urlencode({
                       "token": os.getenv('PUSHOVER_TOKEN'),
                       "user": os.getenv('PUSHOVER_USER'),
                       "message": "\n".join(notify),
             }), {"Content-type": "application/x-www-form-urlencoded"})
  conn.getresponse() # Check response at some point
  
