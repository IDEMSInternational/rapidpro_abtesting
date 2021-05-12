import json

from abtest import ABTest
from rapidpro_abtest_creator import RapidProABTestCreator
from sheets import abtests_from_google_spreadsheet, abtests_from_csvs
import logging
logging.basicConfig(filename='main.log', level=logging.WARNING, filemode='w')

SPREADSHEET_ID = '1FLDxTPNvnWPLgt1lUuCLt7Nsx9UtZoBkYihtvsGnntI'  # Sample
CSVS = ["testdata/Test1_Personalization.csv", "testdata/Test2_Some1337.csv"]
JSON_FILENAME = "testdata/Linear_OneNodePerAction.json"
OUTPUT_FILENAME = "out.json"

SPREADSHEET_ID = '1t-hJkIoI9PaMKLefihQzyBw1GzTIW6RUawStQDielrk'  # Parenting
JSON_FILENAME = "data/plh-international-flavour.json"
OUTPUT_FILENAME = "out.json"

def main():
    abtests = abtests_from_google_spreadsheet(SPREADSHEET_ID)
    # abtests = abtests_from_csvs(CSVS)
    rpx = RapidProABTestCreator(JSON_FILENAME)
    rpx.apply_abtests(abtests)
    rpx.export_to_json(OUTPUT_FILENAME)


if __name__ == '__main__':
    main()
