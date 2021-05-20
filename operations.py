from abc import ABC, abstractmethod
import logging
import node_tools as nt
import re

class FlowSnippet(object):
    '''A piece of flow with a single entry and exit point.

    FlowSnippets are generated by `FlowEditOp`s and replace an original input
    node. A flow snippet may contain multiple variations of the input node,
    which are specifically recorded so that further `FlowEditOp`s can be
    applied to those nodes.

    Args:
        nodes: List of nodes defining the flow snippet
        node_variations: Nodes that are variations of the original node
        root_uuid: Everything previously having the original node
            as destination is redirected to root_uuid
    '''

    def __init__(self, nodes, node_variations, root_uuid=-1):
        self._nodes = nodes
        self._node_variations = node_variations
        if root_uuid == -1:
            self._root_uuid = nodes[0]["uuid"]
        else:
            self._root_uuid = root_uuid

    def nodes(self):
        return self._nodes

    def node_variations(self):
        return self._node_variations

    def root_uuid(self):
        return self._root_uuid


class FlowEditOp(ABC):

    def needs_parameter():
        '''Does this operation read a value from the "change" column?'''
        return True

    def create_edit_op(op_type, flow_id, row_id, node_identifier, bit_of_text,
                       split_by, default_text, debug_string,
                       has_node_for_other_category=True,
                       assign_to_group=False,
                       uuid_lookup=None):
        if op_type not in OPERATION_TYPES:
            logging.warning(debug_string + 'invalid operation type.')
            return None
        class_name = OPERATION_TYPES[op_type]
        return class_name(flow_id, row_id, node_identifier, bit_of_text,
                          split_by, default_text, debug_string,
                          has_node_for_other_category, assign_to_group,
                          uuid_lookup)

    def __init__(self, flow_id, row_id, node_identifier, bit_of_text, split_by,
                 default_text, debug_string,
                 has_node_for_other_category=True,
                 assign_to_group=False,
                 uuid_lookup=None):
        self._flow_id = flow_id
        self._row_id = row_id
        self._node_identifier = node_identifier
        self._bit_of_text = bit_of_text
        self._split_by = split_by
        self._default_text = default_text
        self._categories = []
        self._debug_string = debug_string
        self._has_node_for_other_category = has_node_for_other_category
        self._assign_to_group = assign_to_group  # to be removed
        self._process_uuid_lookup(uuid_lookup)

    def add_category(self, category, uuid_lookup=None):
        # TODO: Perform UUID lookup if type is has_group
        # What if multiple sheets refer to the same group
        # which is only created by an A/B Test op?
        # Store uuid_lookup in Op and only process it
        # lazily?
        self._categories.append(category)

    def _process_uuid_lookup(self, uuid_lookup):
        pass

    @abstractmethod
    def is_match_for_node(self, node):
        pass

    def apply_operation(self, flow, node):
        '''Apply the operation to a given node.

        Replaces the node with an appropriate flow snippet.

        Returns:
            list of nodes: variations of the input node that further
                operations can be applied to.
        '''

        uuid = node["uuid"]
        node_is_entrypoint = flow["nodes"][0]["uuid"] == uuid
        incoming_edges = nt.find_incoming_edges(flow, uuid)

        flow["nodes"].remove(node)
        snippet = self._get_flow_snippet(node)

        # Insert the new snippet.
        # If node was entrypoint, snippet has to become entrypoint
        if node_is_entrypoint:
            flow["nodes"] = snippet.nodes() + flow["nodes"]
        else:
            flow["nodes"] = flow["nodes"] + snippet.nodes()

        # Redirect edges that went into the node to the snippet root
        for edge in incoming_edges:
            edge["destination_uuid"] = snippet.root_uuid()
        
        return snippet.node_variations()

    def debug_string(self):
        '''Returns a human-readable identifier of sheet/row of the FlowEditOp.'''
        return self._debug_string

    def is_match_for_flow(self, flow_name):
        return flow_name == self._flow_id

    def flow_id(self):
        return self._flow_id

    def row_id(self):
        return self._row_id

    def node_identifier(self):
        return self._node_identifier

    def bit_of_text(self):
        return self._bit_of_text

    def split_by(self):
        return self._split_by

    def default_text(self):
        return self._default_text

    def categories(self):
        return self._categories

    def assign_to_group(self):
        return self._assign_to_group  # to be removed

    def has_node_for_other_category(self):
        return self._has_node_for_other_category

    @abstractmethod
    def _get_flow_snippet(self, node):
        pass

    def _matches_entered_flow(self, node):
        # TODO: Check row_id once implemented
        if len(node["actions"]) == 0:
            return False
        action = node["actions"][0]
        if action["type"] != "enter_flow":
            return False
        if action["flow"]["name"] != self.node_identifier():
            return False
        return True

    def _strict_text_match(self, text1, text2):
        return text1 == text2

    def _lenient_text_match(self, text1, text2):
        '''Ignores whitespace differences by replacing groups o
        whitespace with a single space and stipping whitespace
        from the beginning and end of the text.'''
        return re.sub(r'\s+', ' ', text1).strip() == re.sub(r'\s+', ' ', text2).strip()

    def _matches_message_text(self, node):
        # TODO: Check row_id once implemented
        # TODO: If there are multiple exits, warn and return False
        for action in node["actions"]:
            if action["type"] == "send_msg" and self._lenient_text_match(action["text"], self.node_identifier()):
                return True
        return False

    def _matches_save_value(self, node):
        return self._matching_save_value_action_id(node) != -1

    def _matching_save_value_action_id(self, node):
        # TODO: Check row_id once implemented
        for i, action in enumerate(node["actions"]):
            if action["type"] == "set_run_result" and "@results." + action["name"].lower().replace(' ', '_') == self.node_identifier() and str(self.bit_of_text()) == str(action["value"]):
                return i
            if action["type"] == "set_contact_field" and "@fields." + action["field"]["key"].lower() == self.node_identifier() and str(self.bit_of_text()) == str(action["value"]):
                return i
            if action["type"] == "set_contact_name" and "@contact.name" == self.node_identifier() and str(self.bit_of_text()) == str(action["name"]):
                return i
            if action["type"] == "set_contact_channel" and "@contact.channel" == self.node_identifier() and str(self.bit_of_text()) == str(action["channel"]["name"]):
                return i
            if action["type"] == "set_contact_language" and "@contact.language" == self.node_identifier() and str(self.bit_of_text()) == str(action["language"]):
                return i
            if action["type"] == "set_contact_status" and "@contact.status" == self.node_identifier() and str(self.bit_of_text()) == str(action["status"]):
                return i
        return -1

    def _replace_saved_value(self, node, value, action_index):
        action = node["actions"][action_index]
        if action["type"] == "set_run_result":
            action["value"] = value
        elif action["type"] == "set_contact_field":
            action["value"] = value
        elif action["type"] == "set_contact_name":
            action["name"] = value
        elif action["type"] == "set_contact_channel":
            action["channel"]["name"] = value
        elif action["type"] == "set_contact_language":
            action["language"] = value
        elif action["type"] == "set_contact_status":
            action["status"] = value
        else:
            pass  # TODO: Warning.

    def _replace_text_in_message(self, node, replacement_text):
        '''Modifies the input node by replacing message text.'''
        total_occurrences = 0
        for action in node["actions"]:
            if action["type"] == "send_msg":
                text = action["text"]
                total_occurrences += text.count(self.bit_of_text())
                text_new = text.replace(self.bit_of_text(), replacement_text)
        # TODO: If we don't just store the node uuid, but also action uuid
        #   where edit_op is applicable, we could give more helpful
        #   messages here by referring to the action text that doesn't match
        if total_occurrences == 0:
            # This might happen if we're trying to replace text that has
            # already had a replacement applied to it.
            logging.warning(self.debug_string() + 'No occurrences of "{}" found node.'.format(self.bit_of_text()))
        if total_occurrences >= 2:
            logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node.'.format(self.bit_of_text()))

    def _replace_entered_flow(self, node, replacement_text):
        if self._matches_entered_flow(node):
            # TODO: Also UUID
            node["actions"][0]["flow"] = replacement_text
        else:
            logging.warning(self.debug_string() + 'No occurrences of "{}" found in node.'.format(self.bit_of_text()))

    def _replace_text_in_quick_replies(self, node, replacement_text):
        '''Modifies the input node by replacing message text.

        Args:
            replacement_text (str): Semicolon separated list of text pieces.
        '''

        for bit_of_text, repl_text in zip(self._bit_of_text.split(';'), replacement_text.split(';')):
            total_occurrences = 0
            for action in node["actions"]:
                if action["type"] == "send_msg":
                    for i, text in enumerate(action["quick_replies"]):
                        total_occurrences += text.count(bit_of_text)
                        text_new = text.replace(bit_of_text, repl_text)
                        action["quick_replies"][i] = text_new
            if total_occurrences == 0:
                logging.warning(self.debug_string() + 'No occurrences of "{}" found node.'.format(bit_of_text))
            if total_occurrences >= 2:
                logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node.'.format(bit_of_text))

    def _apply_noop(self, node):
        return FlowSnippet([node], [node], node["uuid"])

    def _get_assigntogroup_gadget(self, node):
        if len(self.categories()) != 2:
            logging.warning(self.debug_string() + 'assign_to_group only for A/B tests (i.e. 2 groups).')
            return self._apply_noop(node)
        groupA_uuid = self.categories()[0].condition_arguments[0]
        groupA_name = self.categories()[0].condition_arguments[1]
        groupB_uuid = self.categories()[1].condition_arguments[0]
        groupB_name = self.categories()[1].condition_arguments[1]
        gadget = nt.get_assign_to_group_gadget(groupA_name, groupA_uuid, groupB_name, groupB_uuid, node["uuid"])
        return gadget

    def _get_variation_tree_snippet(self, input_node):
        node_variations = []
        for category in self.categories():
            node = nt.get_unique_node_copy(input_node)
            self._replace_content_in_node(node, category.replacement_text)
            node_variations.append(node)
        # Original variation serves as default option
        self._replace_content_in_node(input_node, self.default_text())

        if self.has_node_for_other_category():
            # Original input_node becomes the "Other" variation
            node_variations.append(input_node)
            destination_uuids = [node["uuid"] for node in node_variations]
        else:
            # Ditch the first variation and use the original instead.
            # No variation for the "Other" category is added.
            node_variations = [input_node] + node_variations[1:]
            # We reroute the "Other" category to first node variation
            destination_uuids = [node["uuid"] for node in node_variations] + [node_variations[0]["uuid"]]

        # TODO: Special case if categories are empty -> unconditional replace
        switch_node = nt.get_switch_node(self, destination_uuids)
        first_node = switch_node
        all_nodes = [switch_node] + node_variations

        if self.assign_to_group():
            gadget = self._get_assigntogroup_gadget(first_node)
            first_node = gadget[0]
            all_nodes = gadget + all_nodes

        return FlowSnippet(all_nodes, node_variations, first_node["uuid"])


class ReplaceSavedValueFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_save_value(node)

    def _replace_content_in_node(self, node, text):
        action_index = self._matching_save_value_action_id(node)
        self._replace_saved_value(node, text, action_index)

    def _get_flow_snippet(self, node):
        return self._get_variation_tree_snippet(node)


class AssignToGroupBeforeSaveValueNodeFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_save_value(node)

    def _get_flow_snippet(self, node):
        gadget = self._get_assigntogroup_gadget(node)
        all_nodes = gadget + [node]
        return FlowSnippet(all_nodes, [node], gadget[0]["uuid"])


class AssignToGroupBeforeMsgNodeFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _get_flow_snippet(self, node):
        gadget = self._get_assigntogroup_gadget(node)
        all_nodes = gadget + [node]
        return FlowSnippet(all_nodes, [node], gadget[0]["uuid"])


class ReplaceBitOfTextFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._replace_text_in_message(node, text)

    def _get_flow_snippet(self, node):
        return self._get_variation_tree_snippet(node)


class ReplaceQuickReplyFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._replace_text_in_quick_replies(node, text)

    def _get_flow_snippet(self, node):
        return self._get_variation_tree_snippet(node)


class ReplaceFlowFlowEditOp(FlowEditOp):

    def _process_uuid_lookup(self, uuid_lookup):
        flow_name = self._default_text
        flow_uuid = uuid_lookup.lookup_flow(flow_name)
        if flow_uuid is None:
            logging.warning(self._debug_string + 'Flow ' + flow_name + ' does not exist.')
        self._default_text = { "uuid": flow_uuid, "name": flow_name, } 

    def add_category(self, category, uuid_lookup):
        flow_name = category.replacement_text
        flow_uuid = uuid_lookup.lookup_flow(flow_name)
        if flow_uuid is None:
            logging.warning(self._debug_string + 'Flow ' + flow_name + ' does not exist.')
        category.replacement_text = { "uuid": flow_uuid, "name": flow_name, }
        self._categories.append(category)

    def is_match_for_node(self, node):
        return self._matches_entered_flow(node)

    def _replace_content_in_node(self, node, text):
        self._replace_entered_flow(node, text)

    def _get_flow_snippet(self, node):
        return self._get_variation_tree_snippet(node)


# In the future, each class has an ID string, and the dict is autogenerated?
OPERATION_TYPES = {
    "replace_bit_of_text" : ReplaceBitOfTextFlowEditOp,
    "replace_quick_replies" : ReplaceQuickReplyFlowEditOp,
    "replace_saved_value" : ReplaceSavedValueFlowEditOp,
    "assign_to_group_before_msg_node" : AssignToGroupBeforeMsgNodeFlowEditOp,
    "assign_to_group_before_save_value_node" : AssignToGroupBeforeSaveValueNodeFlowEditOp,
    "replace_flow" : ReplaceFlowFlowEditOp,  # TODO: rename replace_entered_flow?
}