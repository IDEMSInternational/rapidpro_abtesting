import json

from rapidpro_abtest_creator import RapidProABTestCreator
from sheets import CSVMasterSheetParser, GoogleMasterSheetParser
import logging
logging.basicConfig(filename='main.log', level=logging.WARNING, filemode='w')

SPREADSHEET_ID = '1FLDxTPNvnWPLgt1lUuCLt7Nsx9UtZoBkYihtvsGnntI'  # Sample
MASTER_CSV = "testdata/master_sheet.csv"
JSON_FILENAME = "testdata/Linear_OneNodePerAction.json"
OUTPUT_FILENAME = "out.json"

def main():
    # parser = GoogleMasterSheetParser(SPREADSHEET_ID)
    parser = CSVMasterSheetParser(MASTER_CSV)
    flow_edit_sheets = parser.get_flow_edit_sheets()
    rpx = RapidProABTestCreator(JSON_FILENAME)
    rpx.apply_abtests(flow_edit_sheets)
    rpx.export_to_json(OUTPUT_FILENAME)


if __name__ == '__main__':
    main()
