#------------------------------------------------------------------------------------------------#
# Learning a bit in Python, so expect errors or code that is completely wrong
# Sends a Pushover when any POTA activators that are from a given location
# Only spots that happened less than 2 minutes ago are included
# as well as we are restricted to just FT4 and FT8.
# Three APIs are used:
#  POTA (Parks on the Air): Free API
#  QRZ: Have to be a paid Xml subscriber to use
#  Pushover: Notifications
#
# NOTE: You need to create an .env file in the root of your project that contains the variables:
#       Remember, if in git, add .gitignore that includes .env in it, don't want secrets in git!
# PUSHOVER_TOKEN
# PUSHOVER_USER
# QRZ_USERNAME
# QRZ_PASSWORD
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
import xml.etree.ElementTree as ET

# Load variables from .env file, these are our "secrets" for accessing APIs
load_dotenv()

# Rough conversion from frequency to band, cast the net very wide
def get_ham_band(value):
  frequency = float(value)
  if frequency >= 1800 and frequency <= 2000:
   return "160m"
  elif frequency >= 3500 and frequency <= 4000:
   return "80m"
  elif frequency >= 5300 and frequency <= 5500:
     return "60m"
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

# Retrieves the QRZ key to use in subsequent API calls
# The key is good for 24 hours so at some point, cache this and update daily instead of what is being done now
def get_qrz_key():
  qrz_headers = {'Accept': 'application/xml'}
  qrz_response = requests.get(url=f"http://online.qrz.com/bin/xml?username={os.getenv('QRZ_USERNAME')};password={os.getenv('QRZ_PASSWORD')}",
                              headers=qrz_headers)
  root = ET.fromstring(qrz_response.content)
  ns = {"qrz": "http://online.qrz.com"}  # map a prefix to the default NS
  key =  root.findtext(".//qrz:Key", namespaces=ns)
  return key

# Retrieve the first and last name of the provided callsign
# Eventually will get this to return an object
# NOTE: That is a field is null, it will not be present in the xml
# https://www.qrz.com/XML/specifications.1.2.html
def get_qrz_callsign_info(callsign, qrz_key):
  qrz_headers = {'Accept': 'application/xml'}
  qrz_url = f"http://online.qrz.com/bin/xml?s={qrz_key};callsign={callsign}"
  qrz_resp = requests.get(qrz_url, headers=qrz_headers)
  # Make sure we have a response.. fix this later
  if qrz_resp.text:
   root = ET.fromstring(qrz_resp.content)
   ns = {"qrz": "http://online.qrz.com"}  # map a prefix to the default NS
   first_name = root.findtext(".//qrz:fname", namespaces=ns)
   last_name = root.findtext(".//qrz:name", namespaces=ns)
   #  Not all users actually have a first and last name, could be a trustee is in charge of record
   # e.g. check W4SPF, no fname
   if(first_name is not None and last_name is not None):
    return first_name + ' ' + last_name
   elif( root.findtext(".//qrz:trustee", namespaces=ns) is not None):
     return root.findtext(".//qrz:trustee", namespaces=ns)
  else:
    return 'Not Found'

# Our POTA API, create a class for this at some point
response = requests.get("https://api.pota.app/spot/activator")

spots = json.loads(response.text)

# Locations of interest
locations = ["US-HI", "US-RI", "US-ME", "US-NH", "US-CA", "US-FL", "US-ID", "US-VT", "US-NH"]

# An array to hold our notification text per spot
notify = []

# Current time in utc as is the convention for hams (0 offset)
now = datetime.now(pytz.utc)

# Grab our key for the QRZ API call, no need to grab it repeatedly
# Will need to store this key as it's good for 24-hours
qrz_key = get_qrz_key()

# Over the spots we shall go
for spot in spots:

  # Only interested in digital modes: FT4 or FT8
  if spot["mode"] == "FT8" or spot["mode"] == "FT4":

    # Check if it is a location we are interested in
    if spot["locationDesc"] in locations:

      # Make sure our datetime objects in UTC
      spot_datetime = datetime.fromisoformat(spot["spotTime"]+'+00:00')

      # And the difference between the time we made the call to the API and the spot was recorded in the API is...
      difference = now - spot_datetime

      # We are only interested in spots that occurred less than 2 minutes ago
      if difference.total_seconds() < 120:

        heard = f" ({str(difference.seconds)} seconds ago)"

        # Scarf up our signals that were heard and make it somewhat readable for Pushover
        notify.append(f"[{spot["mode"]}:{spot["locationDesc"]}] {spot["activator"]} ({get_qrz_callsign_info(spot["activator"], qrz_key)}) was at {spot["name"]} on {get_ham_band(spot["frequency"])} {heard}")

# Only send a Pushover IF there are elements in the array
if notify:

  # Ignore SSL issues
  ssl._create_default_https_context = ssl._create_unverified_context

  # Time to send a pushover out: We'll just join the notify array split by a carriage return
  conn = http.client.HTTPSConnection("api.pushover.net:443")

  conn.request("POST",
                   "/1/messages.json",
                       urllib.parse.urlencode({
                       "token": os.getenv('PUSHOVER_TOKEN'),
                       "user": os.getenv('PUSHOVER_USER'),
                       "sound": 'gamelan',
                       "message": "\n".join(notify),
             }), {"Content-type": "application/x-www-form-urlencoded"})
  conn.getresponse() # Check response at some point
