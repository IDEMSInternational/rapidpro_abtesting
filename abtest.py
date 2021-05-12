from contact_group import ContactGroup
import copy
from enum import Enum
import logging

# Column indices
TYPE = 0
FLOW_ID = 1
ROW_ID = 2
ORIG_MSG = 3
A_CONTENT = 4
B_CONTENT = 5
ASSIGN_TO_GROUP = 6

BIT_OF_TEXT = 4
SPLIT_BY = 5
DEFAULT_TEXT = 6
CATEGORIES = 7

class OpType(Enum):
    REPLACE_BIT_OF_TEXT = 1


class SwitchCategory(object):
    def __init__(self, name, condition_type, condition_arguments, replacement_text):
        self.name = name
        self.condition_type = condition_type
        self.condition_arguments = condition_arguments
         # -- note: has_group has uuid and name in arg list.
         #    Fill in uuid upon construction.
        self.replacement_text = replacement_text


class ABTest(object):
    '''
    An A/B test to be applied to RapidPro flow(s).

    It has a name, a group pair representing the ContactGroups
    for the A side and B side of the test, and a list of
    `ABTestOps` to be applied to the flow(s).
    '''

    # Dictionary of valid operation types
    op_types = {"replace_bit_of_text" : OpType.REPLACE_BIT_OF_TEXT}


    def __init__(self, name, rows):
        '''
        Args:
            name (str): Name of the A/B test.
            rows (list of list): list of operations to be applied.
        '''

        self.name_ = name
        groupA = ContactGroup("ABTest_" + self.name_ + "_A")
        groupB = ContactGroup("ABTest_" + self.name_ + "_B")
        self.group_pair_ = (groupA, groupB)
        self.test_ops_ = [] # Store ABTestOps instead of rows
        if not self.validate_header_row(rows[0]):
            logging.warning('ABTest {} has invalid header.'.format(name))
            return

        for i,row in enumerate(rows[1:]):
            test_op = self.row_to_abtestop(row, i)
            if test_op is not None:
                self.test_ops_.append(test_op)

    def validate_header_row(self, row):
        if len(row) < ASSIGN_TO_GROUP:
            return False
        return row[TYPE] == "type" and row[FLOW_ID] == "flow_id" and row[ROW_ID] == "row_id" and row[ORIG_MSG] == "original_message" and row[A_CONTENT] == "a_content(original)" and row[B_CONTENT] == "b_content"
        # We don't require row[ASSIGN_TO_GROUP] == "assign_to_group"

    def row_to_abtestop(self, row, index):
        '''Convert the spreadsheet row into an ABTestOp.

        Tries to fix minor mistakes in the process.
        Returns None if the row is invalid.
        '''

        row_new = copy.deepcopy(row)
        debug_string = 'ABTest {} row {}: '.format(self.name_, index+2)

        if len(row) < ASSIGN_TO_GROUP:
            logging.warning(debug_string + 'too few entries.')
            return None
        if len(row) == ASSIGN_TO_GROUP:
            row_new += [""]    # Last column may be blank

        if row[TYPE] in ABTest.op_types:
            row_new[TYPE] = ABTest.op_types[row[TYPE]]
        else:
            logging.warning(debug_string + 'invalid type.')
            return None

        try:  # Convert ROW_ID to int
            row_new[ROW_ID] = int(row[ROW_ID])
        except ValueError:
            row_new[ROW_ID] = -1
            # TODO: Log a warning once we use the ROW_ID

        if row_new[ASSIGN_TO_GROUP] == "TRUE" or row_new[ASSIGN_TO_GROUP] == "true" or row_new[ASSIGN_TO_GROUP] == "True" or row_new[ASSIGN_TO_GROUP] == True:
            row_new[ASSIGN_TO_GROUP] = True
        else:
            row_new[ASSIGN_TO_GROUP] = False

        return ABTestOp(self.group_pair_, row_new, debug_string)


    def groupA(self):
        '''ContactGroup for the A side of this test.'''
        return self.group_pair_[0]

    def groupB(self):
        '''ContactGroup for the B side of this test.'''
        return self.group_pair_[1]

    def group_pair(self):
        return self.group_pair_

    def test_ops(self):
        return self.test_ops_

    def test_op(self, index):
        return self.test_ops_[index]


class FlowEditOp(object):
    def __init__(self, row, split_by, default_text, debug_string):
        self._op_type = row[TYPE]
        self._flow_id = row[FLOW_ID]
        self._row_id = row[ROW_ID]
        self._orig_msg = row[ORIG_MSG]
        self._bit_of_text = row[BIT_OF_TEXT]
        self._split_by = split_by
        self._default_text = default_text
        self._categories = []
        self._debug_string = debug_string

    def add_category(self, category):
        self._categories.append(category)

    def debug_string(self):
        '''Returns a human-readable identifier of sheet/row of the FlowEditOp.'''
        return self._debug_string

    def op_type(self):
        return self._op_type

    def flow_id(self):
        return self._flow_id

    def row_id(self):
        return self._row_id

    def orig_msg(self):
        return self._orig_msg

    def bit_of_text(self):
        return self._bit_of_text

    def split_by(self):
        return self._split_by

    def default_text(self):
        return self._default_text

    def categories(self):
        return self._categories

    def assign_to_group(self):
        return False


class ABTestOp(FlowEditOp):
    '''
    An individual operation to be applied to a component of a RapidPro flow,
    such as a node.

    Consists of a row defining the operation, and a pair of `ContactGroup`s
    which represent the A and B sides of the A/B test that this operation
    belongs to.
    '''

    def __init__(self, group_pair, row, debug_string):
        super().__init__(row, "@contact.groups", row[A_CONTENT], debug_string)
        self._assign_to_group = row[ASSIGN_TO_GROUP]
        groupA, groupB = group_pair
        categoryA = SwitchCategory(groupA.name, "has_group", [groupA.uuid, groupA.name], row[A_CONTENT])
        self.add_category(categoryA)
        categoryB = SwitchCategory(groupB.name, "has_group", [groupB.uuid, groupB.name], row[B_CONTENT])
        self.add_category(categoryB)

    def groupA(self):
        '''ContactGroup for the A side of this test.'''
        return ContactGroup(self._categories[0].condition_arguments[1], 
                            self._categories[0].condition_arguments[0])

    def groupB(self):
        '''ContactGroup for the A side of this test.'''
        return ContactGroup(self._categories[1].condition_arguments[1], 
                            self._categories[1].condition_arguments[0]) 

    def group_pair(self):
        return (self.groupA(), self.groupB())

    def a_content(self):
        return self._categories[0].replacement_text

    def b_content(self):
        return self._categories[1].replacement_text

    def assign_to_group(self):
        return self._assign_to_group
