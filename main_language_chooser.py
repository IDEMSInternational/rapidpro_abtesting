from language_chooser import replace_flow_with_language_chooser
from sheets import load_content_from_csv
import json
import logging

logging.basicConfig(filename='main.log', level=logging.WARNING, filemode='w')


INPUT_CSV = "testdata/language_choose_malaysia.csv"
FLOW_NAME = "Minimal Flow"
INPUT_JSON = "testdata/minimal.json"
OUTPUT_JSON = "out.json"


def main():
    rpx = json.load(open(INPUT_JSON, 'r'))
    flow = None
    for flow_ in rpx["flows"]:
        if flow_["name"] == FLOW_NAME:
            flow = flow_
    if flow is None:
        logging.error(f"No flow of name {FLOW_NAME} exists.")
        exit(0)

    data = load_content_from_csv(INPUT_CSV)
    replace_flow_with_language_chooser(data, flow)
    json.dump(rpx, open(OUTPUT_JSON, 'w'), indent=2)


if __name__ == '__main__':
    main()
