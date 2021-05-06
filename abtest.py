class ABTest(object):
    '''
    An A/B test to be applied to RapidPro flow(s).

    It has a name, and a table whose rows are operations
    to be applied to the flow(s).
    '''

    # Column indices
    TYPE = 0
    FLOW_ID = 1
    ROW_ID = 2
    ORIG_MSG = 3
    A_CONTENT = 4
    B_CONTENT = 5
    ASSIGN_TO_GROUP = 6

    def __init__(self, name, rows):
        '''
        TODO: In the future, allow loading from a sheet.

        Args:
            name (str): Name of the A/B test.
            rows (list of list): list of operations to be applied.
        '''
        self.name_ = name
        self.rows_ = rows
        self.check_valid()

    def check_valid(self):
        '''TODO: Implement validity check'''

        # Sheet header:
        # type    flow_id row_id  original_message    a_content(original) b_content assign_to_group
        pass

    def groupA_name(self):
        '''Name of the RapidPro contact group for the A side of this test.'''
        return "ABTest_" + self.name_ + "_A"

    def groupB_name(self):
        '''Name of the RapidPro contact group for the B side of this test.'''
        return "ABTest_" + self.name_ + "_B"

    def rows(self):
        return self.rows_


class ABTestOp(object):
    '''
    An individual operation to be applied to a component of a RapidPro flow,
    such as a node.

    Consists of a row defining the operation, and a pair of `ContactGroup`s
    which represent the A and B sides of the A/B test that this operation
    belongs to.
    '''

    def __init__(self, group_pair, row):
        self.group_pair_ = group_pair
        self.row_ = row

    def groupA(self):
        '''Name of the RapidPro contact group for the A side of this test.'''
        return self.group_pair_[0]

    def groupB(self):
        '''Name of the RapidPro contact group for the B side of this test.'''
        return self.group_pair_[1]

    def groupA_name(self):
        '''Name of the RapidPro contact group for the A side of this test.'''
        return self.group_pair_[0].name

    def groupB_name(self):
        '''Name of the RapidPro contact group for the B side of this test.'''
        return self.group_pair_[1].name

    def groupA_uuid(self):
        '''uuid of the RapidPro contact group for the A side of this test.'''
        return self.group_pair_[0].uuid

    def groupB_uuid(self):
        '''uuid of the RapidPro contact group for the B side of this test.'''
        return self.group_pair_[1].uuid

    def group_pair(self):
        return self.group_pair_

    def row(self, col_id):
        return self.row_[col_id]
