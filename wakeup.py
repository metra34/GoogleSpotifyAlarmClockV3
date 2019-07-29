#!/usr/bin/env python
# Google Spotify Alarm Clock
# Author: Artem C

from __future__ import print_function

import logging
# used for development. Not needed for normal usage.
import os
import pickle
import random
import re
import time
from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from math import fabs
from subprocess import Popen

import iso8601
import rfc3339
from apscheduler.schedulers.blocking import BlockingScheduler
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pytz import utc

# create log directory
if not os.path.isdir('logs'):
    os.mkdir('logs')

# BEGIN LOG CONFIG
# TODO make it variable
file_log_level = 10
cons_log_level = 20

rootLogger = logging.getLogger()
rootLogger.setLevel(file_log_level)

logFormatter = logging.Formatter("%(asctime)s - [%(module)-10s %(lineno)-4d] - %(levelname)-5.5s - %(message)s")

fileHandler = TimedRotatingFileHandler("logs/alarms.log", when="midnight", interval=1)
fileHandler.setLevel(file_log_level)
fileHandler.setFormatter(logFormatter)
fileHandler.suffix = "%Y%m%d"
fileHandler.extMatch = re.compile(r"^\d{8}$")
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
consoleHandler.setLevel(cons_log_level)
rootLogger.addHandler(consoleHandler)

# reduce levels for some Module loggers
logging.getLogger('apscheduler.schedulers').setLevel(50)
logging.getLogger('googleapiclient.discovery').setLevel(40)
# END LOG CONFIG

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Global variables that can be changed in wakeup.cfg file
parser = SafeConfigParser()
parser.read('setup.cfg')
calendar = parser.get('alarm', 'calendar')  # TODO
q = parser.get('alarm', 'query')
spotify_playlist = None  # TODO
mp3_paths = parser.get('alarm', 'mp3_paths')

service = None
player_process = None
wait_attempts = 0

def auth():
    global service, SCOPES

    logger = logging.getLogger('wakeup')

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    logger.info('authorizing --')
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)


# Main query
def fullTextQuery():
    global service, player_process, wait_attempts, calendar, q, mp3_paths

    logger = logging.getLogger('wakeup')

    if player_process != None and wait_attempts < 100 and player_process.poll() == None:
        wait_attempts = wait_attempts + 1
        logger.debug('song playing -- defferering task, pOpen poll {}, wait_attempts {}'.format(player_process.poll(), wait_attempts))
        return

    if wait_attempts >= 100:
        logger.critical('CRITICAL: exceeded max attempts to wait on the song to finish, terminating program')
        scheduler.shutdown(wait=False)
        exit(1)

    try:
        if not service:
            auth()
    except:
        logger.critical('CRITICAL: to auth google api data, terminating the program')
        scheduler.shutdown(wait=False)
        exit(1)

    logger.debug('Full text query for events on Primary Calendar: \'{}\''.format(calendar))
    logger.debug('Fetching events with query: \'{}\''.format(q))

    startDate = (datetime.utcnow() + timedelta(days=-1)).isoformat() + 'Z'
    endDate = (datetime.utcnow() + timedelta(days=8)).isoformat() + 'Z'

    # pylint: disable=no-member
    events_result = service.events().list(calendarId='primary', timeMin=startDate,
                                          maxResults=20, timeMax=endDate, singleEvents=True,
                                          orderBy='startTime').execute()
    now = utc.localize(datetime.utcnow())
    events = events_result.get('items', [])
    processedCount = 0
    skippedCount = 0
    alarmsCount = 0
    nextIndex = None
    upperLimitInSecs = 15
    if not events:
        logger.debug('No upcoming events found.')

    for event in events:
        eventDate = get_date_object(event['start'].get('dateTime', event['start'].get('date')))
        dateDifference = (eventDate - now)

        # if (abs(dateDifference.total_seconds()) <= upperLimitInSecs):
        if (1):
            logger.info('Waking you up!')
            logger.debug('{} \n {}'.format(eventDate, dateDifference))
            # play the first available song from a random provided directory
            songfile = None
            split_paths = mp3_paths.split(',')
            random_paths = random.sample(split_paths, len(split_paths))
            for mp3_path in random_paths:
                try:
                    mp3_path = mp3_path.strip()
                    songfile = random.choice(os.listdir(mp3_path))
                    if os.path.isfile(mp3_path + songfile):
                        logger.info('Now Playing: \'{}\''.format(songfile))
                        command = 'mpg321' + ' ' + '"' + mp3_path + songfile + '"'
                        logger.debug('Command: {}'.format(command))
                        player_process = Popen(command)  # plays the song
                        exit_code = player_process.wait()
                        logger.info('finished playing {} with exit_code {}'.format(songfile, exit_code))
                        alarmsCount = alarmsCount + 1
                        player_process = None
                        wait_attempts = 0
                        break
                except:
                    logger.warning('bad path: \'{}\''.format(mp3_path))
        else:
            if not nextIndex and dateDifference.total_seconds() > upperLimitInSecs:
                nextIndex = processedCount
            skippedCount = skippedCount + 1
            processedCount = processedCount + 1

        if dateDifference.days > 1:
            logger.info('processed entries {} | alarms {} | skipped {}'.format(processedCount, alarmsCount, skippedCount))

            if alarmsCount >= len(events):
                logger.info('all alarms have been cleared, set more or turn me off.')
            else:
                nextAlarm = events[max(nextIndex, alarmsCount)]
                nextEventDate = get_date_object(nextAlarm['start'].get('dateTime', nextAlarm['start'].get('date')))
                nextEventDate.strftime('%Y-%m-%d at %H:%M %p %z')
                logger.info('Next alarm will go off on << {} >>'.format(nextEventDate))
            break


def get_date_object(date_string):
    return iso8601.parse_date(date_string)


def get_date_string(date_object):
    return rfc3339.rfc3339(date_object)


# Function to be run by Scheduler
def callable_func():
    # logging.getLogger().info('Starting sceduled call --')
    fullTextQuery()


if __name__ == '__main__':
    auth()
    # Run scheduler service
    scheduler = BlockingScheduler()
    scheduler.configure(timezone='UTC')
    scheduler.add_job(callable_func, 'interval', seconds=10, max_instances=2)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        rootLogger.info('Shutting Down\n---')
        scheduler.shutdown(wait=False)
        exit(0)
