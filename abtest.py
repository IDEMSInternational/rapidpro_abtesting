from contact_group import ContactGroup
import copy
from enum import Enum
import logging
from abc import ABC, abstractmethod
from operations import FlowEditOp, OPERATION_TYPES


class SwitchCategory(object):
    def __init__(self, name, condition_type, condition_arguments, replacement_text):
        self.name = name
        self.condition_type = condition_type
        self.condition_arguments = condition_arguments
         # -- note: has_group has uuid and name in arg list.
         #    Fill in uuid upon construction.
        self.replacement_text = replacement_text
 

class FlowSheet(ABC):
    # Column indices
    TYPE = 0
    FLOW_ID = 1
    ROW_ID = 2
    NODE_IDENTIFIER = 3

    def __init__(self, name, rows):
        '''
        Args:
            name (str): Name of the A/B test.
            rows (list of list): list of operations to be applied.
        '''

        self._name = name
        if rows[0][:type(self).N_FIXED_COLS] != type(self).FIXED_COLS:
            logging.warning('ABTest {} has invalid header.'.format(name))
            return

        self._category_names = self._get_category_names(rows[0])
        if self._category_names is None:
            logging.warning('Omitting {} {}.'.format(type(self), name))
            return

        self._generate_group_pair()

        self._edit_ops = []
        for i,row in enumerate(rows[1:]):
            edit_op = self._row_to_edit_op(row, i)
            if edit_op is not None:
                self._edit_ops.append(edit_op)

    def _get_operation_type(self, row, debug_string):
        if len(row) == 0:
            logging.warning(debug_string + 'empty row.')
            return None

        op_type_str = row[type(self).TYPE]
        if not op_type_str in OPERATION_TYPES:
            logging.warning(debug_string + 'invalid type.')
            return None

        return OPERATION_TYPES[op_type_str]

    def _convert_row_id_to_int(self, row):
        try:
            row[type(self).ROW_ID] = int(row[type(self).ROW_ID])
        except ValueError:
            # TODO: Log a warning once we actually use the ROW_ID
            row[type(self).ROW_ID] = -1

    def _generate_group_pair(self):
        pass

    @abstractmethod
    def edit_ops(self):
        pass

    @abstractmethod
    def edit_op(self, index):
        pass

    @abstractmethod
    def _get_category_names(self, row):
        pass


class FlowEditSheet(FlowSheet):
    FIXED_COLS = ["type_of_edit", "flow_id", "original_row_id", "node_identifier", "change", "condition_var", "category"]
    CATEGORY_PREFIXES = ["category:", "condition:", "condition_type:"]
    N_FIXED_COLS = len(FIXED_COLS)
    N_CATEGORY_PREFIXES = len(CATEGORY_PREFIXES)
    # Column indices
    BIT_OF_TEXT = 4
    SPLIT_BY = 5
    DEFAULT_TEXT = 6
    CATEGORIES = 7

    def _get_category_names(self, row):
        category_names = []
        for cid in range(type(self).N_FIXED_COLS, len(row), type(self).N_CATEGORY_PREFIXES):
            valid_prefixes = True
            names = []
            for col, prefix in zip(row[cid:cid+type(self).N_CATEGORY_PREFIXES], type(self).CATEGORY_PREFIXES):
                if col.startswith(prefix):
                    names.append(col[len(prefix):])
                else:
                    valid_prefixes = False
                    break
            if not valid_prefixes:
                logging.warning('FlowEditSheet {} has invalid category header.'.format(self._name))
                return None
            if len(set(names)) != 1:
                logging.warning('FlowEditSheet {} has category with inconsistent name in header row.'.format(self._name))
                return None
            category_names.append(names[0])

        if len(category_names) == 0:
            # TODO: This could be a valid use case.
            logging.warning('FlowEditSheet {} has no category in header row.'.format(self._name))
            return None
        return category_names

    def _row_to_edit_op(self, row, index):
        debug_string = '{} {} row {}: '.format(type(self), self._name, index+2)
        op_type = self._get_operation_type(row, debug_string)
        if op_type is None:
            return None

        if len(row) < type(self).N_FIXED_COLS + type(self).N_CATEGORY_PREFIXES * len(self._category_names):
            logging.warning(debug_string + 'too few entries.')
            return None

        row_new = copy.copy(row)
        self._convert_row_id_to_int(row_new)

        # Unpack the row entries to create edit op
        edit_op = FlowEditOp.create_edit_op(*row_new[:type(self).CATEGORIES], debug_string)

        for i, name in enumerate(self._category_names):
            # TODO: validate condition_type
            condition_type = row[type(self).N_FIXED_COLS + type(self).N_CATEGORY_PREFIXES * i + 2]
            condition_arguments = [row[type(self).N_FIXED_COLS + type(self).N_CATEGORY_PREFIXES * i + 1]]
            replacement_text = row[type(self).N_FIXED_COLS + type(self).N_CATEGORY_PREFIXES * i]
            category = SwitchCategory(name, condition_type, condition_arguments, replacement_text)
            edit_op.add_category(category)
        return edit_op

    def edit_ops(self):
        return self._edit_ops

    def edit_op(self, index):
        return self._edit_ops[index]


class ABTest(FlowSheet):
    '''
    An A/B test to be applied to RapidPro flow(s).

    It has a name, a group pair representing the ContactGroups
    for the A side and B side of the test, and a list of
    `ABTestOps` to be applied to the flow(s).
    '''

    FIXED_COLS = ["type_of_edit", "flow_id", "original_row_id", "node_identifier", "change"]
    # We don't require row[ASSIGN_TO_GROUP] == "assign_to_group"
    CATEGORY_PREFIXES = ["change:"]
    N_FIXED_COLS = len(FIXED_COLS)
    N_CATEGORY_PREFIXES = len(CATEGORY_PREFIXES)
    DEFAULT_CATEGORY_NAME = "Default"

    # Column indices
    A_CONTENT = 4
    B_CONTENT = 5
    CATEGORIES = 5
    ASSIGN_TO_GROUP = 6  # TODO: Change once we support >2 groups.

    def _generate_group_pair(self):
        groupA = ContactGroup("ABTest_" + self._name + "_" + type(self).DEFAULT_CATEGORY_NAME)
        groupB = ContactGroup("ABTest_" + self._name + "_" + self._category_names[0])
        self._group_pair = (groupA, groupB)


    def _get_category_names(self, row):
        # Lazy implementation. Only 2 groups supported right now.
        if not row[type(self).CATEGORIES].startswith(type(self).CATEGORY_PREFIXES[0]):
            logging.warning('ABTest {} has invalid group B header.'.format(name))
            return None
        return [row[type(self).CATEGORIES].split(':')[1]]


    def _row_to_edit_op(self, row, index):
        '''Convert the spreadsheet row into an ABTestOp.

        Tries to fix minor mistakes in the process.
        Returns None if the row is invalid.
        '''

        debug_string = '{} {} row {}: '.format(type(self), self._name, index+2)
        op_type = self._get_operation_type(row, debug_string)
        if op_type is None:
            return None

        n_required_cols = 6
        if not op_type.needs_parameter():
            n_required_cols = 4
        if len(row) < n_required_cols:
            logging.warning(debug_string + 'too few entries.')
            return None

        if len(row) > type(self).ASSIGN_TO_GROUP and row[type(self).ASSIGN_TO_GROUP] in ["TRUE", "true", "True", True]:
            assign_to_group = True
        else:
            assign_to_group = False

        row_new = copy.copy(row)
        if len(row_new) < 6:  # pad to full length
            row_new += [""] * (6 - len(row_new))
        self._convert_row_id_to_int(row_new)

        edit_op = FlowEditOp.create_edit_op(row_new[type(self).TYPE],
                                            row_new[type(self).FLOW_ID],
                                            row_new[type(self).ROW_ID],
                                            row_new[type(self).NODE_IDENTIFIER],
                                            row_new[type(self).A_CONTENT],
                                            "@contact.groups",
                                            row_new[type(self).A_CONTENT],     
                                            debug_string, False, assign_to_group)

        a_content = row_new[type(self).A_CONTENT]
        b_content = row_new[type(self).B_CONTENT]
        groupA, groupB = self._group_pair
        categoryA = SwitchCategory(groupA.name, "has_group", [groupA.uuid, groupA.name], a_content)
        edit_op.add_category(categoryA)
        categoryB = SwitchCategory(groupB.name, "has_group", [groupB.uuid, groupB.name], b_content)
        edit_op.add_category(categoryB)

        return edit_op

    def groupA(self):
        '''ContactGroup for the A side of this test.'''
        return self._group_pair[0]

    def groupB(self):
        '''ContactGroup for the B side of this test.'''
        return self._group_pair[1]

    def group_pair(self):
        return self._group_pair

    def edit_ops(self):
        return self._edit_ops

    def edit_op(self, index):
        return self._edit_ops[index]
