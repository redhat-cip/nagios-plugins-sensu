#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Nagios script to get Sensu alerts via sensu-api
#
# Copyright © 2014 eNovance <licensing@enovance.com>
#
# Authors:
#   Nicolas Auvray <nicolas.auvray@enovance.com>
# Contributors:
#   Alexandre Maumené <alexandre@enovance.com>
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

import sys
import argparse
import json
import urllib2

# States
STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2
STATE_UNKNOWN = 3


def collect_args():
    parser = argparse.ArgumentParser(
        description='Get a list of events from a Sensu API')
    parser.add_argument('--hostname', metavar='hostname', type=str,
                        default='localhost',
                        help='Hostname or IP address of the Sensu API service')
    parser.add_argument('--port', metavar='port', type=int,
                        default=4567,
                        help='Port of the Sensu API service')
    parser.add_argument('--username', metavar='username', type=str,
                        default="",
                        help='Username to use for the Sensu API service')
    parser.add_argument('--password', metavar='password', type=str,
                        default="",
                        help='Password to use for the Sensu API service')
    parser.add_argument('--timeout', metavar='timeout', type=float,
                        default=10,
                        help='Timeout in seconds for the API call to return')
    parser.add_argument(
        '--info',
        metavar='info',
        type=str,
        default=None,
        help='Additional informations to output like sensu-dashboard address')
    return parser

#
# Format decoded JSON
#


def format_json_and_exit(events, info):
    # in case the returned array is empty: OK
    if len(json.dumps(events)) == 2:
        nagios_output = "OK: no ongoing events returned by Sensu API."
        exit_code = STATE_OK
    else:
        crit_count = 0
        warn_count = 0
        exit_code = STATE_UNKNOWN
        nagios_output = ""
        nagios_output_ext = ""

        for event in events:
            # only CRITICAL events
            if event['check'].get('status') == STATE_CRITICAL:
                crit_count = crit_count + 1
                nagios_output_ext += "%s\t- %s" % (event['client'].get('name'),
                                                   event['check'].get('output'))

            # only WARNING events
            if event['check'].get('status') == STATE_WARNING:
                warn_count = warn_count + 1
                nagios_output_ext += "%s\t- %s" % (event['client'].get('name'),
                                                   event['check'].get('output'))

        # count WARNING checks
        if warn_count:
            if warn_count == 1:
                nagios_output = "WARNING: %d warning event in the Sensu platform.\n" % (
                    warn_count)
            else:
                nagios_output = "WARNING: %d warning events in the Sensu platform.\n" % (
                    warn_count)
            exit_code = STATE_WARNING

        # count CRITICAL checks
        if crit_count:
            if crit_count == 1:
                nagios_output = "CRITICAL: %d critical event in the Sensu platform.\n" % (
                    crit_count)
            else:
                nagios_output = "CRITICAL: %d critical events in the Sensu platform.\n" % (
                    crit_count)
            exit_code = STATE_CRITICAL

        # add all parsed output (warning+critical)
        nagios_output += nagios_output_ext

    # adding additional infos if provided by user
    if info:
        nagios_output += "%s" % (info)

    print(nagios_output)
    sys.exit(exit_code)

#
# GET /events on sensu-api
#


def get_events(args):
    url = "http://%s:%d/events" % (args.hostname, args.port)

    if args.timeout is not None:
        to = args.timeout

    # Build the request and load it
    try:
        if not args.username and not args.password:
            req = urllib2.urlopen(url, timeout=to)
        elif args.username and args.password:
            print("Username/Password not supported ANYMOAR MOUAHAHA.")
            sys.exit(STATE_CRITICAL)
        else:
            print("Error: please provide both username and password.")
            req = None
    except urllib2.HTTPError as e:
        print('CRITICAL: HTTPError = ' + str(e.code))
        sys.exit(STATE_CRITICAL)
    except urllib2.URLError as e:
        print('CRITICAL: URLError = ' + str(e.reason))
        sys.exit(STATE_CRITICAL)
    except httplib.HTTPException as e:
        print('CRITICAL: HTTPException')
        sys.exit(STATE_CRITICAL)

    # Exit if empty requests object
    if not req:
        sys.exit(STATE_UNKNOWN)

    # Handle HTTP codes
    if req.getcode() == 200:
        try:
            res = json.loads(req.read())
        except Exception:
            print("UNKNOWN: Error decoding JSON Object.")
            sys.exit(STATE_UNKNOWN)
        format_json_and_exit(events=res, info=args.info)
    # Error
    elif req.getcode() == 500:
        print("CRITICAL: Sensu API returned an HTTP 500. Is RabbitMQ/sensu-server running?")
        sys.ext(STATE_CRITICAL)
    else:
        print("CRITICAL: Bad response (%d) from Sensu API." % (req.getcode()))
        sys.exit(STATE_CRITICAL)

#
# Main
#
if __name__ == '__main__':
    args = collect_args().parse_args()
    try:
        sys.exit(get_events(args))
    except Exception as e:
        print("CRITICAL: %s" % (e))
        sys.exit(STATE_CRITICAL)
