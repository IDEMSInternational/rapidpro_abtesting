from .language_chooser import replace_flow_with_language_chooser
from .sheets import load_content_from_csv
import json
import logging
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Apply FlowEdits/ABTests to a RapidPro JSON file."
    )
    parser.add_argument(
        "input", help="RapidPro JSON file defining the input RapidPro flows."
    )
    parser.add_argument(
        "flow_name", help="Name of the flow to be replaced with a language chooser."
    )
    parser.add_argument("output", help="RapidPro JSON file to write the output to.")
    parser.add_argument(
        "sheet",
        help="Sheet defining the language chooser options. Either a csv file or a Google Sheet ID.",
    )
    parser.add_argument(
        "--format",
        required=True,
        choices=["csv", "google_sheets"],
        help="Format of the sheet.",
    )
    parser.add_argument("--logfile", help="File to log warnings and errors to.")
    args = parser.parse_args()

    if args.logfile:
        logging.basicConfig(filename=args.logfile, level=logging.WARNING, filemode="w")
    if args.format == "csv":
        data = load_content_from_csv(args.sheet)
    else:
        logging.error(f"Google Sheets currently not supported.")
        exit(0)

    rpx = json.load(open(args.input, "r"))
    flow = None
    for flow_ in rpx["flows"]:
        if flow_["name"] == args.flow_name:
            flow = flow_
    if flow is None:
        logging.error(f"No flow of name {args.flow_name} exists.")
        exit(0)

    replace_flow_with_language_chooser(data, flow)
    json.dump(rpx, open(args.output, "w"), indent=2)


if __name__ == "__main__":
    main()
