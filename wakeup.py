#!/usr/bin/env python
# Google Spotify Alarm Clock
# Author: Artem C

from __future__ import print_function
import pickle
import os
import subprocess
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import random
from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
from pytz import utc
import time
import rfc3339
import iso8601
from math import fabs

from apscheduler.schedulers.blocking import BlockingScheduler

# used for development. Not needed for normal usage.
import logging
logging.basicConfig(filename='alarm.log', filemode='w')
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Global variables that can be changed in wakeup.cfg file
parser = SafeConfigParser()
parser.read('setup.cfg')
calendar = parser.get('alarm', 'calendar')  # TODO
q = parser.get('alarm', 'query')
spotify_playlist = None  # TODO
mp3_path = parser.get('alarm', 'mp3_path')

service = None
events_result = None

def auth():
    global service
    global SCOPES

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    print('authorizing...')
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
    service = build('calendar', 'v3', credentials=creds)


# Main query
def FullTextQuery():
    global service
    global calendar
    global q
    global mp3_path
    global events_result

    try:
        if not service:
            auth()
    except:
        scheduler.shutdown()
        exit(1)

    print('Full text query for events on Primary Calendar: \'%s\'' % (calendar))
    print('Fetching events with query: \'%s\'' % (q))

    startDate = (datetime.utcnow() + timedelta(days=-1)).isoformat() + 'Z'
    endDate = (datetime.utcnow() + timedelta(days=8)).isoformat() + 'Z'

    # pylint: disable=no-member
    events_result = service.events().list(calendarId='primary', timeMin=startDate,
                                          maxResults=20, timeMax=endDate, singleEvents=True,
                                          orderBy='startTime').execute()
    now = utc.localize(datetime.utcnow())
    events = events_result.get('items', [])

    processedCount = 0
    if not events:
        print('No upcoming events found.')

    for event in events:
        eventDate = get_date_object(event['start'].get('dateTime', event['start'].get('date')))
        difference = (eventDate - now)
        print(difference, '  ', difference < timedelta(seconds=15))

        if (abs(difference.total_seconds()) < 15):
            print ("Waking you up!")
            print ("---")
            # play the first available song from a random provided directory
            for mp3_dir in random.shuffle(mp3_path.split(',')):
                songfile = random.choice(os.listdir(mp3_dir))
                if os.path.isfile(songfile):
                    break
            print ("Now Playing:", songfile)
            command = "mpg321" + " " + mp3_path + "'"+songfile+"'" + " -g 100"
            print (command)
            os.system(command)  # plays the song
        else:
            print ("Wait for it...\n")
        processedCount = processedCount + 1

        if (difference.days > 1):
            print('processed ', processedCount, ' entries.')
            exit(0)


def get_date_object(date_string):
    return iso8601.parse_date(date_string)


def get_date_string(date_object):
    return rfc3339.rfc3339(date_object)


# Function to be run by Scheduler
def callable_func():
    os.system("clear")
    print("----------------------------")
    FullTextQuery()
    print("----------------------------")


if __name__ == '__main__':
    auth()
    # Run scheduler service
    scheduler = BlockingScheduler()
    scheduler.configure(timezone='UTC')
    scheduler.add_job(callable_func, 'interval', seconds=10)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        exit(0)
