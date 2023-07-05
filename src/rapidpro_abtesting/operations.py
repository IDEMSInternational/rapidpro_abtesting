from abc import ABC, abstractmethod
import logging
from .node_tools import (
    find_incoming_edges,
    get_assign_to_fixed_group_gadget,
    get_assign_to_group_gadget,
    get_switch_node,
    get_unique_node_copy,
)
import re
import json
from .nodes_layout import NodesLayout, make_tree_layout
from .uuid_tools import generate_random_uuid

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

    def __init__(self, nodes, nodes_layout, node_variations, root_uuid=-1):
        self._nodes = nodes
        self._nodes_layout = nodes_layout
        self._node_variations = node_variations
        if root_uuid == -1:
            self._root_uuid = nodes[0]["uuid"]
        else:
            self._root_uuid = root_uuid

    def nodes(self):
        return self._nodes

    def nodes_layout(self):
        return self._nodes_layout

    def node_variations(self):
        return self._node_variations

    def root_uuid(self):
        return self._root_uuid


class GenericEditOp(ABC):
    # TODO: bit_of_text should be renamed to original_content (or content_to_replace),
    # default_text should be renamed to default_replacement_content.
    @classmethod
    def create_edit_op(cls, op_type, flow_id, row_id, node_identifier, bit_of_text,
                       split_by, default_text, debug_string,
                       has_node_for_other_category=True,
                       assign_to_group=False,
                       uuid_lookup=None, config=None):
        if op_type not in cls.get_operation_types():
            logging.warning(debug_string + 'invalid operation type.')
            return None
        class_name = cls.get_operation_types()[op_type]
        parsed_node_identifier = class_name.parse_node_identifier(node_identifier)
        if parsed_node_identifier is None:
            logging.warning(debug_string + 'invalid node identifier.')
            return None

        return class_name(flow_id, row_id, parsed_node_identifier, bit_of_text,
                          split_by, default_text, debug_string,
                          has_node_for_other_category, assign_to_group,
                          uuid_lookup, config)

    def __init__(self, flow_id, row_id, node_identifier, bit_of_text, split_by,
                 default_text, debug_string,
                 has_node_for_other_category=True,
                 assign_to_group=False,
                 uuid_lookup=None,
                 config=None):
        self._row_id = row_id
        if flow_id[:6].lower() == 'regex:':
            self._flow_id = flow_id[6:]
            self._flow_match_regex = True
        else:
            self._flow_id = flow_id
            self._flow_match_regex = False
        if type(node_identifier) == str and node_identifier[:6].lower() == 'regex:':
            self._node_identifier = node_identifier[6:]
            self._node_match_regex = True
        else:
            self._node_identifier = node_identifier
            self._node_match_regex = False
        self._debug_string = debug_string
        self._bit_of_text = bit_of_text
        self._default_text = default_text
        self._config = config or {}

    @classmethod
    @abstractmethod
    def get_operation_types(cls):
        pass

    @abstractmethod
    def apply_operation(self, flow, node):
        pass

    @abstractmethod
    def is_match_for_node(self, node):
        pass

    def _process_uuid_lookup(self, uuid_lookup):
        pass

    def parse_node_identifier(node_identifier):
        '''Return parsed node identifier or None if it is invalid.'''
        return node_identifier

    def debug_string(self):
        '''Returns a human-readable identifier of sheet/row of the FlowEditOp.'''
        return self._debug_string

    def flow_id(self):
        return self._flow_id

    def row_id(self):
        return self._row_id

    def node_identifier(self):
        return self._node_identifier

    def bit_of_text(self):
        return self._bit_of_text

    def default_text(self):
        return self._default_text

    def matches_unique_flow(self):
        return not self._flow_match_regex

    def is_match_for_flow(self, flow_name):
        if self._flow_match_regex:
            return bool(re.fullmatch(self._flow_id, flow_name))
        else:
            return flow_name == self._flow_id

    def matches_unique_node_identifier(self):
        return not self._node_match_regex

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
        '''Ignores whitespace differences by replacing groups of
        whitespace with a single space and stipping whitespace
        from the beginning and end of the text.'''
        return re.sub(r'\s+', ' ', text1).strip() == re.sub(r'\s+', ' ', text2).strip()

    def _matches_message_text(self, node):
        # TODO: Check row_id once implemented
        # TODO: If there are multiple exits, warn and return False
        result = False
        for action in node["actions"]:
            if action["type"] == "send_msg":
                if self._node_match_regex:
                    result |= bool(re.fullmatch(self.node_identifier(), action["text"], flags=re.DOTALL))
                else:
                    result |= self._lenient_text_match(action["text"], self.node_identifier())
        return result

    def _construct_match_cases(self, node):
        router = node["router"]
        cases = []
        for node_case in router["cases"]:
            category = next(cat for cat in router["categories"] if cat["uuid"] == node_case["category_uuid"])
            case = {
                "type" : node_case["type"],
                "arguments" : node_case["arguments"],
                "category_name" : category["name"]
            }
            cases.append(case)
        return cases

    def _matches_wait_for_response_cases(self, node):
        if "router" not in node:
            return False
        router = node["router"]
        if "wait" not in router or router["type"] != "switch" or not router["operand"].startswith("@input"):
            return False

        cases = self._construct_match_cases(node)
        return cases == self.node_identifier()

    def _matches_switch_router_identifier(self, node):
        if "router" not in node:
            return False
        router = node["router"]
        if router["type"] != "switch":
            return False
        cases = self._construct_match_cases(node)
        match_router = {"operand" : router["operand"], "cases" : cases}

        return match_router == self.node_identifier()

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


class FlowEditOp(GenericEditOp):
    @classmethod
    def get_operation_types(cls):
        return FLOWEDIT_OPERATION_TYPES

    def needs_parameter():
        '''Does this operation read a value from the "change" column?'''
        return True

    def __init__(self, flow_id, row_id, node_identifier, bit_of_text, split_by,
                 default_text, debug_string,
                 has_node_for_other_category=True,
                 assign_to_group=False,
                 uuid_lookup=None,
                 config=None):
        super().__init__(flow_id, row_id, node_identifier, bit_of_text,
                         split_by, default_text, debug_string,
                         has_node_for_other_category, assign_to_group,
                         uuid_lookup, config)
        self._split_by = split_by
        self._categories = []
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

    def apply_operation(self, flow, node):
        '''Apply the operation to a given node.

        Replaces the node with an appropriate flow snippet.

        Returns:
            list of nodes: variations of the input node that further
                operations can be applied to.
        '''

        uuid = node["uuid"]
        node_is_entrypoint = flow["nodes"][0]["uuid"] == uuid
        incoming_edges = find_incoming_edges(flow, uuid)

        flow["nodes"].remove(node)
        nodes_layout = NodesLayout(flow.get("_ui", dict()).get("nodes"))
        node_layout = nodes_layout.get_node(uuid)
        snippet = self._get_flow_snippet(node, node_layout)
        nodes_layout.replace(uuid, snippet.nodes_layout())
        if "_ui" in flow:
            flow["_ui"]["nodes"] = nodes_layout.layout()

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

    def split_by(self):
        return self._split_by

    def categories(self):
        return self._categories

    def assign_to_group(self):
        return self._assign_to_group  # to be removed

    def has_node_for_other_category(self):
        return self._has_node_for_other_category

    @abstractmethod
    def _get_flow_snippet(self, node, node_layout=None):
        pass

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

    def _replace_switch_router_operand(self, node, value):
        node["router"]["operand"] = value

    def _replace_text_in_message(self, node, replacement_text):
        '''Modifies the input node by replacing message text.'''
        total_occurrences = 0
        for action in node["actions"]:
            if action["type"] == "send_msg":
                text = action["text"]
                total_occurrences += text.count(self.bit_of_text())
                text_new = text.replace(self.bit_of_text(), replacement_text)
                action["text"] = text_new
        # TODO: If we don't just store the node uuid, but also action uuid
        #   where edit_op is applicable, we could give more helpful
        #   messages here by referring to the action text that doesn't match
        if total_occurrences == 0:
            # This might happen if we're trying to replace text that has
            # already had a replacement applied to it.
            logging.warning(self.debug_string() + 'No occurrences of "{}" found node.'.format(self.bit_of_text()))
        if total_occurrences >= 2:
            logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node.'.format(self.bit_of_text()))

    def _prepend_send_msg_action(self, node, replacement_text):
        action = {
            "type": "send_msg",
            "text": replacement_text,
            "attachments": [],
            "quick_replies": [],
            "all_urns": False,
            "uuid": generate_random_uuid()
        }
        node["actions"].insert(0, action)

    def _replace_entered_flow(self, node, replacement_text):
        if self._matches_entered_flow(node):
            # TODO: Also UUID
            node["actions"][0]["flow"] = replacement_text
        else:
            logging.warning(self.debug_string() + 'No occurrences of "{}" found in node.'.format(self.bit_of_text()))

    def _replace_in_action_list_field(self, node, replacement_text, action_field):
        '''Modifies the input node by replacing the content of a list-field
        (whose name is specified in action_field) in an action of a send_msg node.

        Args:
            replacement_text (str): Semicolon separated list of values to replace
                the original values with.
        '''

        for bit_of_text, repl_text in zip(self._bit_of_text.split(';'), replacement_text.split(';')):
            total_occurrences = 0
            for action in node["actions"]:
                if action["type"] == "send_msg":
                    for i, text in enumerate(action[action_field]):
                        total_occurrences += text.count(bit_of_text)
                        text_new = text.replace(bit_of_text, repl_text)
                        action[action_field][i] = text_new
            if total_occurrences == 0:
                logging.warning(self.debug_string() + 'No occurrences of "{}" found node.'.format(bit_of_text))
            if total_occurrences >= 2:
                logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node.'.format(bit_of_text))

    def _replace_text_in_quick_replies(self, node, replacement_text):
        self._replace_in_action_list_field(node, replacement_text, "quick_replies")

    def _replace_attachments(self, node, replacement_text):
        self._replace_in_action_list_field(node, replacement_text, "attachments")

    def _replace_wait_for_response_cases(self, node, replacement_text):
        '''Modifies the input node by replacing the content of a list-field
        (whose name is specified in action_field) in an action of a send_msg node.

        Args:
            replacement_text (str): JSON string encoding a list of cases.
                Each case is a dict with fields "category_name", "type", "arguments".
        '''

        try:
            replacement_cases = json.loads(replacement_text)
        except ValueError:
            logging.warning(self.debug_string() + 'Malformed replacement value "{}" (should be JSON).'.format(replacement_text))
            return
        if type(replacement_cases) != list or len(replacement_cases) != len(node["router"]["cases"]):
            logging.warning(self.debug_string() + 'Replacement should be list of length {} but is "{}".'.format(len(node["router"]["cases"]), replacement_text))
            return
        for case, node_case in zip(replacement_cases, node["router"]["cases"]):
            if not {"category_name", "type", "arguments"}.issubset(case.keys()):
                logging.warning(self.debug_string() + 'Skipping invalid replacement case "{}".'.format(case))
                continue
            category = next(cat for cat in node["router"]["categories"] if cat["uuid"] == node_case["category_uuid"])
            category["name"] = case["category_name"]
            node_case["type"] = case["type"]
            node_case["arguments"] = case["arguments"]

    def _get_assigntogroup_gadget(self, node):
        if len(self.categories()) != 2:
            logging.warning(self.debug_string() + 'assign_to_group only for A/B tests (i.e. 2 groups).')
            return None, None
        groupA_uuid = self.categories()[0].condition_arguments[0]
        groupA_name = self.categories()[0].condition_arguments[1]
        groupB_uuid = self.categories()[1].condition_arguments[0]
        groupB_name = self.categories()[1].condition_arguments[1]
        group_assignment = self._config.get("group_assignment", "random")
        if group_assignment == "always A":
            gadget, gadget_layout = get_assign_to_fixed_group_gadget(groupA_name, groupA_uuid, node["uuid"])
        elif group_assignment == "always B":
            gadget, gadget_layout = get_assign_to_fixed_group_gadget(groupB_name, groupB_uuid, node["uuid"])
        else:  # group_assignment == "random":
            gadget, gadget_layout = get_assign_to_group_gadget(groupA_name, groupA_uuid, groupB_name, groupB_uuid, node["uuid"])

        return gadget, NodesLayout(gadget_layout)

    def _get_assigntogroup_snippet(self, node, node_layout):
        gadget, gadget_layout = self._get_assigntogroup_gadget(node)
        if gadget is None:
            return self._get_noop_snippet(node, node_layout)
        all_nodes = gadget + [node]
        if node_layout is not None:
            gadget_layout.insert_after(node["uuid"], node_layout)
        else:
            gadget_layout = NodesLayout()
        return FlowSnippet(all_nodes, gadget_layout, [node], gadget[0]["uuid"])

    def _get_noop_snippet(self, node, node_layout):
        return FlowSnippet([node], node_layout, [node], node["uuid"])

    def _get_variation_tree_snippet(self, input_node, node_layout):
        node_variations = []
        for category in self.categories():
            node = get_unique_node_copy(input_node)
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

        if len(node_variations) == 1:
            # If there is only one possible outcome -> unconditional replace
            first_node = input_node
            all_nodes = node_variations
            full_layout = NodesLayout.from_single_node_layout(input_node["uuid"], node_layout)
        else:
            # Otherwise insert a switch
            switch_node = get_switch_node(self, destination_uuids)
            first_node = switch_node
            all_nodes = [switch_node] + node_variations
            full_layout = make_tree_layout(self.split_by, switch_node["uuid"], node_variations, node_layout)

        if self.assign_to_group():
            gadget, gadget_layout = self._get_assigntogroup_gadget(first_node)
            if gadget is not None:
                first_node = gadget[0]
                all_nodes = gadget + all_nodes
                gadget_layout.merge(full_layout)
                full_layout = gadget_layout

        return FlowSnippet(all_nodes, full_layout, node_variations, first_node["uuid"])


class ReplaceSavedValueFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_save_value(node)

    def _replace_content_in_node(self, node, text):
        action_index = self._matching_save_value_action_id(node)
        self._replace_saved_value(node, text, action_index)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class AssignToGroupBeforeSaveValueNodeFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_save_value(node)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_assigntogroup_snippet(node, node_layout)


class AssignToGroupBeforeMsgNodeFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_assigntogroup_snippet(node, node_layout)


class ReplaceBitOfTextFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._replace_text_in_message(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class ReplaceQuickReplyFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._replace_text_in_quick_replies(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class ReplaceAttachmentsFlowEditOp(FlowEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._replace_attachments(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


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

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class ReplaceWaitForResponseCasesFlowEditOp(FlowEditOp):

    def parse_node_identifier(node_identifier):
        try:
            return json.loads(node_identifier)
        except ValueError:
            return None

    def is_match_for_node(self, node):
        return self._matches_wait_for_response_cases(node)

    def _replace_content_in_node(self, node, text):
        self._replace_wait_for_response_cases(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class ReplaceSplitOperandFlowEditOp(FlowEditOp):

    def parse_node_identifier(node_identifier):
        try:
            return json.loads(node_identifier)
        except ValueError:
            return None

    def is_match_for_node(self, node):
        return self._matches_switch_router_identifier(node)

    def _replace_content_in_node(self, node, text):
        self._replace_switch_router_operand(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class PrependSendMsgActionFlowEditOp(FlowEditOp):
    
    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_content_in_node(self, node, text):
        self._prepend_send_msg_action(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


class PrependSendMsgActionToSaveValueNodeFlowEditOp(FlowEditOp):

    def needs_parameter():
        return False

    def is_match_for_node(self, node):
        return self._matches_save_value(node)

    def _replace_content_in_node(self, node, text):
        self._prepend_send_msg_action(node, text)

    def _get_flow_snippet(self, node, node_layout=None):
        return self._get_variation_tree_snippet(node, node_layout)


# In the future, each class has an ID string, and the dict is autogenerated?
FLOWEDIT_OPERATION_TYPES = {
    "replace_bit_of_text" : ReplaceBitOfTextFlowEditOp,
    "replace_quick_replies" : ReplaceQuickReplyFlowEditOp,
    "replace_attachments" : ReplaceAttachmentsFlowEditOp,
    "replace_saved_value" : ReplaceSavedValueFlowEditOp,
    "assign_to_group_before_msg_node" : AssignToGroupBeforeMsgNodeFlowEditOp,
    "assign_to_group_before_save_value_node" : AssignToGroupBeforeSaveValueNodeFlowEditOp,
    "replace_flow" : ReplaceFlowFlowEditOp,  # TODO: rename replace_entered_flow?
    "replace_wait_for_response_cases" : ReplaceWaitForResponseCasesFlowEditOp,
    "replace_split_operand" : ReplaceSplitOperandFlowEditOp,
    "prepend_send_msg_action" : PrependSendMsgActionFlowEditOp,
    "prepend_send_msg_action_to_save_value_node" : PrependSendMsgActionToSaveValueNodeFlowEditOp,
}


class TranslationEditOp(GenericEditOp):
    @classmethod
    def get_operation_types(cls):
        return TRANSLATIONEDIT_OPERATION_TYPES

    def __init__(self, flow_id, row_id, node_identifier, bit_of_text, split_by,
                 default_text, debug_string,
                 has_node_for_other_category=True,
                 assign_to_group=False,
                 uuid_lookup=None,
                 config=None):
        super().__init__(flow_id, row_id, node_identifier, bit_of_text,
                         split_by, default_text, debug_string,
                         has_node_for_other_category, assign_to_group,
                         uuid_lookup, config)
        self._language = split_by

    @abstractmethod
    def _replace_translation(self, localization, node):
        pass

    def apply_operation(self, flow, node):
        localization = flow.get("localization", {}).get(self._language)
        if not localization:
            logging.warning(f'{self._debug_string} Flow {flow["name"]} has no localization for language {self._language}.')
            [node]

        self._replace_translation(localization, node)
        return [node]

    def _replace_text_in_message(self, localization, node):
        # TODO: Code duplication with FlowEditOp
        total_occurrences = 0
        for action in node["actions"]:
            if action["type"] == "send_msg":
                tr_action = localization.get(action["uuid"])
                if not tr_action:
                    logging.warning(self.debug_string() + f'Translation of action "{action["uuid"]}" does not exist.')
                    continue
                if not "text" in tr_action:
                    logging.warning(self.debug_string() + f'Translation of action "{action["uuid"]}" has no text.')
                    continue
                text = tr_action["text"][0]  # not sure why in translations the text is a list.
                total_occurrences += text.count(self.bit_of_text())
                text_new = text.replace(self.bit_of_text(), self.default_text())
                tr_action["text"][0] = text_new
        # TODO: If we don't just store the node uuid, but also action uuid
        #   where edit_op is applicable, we could give more helpful
        #   messages here by referring to the action text that doesn't match
        if total_occurrences == 0:
            # This might happen if we're trying to replace text that has
            # already had a replacement applied to it.
            logging.warning(self.debug_string() + 'No occurrences of "{}" found node translation.'.format(self.bit_of_text()))
        if total_occurrences >= 2:
            logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node translation.'.format(self.bit_of_text()))

    def _replace_in_action_list_field(self, localization, node, action_field):
        # TODO: Code duplication with FlowEditOp
        for bit_of_text, repl_text in zip(self.bit_of_text().split(';'), self.default_text().split(';')):
            total_occurrences = 0
            for action in node["actions"]:
                if action["type"] == "send_msg":
                    tr_action = localization.get(action["uuid"])
                    if not tr_action:
                        logging.warning(self.debug_string() + f'Translation of action "{action["uuid"]}" does not exist.')
                        continue
                    if not "text" in tr_action:
                        logging.warning(self.debug_string() + f'Translation of action "{action["uuid"]}" has no {action_field}.')
                        continue
                    for i, text in enumerate(tr_action[action_field]):
                        total_occurrences += text.count(bit_of_text)
                        text_new = text.replace(bit_of_text, repl_text)
                        tr_action[action_field][i] = text_new
            if total_occurrences == 0:
                logging.warning(self.debug_string() + 'No occurrences of "{}" found node translation.'.format(bit_of_text))
            if total_occurrences >= 2:
                logging.warning(self.debug_string() + 'Multiple occurrences of "{}" found in node translation.'.format(bit_of_text))

    def _replace_text_in_quick_replies(self, localization, node):
        self._replace_in_action_list_field(localization, node, "quick_replies")

    def _replace_attachments(self, localization, node):
        self._replace_in_action_list_field(localization, node, "attachments")

    def _replace_wait_for_response_cases(self, localization, node):
        '''Modifies the input node by replacing the content of a list-field
        (whose name is specified in action_field) in an action of a send_msg node.

        Args:
            replacement_text (str): JSON string encoding a list of cases.
                Each case is a dict with fields "category_name", "type", "arguments".
        '''
        replacement_text = self.default_text()
        try:
            replacement_cases = json.loads(replacement_text)
        except ValueError:
            logging.warning(self.debug_string() + 'Malformed replacement value "{}" (should be JSON).'.format(replacement_text))
            return
        if type(replacement_cases) != list or len(replacement_cases) != len(node["router"]["cases"]):
            logging.warning(self.debug_string() + 'Replacement should be list of length {} but is "{}".'.format(len(node["router"]["cases"]), replacement_text))
            return
        for case, node_case in zip(replacement_cases, node["router"]["cases"]):
            # TODO: Don't ignore bit of text
            if not {"arguments"}.issubset(case.keys()):
                logging.warning(self.debug_string() + 'No case arguments provided for tranlsation "{}".'.format(case))
            else:
                tr_case = localization.get(node_case["uuid"])
                if not tr_case:
                    logging.warning(self.debug_string() + f'Translation of case "{node_case["uuid"]}" does not exist.')
                elif not "arguments" in tr_case:
                    logging.warning(self.debug_string() + f'Translation of case "{node_case["uuid"]}" has no arguments.')
                else:
                    for i, arg in enumerate(case["arguments"]):
                        if i < len(tr_case["arguments"]):
                            # There's a bug in RapidPro where the translation only has the first argument
                            tr_case["arguments"][i] = arg

            if not {"category_name"}.issubset(case.keys()):
                logging.warning(self.debug_string() + 'No category name for tranlsation "{}".'.format(case))
                continue
            node_category = next(cat for cat in node["router"]["categories"] if cat["uuid"] == node_case["category_uuid"])
            tr_category = localization.get(node_category["uuid"])
            if not tr_category:
                logging.warning(self.debug_string() + f'Translation of category "{node_category["uuid"]}" does not exist.')
                continue
            if not "name" in tr_category:
                logging.warning(self.debug_string() + f'Translation of category "{node_category["uuid"]}" has no name.')
                continue
            tr_category["name"][0] = case["category_name"]


class ReplaceBitOfTextTranslationEditOp(TranslationEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_translation(self, localization, node):
        self._replace_text_in_message(localization, node)


class ReplaceQuickReplyTranslationEditOp(TranslationEditOp):

    def is_match_for_node(self, node):
        return self._matches_message_text(node)

    def _replace_translation(self, localization, node):
        self._replace_text_in_quick_replies(localization, node)


class ReplaceWaitForResponseCasesTranslationEditOp(TranslationEditOp):

    def parse_node_identifier(node_identifier):
        try:
            return json.loads(node_identifier)
        except ValueError:
            return None

    def is_match_for_node(self, node):
        return self._matches_wait_for_response_cases(node)

    def _replace_translation(self, localization, node):
        self._replace_wait_for_response_cases(localization, node)


TRANSLATIONEDIT_OPERATION_TYPES = {
    "replace_bit_of_text" : ReplaceBitOfTextTranslationEditOp,
    "replace_quick_replies" : ReplaceQuickReplyTranslationEditOp,
    "replace_wait_for_response_cases" : ReplaceWaitForResponseCasesTranslationEditOp,
}