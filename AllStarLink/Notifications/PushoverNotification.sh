#!/bin/bash
#
# Remember: sudo chmod +x PushoverNotification.sh 
# This script is used to send a Pushover (https://pushover.net/) notification when a node connects to your AllStarLink node (https://allstarlink.org/)
# You will need to update your /etc/asterisk/rpt.conf file by adding the following at the bottom, under your node stanza
# 
# connpgm=/etc/asterisk/scripts/PushoverNotification.sh 1
# discpgm=/etc/asterisk/scripts/PushoverNotification.sh 0
#
# NOTE: You will need to add jq (command line JSON processor) to your pi (sudo apt-get install jq)

# For Pushover credentials, I created the file /etc/asterisk/scripts/creds.ini that contained
# APP_TOKEN=MyToken
# USER_KEY=MyUserKey

# Both connpgm and discpgm pass two command line arguments to your program: The first is your node number while the second is their node number
# NOTE: Make sure you have quotes around the command line arguments assignments and no spaces before or after the =
CONNECT_OR_DISCONNECT="$1"
MY_NODE="$2"
THEIR_NODE="$3"

# Determine whetherthis is a connect or a disconnect and we'll substitute the text into the message at the end
CONN_TYPE=$([[ "$CONNECT_OR_DISCONNECT" -eq 1 ]] && echo "connected to" || echo "disconnected from")

# We don't have any error checking here, things might explode, this contains our secrets
source "/etc/asterisk/scripts/creds.ini"

# Let's call the AllStarLink API and substitute in their node number.
# We will then pipe the output to jq, the -r flag removes double quotes.
# We are grabbing the User_ID (which is the users call sign) and their location.
# The + "|" + concatenates the User_ID and Location together using the pipe (|) as the separator character
# We then just need to specify the location of the data we're interested in the JSON: .node.server.User_ID and .node.server.Location
# As an example, your node info is here: https://stats.allstarlink.org/api/stats/1234 [replace 1234 with your node number]
# Note that you'll need to format it to make it readable, you can use https://jsonformatter.org/ or visual studio code, or whatever your preference is
ASL_RESPONSE=$(curl -X GET "https://stats.allstarlink.org/api/stats/${THEIR_NODE}" | jq -r '.node.server.User_ID + "|" + .node.server.Location')

# Recall we used the pipe above to concatenate the response into result
# We can then use cut, specify our delimiter, then choose the piece of the array you want (-f 1 is the first while -f 2 is the second)
CALLSIGN=$(echo "$ASL_RESPONSE" | cut -d '|' -f 1)
CALLSIGN_LOCATION=$(echo "$ASL_RESPONSE" | cut -d '|' -f 2)

# As we now have their callsign, we can use the following API: https://call3.n0agi.com/
# Note that we append their callsign and then a /json/ to retrieve JSON data from the API
# We again concatenate the .First and .Last elements together but use one space for concatenating the result together
CALLSIGN_RESULT=$(curl -X GET "https://call3.n0agi.com/${CALLSIGN}/json/" | jq -r '.First + " " + .Last + "|" + ."License Status" + " " + ."Operator Class"')
CALLSIGN_NAME=$(echo "$CALLSIGN_RESULT" | cut -d '|' -f 1)
CALLSIGN_STATUS=$(echo "$CALLSIGN_RESULT" | cut -d '|' -f 2)

# Construct URLs to get to their AllStarLink Node page as well as tehir QRZ page
THEIR_NODE_URL="<a href=\"https://stats.allstarlink.org/stats/${THEIR_NODE}\">${THEIR_NODE}</a>"
THEIR_CALLSIGN_URL="<a href=\"https://www.qrz.com/db/${CALLSIGN}\">${CALLSIGN}</a>"

# For a carriage return in the message to Pushover
NEW_LINE='
'

# Let's format our message that we're going to send via Pushover:
MESSAGE="Node ${THEIR_NODE_URL} has ${CONN_TYPE} your node ${MY_NODE}.${NEW_LINE}${THEIR_CALLSIGN_URL}: ${CALLSIGN_NAME} from ${CALLSIGN_LOCATION} ${NEW_LINE}License Info: ${CALLSIGN_STATUS}"

# Now let's send our notification
curl -s \
    -F "token=${APP_TOKEN}" \
    -F "html=1" \
    -F "user=${USER_KEY}" \
    -F "message=${MESSAGE}" \
    https://api.pushover.net/1/messages.json
