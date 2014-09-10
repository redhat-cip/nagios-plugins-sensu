#!/bin/bash
#
# Nagios script to check whether sensu is running or not.
#
# Copyright © 2014 eNovance <licensing@enovance.com>
#
# Author: Nicolas Auvray <nicolas.auvray@enovance.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Requirement: curl
#

# States
STATE_OK=0
STATE_WARNING=1
STATE_CRITICAL=2
STATE_UNKNOWN=3

usage ()
{
    echo "Usage: $0 [OPTIONS]"
    echo " -h        Get help"
    echo ""
    echo "This script checks Sensu API. It relies on a call to /health endpoint. You can specify host, port and critical values hereafter:"
    echo " -H        Host of the Sensu API. Default: localhost"
    echo " -p        Port of the Sensu API. Default: 4567"
    echo " -c        Minimum number of consumers to be considered healthy. Default: 1"
    echo " -m        Maximum number of messages to be considered healthy. Default: 10"
    echo " -t        Timeout in seconds for the API call. Default: 10"
}

while getopts 'hH:p:c:m:t:' OPTION
do
    case $OPTION in
        h)
            usage
            exit 0
            ;;
        H)
            API_HOST=$OPTARG
            ;;
        p)
            API_PORT=$OPTARG
            ;;
        c)
            API_CONSUMERS=$OPTARG
            ;;
        m)
            API_MESSAGES=$OPTARG
            ;;
        t)
            API_TIMEOUT=$OPTARG
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done

# Requirements
if [ ! which curl >/dev/null 2>&1 ]; then echo "UNKNOWN: curl is not installed"; exit $STATE_UNKNOWN; fi

# Default values
API_CONSUMERS=${API_CONSUMERS:-1}
API_MESSAGES=${API_MESSAGES:-10}
API_HOST=${API_HOST:-"localhost"}
API_PORT=${API_PORT:-4567}
API_TIMEOUT=${API_TIMEOUT:-10}

# Let's go
API_RESP=$(curl -s -m ${API_TIMEOUT} -w "%{http_code}\\n" "http://${API_HOST}:${API_PORT}/health?consumers=${API_CONSUMERS}&messages=${API_MESSAGES}" -o /dev/null)
CURL_CODE=$(echo $?)

# Handle HTTP responses first
if [ ${API_RESP} = 204 ]; then
    echo "OK: Got an HTTP 204 response from the API, meaning Sensu service is running well."
    exit $STATE_OK
elif [ ${API_RESP} = 503 ]; then
    echo "CRITICAL: Sensu API returned an HTTP 503 response. Either the number of consumers/messages is respectively too low/high or sensu-server/rabbitMQ is down."
    exit $STATE_CRITICAL
# Then curl return code
elif [ ${CURL_CODE} = 7 ]; then
    echo "CRITICAL: Unable to contact Sensu API. Seems like sensu-api service is down."
    exit $STATE_CRITICAL
elif [ ${CURL_CODE} = 28 ]; then
    echo "CRITICAL: Timeout exceeded in API call. It most likely means that sensu-api or sensu-server is gone away."
    exit $STATE_CRITICAL
else
    echo "UNKNOWN: Unable to get an understandable answer from Sensu API."
    exit $STATE_UNKNOWN
fi

