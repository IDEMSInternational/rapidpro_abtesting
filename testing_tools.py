import json
import uuid
import copy
from collections import defaultdict


# TODO: Implement some kind of check that uuids are unique whereever
# they are supposed to be unique?

def traverse_flow(flow, group_names):
    '''
    Traverse a given flow, assuming the user's group memberships
    as specified in group_names, which determine which path through
    the flow is taken.

    Returns:
        A list of strings, which are the outputs of send_msg actions
        that are encounters while traversing through the flow.

    Only supports send_msg actions and group switches
    TODO: Incorporate more node types, user input, etc.
    TODO: Also check Group UUIDs, not just names?
    '''

    outputs = []
    current_node = flow["nodes"][0]
    while current_node is not None:
        for action in current_node["actions"]:
            if action["type"] == "send_msg":
                outputs.append(action["text"])
        destination_uuid = current_node["exits"][0]["destination_uuid"]
        if "router" in current_node:
            router = current_node["router"]
            if router["type"] == "switch":  # other type is "random"
                category_uuid = router["default_category_uuid"]  # The "Other" option (default)
                for case in router["cases"]:
                    if case["type"] == "has_group" and case["arguments"][1] in group_names:
                        category_uuid = case["category_uuid"]
                        break
                exit_uuid = None
                for category in router["categories"]:
                    if category["uuid"] == category_uuid:
                        exit_uuid = category["exit_uuid"]
                if exit_uuid is None:
                    raise ValueError("No valid exit_uuid in router of node with uuid " + current_node["uuid"])
                destination_uuid = -1  # None is a valid value indicating the end of a flow
                for exit in current_node["exits"]:
                    if exit["uuid"] == exit_uuid:
                        destination_uuid = exit["destination_uuid"]
                        break
                if destination_uuid == -1:
                    raise ValueError("No valid destination_uuid in router of node with uuid " + current_node["uuid"])
        current_node = None
        for node in flow["nodes"]:
            if node["uuid"] == destination_uuid:
                current_node = node
                break
    return outputs
