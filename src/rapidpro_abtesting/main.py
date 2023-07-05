import argparse
import json
import logging

from .rapidpro_abtest_creator import RapidProABTestCreator
from .sheets import CSVMasterSheetParser, GoogleMasterSheetParser


def main():
    parser = argparse.ArgumentParser(
        description="Apply FlowEdits/ABTests to a RapidPro JSON file."
    )
    parser.add_argument(
        "input",
        help="RapidPro JSON file defining the input RapidPro flows.",
    )
    parser.add_argument(
        "output",
        help="RapidPro JSON file to write the output to.",
    )
    parser.add_argument(
        "master_sheets",
        nargs="+",
        help=(
            "Master sheet(s) referencing FlowEdits/ABTests. "
            "Either CSV file(s) or a Google Sheet ID(s)."
        ),
    )
    parser.add_argument(
        "--format",
        required=True,
        choices=["csv", "google_sheets"],
        help="Format of the master sheet.",
    )
    parser.add_argument(
        "--logfile",
        help="File to log warnings and errors to.",
    )
    parser.add_argument(
        "--config",
        help="JSON config file.",
    )
    args = parser.parse_args()
    apply_abtests(
        args.input,
        args.output,
        args.master_sheets,
        args.format,
        logfile=args.logfile,
        config_fp=args.config,
    )


def apply_abtests(
    input_flow,
    output_flow,
    main_sheets,
    sheet_format,
    logfile=None,
    config_fp=None,
):
    if logfile:
        logging.basicConfig(
            filename=logfile,
            level=logging.WARNING,
            filemode="w",
        )

    config = {}
    if config_fp:
        with open(config_fp, "r") as config_file:
            config = json.load(config_file)

    if format == "csv":
        sheet_parser = CSVMasterSheetParser(main_sheets)
    else:
        sheet_parser = GoogleMasterSheetParser(main_sheets)

    flow_edit_sheet_groups = sheet_parser.get_flow_edit_sheet_groups(config)
    rpx = RapidProABTestCreator(input_flow)
    for flow_edit_sheets in flow_edit_sheet_groups:
        rpx.apply_abtests(flow_edit_sheets)
    rpx.export_to_json(output_flow)


if __name__ == "__main__":
    main()
