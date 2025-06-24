
#!/bin/bash
#
# This script is used to send a Pushover (https://pushover.net/) notification when a node connects to your AllStarLink node (https://allstarlink.org/)
# You will need to update your /etc/asterisk/rpt.conf file by adding the following at the bottom, under your node stanza
# 
# connpgm=/etc/asterisk/scripts/OnConnect.sh
# discpgm=/etc/asterisk/scripts/OnDisconnect.sh
#
# NOTE: You will need to add jq (command line JSON processor) to your pi (sudo apt-get install jq)
#
# Pushover credentials: Probably want to store elsewhere


# NOTE: Make sure you do not put a space before/after the = sign
APP_TOKEN="your app token"
USER_KEY="your user key"

# Both connpgm and discpgm pass two command line arguments to your program: The first is your node number while the second is their node number
# NOTE: Make sure you have quotes around the command line arguments assignments
MyNode="$1"
TheirNode="$2"

# Let's call the AllStarLink API and substitute in their node number.
# We will then pipe the output to jq, the -r flag removes double quotes.
# We are grabbing the User_ID (which is the users call sign) and their location.
# The + "|" + concatenates the User_ID and Location together using the pipe (|) as the separator character
# We then just need to specify the location of the data we're interested in the JSON: .node.server.User_ID and .node.server.Location
# As an example, your node info is here: https://stats.allstarlink.org/api/stats/1234 [replace 1234 with your node number]
# Note that you'll need to format it to make it readable, you can use https://jsonformatter.org/ or visual studio code, or whatever your preference is
result=$(curl -X GET "https://stats.allstarlink.org/api/stats/${TheirNode}" | jq -r '.node.server.User_ID + "|" + .node.server.Location')

# Recall we used the pipe above to concatenate the response into result
# We can then use cut, specify our delimiter, then choose the piece of the array you want (-f 1 is the first while -f 2 is the second)
callsign=$(echo "$result" | cut -d '|' -f 1)

callsignLocation=$(echo "$result" | cut -d '|' -f 2)

# As we now have their callsign, we can use the following API: https://call3.n0agi.com/
# Note that we append their callsign and then a /json/ to retrieve JSON data from the API
# We again concatenate the .First and .Last elements together but use one space for concatenating the result together
callsignName=$(curl -X GET "https://call3.n0agi.com/${callsign}/json/" | jq -r '.First + " " + .Last')

# Let's format our message that we're going to send via Pushover:
MESSAGE="Node ${TheirNode}: ${callsign} [${callsignName} from ${callsignLocation}] has disconnected from your AllStar node ${MyNode}."

# Now let's send our notification
curl -s \
    -F "token=${APP_TOKEN}" \
    -F "user=${USER_KEY}" \
    -F "message=${MESSAGE}" \
    https://api.pushover.net/1/messages.json
