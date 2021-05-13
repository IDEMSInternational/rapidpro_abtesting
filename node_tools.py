import json
import copy
import logging

from abtest import ABTest, ABTestOp, OpType
from uuid_tools import generate_random_uuid
from templates import group_switch_node_template, assign_to_group_template


class NodeVariation(object):
    '''Variation of a node.

    Variations are generated from an original node by applying
    `ABTestOp`s to it.

    Attributes:
        node: The node itself.
        groups (`list` of :obj:`ContactGroup`):
            One entry for each `ABTestOp` that applies to the node,
            indicating which side of the A/B test it belongs to.
    '''
    def __init__(self, node, groups):
        self.node = node
        self.groups = groups


def get_assign_to_group_gadget(test_op, destination_uuid):
    '''
    Create a gadget that checks whether the contact is in a group
    from a group pair (which is specified in test_op), and if not,
    randomly add the contact to one group from the pair.

    Returns:
        list of nodes: Nodes of the gadget.
            The first node is entry point to the gadget.
            All exit points are rerouted to the specified destination UUID.
    '''
    template = assign_to_group_template \
        .replace("EntryNode_UUID", generate_random_uuid()) \
        .replace("CaseA_UUID", generate_random_uuid()) \
        .replace("CaseB_UUID", generate_random_uuid()) \
        .replace("GroupA_UUID", test_op.groupA().uuid) \
        .replace("GroupB_UUID", test_op.groupB().uuid) \
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
        .replace("GroupA_name", test_op.groupA().name) \
        .replace("GroupB_name", test_op.groupB().name)
    n_one_time_uuids = template.count("OneTimeUse_UUID")
    for _ in range(n_one_time_uuids):
        # Each time, only replace first instance.
        template = template.replace("OneTimeUse_UUID", generate_random_uuid(), 1)
    return json.loads(template)


def get_group_switch_node(test_op, dest_uuids):
    '''
    Create a router node with two exits, one for each of the two groups
    of the group pair defined in test_op.

    Args:
        test_op (:obj:`ABTestOp`): ABTestOp containing the group pair.
        destA_uuid: UUID of the node to transition into if the contact
            is in group A of the group pair.
        destB_uuid: UUID of the node to transition into if the contact
            is in group B of the group pair.

    Returns:
        node
    '''
    return get_switch_node(test_op, dest_uuids + [dest_uuids[-1]])

    # Obsoleted due to more general version from get_switch_node
    template = group_switch_node_template \
        .replace("Node_UUID", generate_random_uuid()) \
        .replace("CaseA_UUID", generate_random_uuid()) \
        .replace("CaseB_UUID", generate_random_uuid()) \
        .replace("GroupA_UUID", test_op.groupA().uuid) \
        .replace("GroupB_UUID", test_op.groupB().uuid) \
        .replace("GroupA_Category_UUID", generate_random_uuid()) \
        .replace("GroupB_Category_UUID", generate_random_uuid()) \
        .replace("Other_Category_UUID", generate_random_uuid()) \
        .replace("ExitA_UUID", generate_random_uuid()) \
        .replace("ExitB_UUID", generate_random_uuid()) \
        .replace("ExitOther_UUID", generate_random_uuid()) \
        .replace("DestinationA_UUID", dest_uuids[0]) \
        .replace("DestinationB_UUID", dest_uuids[1]) \
        .replace("GroupA_name", test_op.groupA().name) \
        .replace("GroupB_name", test_op.groupB().name)
    return json.loads(template)


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


def replace_text_in_node(node, edit_op, replacement_text):
    '''Modifies the input node.
    '''
    total_occurrences = 0
    for action in node["actions"]:
        if action["type"] == "send_msg":
            text = action["text"]
            total_occurrences += text.count(edit_op.bit_of_text())
            text_new = text.replace(edit_op.bit_of_text(), replacement_text)
            action["text"] = text_new

    # TODO: If we don't just store the node uuid, but also action uuid
    #   where edit_op is applicable, we could give more helpful
    #   messages here by referring to the action text that doesn't match
    if total_occurrences == 0:
        # This might happen if we're trying to replace text that has
        # already had a replacement applied to it.
        logging.warning(edit_op.debug_string() + 'No occurrences of "{}" found node.'.format(edit_op.bit_of_text()))
    if total_occurrences >= 2:
        logging.warning(edit_op.debug_string() + 'Multiple occurrences of "{}" found in node.'.format(edit_op.bit_of_text()))


def apply_replace_bit_of_text(var, edit_op, replacement_text):
    '''Apply "replace_bit_of_text" operation on node variation.

    Leaves the input variation unaffected and returns a new variation.

    Args:
        var (`NodeVariation`): node to apply the operation to.
        test_op (`FlowEditOp`): Operation to be applied,
            must be of type "replace_bit_of_text"
    '''

    # Take a copy of the original variation and replace action text.
    var_new = copy.deepcopy(var)
    replace_text_in_node(var_new.node, edit_op, replacement_text)

    # Generate new uuids for everything that should have a unique one.
    # We don't have to worry about routers because nodes with a send_msg
    # action cannot have a router.
    # TODO: There are 3 action types with fields where this is unclear.
    #   "call_classifier" -- has a "classifier" with uuid
    #   "open_ticket" -- has a "ticketer" with uuid
    #   "set_contact_channel" -- has a field "channel" with uuid
    #   Which of these have to be unique?
    var_new.node["uuid"] = generate_random_uuid()
    for action in var_new.node["actions"]:
        action["uuid"] = generate_random_uuid()
        # send_msg actions can have a templating field with templates.
        # The templating uuid should be unique, while the templates
        # themselves refer to external objects with a fixed uuid.
        if "templating" in action:
            action["templating"]["uuid"] = generate_random_uuid()
        # attachments, quick_replies don't have unique uuids.
    for exit in var_new.node["exits"]:
        exit["uuid"] = generate_random_uuid()
        # Note: exit["destination_uuid"] is NOT modified because all variations
        # should exit into the same destination as the original.
    return var_new


def generate_node_variations(orig_node, edit_ops):
    '''
    Generate 2^N versions of orig_node, one for each
    combination of A/B tests affecting this node.
    Each variation knows which sides of the various A/B tests it belongs to.

    For example, if an initial node is affected by Test1 and Test2,
    which have associated contact groups Test1A, Test1B and Test2A, Test2B
    respectively, the first node will have groups [Test1A, Test2A],
    and there will be three more nodes with groups [Test1A, Test2B],
    [Test1B, Test2A] and [Test1B, Test2B] respectively.

    Args:
        orig_node: Node to create variations of. This node will correspond to
            the default case, and its message text may be modified.
        edit_ops (list of :obj:`FlowEditOp`): Operations to apply to the node.

    Returns:
        list of :obj:`NodeVariation`: The generated node variations.
    '''

    # Start off with one variation: the original node.
    variations = [NodeVariation(orig_node, [])]
    for op in edit_ops:
        # Each test_op multiplies the number of variations by 2:
        # for each existing variations, we keep the original but also
        # create a new one with the additional test_op applied to it.
        # new_variations collects all variations (original and modified).
        new_variations = []
        for var in variations:
            # For each variation, create a new node with the op applied,
            # and add the original and modified version to new_variations.
            if op.op_type() == OpType.REPLACE_BIT_OF_TEXT:
                var_variations = []
                for category in op.categories():
                    var_new = apply_replace_bit_of_text(var, op, category.replacement_text)
                    var_new.groups.append(category.name)
                    var_variations.append(var_new)
                # Original variation serves as default option
                replace_text_in_node(var.node, op, op.default_text())

                if op.has_node_for_other_category():
                    # Original node becomes the "Other" variation
                    var.groups += "Other"  # 
                    new_variations += var_variations + [var]
                else:
                    # Ditch the first variation and use the original instead.
                    # No variation for the "Other" category is added.
                    var.groups = var_variations[0].groups
                    new_variations += [var] + var_variations[1:]
        variations = new_variations
    return variations


def generate_group_membership_tree(test_ops, variations):
    '''
    Given a list of A/B tests, generate a binary tree whose nodes
    check for group membership for side A and B for each of the tests
    and have an exit for each side.
    The exits of the lowest level of the tree are connected
    (in order) to the provided `NodeVariation`s.

    Args:
        test_ops (list of `ABTestOp`)
        variations (list of :obj:`NodeVariation`)

    Returns:
        uuid of the root of the tree
        list of nodes of the tree; the last node is the root.
    '''

    edit_op = test_ops[0]
    if len(test_ops) == 1:
        destination_uuids = [variation.node["uuid"] for variation in variations]
        if not edit_op.has_node_for_other_category():
            # reroute "Other" category to last proper category
            destination_uuids.append(destination_uuids[-1])
        switch = get_group_switch_node(edit_op, destination_uuids)
        return switch["uuid"], [switch]

    n_variations = len(variations)
    if edit_op.has_node_for_other_category():
        n_categories = len(edit_op.categories()) + 1
    else:
        n_categories = len(edit_op.categories())

    all_switches = []
    destination_uuids = []
    for i in range(n_categories):
        first_var_index = i * n_variations // n_categories
        last_var_index = (i+1) * n_variations // n_categories
        root_uuid, switches = generate_group_membership_tree(test_ops[1:], variations[first_var_index:last_var_index])
        destination_uuids.append(root_uuid)
        all_switches += switches
    if not edit_op.has_node_for_other_category():
        # reroute "Other" category to last proper category
        destination_uuids.append(destination_uuids[-1])
    root_switch = get_group_switch_node(edit_op, destination_uuids)
    all_switches.append(root_switch)
    return root_switch["uuid"], all_switches


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
            if exit["destination_uuid"] == uuid:
                exits.append(exit)
    return exits
