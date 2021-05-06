import json
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from abtest import ABTest
import csv

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def load_google_spreadsheet(spreadsheet_id):
    """Load spreadsheet from Google Drive.

    Args:
        spreadsheet_id: You can extract it from the spreadsheed URL, like this
        https://docs.google.com/spreadsheets/d/[spreadsheet_id]/edit

    Returns:
        Object as specified here:
        https://developers.google.com/resources/api-libraries/documentation/sheets/v4/python/latest/sheets_v4.spreadsheets.values.html#batchGet
    """

    # Authentication code nabbed from
    # https://developers.google.com/sheets/api/quickstart/python
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # TODO: Provide instructions how to obtain this file and get access
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', '')
    titles = []
    for sheet in sheets:
        title = sheet.get("properties", {}).get("title", "Sheet1")
        titles.append(title)

    result = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id, ranges=titles).execute()
    return result


def abtests_from_google_spreadsheet(spreadsheet_id):
    result = load_google_spreadsheet(spreadsheet_id)

    abtests = []
    for sheet in result.get('valueRanges', []):
        name = sheet.get('range', '').split('!')[0]
        content = sheet.get('values', [])
        abtest = ABTest(name, content)
        abtests.append(abtest)
    return abtests


def abtest_from_csv(filename):
    with open(filename, newline='') as f:
        reader = csv.reader(f)
        content = list(reader)
    name = os.path.splitext(os.path.basename(filename))[0]
    return ABTest(name, content)


def abtests_from_csvs(filenames):
    return [abtest_from_csv(filename) for filename in filenames]


if __name__ == '__main__':
    main()