import json
import copy
import logging
from collections import defaultdict
import node_tools as nt
from abtest import ABTest, FlowEditSheet
from uuid_tools import UUIDLookup
from contact_group import ContactGroup
import nodes_layout

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
    - No ui_ output yet, RapidPro will lay it out in a single column.
      TODO: Take input node layout, modify sensibly.
    '''

    def __init__(self, json_filename):
        '''Args:
            json_filename (str): Filename of the RapidPro json to be processed.
        '''

        # data_ (dict): data loaded from RapidPro json. Nested dictionary.
        with open(json_filename, 'r') as file:
            self._data = json.load(file)

        self._uuid_lookup = UUIDLookup()
        for flow in self._data["flows"]:
            self._uuid_lookup.add_flow(flow["name"], flow["uuid"])
        for group in self._data["groups"]:
            self._uuid_lookup.add_group(group["name"], group["uuid"])


    def get_uuid_lookup(self):
        return self._uuid_lookup


    def _find_matching_nodes(self, edit_op):
        '''
        Go through entire data to find nodes matching the specifications.

        Nodes of interest are nodes with "send_msg" actions.

        Args:
            edit_op:
        '''

        # TODO: We should also store the action(s) where the text was found
        #   This would allow us to log more helpful warnings.

        results = []
        # TODO: Caching for performance?
        node_flow = None
        for flow in self._data["flows"]:
            if edit_op.is_match_for_flow(flow["name"]):
                node_flow = flow
        if node_flow is None:
            logging.warning(edit_op.debug_string() + 'No flow with name "{}" found.'.format(edit_op.flow_id()))
            return []
        for node in node_flow["nodes"]:
            if edit_op.is_match_for_node(node):
                if not node["uuid"] in results:  # only need one instance per node
                    results.append(node["uuid"])
        return results


    def apply_abtests(self, floweditsheets):
        '''Modify the internal RapidPro flow data by apply the A/B tests.'''

        # List of pairs of node uuids and test_ops, each pair indicating that
        # before the given node the user should have been assigned to one of the
        # `ContactGroup`s for the A/B test the edit_op belongs to
        assign_to_group_ops = []
        # Dictionary mapping each node (indexed by uuid) to the list of
        # `FlowEditOp`s that should be applied to the node.
        edit_ops_by_node = defaultdict(list)

        # Find nodes affected by operations in some way
        for sheet in floweditsheets:
            sheet.parse_rows(self._uuid_lookup)
            for edit_op in sheet.edit_ops():
                uuids = self._find_matching_nodes(edit_op)
                if len(uuids) == 0:
                    logging.warning(edit_op.debug_string() + "No node found where operation is applicable.")
                if len(uuids) >= 2:
                    logging.warning(edit_op.debug_string() + "Multiple nodes found where operation is applicable.")
                for uuid in uuids:
                    edit_ops_by_node[uuid].append(edit_op)

        # For each nodes affected by A/B tests, apply the test operations
        for flow in self._data["flows"]:
            # Iterate over copy of node list because the real list of nodes
            # is modified in the process.
            for node in copy.copy(flow["nodes"]):
                if node["uuid"] in edit_ops_by_node:
                    edit_ops = edit_ops_by_node[node["uuid"]]
                    apply_editops_to_node(flow, node, edit_ops)
            # Make sure all flow nodes have positive coordinates
            nodes_layout.normalize_flow_layout(flow)

        # Collect all previously existing and newly created groups
        self._data["groups"] = []
        for group in self._uuid_lookup.all_groups():
            self._data["groups"].append(group.to_json_group())


    def export_to_json(self, filename):
        with open(filename, "w") as fout:
            json.dump(self._data, fout, indent=2)


def apply_editops_to_node(flow, node, edit_ops):
    '''
    Apply edit_ops to a given node.

    In the process, the flow is modified.

    If the flow is in a consistent state before applying the edit_ops,
    it will be in a consistent state afterwards.

    Args:
        flow: flow the node belongs to
        node: node to apply edit_ops to
        edit_ops (`FlowEditOp`):
    '''

    # TODO: There could be multiple ops from the same A/B test
    #   on the same node. Simplify tree/variations in that case?

    operable_nodes = [node]
    for edit_op in edit_ops:
        new_operable_nodes = []
        for onode in operable_nodes:
            new_operable_nodes += edit_op.apply_operation(flow, onode)
        operable_nodes = new_operable_nodes
    return operable_nodes  # Return value only used for testing