import json
import copy
import logging

from uuid_tools import generate_random_uuid
from templates import assign_to_random_group_template, assign_to_fixed_group_template


def get_assign_to_group_gadget(groupA_name, groupA_uuid, groupB_name, groupB_uuid, destination_uuid):
    '''
    Create a gadget that checks whether the contact is in a group
    from a group pair (which is specified in test_op), and if not,
    randomly add the contact to one group from the pair.

    Returns:
        list of nodes: Nodes of the gadget.
            The first node is entry point to the gadget.
            All exit points are rerouted to the specified destination UUID.
        node layout dict: mapping node uuid to layout information.

    '''
    template = assign_to_random_group_template \
        .replace("EntryNode_UUID", generate_random_uuid()) \
        .replace("CaseA_UUID", generate_random_uuid()) \
        .replace("CaseB_UUID", generate_random_uuid()) \
        .replace("GroupA_UUID", groupA_uuid) \
        .replace("GroupB_UUID", groupB_uuid) \
        .replace("GroupA_Category_UUID", generate_random_uuid()) \
        .replace("GroupB_Category_UUID", generate_random_uuid()) \
        .replace("Other_Category_UUID", generate_random_uuid()) \
        .replace("ExitA_UUID", generate_random_uuid()) \
        .replace("ExitB_UUID", generate_random_uuid()) \
        .replace("ExitOther_UUID", generate_random_uuid()) \
        .replace("Destination_UUID", destination_uuid) \
        .replace("PickRandomGroupNode_UUID", generate_random_uuid()) \
        .replace("RandomChoiceGroupA_Exit", generate_random_uuid()) \
        .replace("RandomChoiceGroupB_Exit", generate_random_uuid()) \
        .replace("AssignToGroupANode_UUID", generate_random_uuid()) \
        .replace("AssignToGroupBNode_UUID", generate_random_uuid()) \
        .replace("GroupA_name", groupA_name) \
        .replace("GroupB_name", groupB_name)
    n_one_time_uuids = template.count("OneTimeUse_UUID")
    for _ in range(n_one_time_uuids):
        # Each time, only replace first instance.
        template = template.replace("OneTimeUse_UUID", generate_random_uuid(), 1)
    data = json.loads(template)
    return data["nodes"], data["_ui"]["nodes"]


def get_assign_to_fixed_group_gadget(group_name, group_uuid, destination_uuid):
    ''' Always assigns the contact to the given group. '''

    template = assign_to_fixed_group_template \
        .replace("GroupA_UUID", group_uuid) \
        .replace("Destination_UUID", destination_uuid) \
        .replace("AssignToGroupANode_UUID", generate_random_uuid()) \
        .replace("GroupA_name", group_name)
    n_one_time_uuids = template.count("OneTimeUse_UUID")
    for _ in range(n_one_time_uuids):
        # Each time, only replace first instance.
        template = template.replace("OneTimeUse_UUID", generate_random_uuid(), 1)
    data = json.loads(template)
    return data["nodes"], data["_ui"]["nodes"]


def get_switch_node(edit_op, dest_uuids):
    '''
    Create a router node with N cases as specified in the edit_op,
    and N+1 categories and exits (one extra for the default option).

    Args:
        edit_op (:obj:`FlowEditOp`): has N categories.
        dest_uuids: List of N+1 destination uuids to connect the exits to.
            If the k-th case applies, the corresponding exit is connected
            to the node with the k-th destination uuids. The last destination
            uuid is for the default/other case.

    Returns:
        node
    '''
    cases = []
    node_categories = []
    exits = []
    # For each category, make node case/category/exit
    for dest_uuid, category in zip(dest_uuids[:-1], edit_op.categories()):
        exit = {
          "uuid": generate_random_uuid(),
          "destination_uuid": dest_uuid
        }
        exits.append(exit)
        node_category = {
            "uuid": generate_random_uuid(),
            "name": category.name,
            "exit_uuid": exit["uuid"]
        }
        node_categories.append(node_category)
        case = {
            "uuid": generate_random_uuid(),
            "type": category.condition_type,
            "arguments": category.condition_arguments,
            "category_uuid": node_category["uuid"]
        }
        cases.append(case)
    # Add a default/other option
    other_exit = {
        "uuid": generate_random_uuid(),
        "destination_uuid": dest_uuids[-1]
    }
    exits.append(other_exit)
    other_category = {
        "uuid": generate_random_uuid(),
        "name": "Other",
        "exit_uuid": other_exit["uuid"]
    }
    node_categories.append(other_category)
    # Make the router and node
    router = {
        "type": "switch",
        "cases": cases,
        "categories": node_categories,
        "default_category_uuid": other_category["uuid"],
        "operand": edit_op.split_by(),
        "result_name": ""
    }
    node = {
        "uuid": generate_random_uuid(),
        "actions": [],
        "router": router,
        "exits" : exits
    }
    return node


def find_node_by_uuid(flow, node_uuid):
    '''Given a node uuid, finds the corresponding node.

    Args:
        flow: flow to search in
        node_uuid: node to search for

    Returns:
        node with uuid matchign node_uuid
        None if no node was found.
    '''

    for node in flow["nodes"]:
        if node["uuid"] == node_uuid:
            return node
    return None


def get_unique_node_copy(node):
    '''Given a node, creates a new node with unique uuids wherever appropriate.

    TODO: Make this work for any kind of node. (Check specification.)'''

    node_new = copy.deepcopy(node)
    # Generate new uuids for everything that should have a unique one.
    # TODO: There are 3 action types with fields where this is unclear.
    #   "call_classifier" -- has a "classifier" with uuid
    #   "open_ticket" -- has a "ticketer" with uuid
    #   "set_contact_channel" -- has a field "channel" with uuid
    #   Which of these have to be unique?
    node_new["uuid"] = generate_random_uuid()
    for action in node_new["actions"]:
        action["uuid"] = generate_random_uuid()
        # send_msg actions can have a templating field with templates.
        # The templating uuid should be unique, while the templates
        # themselves refer to external objects with a fixed uuid.
        if "templating" in action:
            action["templating"]["uuid"] = generate_random_uuid()
        # attachments, quick_replies don't have unique uuids.
    uuid_map = dict()
    for exit in node_new["exits"]:
        new_uuid = generate_random_uuid()
        uuid_map[exit["uuid"]] = new_uuid
        exit["uuid"] = new_uuid
        # Note: exit["destination_uuid"] is NOT modified because all variations
        # should exit into the same destination as the original.
    if "router" in node_new:
        for category in node_new["router"]["categories"]:
            new_uuid = generate_random_uuid()
            uuid_map[category["uuid"]] = new_uuid
            category["uuid"] = new_uuid
            category["exit_uuid"] = uuid_map[category["exit_uuid"]]
        if "cases" in node_new["router"]:
            for case in node_new["router"]["cases"]:
                new_uuid = generate_random_uuid()
                uuid_map[case["uuid"]] = new_uuid
                case["uuid"] = new_uuid
                case["category_uuid"] = uuid_map[case["category_uuid"]]
        node_new["router"]["default_category_uuid"] = uuid_map[node_new["router"]["default_category_uuid"]]

    return node_new


def find_incoming_edges(flow, uuid):
    '''
    For a given node uuid, returns a list of exits from other nodes
    that lead into the original node.

    Args:
        flow: flow to scan for nodes with edges into the given node.
        uuid: uuid of the node whose incoming edges to find.

    Returns:
        list of exits
    '''

    # TODO: Caching for performance?
    exits = []
    for node in flow["nodes"]:
        for exit in node["exits"]:
            if exit.get("destination_uuid", None) == uuid:
                exits.append(exit)
    return exits
