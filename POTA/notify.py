#------------------------------------------------------------------------------------------------#
#
# Purpose:
#  Wanted to dive into Pyton deeper for years so I took the following as my first deep dive:
#  In amateur radio there is Parks on the Air (POTA) in which you "hunt" activators in different
#  parks around the USA or the world. You receive "achivement" points for making contacts across
#  all 50 states and DC. I'm at my last 2 states needed to get all 50+DC: I'm currently missing
#  Hawaii and Rhode Island. I decided to make a Python script that will parse the POTA API looking
#  for activators who are using digital modes (FT4 or FT8) from either of these two states
#  If an activator is found, and their latest spot occurred in the last 2 minutes, then a
#  Pushover notification is sent with the details of the activator and then I can hunt them on the
#  reported band and hopefully get them into my log as a confirmed contact and wrap a bow on my
#  50 states.
#  This task (and others) will be orchestrated by Prefect (https://prefect.io) which will be
#  running in a Docker container as that's another piece of technology I'd like to begin using
#  So, there you have it. Happy hunting, feel free to adapt this script in any way you see fit
#
# Learning a bit in Python, so expect errors or code that is completely wrong, will eventually
# move a lot of this into classes, but that's for another day as is getting appropriate styling
# conventions. Code is a maximum of 79 characters wide, will do same to comments
#
# Sends a Pushover when any POTA activators that are from a given location
# Only spots that happened less than 2 minutes ago are included
# as well as we are restricted to just FT4 and FT8 modes.
# Three APIs are used:
#  POTA (Parks on the Air): Free API
#  QRZ: Have to be a paid Xml subscriber to use
#  Pushover: Notifications
#
# NOTE: You need to create an .env file in the root of your project that contains the variables:
#       Remember, if in git, add .gitignore that includes .env in it, don't want secrets in git!
#
# PUSHOVER_TOKEN
# PUSHOVER_USER
# QRZ_USERNAME
# QRZ_PASSWORD
#
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
# A frequency is the input from the POTA API and the amateur radio
# band is returned. Only interested in HF
# Switched to tuples based upon recommendations
def get_ham_band(value):
  frequency = float(value)
  bands = [
    (1800, 2000, "160m"),
    (3500, 4000, "80m"),
    (5300, 5500, "60m"),
    (7000, 7300, "40m"),
    (10100, 10150, "30m"),
    (14000, 14350, "20m"),
    (18000, 18200, "17m"),
    (21000, 21450, "15m"),
    (24800, 25000, "12m"),
    (28000, 29700, "10m"),
  ]
  for low, high, band in bands:
    if low <= frequency <= high:
      return band

  return f"[ERROR: Not Mapped]: {frequency}"

# Retrieves the QRZ key to use in subsequent API calls
# The key is good for 24 hours so at some point, cache this and update daily
# instead of what is being done now
# Modified based upon code suggestions
def get_qrz_key():
  QRZ_NS = {"qrz": "http://online.qrz.com"}
  QRZ_API_URL = "http://online.qrz.com/bin/xml"

  # Read from .env note that you HAVE to be a paying member to QRZ that includes
  # Xml support to use this lookup
  params = {
    "username": os.getenv("QRZ_USERNAME"),
    "password": os.getenv("QRZ_PASSWORD")
  }
  headers = {"Accept": "application/xml"}

  response = requests.get(QRZ_API_URL, params=params, headers=headers)
  response.raise_for_status()  # Raise exception for HTTP errors
  root = ET.fromstring(response.content)
  return root.findtext(".//qrz:Key", namespaces=QRZ_NS)

# Retrieve the first and last name of the provided callsign
# Eventually will get this to return an object
# NOTE: That is a field is null, it will not be present in the xml
# See: https://www.qrz.com/XML/specifications.1.2.html
# Also modified based upon suggestions
def get_qrz_callsign_info(callsign, qrz_key):
  QRZ_NS = {"qrz": "http://online.qrz.com"}
  QRZ_API_URL = "http://online.qrz.com/bin/xml"

  # Our request to get callsign information from QRZ
  response = requests.get(
    QRZ_API_URL,
    params={"s": qrz_key, "callsign": callsign},
    headers={"Accept": "application/xml"},
    timeout=10
  )
  response.raise_for_status()

  if not response.text:
    return "Not Found"

  root = ET.fromstring(response.content)
  first_name = root.findtext(".//qrz:fname", namespaces=QRZ_NS)
  last_name = root.findtext(".//qrz:name", namespaces=QRZ_NS)
  trustee = root.findtext(".//qrz:trustee", namespaces=QRZ_NS)

  # Note that not all callsign lookups contain both the fname and name
  # for example, look at W4SPF
  if first_name and last_name:
    return f"{first_name} {last_name}"
  elif trustee:
    return trustee
  else:
    return "Not Found"

# Our POTA API, create a class for this at some point
response = requests.get("https://api.pota.app/spot/activator")

spots = json.loads(response.text)

# Locations of interest
locations = [
    "US-HI", "US-RI", "US-ME", "US-NH",
    "US-CA", "US-FL", "US-ID", "US-VT"
]

spot_mode={"FT8", "FT4"}

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
  if spot["mode"] in spot_mode:

    # Check if it is a location we are interested in
    if spot["locationDesc"] in locations:

      # Make sure our datetime objects in UTC
      spot_datetime = datetime.fromisoformat(spot["spotTime"]+'+00:00')

      # And the difference between the time we made the call to the API and
      # the spot was recorded in the API is...
      difference = now - spot_datetime

      # We are only interested in spots that occurred less than 2 minutes ago
      if difference.total_seconds() < 120:

        heard = f" ({str(difference.seconds)} seconds ago)"

        # Scarf up our signals that were heard and make it somewhat readable
        # for Pushover
        notify.append(
          f"[{spot['mode']}:{spot['locationDesc']}] "
          f"{spot['activator']} "
          f"({get_qrz_callsign_info(spot['activator'], qrz_key)}) "
          f"was at {spot['name']} on {get_ham_band(spot['frequency'])} {heard}"
        )
# Only send a Pushover IF there are elements in the array
if notify:

  # Ignore SSL issues
  ssl._create_default_https_context = ssl._create_unverified_context

  # Time to send a pushover out: We'll just join the notify array split by a
  # carriage return
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
