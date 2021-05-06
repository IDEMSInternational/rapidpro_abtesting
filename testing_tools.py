import json
import uuid
import copy
from collections import defaultdict
import node_tools as nt


# TODO: Implement some kind of check that uuids are unique whereever
# they are supposed to be unique?

def find_destination_uuid(current_node, group_names):
    '''
    For a given node, find the next node that is visited and return its uuid.

    The groups the user is in may affect the outcome.

    Args:
        current_node: 
        group_names (`list` of `str`): groups the user is in

    Returns:
        uuid of the node visited after this node.
        Maybe be None if it is the last node.
    '''

    destination_uuid = current_node["exits"][0]["destination_uuid"]
    if "router" in current_node:
        router = current_node["router"]
        if router["type"] == "switch":  # other type is "random"
            # TODO: Check "operand" to ensure it is group: 
            # "operand": "@contact.groups"
            # and case type is "has_group"
            category_uuid = router["default_category_uuid"]  # The "Other" option (default)
            for case in router["cases"]:
                # TODO: Also check Group UUIDs, not just names?
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
    return destination_uuid


# List of actions: https://app.rapidpro.io/mr/docs/flows.html#actions
action_value_fields = {
    "add_contact_groups" : (lambda x: x["groups"][0]["name"]),
    "add_contact_urn" : (lambda x: x["path"]),
    "add_input_labels" : (lambda x: x["labels"][0]["name"]),
    "call_classifier" : (lambda x: x["classified"]["name"]),
    "call_resthook" : (lambda x: x["resthook"]),
    "call_webhook" : (lambda x: x["url"]),
    "enter_flow" : (lambda x: x["flow"]["name"]),
    "open_ticket" : (lambda x: x["subject"]),
    "play_audio" : (lambda x: x["audio_url"]),
    "remove_contact_groups" : (lambda x: x["groups"][0]["name"]),
    "say_msg" : (lambda x: x["text"]),
    "send_broadcast" : (lambda x: x["text"]),
    "send_email" : (lambda x: x["subject"]),
    "send_msg" : (lambda x: x["text"]),
    "set_contact_channel" : (lambda x: x["channel"]["name"]),
    "set_contact_field" : (lambda x: x["field"]["name"]),
    "set_contact_language" : (lambda x: x["language"]),
    "set_contact_name" : (lambda x: x["name"]),
    "set_contact_status" : (lambda x: x["status"]),
    "set_contact_timezone" : (lambda x: x["timezone"]),
    "set_run_result" : (lambda x: x["name"]),
    "start_session" : (lambda x: x["flow"]["name"]),
    "transfer_airtime" : (lambda x: "Amount"),
}

def traverse_flow(flow, group_names):
    '''
    Traverse a given flow, assuming the user's group memberships
    as specified in group_names, which determine which path through
    the flow is taken.

    Returns:
        A list of strings, which are the outputs of send_msg actions
        that are encounters while traversing through the flow.

    Only supports send_msg actions and group switches
    TODO: Incorporate more node types, user input, "enter new flow", etc.
    TODO: Abort after too many steps (there may be cycles).
    '''

    outputs = []
    current_node = flow["nodes"][0]
    while current_node is not None:
        for action in current_node["actions"]:
            action_type = action["type"]
            # TODO: Try/catch in case of unrecognized action/missing field?
            action_value = action_value_fields[action_type](action)
            outputs.append((action_type, action_value))
        destination_uuid = find_destination_uuid(current_node, group_names)
        current_node = nt.find_node_by_uuid(flow, destination_uuid)
    return outputs


def find_final_destination(flow, node, group_names):
    '''Starting at node in flow, traverse the flow until we reach a
    destination that is not contained inside the flow.

    Returns:
        uuid of the destination outside the flow
    '''

    while node is not None:
        destination_uuid = find_destination_uuid(node, group_names)
        node = nt.find_node_by_uuid(flow, destination_uuid)
    return destination_uuid

