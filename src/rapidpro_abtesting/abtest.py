import copy
import logging
from abc import ABC, abstractmethod

from rapidpro_abtesting.contact_group import ContactGroup
from rapidpro_abtesting.operations import (
    FlowEditOp,
    TranslationEditOp,
    FLOWEDIT_OPERATION_TYPES,
    TRANSLATIONEDIT_OPERATION_TYPES
)


logger = logging.getLogger(__name__)


class SwitchCategory(object):
    def __init__(self, name, condition_type, condition_arguments, replacement_text):
        self.name = name
        self.condition_type = condition_type
        # If the condition type is has_group, there are 2 arguments: uuid and name
        # If not from an A/B test, we have to fill in the uuid upon construction.
        self.condition_arguments = condition_arguments
        # For enter_flow operations, this should be a dict
        # with keys "name" and "uuid" indicating the flow
        self.replacement_text = replacement_text

# Condition types which do not need (though some may have) condition arguments
NO_ARG_CONDITION_TYPES = [
    "has_date",
    "has_district",
    "has_email",
    "has_error",
    "has_number",
    "has_phone",
    "has_state",
    "has_text",
    "has_time",
    "has_ward",
]

class FlowSheet(ABC):
    # Column indices
    TYPE = 0
    FLOW_ID = 1
    ROW_ID = 2
    NODE_IDENTIFIER = 3

    OPERATION_TYPES = FLOWEDIT_OPERATION_TYPES

    def __init__(self, name, rows, config=None):
        '''
        Args:
            name (str): Name of the A/B test.
            rows (list of list): list of operations to be applied.
        '''

        self._name = name
        self._rows = rows
        self._config = config or {}

    def parse_rows(self, uuid_lookup):
        self._edit_ops = []
        self._uuid_lookup = uuid_lookup

        if self._rows[0][:len(self.FIXED_COLS)] != self.FIXED_COLS:
            logger.warning('ABTest {} has invalid header.'.format(self._name))
            return

        self._category_names = self._get_category_names(self._rows[0])
        if self._category_names is None:
            logger.warning('Omitting {} {}.'.format(type(self), self._name))
            return

        self._generate_group_pair()

        for i,row in enumerate(self._rows[1:]):
            edit_op = self._row_to_edit_op(row, i)
            if edit_op is not None:
                self._edit_ops.append(edit_op)

    def _get_operation_type(self, row, debug_string):
        if len(row) == 0:
            logger.warning(debug_string + 'empty row.')
            return None

        op_type_str = row[self.TYPE]
        if not op_type_str in self.OPERATION_TYPES:
            logger.warning(debug_string + 'invalid type.')
            return None

        return self.OPERATION_TYPES[op_type_str]

    def _convert_row_id_to_int(self, row):
        try:
            row[self.ROW_ID] = int(row[self.ROW_ID])
        except ValueError:
            row[self.ROW_ID] = -1

    def _generate_group_pair(self):
        pass

    def get_groups(self):
        return []

    def edit_ops(self):
        if not hasattr(self, '_edit_ops'):
            raise AttributeError("Uninitialized sheet. Call parse_rows() before accessing data.")
        return self._edit_ops

    def edit_op(self, index):
        return self.edit_ops()[index]

    @abstractmethod
    def _get_category_names(self, row):
        pass


class FlowEditSheet(FlowSheet):
    FIXED_COLS = [
        "type_of_edit",
        "flow_id",
        "original_row_id",
        "node_identifier",
        "change",
        "condition_var",
        "category",
    ]
    CATEGORY_PREFIXES = [
        "category:",
        "condition:",
        "condition_type:",
    ]
    # Column indices
    BIT_OF_TEXT = 4
    SPLIT_BY = 5
    DEFAULT_TEXT = 6
    CATEGORIES = 7

    def _get_category_names(self, row):
        category_names = []
        for cid in range(len(self.FIXED_COLS), len(row), len(self.CATEGORY_PREFIXES)):
            valid_prefixes = True
            names = []
            for col, prefix in zip(row[cid:cid + len(self.CATEGORY_PREFIXES)], self.CATEGORY_PREFIXES):
                if col.startswith(prefix):
                    names.append(col[len(prefix):])
                else:
                    valid_prefixes = False
                    break
            if not valid_prefixes:
                logger.warning(
                    f"FlowEditSheet {self._name} has invalid category header."
                )
                return None
            if len(set(names)) != 1:
                logger.warning(
                    f"FlowEditSheet {self._name} has category with inconsistent name in header row."
                )
                return None
            category_names.append(names[0])

        return category_names

    def _row_to_edit_op(self, row, index):
        debug_string = '{} {} row {}: '.format(type(self).__name__, self._name, index+2)
        op_type = self._get_operation_type(row, debug_string)
        if op_type is None:
            return None

        expected_col_count = (
            len(self.FIXED_COLS) +
            len(self.CATEGORY_PREFIXES) * len(self._category_names)
        )
        row_new = pad(copy.copy(row), expected_col_count)

        self._convert_row_id_to_int(row_new)

        # Unpack the row entries to create edit op
        edit_op = FlowEditOp.create_edit_op(
            *row_new[:self.CATEGORIES],
            debug_string,
            uuid_lookup=self._uuid_lookup,
            config=self._config,
        )

        for i, name in enumerate(self._category_names):
            condition_type = row[len(self.FIXED_COLS) + len(self.CATEGORY_PREFIXES) * i + 2]
            condition_arguments = [row[len(self.FIXED_COLS) + len(self.CATEGORY_PREFIXES) * i + 1]]
            if condition_arguments == [""] and condition_type in NO_ARG_CONDITION_TYPES:
                # For some condition_types "" is a valid and sensible argument, while for
                # others, in particular those that work without arguments, the intent is
                # likely to have no argument.
                condition_arguments = []
            replacement_text = row[len(self.FIXED_COLS) + len(self.CATEGORY_PREFIXES) * i]
            category = SwitchCategory(name, condition_type, condition_arguments, replacement_text)
            edit_op.add_category(category, self._uuid_lookup)
        return edit_op


class ABTest(FlowSheet):
    '''
    An A/B test to be applied to RapidPro flow(s).

    It has a name, a group pair representing the ContactGroups
    for the A side and B side of the test, and a list of
    `ABTestOps` to be applied to the flow(s).
    '''

    FIXED_COLS = [
        "type_of_edit",
        "flow_id",
        "original_row_id",
        "node_identifier",
        "change",
    ]
    # We don't require row[ASSIGN_TO_GROUP] == "assign_to_group"
    CATEGORY_PREFIXES = ["change:"]
    DEFAULT_CATEGORY_NAME = "Default"

    # Column indices
    A_CONTENT = 4
    B_CONTENT = 5
    CATEGORIES = 5
    ASSIGN_TO_GROUP = 6

    def _generate_group_pair(self):
        groupA_name = "ABTest_" + self._name + "_" + self.DEFAULT_CATEGORY_NAME
        groupB_name = "ABTest_" + self._name + "_" + self._category_names[0]
        groupA_uuid = self._uuid_lookup.lookup_group(groupA_name)
        groupB_uuid = self._uuid_lookup.lookup_group(groupB_name)
        groupA = ContactGroup(groupA_name, groupA_uuid)
        groupB = ContactGroup(groupB_name, groupB_uuid)
        self._group_pair = (groupA, groupB)


    def _get_category_names(self, row):
        # Lazy implementation. Only 2 groups supported right now.
        if not row[self.CATEGORIES].startswith(self.CATEGORY_PREFIXES[0]):
            logger.warning('ABTest {} has invalid group B header.'.format(self._name))
            return None
        return [row[self.CATEGORIES].split(':')[1]]


    def _row_to_edit_op(self, row, index):
        '''Convert the spreadsheet row into an ABTestOp.

        Tries to fix minor mistakes in the process.
        Returns None if the row is invalid.
        '''

        debug_string = '{} {} row {}: '.format(type(self).__name__, self._name, index+2)
        op_type = self._get_operation_type(row, debug_string)
        if op_type is None:
            return None

        n_required_cols = 6
        if not op_type.needs_parameter():
            n_required_cols = 4
        if len(row) < n_required_cols:
            logger.warning(debug_string + 'too few entries.')
            return None

        if len(row) > self.ASSIGN_TO_GROUP and row[self.ASSIGN_TO_GROUP] in ["TRUE", "true", "True", True]:
            assign_to_group = True
        else:
            assign_to_group = False

        row_new = copy.copy(row)
        if len(row_new) < 6:
            row_new = pad(row_new, 6)
        self._convert_row_id_to_int(row_new)

        edit_op = FlowEditOp.create_edit_op(
            row_new[self.TYPE],
            row_new[self.FLOW_ID],
            row_new[self.ROW_ID],
            row_new[self.NODE_IDENTIFIER],
            row_new[self.A_CONTENT],
            "@contact.groups",
            row_new[self.A_CONTENT],
            debug_string, False, assign_to_group,
            self._uuid_lookup,
            self._config,
        )

        a_content = row_new[self.A_CONTENT]
        b_content = row_new[self.B_CONTENT]
        groupA, groupB = self._group_pair
        categoryA = SwitchCategory(groupA.name, "has_group", [groupA.uuid, groupA.name], a_content)
        edit_op.add_category(categoryA, self._uuid_lookup)
        categoryB = SwitchCategory(groupB.name, "has_group", [groupB.uuid, groupB.name], b_content)
        edit_op.add_category(categoryB, self._uuid_lookup)

        return edit_op

    def groupA(self):
        '''ContactGroup for the A side of this test.'''
        return self.group_pair()[0]

    def groupB(self):
        '''ContactGroup for the B side of this test.'''
        return self.group_pair()[1]

    def group_pair(self):
        if not hasattr(self, '_group_pair'):
            raise AttributeError("Uninitialized sheet. Call parse_rows() before accessing data.")
        return self._group_pair

    def get_groups(self):
        return list(self._group_pair)


class TranslationEditSheet(FlowSheet):
    FIXED_COLS = [
        "type_of_edit",
        "flow_id",
        "original_row_id",
        "node_identifier",
        "original",
        "language",
        "replacement",
    ]
    # Column indices
    BIT_OF_TEXT = 4
    LANGUAGE = 5
    REPLACEMENT_TEXT = 6

    OPERATION_TYPES = TRANSLATIONEDIT_OPERATION_TYPES

    def _get_category_names(self, row):
        return []

    def _row_to_edit_op(self, row, index):
        debug_string = '{} {} row {}: '.format(type(self).__name__, self._name, index + 2)
        op_type = self._get_operation_type(row, debug_string)
        if op_type is None:
            return None

        row_new = pad(copy.copy(row), len(self.FIXED_COLS))
        self._convert_row_id_to_int(row_new)

        # Unpack the row entries to create edit op
        edit_op = TranslationEditOp.create_edit_op(
            *row_new[:len(self.FIXED_COLS)],
            debug_string,
            uuid_lookup=self._uuid_lookup,
            config=self._config,
        )
        return edit_op


def pad(row, n):
    return row + [''] * (n - len(row))
