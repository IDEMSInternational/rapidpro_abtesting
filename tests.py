import unittest
import json

import node_tools as nt
from abtest import ABTest, ABTestOp, OpType
from rapidpro_abtest_creator import ContactGroup, RapidProABTestCreator
from testing_tools import traverse_flow, find_final_destination
from sheets import abtests_from_csvs
from contact_group import ContactGroup
import logging

logging.basicConfig(filename='tests.log', level=logging.WARNING, filemode='w')

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

test_node_3actions = {
    "uuid": "aa0028ce-6f67-4313-bdc1-c2dd249a227d",
    "actions": [
        {
            "attachments": [],
            "text": "The first personalizable message.",
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": [],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d"
        },
        {
            "attachments": [],
            "text": "Good morning!",
            "templating": {
                "uuid": "32c2ead6-3fa3-4402-8e27-9cc718175c5a",
                "template": {
                    "uuid": "3ce100b7-a734-4b4e-891b-350b1279ade2",
                    "name": "revive_issue"
                },
                "variables": [
                    "@contact.name"
                ]
            },
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": [],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d"
        },
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
        filename = "testdata/Linear_OneNodePerAction.json"
        with open(filename, "r") as rpfile:
            self.rp_json = json.load(rpfile)
            self.flow = self.rp_json["flows"][0]
        self.abtests = abtests_from_csvs(["testdata/Test1_Personalization.csv", "testdata/Test2_Some1337.csv"])


    def test_generate_node_variations(self):
        test_ops = [
            self.abtests[0].test_op(1),
            self.abtests[1].test_op(0),
        ]

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

    def test_generate_node_variations_multiple_actions(self):
        test_ops = [
            self.abtests[0].test_op(0),
            self.abtests[1].test_op(0),
        ]

        variations = nt.generate_node_variations(test_node_3actions, test_ops)
        nodes = [variation.node for variation in variations]
        self.assertEqual(nodes[0], test_node_3actions)  # First node should be original
        self.assertEqual(nodes[1]["actions"][0]["text"], "The first personalizable message.")
        self.assertEqual(nodes[2]["actions"][0]["text"], "The first personalizable message, Steve!")
        self.assertEqual(nodes[3]["actions"][0]["text"], "The first personalizable message, Steve!")
        self.assertEqual(nodes[1]["actions"][1]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][1]["text"], "Good morning!")
        self.assertEqual(nodes[3]["actions"][1]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[1]["actions"][2]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][2]["text"], "Good morning!")
        self.assertEqual(nodes[3]["actions"][2]["text"], "g00d m0rn1ng!")
        self.assertNotEqual(test_node_3actions["actions"][0]["uuid"], nodes[1]["actions"][0]["uuid"])
        self.assertNotEqual(test_node_3actions["actions"][1]["uuid"], nodes[1]["actions"][1]["uuid"])
        self.assertNotEqual(test_node_3actions["actions"][2]["uuid"], nodes[1]["actions"][2]["uuid"])
        self.assertNotEqual(test_node_3actions["actions"][1]["templating"]["uuid"], nodes[1]["actions"][1]["templating"]["uuid"])


    def test_generate_group_membership_tree(self):
        test_ops = [
            self.abtests[0].test_op(1),
            self.abtests[1].test_op(0),
        ]

        variations = nt.generate_node_variations(test_node, test_ops)
        root_uuid, tree_nodes = nt.generate_group_membership_tree(test_ops, variations)
        flow = {"nodes" : tree_nodes}
        root_node = nt.find_node_by_uuid(flow, root_uuid)
        # print(json.dumps(tree_nodes, indent=4))

        # Check that the branches of the tree lead to the correct variations.
        groupnamesAA = [test_ops[0].groupA().name, test_ops[1].groupA().name]
        groupnamesAB = [test_ops[0].groupA().name, test_ops[1].groupB().name]
        groupnamesBA = [test_ops[0].groupB().name, test_ops[1].groupA().name]
        groupnamesBB = [test_ops[0].groupB().name, test_ops[1].groupB().name]
        destAA = find_final_destination(flow, root_node, groupnamesAA)
        destAB = find_final_destination(flow, root_node, groupnamesAB)
        destBA = find_final_destination(flow, root_node, groupnamesBA)
        destBB = find_final_destination(flow, root_node, groupnamesBB)
        # Get unique, hashable representations of the groupname/destination pairs
        treeAA = (destAA, tuple(sorted(set(groupnamesAA))))
        treeAB = (destAB, tuple(sorted(set(groupnamesAB))))
        treeBA = (destBA, tuple(sorted(set(groupnamesBA))))
        treeBB = (destBB, tuple(sorted(set(groupnamesBB))))
        tree_matches = {treeAA, treeAB, treeBA, treeBB}
        
        variation_matches = set()
        for var in variations:
            var_groupnames = tuple(sorted({group.name for group in var.groups}))
            var_nodeuuid = var.node["uuid"]
            variation_matches.add((var_nodeuuid, var_groupnames))

        self.assertEqual(tree_matches, variation_matches)

    # def test_get_group_switch_node(self):
    #     test_op = self.abtests[0].test_op(1)
    #     switch = nt.get_group_switch_node(test_op, "dest1uuid", "dest2uuid")
    #     print(json.dumps(switch, indent=4))

    # def test_get_assign_to_group_gadget(self):
    #     test_op = self.abtests[0].test_op(1)
    #     switch = nt.get_assign_to_group_gadget(test_op, "destuuid")
    #     print(json.dumps(switch, indent=4))


class TestRapidProABTestCreatorMethods(unittest.TestCase):
    def setUp(self):
        filename = "testdata/Linear_OneNodePerAction.json"
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
    def setUp(self):
        self.abtests = abtests_from_csvs(["testdata/Test1_Personalization.csv", "testdata/Test2_Some1337.csv"])

    def test_apply_abtests_linear_onenodeperaction(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)
        self.evaluate_result(rpx)

    def test_apply_abtests_linear_twoactionspernode(self):
        filename = "testdata/Linear_TwoActionsPerNode.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)
        self.evaluate_result(rpx)

    def test_apply_abtests_linear_nodewith3actions(self):
        filename = "testdata/Linear_NodeWith3Actions.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)
        self.evaluate_result(rpx)

    def test_apply_abtests_linear_onenode4actions(self):
        filename = "testdata/Linear_OneNode4Actions.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)
        self.evaluate_result(rpx)

    def evaluate_result(self, rpx):
        exp1 = [
            ('send_msg', 'The first personalizable message.'),
            ('send_msg', 'Some generic message.'),
            ('send_msg', 'Good morning!'),
            ('send_msg', 'This is a test.'),
        ]
        exp2 = [
            ('send_msg', 'The first personalizable message.'),
            ('send_msg', 'Some generic message.'),
            ('send_msg', 'g00d m0rn1ng!'),
            ('send_msg', 'This is a test.'),
        ]
        exp3 = [
            ('send_msg', 'The first personalizable message, Steve!'),
            ('send_msg', 'Some generic message.'),
            ('send_msg', 'g00d m0rn1ng, Steve!'),
            ('send_msg', 'This is a test.'),
        ]
        exp4 = [
            ('send_msg', 'The first personalizable message, Steve!'),
            ('send_msg', 'Some generic message.'),
            ('send_msg', 'g00d m0rn1ng, Steve!'),
            ('send_msg', 'This is a test.'),
        ]

        # Traverse the flow with different group memberships and check the sent messages.
        flows = rpx.data_["flows"][0]
        msgs1 = traverse_flow(flows, [self.abtests[0].groupA().name, self.abtests[1].groupA().name])
        self.assertEqual(msgs1, exp1)
        msgs2 = traverse_flow(flows, [self.abtests[0].groupA().name, self.abtests[1].groupB().name])
        self.assertEqual(msgs2, exp2)
        msgs3 = traverse_flow(flows, [self.abtests[0].groupB().name, self.abtests[1].groupB().name])
        self.assertEqual(msgs3, exp3)
        msgs4 = traverse_flow(flows, [])  # "Other" branch. Should be same as msgs3
        self.assertEqual(msgs4, exp4)


if __name__ == '__main__':
    unittest.main()
