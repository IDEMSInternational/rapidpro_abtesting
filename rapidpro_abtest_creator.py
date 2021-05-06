import json
import copy
from collections import defaultdict
import node_tools as nt
from abtest import ABTest, ABTestOp
from uuid_tools import generate_random_uuid



class ContactGroup(object):
    '''Represents a RapidPro contact group

    Attributes:
        name: group name
        uuid: group uuid
    '''

    def __init__(self, name, uuid=generate_random_uuid()):
        self.name = name
        self.uuid = uuid

    def to_json_group(self):
        '''Return corresponding json object for use in RapidPro file.'''

        return {
            'uuid': self.uuid,
            'name': self.name,
            'query': None,
        }


class RapidProABTestCreator(object):
    '''Modifies RapidPro flows to support A/B testing.

    This class takes a RapidPro json file as input.
    The method `apply_abtests` accepts a list of A/B test specifications,
    and produces RapidPro flows that assign users to A/B test groups,
    and interact with the users differently (as specified in the A/B test
    specifications) depending on which test groups they have been assigned to.
    The method `export_to_json` exports the result to a specified json file.

    Notes:
    - We assume the input is valid, conforming to e.g.
      https://github.com/fagiothree/excel-to-json-flow/blob/main/types/index.ts
    - We keep the flow uuids (and most other uuids) the same, i.e. the uuids
      in the output are the same as in the input and will overwrite the input
      when importing in RapidPro
    - Each A/B test operation is replace_bit_of_text, and refers to text within
      a send_msg action. If multiple nodes match the text, the operation will
      affect all of these nodes.
      - The row_id from the A/B testing spreadsheets is ignored
      - Further operations may be supported in future versions.
    - Assume only one action per node, for now.
      TODO: Support multiple actions per node
    - No ui_ output yet, RapidPro will lay it out in a single column.
      TODO: Take input node layout, modify sensibly.
    '''

    def __init__(self, json_filename):
        '''Args:
            json_filename (str): Filename of the RapidPro json to be processed.
        '''

        # data_ (dict): data loaded from RapidPro json. Nested dictionary.
        with open(json_filename, 'r') as file:
            self.data_ = json.load(file)


    def find_nodes_by_content(self, flow_name, row_id, text_content):
        '''
        Go through entire data to find nodes matching the specifications.

        Nodes of interest are nodes with "send_msg" actions.

        Args:
            flow_name: Name of the flow the node should be part of.
            row_id: (Currently ignored)
            text_content: Text sent by a "send_msg" action.
        '''

        results = []
        # TODO: Caching for performance?
        node_flow = None
        for flow in self.data_["flows"]:
            if flow["name"] == flow_name:
                node_flow = flow
        if node_flow is None:
            # TODO: Log an error
            return []
        for node in node_flow["nodes"]:
            # TODO: Check row_id once implemented
            for action in node["actions"]:
                if action["type"] == "send_msg" and action["text"] == text_content:
                    results.append(node["uuid"])
        return results


    def find_node_by_uuid(self, node_uuid):
        ''' Find a node with given uuid in the RapidPro data.'''

        # TODO: Caching for performance?
        for flow in self.data_["flows"]:
            node = nt.find_node_by_uuid(flow, node_uuid)
            if node is not None:
                return flow, node
        return None, None


    def insert_assign_to_group_gadget(self, node_uuid, test_op):
        '''Insert a gadget that assigns the user to a A/B testing group

        Args:
            node_uuid: uuid of the node in front of which to assign the gadget
            test_op (`ABTestOp`): specifies the relevant A/B testing group.
        '''

        flow, node = self.find_node_by_uuid(node_uuid)
        node_is_entrypoint = flow["nodes"][0]["uuid"] == node_uuid
        incoming_edges = nt.find_incoming_edges(flow, node_uuid)
        gadget_nodes = nt.get_assign_to_group_gadget(test_op, node_uuid)
        gadget_entry_uuid = gadget_nodes[0]["uuid"]
        for incoming_edge in incoming_edges:
            incoming_edge["destination_uuid"] = gadget_entry_uuid
        if node_is_entrypoint:
            # First node must become the new entry point
            flow["nodes"] = gadget_nodes[:1] + flow["nodes"] + gadget_nodes[1:]
        else:
            flow["nodes"] += gadget_nodes


    def apply_testops_to_node(self, flow, node, test_ops):
        '''
        Apply test_ops to a given node.

        Args:
            flow: flow the node belongs to
            node: node to apply test_ops to
            test_ops (`ABTestOp`):
        '''

        # TODO: Consider multiple ops on the same node from the same test?
        uuid = node["uuid"]
        node_is_entrypoint = flow["nodes"][0]["uuid"] == uuid
        incoming_edges = nt.find_incoming_edges(flow, uuid)

        # Generate test-specific node variations and add them to flow.
        variations = nt.generate_node_variations(node, test_ops)
        flow["nodes"] += [variation.node for variation in variations[1:]]

        # Generate group membership tree and add its nodes to flow
        root_uuid, tree_nodes = nt.generate_group_membership_tree(test_ops, variations)
        if node_is_entrypoint:
            # Root of the tree is the last in the list and must become the new entry point
            flow["nodes"] = tree_nodes[-1:] + flow["nodes"] + tree_nodes[:-1]
        else:
            flow["nodes"] += tree_nodes


        # Redirect edges that went into the node to the root of
        # the group membership tree.
        for edge in incoming_edges:
            edge["destination_uuid"] = root_uuid


    def apply_abtests(self, abtests):
        '''Modify the internal RapidPro flow data by apply the A/B tests.'''

        # List of pairs of node uuids and test_ops, each pair indicating that
        # before the given node the user should have been assigned to one of the
        # `ContactGroup`s for the A/B test the test_op belongs to
        assign_to_group_ops = []
        # Dictionary mapping each node (indexed by uuid) to the list of
        # `ABTestOp`s that should be applied to the node.
        test_ops_by_node = defaultdict(list)

        # Find nodes affected by A/B tests in some way
        for abtest in abtests:
            group_pair = (ContactGroup(abtest.groupA_name()), ContactGroup(abtest.groupB_name()))
            self.data_["groups"].append(group_pair[0].to_json_group())
            self.data_["groups"].append(group_pair[1].to_json_group())
            for row in abtest.rows():
                test_op = ABTestOp(group_pair, row)
                uuids = self.find_nodes_by_content(row[ABTest.FLOW_ID], row[ABTest.ROW_ID], row[ABTest.ORIG_MSG])
                for uuid in uuids:
                    # TODO: Warn if no or multiple results.
                    # TODO: Return a uuid rather than list of uuids?
                    test_ops_by_node[uuid].append(test_op)
                    if row[ABTest.ASSIGN_TO_GROUP]:
                        assign_to_group_ops.append((uuid, test_op))

        # For each node for which the contact should be assigned to a group
        # before visiting it, insert the corresponding gadget before the node.
        for node_uuid, test_op in assign_to_group_ops:
            self.insert_assign_to_group_gadget(node_uuid, test_op)

        # For each nodes affected by A/B tests, 
        for flow in self.data_["flows"]:
            for node in flow["nodes"]:
                if node["uuid"] in test_ops_by_node:
                    test_op = test_ops_by_node[node["uuid"]]
                    self.apply_testops_to_node(flow, node, test_op)


    def export_to_json(self, filename):
        with open(filename, "w") as fout:
            json.dump(self.data_, fout, indent=2)
