import json
import copy

from abtest import ABTest, ABTestOp
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
        .replace("GroupA_UUID", test_op.groupA_uuid()) \
        .replace("GroupB_UUID", test_op.groupB_uuid()) \
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
        .replace("GroupA_name", test_op.groupA_name()) \
        .replace("GroupB_name", test_op.groupB_name())
    n_one_time_uuids = template.count("OneTimeUse_UUID")
    for _ in range(n_one_time_uuids):
        # Each time, only replace first instance.
        template = template.replace("OneTimeUse_UUID", generate_random_uuid(), 1)
    return json.loads(template)


def get_group_switch_node(test_op, destA_uuid, destB_uuid):
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
    template = group_switch_node_template \
        .replace("Node_UUID", generate_random_uuid()) \
        .replace("CaseA_UUID", generate_random_uuid()) \
        .replace("CaseB_UUID", generate_random_uuid()) \
        .replace("GroupA_UUID", test_op.groupA_uuid()) \
        .replace("GroupB_UUID", test_op.groupB_uuid()) \
        .replace("GroupA_Category_UUID", generate_random_uuid()) \
        .replace("GroupB_Category_UUID", generate_random_uuid()) \
        .replace("Other_Category_UUID", generate_random_uuid()) \
        .replace("ExitA_UUID", generate_random_uuid()) \
        .replace("ExitB_UUID", generate_random_uuid()) \
        .replace("ExitOther_UUID", generate_random_uuid()) \
        .replace("DestinationA_UUID", destA_uuid) \
        .replace("DestinationB_UUID", destB_uuid) \
        .replace("GroupA_name", test_op.groupA_name()) \
        .replace("GroupB_name", test_op.groupB_name())
    return json.loads(template)


def find_node_by_uuid(flow, node_uuid):
    '''Given a node uuid, finds the corresponding node.

    Args:
        flow: flow to search in
        node_uuid:

    Returns:
        node with uuid matchign node_uuid
        None is node node was found.
    '''

    for node in flow["nodes"]:
        if node["uuid"] == node_uuid:
            return node
    return None


def apply_replace_bit_of_text(var, op):
    '''Apply "replace_bit_of_text" operation on node variation.

    Leaves the input variation unaffected and returns a new variation.

    Args:
        var (`NodeVariation`): node to apply the operation to.
        op (`ABTestOp`): Operation to be applied,
            must be of type "replace_bit_of_text"
    '''

    # Take a copy of the original variation and replace action text.
    var_new = copy.deepcopy(var)
    for action in var_new.node["actions"]:
        if action["type"] == "send_msg":
            text = action["text"]
            # TODO: Check that there is exactly one occurrence in the text
            text_new = text.replace(op.row(ABTest.A_CONTENT), op.row(ABTest.B_CONTENT))
            action["text"] = text_new

    # Generate new uuids for everything that should have a unique one.
    # TODO: The node may have other fields with UUIDs that should
    #   be unique for each variation. Compile a list of fields to check.
    #   Nodes with actions cannot have a router.
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


def generate_node_variations(orig_node, test_ops):
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
        orig_node: Node to create variations of.
        test_ops (list of :obj:`ABTestOp`): Operations to apply to the node.

    Returns:
        list of :obj:`NodeVariation`: The generated node variations.
    '''

    # Start off with one variation: the original node.
    variations = [NodeVariation(orig_node, [])]
    for op in test_ops:
        # Each test_op multiplies the number of variations by 2:
        # for each existing variations, we keep the original but also
        # create a new one with the additional test_op applied to it.
        # new_variations collects all variations (original and modified).
        new_variations = []
        for var in variations:
            # For each variation, create a new node with the op applied,
            # and add the original and modified version to new_variations.
            if op.row(ABTest.TYPE) == "replace_bit_of_text":
                var_new = apply_replace_bit_of_text(var, op)
                var.groups.append(op.groupA())
                var_new.groups.append(op.groupB())
                new_variations += [var, var_new]
            else:
                # TODO: Log an error
                pass
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

    destination_uuids = [variation.node["uuid"] for variation in variations]

    tree_nodes = []
    # Traverse the group pairs back to front; we build the tree bottom to top.
    for p in range(len(test_ops) - 1, -1, -1):
        copies = []
        for i in range(2**p):
            copies.append(get_group_switch_node(test_ops[p], destination_uuids[2*i], destination_uuids[2*i+1]))
        destination_uuids = [node["uuid"] for node in copies]
        tree_nodes += copies
    return tree_nodes[-1]["uuid"], tree_nodes


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
