import os.path
import json
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from .abtest import ABTest, FlowEditSheet, TranslationEditSheet
from collections import defaultdict
import csv
import logging
from pathlib import Path
from abc import ABC, abstractmethod

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def load_google_spreadsheet(spreadsheet_id):
    
    service = build('sheets', 'v4', credentials=get_credentials())

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
    _MASTER_HEADER_OPTIONAL = ["order"]
    _N_COLUMNS = len(_MASTER_HEADER)
    _N_OPTIONAL_COLUMNS = len(_MASTER_HEADER_OPTIONAL)

    _OPERATION_TYPE = 0
    _FLOW_NAME = 1
    _SHEET_NAME = 2
    _STATUS = 3
    _ORDER = 4

    def __init__(self):
        self._sheets = dict()
        self._name = ""
        self._master_content = None

    def get_flow_edit_sheet_groups(self, config={}):
        if self._master_content is None:
            logging.warning("Master sheet " + self._name + "could not be loaded.")
            return []
        if not self._is_valid_master_header(self._master_content[0]):
            logging.warning("Master sheet " + self._name + "has invalid header row.")
            return []
        flow_operation_dict = defaultdict(list)
        for i, row in enumerate(self._master_content[1:]):
            debug_string = "Master sheet " + self._name + " row " + str(i+2) + ": "
            result = self._parse_row(row, debug_string, config)
            if result is not None:
                operation, order = result
                flow_operation_dict[order].append(operation)
        flow_operations = []
        for order, operations in sorted(flow_operation_dict.items()):
            flow_operations.append(operations)
        return flow_operations

    @abstractmethod
    def _get_content_from_sheet_name(self, sheet_name, debug_string):
        pass

    def _is_valid_master_header(self, row):
        if row[:type(self)._N_COLUMNS] == type(self)._MASTER_HEADER:
            for entry,expected in zip(row[type(self)._N_COLUMNS:], type(self)._MASTER_HEADER_OPTIONAL):
                if entry != expected:
                    return False
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
        if len(row) > type(self)._N_COLUMNS:
            try:
                order = row[type(self)._ORDER]
                order = int(order)
            except ValueError:
                logging.warning(debug_string + "invalid order: " + order + ". Assuming 0.")
                order = 0
        else:
            order = 0

        if status != "released":
            logging.info(debug_string + "Skipping because status is not released.")
            return None
        if operation_type == "flow_testing":
            content = self._get_content_from_sheet_name(sheet_name, debug_string)
            return ABTest(sheet_name, content, config.get(sheet_name, None)), order
        elif operation_type == "flow_editing":
            content = self._get_content_from_sheet_name(sheet_name, debug_string)
            return FlowEditSheet(sheet_name, content, config.get(sheet_name, None)), order
        elif operation_type == "translation_editing":
            content = self._get_content_from_sheet_name(sheet_name, debug_string)
            return TranslationEditSheet(sheet_name, content, config.get(sheet_name, None)), order
        else:
            logging.warning(debug_string + "invalid operation_type: " + operation_type)

    def _add_to_master_content(self, content):
        if self._master_content is None:
            self._master_content = content
        else:
            if self._master_content[0] != content[0]:
                logging.warning(f"Warning: In compatible master header rows: {self._master_content[0]} differs from {content[0]}.")
            self._master_content += content[1:]


class GoogleMasterSheetParser(MasterSheetParser):
    MASTER_SHEET_NAME = "==content=="

    def __init__(self, spreadsheet_ids):
        super().__init__()
        for spreadsheet_id in spreadsheet_ids:
            self._add_master_sheet(spreadsheet_id)
        if not self._master_content:
            logging.warning("No master sheet with title " + type(self).MASTER_SHEET_NAME + " found.")
        self._name = self._name[:-1]

    def _add_master_sheet(self, spreadsheet_id):
        self._name += spreadsheet_id + '|'
        result = load_google_spreadsheet(spreadsheet_id)

        for sheet in result.get('valueRanges', []):
            name = sheet.get('range', '').split('!')[0]
            if name.startswith("'") and name.endswith("'"):
                name = name[1:-1]
            content = sheet.get('values', [])
            if name == type(self).MASTER_SHEET_NAME:
                self._add_to_master_content(content)
            elif name in self._sheets:
                logging.warning("Warning: Duplicate sheet name: " + name)
            else:
                self._sheets[name] = content

    def _get_content_from_sheet_name(self, name, debug_string):
        if not name in self._sheets:
            logging.warning(debug_string + name + " does not exist.")
            return None
        return self._sheets[name]


class CSVMasterSheetParser(MasterSheetParser):

    def __init__(self, filenames):
        super().__init__()
        self._path = None
        for filename in filenames:
            self._add_master_sheet(filename)
        self._name = self._name[:-1]

    def _add_master_sheet(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        path = os.path.dirname(filename)
        if not self._path:
            self._path = path
        elif path != self._path:
            logging.error(f"Error: Master sheets {self._name} and {name} must be in the same directory. Skipping {name}.")
            return

        self._name += name + '|'
        content = load_content_from_csv(filename)
        self._add_to_master_content(content)

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


def translationeditsheet_from_csv(filename):
    content = load_content_from_csv(filename)
    name = os.path.splitext(os.path.basename(filename))[0]
    return TranslationEditSheet(name, content)

def get_credentials():
    sa_creds = os.getenv("CREDENTIALS")
    if sa_creds:
        return ServiceAccountCredentials.from_service_account_info(
            json.loads(sa_creds),
            scopes=SCOPES
        )
    
    creds = None
    token_file_name = "token.json"

    if os.path.exists(token_file_name):
        creds = Credentials.from_authorized_user_file(
            token_file_name,
            scopes=SCOPES
        )

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json',
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_file_name, 'w') as token:
            token.write(creds.to_json())

    return creds
