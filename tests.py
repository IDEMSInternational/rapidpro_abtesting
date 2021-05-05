import unittest
import json

import node_tools as nt
from abtest import ABTest, ABTestOp
from rapidpro_abtest_creator import ContactGroup, RapidProABTestCreator
from testing_tools import traverse_flow


test1_rows = [
    ["replace_bit_of_text","ABTesting_Pre",1,"The first personalizable message.","message.","message, Steve!",False],
    ["replace_bit_of_text","ABTesting_Pre",3,"Good morning!","Good morning!","Good morning, Steve!",False],
]

test2_rows = [
    ["replace_bit_of_text","ABTesting_Pre",3,"Good morning!","Good morning","g00d m0rn1ng",False],
]

abtest1 = ABTest("Personalization", test1_rows)
abtest2 = ABTest("Some1337Text", test2_rows)
abtests = [abtest1, abtest2]

group_pair1 = (ContactGroup(abtest1.groupA_name()), ContactGroup(abtest1.groupB_name()))
group_pair2 = (ContactGroup(abtest2.groupA_name()), ContactGroup(abtest2.groupB_name()))

test_ops = [
    ABTestOp(group_pair1, test1_rows[1]),
    ABTestOp(group_pair2, test2_rows[0]),
]


test_node = {
    "uuid": "aa0028ce-6f67-4313-bdc1-c2dd249a227d",
    "actions": [
        {
            "attachments": [],
            "text": "Good morning!",
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": [],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d"
        }
    ],
    "exits": [
        {
            "uuid": "f90de082-5409-4ce7-8e40-d649458215d2",
            "destination_uuid": "3f6c8241-5d52-4b5b-8ba5-0f8f8cfdc4a0"
        }
    ]
}


class TestNodeTools(unittest.TestCase):
    def setUp(self):
        filename = "testdata/LinearMessages.json"
        with open(filename, "r") as rpfile:
            self.rp_json = json.load(rpfile)
            self.flow = self.rp_json["flows"][0]

    def test_generate_node_variations(self):
        variations = nt.generate_node_variations(test_node, test_ops)
        nodes = [variation.node for variation in variations]
        self.assertEqual(len(variations), 4)
        self.assertEqual(nodes[0], test_node)  # First node should be original
        self.assertEqual(nodes[1]["actions"][0]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][0]["text"], "Good morning, Steve!")
        self.assertEqual(nodes[3]["actions"][0]["text"], "g00d m0rn1ng, Steve!")
        destination_uuid = test_node["exits"][0]["destination_uuid"]
        self.assertEqual(nodes[1]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertEqual(nodes[2]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertEqual(nodes[3]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertNotEqual(test_node["uuid"], nodes[1]["uuid"])
        self.assertNotEqual(test_node["actions"][0]["uuid"], nodes[1]["actions"][0]["uuid"])
        self.assertNotEqual(test_node["exits"][0]["uuid"], nodes[1]["exits"][0]["uuid"])
        # print(json.dumps([v.node for v in variations], indent=4))

    # def test_get_group_switch_node(self):
    #     switch = nt.get_group_switch_node(test_ops[0], "dest1uuid", "dest2uuid")
    #     print(json.dumps(switch, indent=4))

    # def test_get_assign_to_group_gadget(self):
    #     switch = nt.get_assign_to_group_gadget(test_ops[0], "destuuid")
    #     print(json.dumps(switch, indent=4))

    def test_generate_group_membership_tree(self):
        variations = nt.generate_node_variations(test_node, test_ops)
        # TODO(testing): Check order of the of the tree nodes
        # TODO(testing): Ensure consistent with order of variations
        root_uuid, tree_nodes = nt.generate_group_membership_tree(test_ops, variations)
        # print(json.dumps(tree, indent=4))


class TestRapidProABTestCreatorMethods(unittest.TestCase):
    def setUp(self):
        filename = "testdata/LinearMessages.json"
        self.rpx = RapidProABTestCreator(filename)

    def test_find_nodes(self):
        # A valid node in given flow with given text
        nodes1 = self.rpx.find_nodes_by_content("ABTesting_Pre", -1, 'Good morning!')
        self.assertEqual(nodes1, ['aa0028ce-6f67-4313-bdc1-c2dd249a227d'])
        # non-existing node text
        nodes2 = self.rpx.find_nodes_by_content("ABTesting_Pre", -1, 'LOL!')
        self.assertEqual(nodes2, [])
        # non-existing flow name
        nodes3 = self.rpx.find_nodes_by_content("Trololo", -1, 'Good morning!')
        self.assertEqual(nodes3, [])


class TestRapidProABTestCreator(unittest.TestCase):

    def test_apply_abtests(self):
        filename = "testdata/LinearMessages.json"
        # abtests = get_abtests()
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(abtests)

        # Traverse the flow with different group memberships and check the sent messages.
        msgs1 = traverse_flow(rpx.data_["flows"][0], [abtests[0].groupA_name(), abtests[1].groupA_name()])
        self.assertEqual(msgs1, ['The first personalizable message.', 'Some generic message.', 'Good morning!', 'This is a test.'])
        msgs2 = traverse_flow(rpx.data_["flows"][0], [abtests[0].groupA_name(), abtests[1].groupB_name()])
        self.assertEqual(msgs2, ['The first personalizable message.', 'Some generic message.', 'g00d m0rn1ng!', 'This is a test.'])
        msgs3 = traverse_flow(rpx.data_["flows"][0], [abtests[0].groupB_name(), abtests[1].groupB_name()])
        self.assertEqual(msgs3, ['The first personalizable message, Steve!', 'Some generic message.', 'g00d m0rn1ng, Steve!', 'This is a test.'])
        msgs4 = traverse_flow(rpx.data_["flows"][0], [])  # "Other" branch. Should be same as msgs3
        self.assertEqual(msgs4, ['The first personalizable message, Steve!', 'Some generic message.', 'g00d m0rn1ng, Steve!', 'This is a test.'])


if __name__ == '__main__':
    unittest.main()
