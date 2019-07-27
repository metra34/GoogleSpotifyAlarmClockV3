#!/usr/bin/env python
# Google Spotify Alarm Clock
# Author: Artem C

from __future__ import print_function
import pickle
import os
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import random
from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
import time
import rfc3339
import iso8601

from apscheduler.schedulers.blocking import BlockingScheduler

# used for development. Not needed for normal usage.
import logging
logging.basicConfig(filename='wakeup.log', filemode='w')
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Global variables that can be changed in wakeup.cfg file
parser = SafeConfigParser()
parser.read('setup.cfg')
calendar = parser.get('alarm', 'calendar')  # TODO
q = parser.get('alarm', 'query')
spotify_playlist = None  # TODO
mp3_path = parser.get('alarm', 'mp3_path')

service = None
# limit the query range to 8 days
# date = (datetime.now() + timedelta(days=-1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
# endDate = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def auth():
    global service
    global SCOPES

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
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

    print('Full text query for events on Primary Calendar: \'%s\'' % (calendar))
    print('Looking for query: \'%s\'' % (q))

    print('Getting the upcoming alarms')

    if not service:
        auth()

    startDate = (datetime.utcnow() + timedelta(days=-1)).isoformat() + 'Z'
    endDate = (datetime.utcnow() + timedelta(days=8)).isoformat() + 'Z'
    # TODO implement method for getting all calendars, then filtering ID by name
    # pylint: disable=no-member
    events_result = service.events().list(calendarId='primary', timeMin=startDate,
                                          maxResults=100, timeMax=endDate, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, ' ', event['summary'])
        currDate = get_date_object(start)
        now = datetime.now()
        print(now, ' works? ', currDate)

    # feed = calendar_service.CalendarQuery(query)
    # for i, an_event in enumerate(feed.entry):
    #     for a_when in an_event.when:
    #         print " "
    #         print an_event.title.text, "Scheduled:", i, "For:", time.strftime('%d-%m-%Y %H:%M',
    #   time.localtime(tf_from_timestamp(a_when.start_time))), "Current Time:", time.strftime('%d-%m-%Y %H:%M')
    #         if time.strftime('%d-%m-%Y %H:%M', time.localtime(tf_from_timestamp(a_when.start_time))) == time.strftime('%d-%m-%Y %H:%M'):
    #             print "Waking you up!"
    #             print "---"
    #             # choosing by random an .mp3 file from direcotry
    #             songfile = random.choice(os.listdir(mp3_path))
    #             print "Now Playing:", songfile
    #             #  plays the MP3 in it's entierty. As long as the file is longer
    #             #  than a minute it will only be played once:
    #             command = "mpg321" + " " + mp3_path + "'"+songfile+"'" + " -g 100"
    #             print command
    #             os.system(command)  # plays the song
    #         else:
    #             print "Wait for it..."  # the event's start time is not the system's current time

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
    scheduler.add_job(callable_func, 'interval', seconds=5)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        exit(0)
