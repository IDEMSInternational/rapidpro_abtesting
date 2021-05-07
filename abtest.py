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


class OpType(Enum):
    REPLACE_BIT_OF_TEXT = 1


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


class ABTestOp(object):
    '''
    An individual operation to be applied to a component of a RapidPro flow,
    such as a node.

    Consists of a row defining the operation, and a pair of `ContactGroup`s
    which represent the A and B sides of the A/B test that this operation
    belongs to.
    '''

    def __init__(self, group_pair, row, debug_string):
        self.group_pair_ = group_pair
        self.row_ = row
        self.debug_string_ = debug_string

    def __eq__(self, other):
        """Equality currently ignores the ROW_ID as it is unused."""
        if isinstance(other, ABTestOp):
            return self.row_[:ROW_ID] + self.row_[:ORIG_MSG] == other.row_[:ROW_ID] + other.row_[:ORIG_MSG] and self.group_pair_ == other.group_pair_
        return False

    def groupA(self):
        '''ContactGroup for the A side of this test.'''
        return self.group_pair_[0]

    def groupB(self):
        '''ContactGroup for the B side of this test.'''
        return self.group_pair_[1]

    def group_pair(self):
        return self.group_pair_

    def op_type(self):
        return self.row_[TYPE]

    def flow_id(self):
        return self.row_[FLOW_ID]

    def row_id(self):
        return self.row_[ROW_ID]

    def orig_msg(self):
        return self.row_[ORIG_MSG]

    def a_content(self):
        return self.row_[A_CONTENT]

    def b_content(self):
        return self.row_[B_CONTENT]

    def assign_to_group(self):
        return self.row_[ASSIGN_TO_GROUP]

    def debug_string(self):
        '''Returns a human-readable identifier of sheet/row of the test_op.'''
        return self.debug_string_
