import json
import copy
import logging
from collections import defaultdict
from .uuid_tools import UUIDLookup
from .nodes_layout import normalize_flow_layout


logger = logging.getLogger(__name__)


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
    '''

    def __init__(self, json_filename):
        '''Args:
            json_filename (str): Filename of the RapidPro json to be processed.
        '''

        # data_ (dict): data loaded from RapidPro json. Nested dictionary.
        with open(json_filename, 'r', encoding='utf-8') as file:
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
        results = []
        node_flows = []
        for flow in self._data["flows"]:
            if edit_op.is_match_for_flow(flow["name"]):
                node_flows.append(flow)
        if not node_flows:
            logger.warning(edit_op.debug_string() + 'No flow that matches "{}" found.'.format(edit_op.flow_id()))
            return []
        for node_flow in node_flows:
            for node in node_flow["nodes"]:
                if edit_op.is_match_for_node(node):
                    if not node["uuid"] in results:  # only need one instance per node
                        results.append(node["uuid"])
        return results


    def get_edit_ops_by_node(self, editsheets):
        # Returns:
        #     Dictionary mapping each node (indexed by uuid) to the list of
        #     `FlowEditOp`s that should be applied to the node.
        edit_ops_by_node = defaultdict(list)
        # Find nodes affected by operations in some way
        for sheet in editsheets:
            sheet.parse_rows(self._uuid_lookup)
            for edit_op in sheet.edit_ops():
                uuids = self._find_matching_nodes(edit_op)
                if len(uuids) == 0:
                    logger.warning(edit_op.debug_string() + "No node found where operation is applicable.")
                if len(uuids) >= 2 and edit_op.matches_unique_flow() and edit_op.matches_unique_node_identifier():
                    logger.warning(edit_op.debug_string() + "Multiple nodes found where operation is applicable.")
                for uuid in uuids:
                    edit_ops_by_node[uuid].append(edit_op)
        return edit_ops_by_node


    def apply_editsheets(self, editsheets, normalize_layout=False):
        edit_ops_by_node = self.get_edit_ops_by_node(editsheets)
        # For each nodes affected by A/B tests, apply the test operations
        for flow in self._data["flows"]:
            # Iterate over copy of node list because the real list of nodes
            # is modified in the process.
            for node in copy.copy(flow["nodes"]):
                if node["uuid"] in edit_ops_by_node:
                    edit_ops = edit_ops_by_node[node["uuid"]]
                    apply_editops_to_node(flow, node, edit_ops)
            # Make sure all flow nodes have positive coordinates
            normalize_flow_layout(flow)


    def apply_abtests(self, floweditsheets):
        '''Modify the internal RapidPro flow data by apply the A/B tests.'''

        self.apply_editsheets(floweditsheets, normalize_layout=True)

        # Collect all previously existing and newly created groups
        self._data["groups"] = []
        for group in self._uuid_lookup.all_groups():
            self._data["groups"].append(group.to_json_group())


    def apply_translationedits(self, translationeditsheets):
        '''Modify the internal RapidPro flow data by applying Translation changes.'''
        self.apply_editsheets(translationeditsheets)


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
    operable_nodes = [node]
    for edit_op in edit_ops:
        new_operable_nodes = []
        for onode in operable_nodes:
            new_operable_nodes += edit_op.apply_operation(flow, onode)
        operable_nodes = new_operable_nodes
    return operable_nodes  # Return value only used for testing
