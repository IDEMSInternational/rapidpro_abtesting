import json
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from abtest import ABTest, FlowEditSheet
import csv
import re
import logging
from pathlib import Path
from abc import ABC, abstractmethod

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


def load_content_from_csv(filename):
    with open(filename, newline='') as f:
        reader = csv.reader(f)
        return list(reader)


class MasterSheetParser(ABC):
    _MASTER_HEADER = ["flow_type", "flow_name", "sheet_name", "status"]
    _N_COLUMNS = len(_MASTER_HEADER)

    _OPERATION_TYPE = 0
    _FLOW_NAME = 1
    _SHEET_NAME = 2
    _STATUS = 3

    # Subclasses should initialize the following properties:
    # self._name
    # self._master_content

    def get_flow_edit_sheets(self, config={}):
        if self._master_content is None:
            logging.warning("Master sheet " + self._name + "could not be loaded.")
            return []
        if not self._is_valid_master_header(self._master_content[0]):
            logging.warning("Master sheet " + self._name + "has invalid header row.")
            return []
        flow_operations = []
        for i, row in enumerate(self._master_content[1:]):
            debug_string = "Master sheet " + self._name + " row " + str(i+2) + ": "
            result = self._parse_row(row, debug_string, config)
            if result is not None:
                flow_operations.append(result)
        return flow_operations

    @abstractmethod
    def _get_content_from_sheet_name(self, sheet_name, debug_string):
        pass

    def _is_valid_master_header(self, row):
        if row[:type(self)._N_COLUMNS] == type(self)._MASTER_HEADER:
            return True
        return False

    def _parse_row(self, row, debug_string, config={}):
        if len(row) < type(self)._N_COLUMNS:
            logging.warning(debug_string + "Too few entries in row.")
            return None

        sheet_name = row[type(self)._SHEET_NAME]
        if not sheet_name:
            sheet_name = row[type(self)._FLOW_NAME]
        operation_type = row[type(self)._OPERATION_TYPE]
        status = row[type(self)._STATUS]

        if status != "released":
            logging.info(debug_string + "Skipping because status is not released.")
            return None
        if operation_type == "flow_testing":
            content = self._get_content_from_sheet_name(sheet_name, debug_string)
            return ABTest(sheet_name, content, config.get(sheet_name, None))
        elif operation_type == "flow_editing":
            content = self._get_content_from_sheet_name(sheet_name, debug_string)
            return FlowEditSheet(sheet_name, content, config.get(sheet_name, None))
        else:
            logging.warning(debug_string + "invalid operation_type: " + operation_type)


class GoogleMasterSheetParser(MasterSheetParser):
    MASTER_SHEET_NAME = "==content=="

    def __init__(self, spreadsheet_id):
        result = load_google_spreadsheet(spreadsheet_id)
        self._name = spreadsheet_id

        self._sheets = dict()
        for sheet in result.get('valueRanges', []):
            name = sheet.get('range', '').split('!')[0]
            if name.startswith("'") and name.endswith("'"):
                name = name[1:-1]
            content = sheet.get('values', [])
            self._sheets[name] = content

        if not type(self).MASTER_SHEET_NAME in self._sheets:
            logging.warning("No master sheet with title " + type(self).MASTER_SHEET_NAME + " found.")
        else:
            self._master_content = self._sheets[type(self).MASTER_SHEET_NAME]

    def _get_content_from_sheet_name(self, name, debug_string):
        if not name in self._sheets:
            logging.warning(debug_string + name + " does not exist.")
            return None
        return self._sheets[name]


class CSVMasterSheetParser(MasterSheetParser):

    def __init__(self, filename):
        self._path = os.path.dirname(filename)
        self._name = os.path.splitext(os.path.basename(filename))[0]
        self._master_content = load_content_from_csv(filename)

    def _get_content_from_sheet_name(self, name, debug_string):
        filename = os.path.join(self._path, name + ".csv")
        if not Path(filename).is_file():
            logging.warning(debug_string + filename + " does not exist.")
            return None
        return load_content_from_csv(filename)


# Helper functions for tests cases
def abtest_from_csv(filename):
    content = load_content_from_csv(filename)
    name = os.path.splitext(os.path.basename(filename))[0]
    return ABTest(name, content)


def floweditsheet_from_csv(filename):
    content = load_content_from_csv(filename)
    name = os.path.splitext(os.path.basename(filename))[0]
    return FlowEditSheet(name, content)
