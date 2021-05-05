import json
import copy

from abtest import ABTest, ABTestOp
from uuid_tools import generate_random_uuid
from templates import group_switch_node_template, assign_to_group_template

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
            # For each variation, create a new node with the op applied.
            # TODO: Deal with nodes that have multiple actions.
            #     At least such nodes cannot have a router.
            #     TODO: Compile a list of fields such nodes can have?
            if op.row(ABTest.TYPE) == "replace_bit_of_text" and var.node["actions"] and var.node["actions"][0]["type"] == "send_msg":
                text = var.node["actions"][0]["text"]
                # TODO: Code for nodes with multiple actions.
                # TODO: Check that there is exactly one occurrence in the text
                text_new = text.replace(op.row(ABTest.A_CONTENT), op.row(ABTest.B_CONTENT))
                # The new variation is obtained by taking a copy of the
                # original, replacing the text, and replacing all uuids
                # except for destination_uuids.
                # TODO: Actions can have a templating field that has a uuid to be changed.
                #     The templating field can have templates each with uuids
                #     which shouldn't be changed.
                # TODO: The node may have other fields with UUIDs that should
                #     be unique for each variation. Compile a list of fields to check.
                var_new = copy.deepcopy(var)
                var_new.node["actions"][0]["text"] = text_new
                var_new.node["uuid"] = generate_random_uuid()
                for action in var_new.node["actions"]:
                    action["uuid"] = generate_random_uuid()
                for exit in var_new.node["exits"]:
                    exit["uuid"] = generate_random_uuid()
                    # exit["destination_uuid"] is NOT modified.
                var.groups.append(op.groupA_name())
                var_new.groups.append(op.groupB_name())
                # Add the original and modified version to new_variations.
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
