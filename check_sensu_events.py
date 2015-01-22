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
#   Julien Syx <julien@syx.fr>
#   Hugo Rosnet <hugo.rosnet@enovance.com>
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
import re
import argparse
import requests
import logging
from urllib2 import HTTPError

# States
STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2
STATE_UNKNOWN = 3

LVL = {'INFO': logging.INFO,
       'DEBUG': logging.DEBUG,
       'ERROR': logging.ERROR,
       'CRITICAL': logging.CRITICAL}

def setup_log(name=__name__, level='INFO', log=None, debug=False,
              console=True, form='%(asctime)s [%(levelname)s] - %(message)s'):
    """
    Setup logger object for displaying information into console/file
    Currently only used for debugging purpose, but could do more if necessary

    :param name: Name of the logger object to create
    :type name: str

    :param level: Level INFO/DEBUG/ERROR etc
    :type level: str

    :param log: File to which log information
    :type log: str

    :param console: If log information sent to console as well
    :type console: Boolean

    :param form: The format in which the log will be displayed
    :type form: str

    :returns: The object logger
    :rtype: logger object
    """
    if debug is True:
        level = 'DEBUG'
    level = level.upper()
    if level not in LVL:
        logging.warning("Option of log level %s incorrect, using INFO." % level)
        level = 'INFO'
    level = LVL[level]
    formatter = logging.Formatter(form)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if log is not None:
        filehdl = logging.FileHandler(log)
        filehdl.setFormatter(formatter)
        logger.addHandler(filehdl)
    if console is True:
        consolehdl = logging.StreamHandler()
        consolehdl.setFormatter(formatter)
        logger.addHandler(consolehdl)
    return logger

def collect_args():
    """
    Get argument from the command line to fit user needs
    """
    parser = argparse.ArgumentParser(description='Get a list of events from a Sensu API')
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
    parser.add_argument('--info', metavar='info', type=str,
                        default=None,
                        help='Additional informations to output like sensu-dashboard address or whatever')
    parser.add_argument('--debug', action='store_true',
                        default=False,
                        help='Decide level of verbosity (mostly for DEBUG)')
    parser.add_argument('--filter', metavar='filter', type=str,
                        default='.*',
                        help='Decide client name to keep, other will be ignored')
    return parser


#
# Format decoded JSON
#
def format_json_and_exit(events, stashes, info=None, filter=".*", logger=__name__):
    """
    Format events and stashes to have nice output for nagios check

    :param events: Name of the logger object to create
    :type events: list of json object

    :param stashes: List of stashes
    :type stashes: list of json object

    :param info: Additional informations to output, e.g. sensu-dashboard
    :type info: str

    :param filter: Decide client name to keep, other will be ignored
    :type filter: str

    :param logger: The name of logger to use, previously setup
    :type logger: str
    """
    log = logging.getLogger(logger)
    nagios_output = ""
    nagios_output_ext = ""
    exit_code = STATE_UNKNOWN
    crit_count = 0
    warn_count = 0
    unknown_count = 0
    stash_count = 0
    filter_count = 0

    # in case the returned array is empty: OK
    if not events:
        nagios_output = "OK: no ongoing events returned by Sensu API.\n"
        exit_code = STATE_OK

    client_filter = re.compile(filter)
    log.debug("Filter: %s" % filter)
    for event in events:
        log.debug("Event: %s" % event)
        in_stash = False
        filtered = False
        check = event.get('check')
        client = event.get('client')
        status = check.get('status')
        log.debug("Check (%s): %s" % (event, check))
        log.debug("Client (%s): %s" % (event, client))
        log.debug("Status (%s): %s" % (event, status))

        if client_filter.match(client['name']) is None:
            log.debug("Client: %s didn't match pattern [%s]" % (client['name'], filter))
            filter_count += 1
            filtered = True
        else:
            for stash in stashes:
                log.debug("Stash: %s" % stash)
                if '/'.join(['silence', client['name'], check['name']]) in stash['path']:
                    in_stash = True
                    stash_count += 1

        if not in_stash and not filtered:
            # only CRITICAL events
            if status == STATE_CRITICAL and not in_stash:
                crit_count += 1
                nagios_output_ext += "%s - %s: %s\n" % (client['name'],
                                                        check['name'],
                                                        check['output'])

            # only WARNING events
            if status == STATE_WARNING and not in_stash:
                warn_count += 1
                nagios_output_ext += "%s - %s: %s\n" % (client['name'],
                                                        check['name'],
                                                        check['output'])

            # only UNKNOWN events
            if status == STATE_UNKNOWN and not in_stash:
                unknown_count += 1
                nagios_output_ext += "%s - %s: %s\n" % (client['name'],
                                                        check['name'],
                                                        check['output'])

    log.debug("Total WARNING: %s" % warn_count)
    log.debug("Total CRITICAL: %s" % crit_count)
    log.debug("Total UNKNOWN: %s" % unknown_count)
    log.debug("Total STASHES: %s" % stash_count)
    log.debug("Total FILTERED: %s" % filter_count)

    # count WARNING checks
    if warn_count:
        nagios_output = "WARNING: %d warning events in the Sensu platform." % warn_count
        exit_code = STATE_WARNING

    # count CRITICAL checks
    if crit_count:
        nagios_output = "CRITICAL: %d critical events in the Sensu platform." % crit_count
        exit_code = STATE_CRITICAL

    # count UNKNOWN checks
    if unknown_count:
        nagios_output = "UNKNOWN: %d unknown events in the Sensu platform." % unknown_count
        exit_code = STATE_UNKNOWN

    # count STASH checks
    if stash_count or filter_count:
        if stash_count == len(events) or filter_count == len(events):
            nagios_output = "OK: no ongoing events returned by Sensu API."
            exit_code = STATE_OK

    # add all parsed output (warning+critical+unknown)
    nagios_output += " (%d in stash & %d filtered.)\n" % (stash_count, filter_count)
    nagios_output += nagios_output_ext
    # adding additional infos if provided by user
    if info:
        nagios_output += "%s" % info

    print str(nagios_output)
    sys.exit(exit_code)


#
# GET /events on sensu-api
#
def get_events(args, logger=__name__):
    """
    Fetch events and stashes from the Sensu API using specified user's option

    :param args: List of argument given through command line
    :type args: dict

    :param logger: The name of logger to use, previously setup
    :type logger: str
    """
    log = logging.getLogger(logger)
    event_url = "http://%s:%d/events" % (args.hostname, args.port)
    stashes_url = "http://%s:%d/stashes" % (args.hostname, args.port)
    to = 10
    if args.timeout is not None:
        to = args.timeout
    log.debug("Event_url: %s" % event_url)
    log.debug("Stashes_url: %s" % stashes_url)
    log.debug("Timeout: %s" % to)

    # Build the request and load it
    try:
        if not args.username and not args.password:
            log.debug("Username: %s" % args.username)
            log.debug("Password: %s" % args.password)
            req_event = requests.get(event_url, timeout=to)
            req_stashes = requests.get(stashes_url, timeout=to)
        elif args.username and args.password:
            req_event = requests.get(event_url, timeout=to, auth=(args.username, args.password))
            req_stashes = requests.get(stashes_url, timeout=to, auth=(args.username, args.password))
        else:
            print "Error: please provide both username and password"
            req_event = None
            req_stashes = None
    except requests.ConnectionError:
        print "CRITICAL: Unable to connect to %s" % event_url
        sys.exit(STATE_CRITICAL)
    except requests.Timeout:
        print "CRITICAL: Timeout reached when attempting to connect to Sensu API."
        sys.exit(STATE_CRITICAL)
    except HTTPError as e:
        print "UNKNOWN: Sensu API sent an HTTP response that I cannot understand. %s" % e
        sys.exit(STATE_UNKNOWN)

    log.debug("Req_event: %s" % req_event)
    log.debug("Req_stashes: %s" % req_stashes)
    log.debug("Req_event (dict): %s" % req_event.__dict__)
    log.debug("Req_stashes (dict): %s" % req_stashes.__dict__)
    # Exit if empty requests object
    if not req_event:
        sys.exit(STATE_UNKNOWN)

    # Handle HTTP codes
    if req_event.status_code == 200:
        try:
            # python-requests has its own json decoder
            res_event = req_event.json()
            res_stashes = req_stashes.json()
        except Exception, e:
            print "UNKNOWN: Error decoding JSON Object %s" % e
            sys.exit(STATE_UNKNOWN)
        log.debug("Res_event: %s" % res_event)
        log.debug("Res_stashes: %s" % res_stashes)
        format_json_and_exit(events=res_event, stashes=res_stashes, info=args.info, filter=args.filter)
    # Error
    elif req_event.status_code == 500:
        print "CRITICAL: Sensu API returned an HTTP 500. Is RabbitMQ/sensu-server running?"
        sys.exit(STATE_CRITICAL)
    else:
        print "CRITICAL: Bad response (%d) from Sensu API." % req_event.status_code
        sys.exit(STATE_CRITICAL)

#
# Main
#
if __name__ == '__main__':
    args = collect_args().parse_args()
    try:
        setup_log(console=True, debug=args.debug)
        sys.exit(get_events(args))
    except Exception as e:
        print "CRITICAL: %s" % e
        sys.exit(STATE_CRITICAL)
