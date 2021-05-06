import json

from abtest import ABTest
from rapidpro_abtest_creator import RapidProABTestCreator
from sheets import abtests_from_google_spreadsheet, abtests_from_csvs
import logging
logging.basicConfig(filename='main.log', level=logging.WARNING, filemode='w')

CSVS = ["testdata/Test1_Personalization.csv", "testdata/Test2_Some1337.csv"]
JSON_FILENAME = "testdata/Linear_OneNodePerAction.json"
OUTPUT_FILENAME = "out.json"

def main():
    # abtests = abtests_from_google_spreadsheet(SPREADSHEET_ID)
    abtests = abtests_from_csvs(CSVS)
    rpx = RapidProABTestCreator(JSON_FILENAME)
    rpx.apply_abtests(abtests)
    rpx.export_to_json(OUTPUT_FILENAME)


if __name__ == '__main__':
    main()
