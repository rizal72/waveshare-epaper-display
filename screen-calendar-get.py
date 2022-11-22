import datetime
import pickle
import os.path
import os
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from calendar_providers.base_provider import CalendarEvent
from calendar_providers.caldav import CalDav
from calendar_providers.ics import ICS
from calendar_providers.outlook import OutlookCalendar
from utility import is_stale, update_svg, configure_logging, get_formatted_date


configure_logging()

# note: increasing this will require updates to the SVG template to accommodate more events
max_event_results = 10

google_calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
outlook_calendar_id = os.getenv("OUTLOOK_CALENDAR_ID", None)

caldav_calendar_url = os.getenv('CALDAV_CALENDAR_URL', None)
caldav_username = os.getenv("CALDAV_USERNAME", None)
caldav_password = os.getenv("CALDAV_PASSWORD", None)
caldav_calendar_id = os.getenv("CALDAV_CALENDAR_ID", None)

ics_calendar_url = os.getenv("ICS_CALENDAR_URL", None)

ttl = float(os.getenv("CALENDAR_TTL", 1 * 60 * 60))


def get_google_credentials():

    google_token_pickle = 'token.pickle'
    google_credentials_json = 'credentials.json'
    google_api_scopes = ['https://www.googleapis.com/auth/calendar.readonly']

    credentials = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(google_token_pickle):
        with open(google_token_pickle, 'rb') as token:
            credentials = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                google_credentials_json, google_api_scopes)
            credentials = flow.run_local_server()
        # Save the credentials for the next run
        with open(google_token_pickle, 'wb') as token:
            pickle.dump(credentials, token)

    return credentials


def get_google_events(max_event_results):

    google_calendar_pickle = 'cache_calendar.pickle'

    service = build('calendar', 'v3', credentials=get_google_credentials(), cache_discovery=False)

    events_result = None

    if is_stale(os.getcwd() + "/" + google_calendar_pickle, ttl):
        logging.debug("Pickle is stale, calling the Calendar API")

        today_start_time = datetime.datetime.utcnow()
        if os.getenv("CALENDAR_INCLUDE_PAST_EVENTS_FOR_TODAY", "0") == "1":
            today_start_time = datetime.datetime.combine(datetime.datetime.utcnow(), datetime.datetime.min.time())
        # Call the Calendar API
        events_result = service.events().list(
            calendarId=google_calendar_id,
            timeMin=today_start_time.isoformat() + 'Z',
            maxResults=max_event_results,
            singleEvents=True,
            orderBy='startTime').execute()

        with open(google_calendar_pickle, 'wb') as cal:
            pickle.dump(events_result, cal)

    else:
        logging.info("Found in cache")
        with open(google_calendar_pickle, 'rb') as cal:
            events_result = pickle.load(cal)

    events = events_result.get('items', [])

    if not events:
        logging.info("No upcoming events found.")

    return events


def get_output_dict_from_google_events(events, event_slot_count):
    formatted_events = {}
    event_count = len(events)
    for event_i in range(event_slot_count):
        event_label_id = str(event_i + 1)
        if (event_i <= event_count - 1):
            formatted_events['CAL_DATETIME_' + event_label_id] = \
                get_google_datetime_formatted(events[event_i]['start'], events[event_i]['end'])
            formatted_events['CAL_DESC_' + event_label_id] = events[event_i]['summary']
        else:
            formatted_events['CAL_DATETIME_' + event_label_id] = ""
            formatted_events['CAL_DESC_' + event_label_id] = ""
    return formatted_events


def get_google_datetime_formatted(event_start, event_end):
    if event_start.get('dateTime'):
        start_date = datetime.datetime.strptime(event_start.get('dateTime'), "%Y-%m-%dT%H:%M:%S%z")
        end_date = datetime.datetime.strptime(event_end.get('dateTime'), "%Y-%m-%dT%H:%M:%S%z")
        if start_date.date() == end_date.date():
            start_formatted = get_formatted_date(start_date)
            end_formatted = end_date.strftime("%-I:%M %p")
        else:
            start_formatted = get_formatted_date(start_date)
            end_formatted = get_formatted_date(end_date)
        day = "{} - {}".format(start_formatted, end_formatted)
    else:
        start = datetime.datetime.strptime(event_start.get('date'), "%Y-%m-%d")
        end = datetime.datetime.strptime(event_end.get('date'), "%Y-%m-%d")
        # Google Calendar marks the 'end' of all-day-events as
        # the day _after_ the last day. eg, Today's all day event ends tomorrow!
        # So subtract a day
        end = end - datetime.timedelta(days=1)
        start_day = get_formatted_date(start, include_time=False)
        end_day = get_formatted_date(end, include_time=False)
        if start == end:
            day = start_day
        else:
            day = "{} - {}".format(start_day, end_day)
    return day


def get_formatted_calendar_events(fetched_events: list[CalendarEvent]) -> dict:
    formatted_events = {}

    for index, event in enumerate(fetched_events):
        event_label_id = str(index + 1)
        if index <= max_event_results - 1:
            formatted_events['CAL_DATETIME_' + event_label_id] = get_datetime_formatted(event.start, event.end, event.all_day_event)
            formatted_events['CAL_DESC_' + event_label_id] = event.summary
        else:
            formatted_events['CAL_DATETIME_' + event_label_id] = ""
            formatted_events['CAL_DESC_' + event_label_id] = ""

    return formatted_events


def get_datetime_formatted(event_start, event_end, is_all_day_event):

    if is_all_day_event or type(event_start) == datetime.date:
        start = datetime.datetime.combine(event_start, datetime.time.min)
        end = datetime.datetime.combine(event_end, datetime.time.min)

        start_day = get_formatted_date(start, include_time=False)
        end_day = get_formatted_date(end, include_time=False)
        if start == end:
            day = start_day
        else:
            day = "{} - {}".format(start_day, end_day)
    elif type(event_start) == datetime.datetime:
        start_date = event_start
        end_date = event_end
        if start_date.date() == end_date.date():
            start_formatted = get_formatted_date(start_date)
            end_formatted = end_date.strftime("%-I:%M %p")
        else:
            start_formatted = get_formatted_date(start_date)
            end_formatted = get_formatted_date(end_date)
        day = "{} - {}".format(start_formatted, end_formatted)
    else:
        day = ''
    return day


def main():

    output_svg_filename = 'screen-output-weather.svg'

    today_start_time = datetime.datetime.utcnow()
    if os.getenv("CALENDAR_INCLUDE_PAST_EVENTS_FOR_TODAY", "0") == "1":
        today_start_time = datetime.datetime.combine(datetime.datetime.utcnow(), datetime.datetime.min.time())
    oneyearlater_iso = (datetime.datetime.now().astimezone()
                        + datetime.timedelta(days=365)).astimezone()

    if outlook_calendar_id:
        logging.info("Fetching Outlook Calendar Events")
        provider = OutlookCalendar(outlook_calendar_id, max_event_results, today_start_time, oneyearlater_iso)
        calendar_events = provider.get_calendar_events()
        output_dict = get_formatted_calendar_events(calendar_events)
    elif caldav_calendar_url:
        logging.info("Fetching Caldav Calendar Events")
        provider = CalDav(caldav_calendar_url, caldav_calendar_id, max_event_results,
                          today_start_time, oneyearlater_iso, caldav_username, caldav_password)
        calendar_events = provider.get_calendar_events()
        output_dict = get_formatted_calendar_events(calendar_events)
    elif ics_calendar_url:
        logging.info("Fetching ics Calendar Events")
        provider = ICS(ics_calendar_url, max_event_results, today_start_time, oneyearlater_iso)
        calendar_events = provider.get_calendar_events()
        output_dict = get_formatted_calendar_events(calendar_events)
    else:
        logging.info("Fetching Google Calendar Events")
        google_events = get_google_events(max_event_results)
        output_dict = get_output_dict_from_google_events(google_events, max_event_results)

    logging.info("main() - {}".format(output_dict))

    logging.info("Updating SVG")
    update_svg(output_svg_filename, output_svg_filename, output_dict)


if __name__ == "__main__":
    main()
