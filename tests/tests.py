import copy
import json
import logging
import unittest

from rapidpro_abtesting.node_tools import (
    find_node_by_uuid,
    get_assign_to_group_gadget,
    get_assign_to_fixed_group_gadget,
    get_localizable_uuids,
    get_switch_node,
    get_unique_node_copy,
)
from rapidpro_abtesting.abtest import SwitchCategory
from rapidpro_abtesting.rapidpro_abtest_creator import (
    RapidProABTestCreator,
    apply_editops_to_node,
)
from .testing_tools import traverse_flow, find_final_destination, Context
from rapidpro_abtesting.sheets import (
    abtest_from_csv,
    floweditsheet_from_csv,
    translationeditsheet_from_csv,
    CSVMasterSheetParser,
    JSONMasterSheetParser,
)
from rapidpro_abtesting.uuid_tools import UUIDLookup
from rapidpro_abtesting.operations import (
    FlowEditOp,
    RemoveAttachmentsFlowEditOp,
    ReplaceAttachmentsFlowEditOp,
    ReplaceFlowFlowEditOp,
    ReplaceQuickReplyFlowEditOp,
    ReplaceSavedValueFlowEditOp,
    ReplaceWaitForResponseCasesFlowEditOp,
)
from rapidpro_abtesting.nodes_layout import NodesLayout, make_tree_layout

logging.basicConfig(filename="tests.log", level=logging.WARNING, filemode="w")

test_node = {
    "uuid": "aa0028ce-6f67-4313-bdc1-c2dd249a227d",
    "actions": [
        {
            "attachments": [
                'image:@(fields.image_path & "parent_and_baby.jpg")',
                "image:https://i.imgur.com/TQZFqMq.jpeg",
                'audio:@(fields.voiceover_audio_path & "Crying.mp3")',
            ],
            "text": "Good morning!",
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": ["Yes", "Maybe", "No"],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d",
        }
    ],
    "exits": [
        {"uuid": "f90de082-5409-4ce7-8e40-d649458215d2", "destination_uuid": None}
    ],
}

test_node_layout = {"position": {"left": 1000, "top": 100}, "type": "execute_actions"}

test_value_actions_node = {
    "uuid": "aa0028ce-6f67-4313-bdc1-c2dd249a227d",
    "actions": [
        {
            "type": "set_contact_name",
            "uuid": "8eebd020-1af5-431c-b943-aa670fc74da1",
            "name": "Bob Smith",
        },
        {
            "type": "set_contact_language",
            "uuid": "8eebd020-1af5-431c-b943-aa670fc74da2",
            "language": "eng",
        },
        {
            "type": "set_contact_field",
            "uuid": "8eebd020-1af5-431c-b943-aa670fc74da3",
            "field": {"key": "variable", "name": "Variable"},
            "value": "some value",
        },
        {
            "type": "set_run_result",
            "uuid": "8eebd020-1af5-431c-b943-aa670fc74da9",
            "name": "Result Number 1",
            "value": "some result",
            "category": "",
        },
    ],
    "exits": [
        {"uuid": "f90de082-5409-4ce7-8e40-d649458215d2", "destination_uuid": None}
    ],
}

test_enter_flow_node = {
    "uuid": "d489fd26-a58d-4548-89e0-ab7c2daad202",
    "actions": [
        {
            "uuid": "beb6f42d-2f22-4ca5-be26-bf87575298de",
            "type": "enter_flow",
            "flow": {
                "uuid": "085b194c-8fb0-4362-bff8-1203a2c12162",
                "name": "Flow Name",
            },
        }
    ],
    "router": {
        "type": "switch",
        "operand": "@child.run.status",
        "cases": [
            {
                "uuid": "3054699c-e41a-475f-bbdd-88c5dd26df43",
                "type": "has_only_text",
                "arguments": ["completed"],
                "category_uuid": "6a63f69e-f0f5-41f8-83ac-fd9d386e2e79",
            },
            {
                "uuid": "889c2c76-7e4a-43ae-9ada-00a92b579dff",
                "arguments": ["expired"],
                "type": "has_only_text",
                "category_uuid": "af5bf685-fae4-4464-9080-6cf34976cbcf",
            },
        ],
        "categories": [
            {
                "uuid": "6a63f69e-f0f5-41f8-83ac-fd9d386e2e79",
                "name": "Complete",
                "exit_uuid": "a4d2b9ac-8e55-4fa3-b730-07259d2ce629",
            },
            {
                "uuid": "af5bf685-fae4-4464-9080-6cf34976cbcf",
                "name": "Expired",
                "exit_uuid": "9dd40439-052a-4739-847e-4af30dad7c62",
            },
        ],
        "default_category_uuid": "af5bf685-fae4-4464-9080-6cf34976cbcf",
    },
    "exits": [
        {
            "uuid": "a4d2b9ac-8e55-4fa3-b730-07259d2ce629",
            "destination_uuid": "aa0028ce-6f67-4313-bdc1-c2dd249a227d",
        },
        {"uuid": "9dd40439-052a-4739-847e-4af30dad7c62", "destination_uuid": None},
    ],
}

test_wait_for_response_node = {
    "uuid": "5dddd554-88f9-4895-b752-4bb8086ba3ec",
    "actions": [],
    "router": {
        "type": "switch",
        "default_category_uuid": "ee53d915-a6f2-4d3f-b0a3-f3a46d042c64",
        "cases": [
            {
                "arguments": ["good"],
                "type": "has_any_word",
                "uuid": "b46a5865-532f-4b1d-98e2-2ef5dba188e3",
                "category_uuid": "3aab634e-f329-48c1-99a8-83b7e56c9d3c",
            },
            {
                "arguments": [],
                "type": "has_email",
                "uuid": "fed77203-c1d5-479c-85d6-95ee9a1ba710",
                "category_uuid": "67a6c351-3deb-4c01-ac49-cfe9cc1085d5",
            },
            {
                "arguments": ["40", "60"],
                "type": "has_number_between",
                "uuid": "97579ab6-6c65-491c-bd20-5a200a8d37c6",
                "category_uuid": "ff454f86-0786-4d6b-b98e-e8b537a0c24e",
            },
        ],
        "categories": [
            {
                "uuid": "3aab634e-f329-48c1-99a8-83b7e56c9d3c",
                "name": "Good",
                "exit_uuid": "1da1dd9c-0f52-4ab6-97fa-ef8653385287",
            },
            {
                "uuid": "67a6c351-3deb-4c01-ac49-cfe9cc1085d5",
                "name": "Email",
                "exit_uuid": "34c29388-06a9-43a6-8c93-ce5224fcf81e",
            },
            {
                "uuid": "ff454f86-0786-4d6b-b98e-e8b537a0c24e",
                "name": "Number around 50",
                "exit_uuid": "06a5a541-2b5a-499b-92e4-a44ea5742be3",
            },
            {
                "uuid": "ee53d915-a6f2-4d3f-b0a3-f3a46d042c64",
                "name": "Other",
                "exit_uuid": "f00b9d62-6d33-4ccf-ae2a-ca76c5492777",
            },
        ],
        "operand": "@input.text",
        "wait": {"type": "msg"},
        "result_name": "Result 1",
    },
    "exits": [
        {
            "uuid": "1da1dd9c-0f52-4ab6-97fa-ef8653385287",
            "destination_uuid": "5775606a-4b7a-4f76-adb8-cece6ba3038d",
        },
        {
            "uuid": "34c29388-06a9-43a6-8c93-ce5224fcf81e",
            "destination_uuid": "7f294a83-a2a5-4174-88e5-81ca420fe6f3",
        },
        {
            "uuid": "06a5a541-2b5a-499b-92e4-a44ea5742be3",
            "destination_uuid": "7f294a83-a2a5-4174-88e5-81ca420fe6f3",
        },
        {
            "uuid": "f00b9d62-6d33-4ccf-ae2a-ca76c5492777",
            "destination_uuid": "064339b6-0499-47f2-aca6-6c3ac117839c",
        },
    ],
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
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d",
        },
        {
            "attachments": [],
            "text": "Good morning!",
            "templating": {
                "uuid": "32c2ead6-3fa3-4402-8e27-9cc718175c5a",
                "template": {
                    "uuid": "3ce100b7-a734-4b4e-891b-350b1279ade2",
                    "name": "revive_issue",
                },
                "variables": ["@contact.name"],
            },
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": [],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d",
        },
        {
            "attachments": [],
            "text": "Good morning!",
            "type": "send_msg",
            "all_urns": False,
            "quick_replies": [],
            "uuid": "72d69a5d-ba85-4b94-81a1-e550ee43758d",
        },
    ],
    "exits": [
        {
            "uuid": "f90de082-5409-4ce7-8e40-d649458215d2",
            "destination_uuid": "3f6c8241-5d52-4b5b-8ba5-0f8f8cfdc4a0",
        }
    ],
}


class TestNodeTools(unittest.TestCase):
    def setUp(self):
        abtest1 = abtest_from_csv("testdata/Test1_Personalization.csv")
        abtest2 = abtest_from_csv("testdata/Test2_Some1337.csv")
        self.abtests = [abtest1, abtest2]
        self.floweditsheet = floweditsheet_from_csv("testdata/FlowEdit1_Gender.csv")
        abtest1.parse_rows(UUIDLookup())
        abtest2.parse_rows(UUIDLookup())
        self.floweditsheet.parse_rows(UUIDLookup())

    def test_get_unique_node_copy(self):
        copied = get_unique_node_copy(test_enter_flow_node)
        # Ensure all relevant uuids have been replaced
        self.assertNotEqual(copied["uuid"], test_enter_flow_node["uuid"])
        for a1, a2 in zip(copied["actions"], test_enter_flow_node["actions"]):
            self.assertNotEqual(a1, a2)
        for a1, a2 in zip(copied["exits"], test_enter_flow_node["exits"]):
            self.assertNotEqual(a1, a2)
        for a1, a2 in zip(
            copied["router"]["cases"], test_enter_flow_node["router"]["cases"]
        ):
            self.assertNotEqual(a1, a2)
        for a1, a2 in zip(
            copied["router"]["categories"], test_enter_flow_node["router"]["categories"]
        ):
            self.assertNotEqual(a1, a2)

        # Make sure identical uuids have been replaced consistently
        flow = {"nodes": [copied, test_node]}
        msgs1 = traverse_flow(
            flow, Context(variables={"@child.run.status": "completed"})
        )
        exp1 = [("enter_flow", "Flow Name"), ("send_msg", "Good morning!")]
        self.assertEqual(msgs1, exp1)

        msgs2 = traverse_flow(flow, Context())
        exp2 = [("enter_flow", "Flow Name")]
        self.assertEqual(msgs2, exp2)

    def test_get_group_switch_node(self):
        test_op = self.abtests[0].edit_op(1)
        switch = get_switch_node(test_op, ["dest1uuid", "dest2uuid", "dest2uuid"])
        flow = {"nodes": [switch]}
        dest1 = find_final_destination(
            flow, switch, Context([self.abtests[0].groupA().name])
        )
        dest2 = find_final_destination(
            flow, switch, Context([self.abtests[0].groupB().name])
        )
        dest3 = find_final_destination(flow, switch, Context())
        self.assertEqual(dest1, "dest1uuid")
        self.assertEqual(dest2, "dest2uuid")
        self.assertEqual(dest3, "dest2uuid")
        # print(json.dumps(switch, indent=4))

    def test_get_switch_node(self):
        test_op = self.floweditsheet.edit_op(0)
        switch = get_switch_node(test_op, ["dest1uuid", "dest2uuid", "dest3uuid"])
        flow = {"nodes": [switch]}
        dest1 = find_final_destination(
            flow, switch, Context(variables={"@fields.gender": "man"})
        )
        dest2 = find_final_destination(
            flow, switch, Context(variables={"@fields.gender": "woman"})
        )
        dest3 = find_final_destination(
            flow, switch, Context(variables={"@fields.gender": "something"})
        )
        dest4 = find_final_destination(flow, switch, Context())
        self.assertEqual(dest1, "dest1uuid")
        self.assertEqual(dest2, "dest2uuid")
        self.assertEqual(dest3, "dest3uuid")
        self.assertEqual(dest4, "dest3uuid")
        # print(json.dumps(switch, indent=4))

    def test_get_assign_to_group_gadget(self):
        gadget, gadget_ui = get_assign_to_group_gadget(
            "GAname", "GAuuid", "GBname", "BGuuid", "destuuid"
        )
        flow = {"nodes": gadget}
        context1 = Context(random_choices=[0])
        find_final_destination(flow, gadget[0], context1)
        self.assertEqual(len(context1.group_names), 1)
        self.assertEqual(context1.group_names[0], "GAname")
        context2 = Context(random_choices=[1])
        find_final_destination(flow, gadget[0], context2)
        self.assertEqual(len(context2.group_names), 1)
        self.assertEqual(context2.group_names[0], "GBname")
        # print(json.dumps(gadget, indent=4))

    def test_get_assign_to_fixed_group_gadget(self):
        gadget, gadget_ui = get_assign_to_fixed_group_gadget(
            "GAname", "GAuuid", "destuuid"
        )
        flow = {"nodes": gadget}
        context1 = Context(random_choices=[0])
        find_final_destination(flow, gadget[0], context1)
        self.assertEqual(len(context1.group_names), 1)
        self.assertEqual(context1.group_names[0], "GAname")
        context2 = Context(random_choices=[1])
        find_final_destination(flow, gadget[0], context2)
        self.assertEqual(len(context2.group_names), 1)
        self.assertEqual(context2.group_names[0], "GAname")
        # print(json.dumps(gadget, indent=4))


class TestOperations(unittest.TestCase):
    def setUp(self):
        abtest1 = abtest_from_csv("testdata/Test1_Personalization.csv")
        abtest2 = abtest_from_csv("testdata/Test2_Some1337.csv")
        abtest1.parse_rows(UUIDLookup())
        abtest2.parse_rows(UUIDLookup())
        self.abtests = [abtest1, abtest2]
        # Same as test_node, but with exit pointing to None.
        self.test_node_x = copy.deepcopy(test_node)
        self.test_node_x["exits"][0]["destination_uuid"] = None

    def test_apply_replace_bit_of_text(self):
        edit_op = self.abtests[1].edit_op(0)
        flow_snippet = edit_op._get_flow_snippet(self.test_node_x)
        self.assertEqual(len(flow_snippet.node_variations()), 2)
        self.assertEqual(
            flow_snippet.node_variations()[0],
            self.test_node_x,
            "First node should be original",
        )

        # Turn snippet into complete flow and simulate it.
        flow = {"nodes": flow_snippet.nodes()}
        groupsA = [self.abtests[1].groupA().name]
        msgs1 = traverse_flow(flow, Context(groupsA))
        self.assertEqual(msgs1, [("send_msg", "Good morning!")])
        groupsB = [self.abtests[1].groupB().name]
        msgs2 = traverse_flow(flow, Context(groupsB))
        self.assertEqual(msgs2, [("send_msg", "g00d m0rn1ng!")])
        msgs3 = traverse_flow(flow, Context())
        self.assertEqual(msgs3, [("send_msg", "Good morning!")])

    def test_apply_replace_bit_of_text_0categories(self):
        row = ["replace_bit_of_text", "", 0, "Good Morning!", "Good", "", "OK"]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        # edit_op.add_category(SwitchCategory("Cat1", "has_text", "", 'OK'))
        flow_snippet = edit_op._get_flow_snippet(self.test_node_x)
        self.assertEqual(len(flow_snippet.nodes()), 1)
        flow = {"nodes": flow_snippet.nodes()}
        msgs1 = traverse_flow(flow, Context())
        self.assertEqual(msgs1, [("send_msg", "OK morning!")])

    def test_apply_replace_bit_of_text_1category(self):
        row = ["replace_bit_of_text", "", 0, "Good Morning!", "Good", "", "OK"]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "Ignored Value"))
        flow_snippet = edit_op._get_flow_snippet(self.test_node_x)
        self.assertEqual(len(flow_snippet.nodes()), 1)
        flow = {"nodes": flow_snippet.nodes()}
        msgs1 = traverse_flow(flow, Context())
        self.assertEqual(msgs1, [("send_msg", "OK morning!")])

    def test_apply_replace_quick_replies(self):
        row = [
            "replace_quick_replies",
            "",
            0,
            "Good morning!",
            "Yes;No",
            "",
            "Yeah;Nay",
        ]
        edit_op = FlowEditOp.create_edit_op(*row, "debug_str")
        self.assertEqual(type(edit_op), ReplaceQuickReplyFlowEditOp)
        input_node = copy.deepcopy(test_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        quick_replies = flow_snippet.node_variations()[0]["actions"][0]["quick_replies"]
        quick_replies_exp = ["Yeah", "Maybe", "Nay"]
        self.assertEqual(quick_replies, quick_replies_exp)

    def test_apply_replace_attachments(self):
        orig_str = 'image:@(fields.image_path & "parent_and_baby.jpg");"Crying.mp3"'
        repl_str = 'image:@(fields.image_path & "mother_and_baby.jpg");"Happy.mp3"'
        row = ["replace_attachments", "", 0, "Good morning!", orig_str, "", repl_str]
        edit_op = FlowEditOp.create_edit_op(*row, "debug_str")
        self.assertEqual(type(edit_op), ReplaceAttachmentsFlowEditOp)
        input_node = copy.deepcopy(test_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        attachments = flow_snippet.node_variations()[0]["actions"][0]["attachments"]
        attachments_exp = [
            'image:@(fields.image_path & "mother_and_baby.jpg")',
            "image:https://i.imgur.com/TQZFqMq.jpeg",
            'audio:@(fields.voiceover_audio_path & "Happy.mp3")',
        ]
        self.assertEqual(attachments, attachments_exp)

    def test_apply_remove_attachments(self):
        orig_str = 'image:@(fields.image_path & "parent_and_baby.jpg");"Crying.mp3"'
        row = ["remove_attachments", "", 0, "Good morning!", orig_str, "", ""]
        edit_op = FlowEditOp.create_edit_op(*row, "debug_str")
        self.assertEqual(type(edit_op), RemoveAttachmentsFlowEditOp)
        input_node = copy.deepcopy(test_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        attachments = flow_snippet.node_variations()[0]["actions"][0]["attachments"]
        attachments_exp = [
            "image:https://i.imgur.com/TQZFqMq.jpeg",
        ]
        self.assertEqual(attachments, attachments_exp)

    def test_apply_replace_wait_for_response_cases(self):
        matching_cases = """[
            {"category_name": "Good", "type": "has_any_word", "arguments": ["good"]},
            {"category_name": "Email", "type": "has_email", "arguments": []},
            {
                "category_name": "Number around 50",
                "arguments": [40, 60],
                "type": "has_number_between"
            }
        ]"""
        replacement_1 = matching_cases
        replacement_2 = """[
            {
                "category_name": "Some stuff",
                "type": "has_phrase",
                "arguments": ["some stuff"]
            },
            {"category_name": "Ok", "type": "has_any_word", "arguments": ["OK"]},
            {"category_name": "Meh", "type": "has_any_word", "arguments": ["meh"]}
        ]"""
        row = [
            "replace_wait_for_response_cases",
            "",
            0,
            matching_cases,
            replacement_1,
            "",
            replacement_2,
        ]
        edit_op = FlowEditOp.create_edit_op(*row, "debug_str")
        self.assertEqual(type(edit_op), ReplaceWaitForResponseCasesFlowEditOp)
        input_node = copy.deepcopy(test_wait_for_response_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        replacement_2_list = json.loads(replacement_2)
        router = flow_snippet.node_variations()[0]["router"]
        self.assertEqual(router["cases"][0]["type"], replacement_2_list[0]["type"])
        self.assertEqual(router["cases"][1]["type"], replacement_2_list[1]["type"])
        self.assertEqual(router["cases"][2]["type"], replacement_2_list[2]["type"])
        self.assertEqual(
            router["cases"][0]["arguments"], replacement_2_list[0]["arguments"]
        )
        self.assertEqual(
            router["cases"][1]["arguments"], replacement_2_list[1]["arguments"]
        )
        self.assertEqual(
            router["cases"][2]["arguments"], replacement_2_list[2]["arguments"]
        )
        matching_cats = list(
            filter(
                lambda cat: cat["uuid"] == router["cases"][0]["category_uuid"],
                router["categories"],
            )
        )
        self.assertEqual(
            matching_cats[0]["name"], replacement_2_list[0]["category_name"]
        )
        matching_cats = list(
            filter(
                lambda cat: cat["uuid"] == router["cases"][1]["category_uuid"],
                router["categories"],
            )
        )
        self.assertEqual(
            matching_cats[0]["name"], replacement_2_list[1]["category_name"]
        )
        matching_cats = list(
            filter(
                lambda cat: cat["uuid"] == router["cases"][2]["category_uuid"],
                router["categories"],
            )
        )
        self.assertEqual(
            matching_cats[0]["name"], replacement_2_list[2]["category_name"]
        )

    def test_apply_replace_saved_value_1(self):
        row = [
            "replace_saved_value",
            "",
            0,
            "@fields.variable",
            "some value",
            "@fields.flag",
            "some value",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "new value"))
        self.assertEqual(type(edit_op), ReplaceSavedValueFlowEditOp)

        input_node = copy.deepcopy(test_value_actions_node)
        action_index = edit_op._matching_save_value_action_id(input_node)
        self.assertEqual(action_index, 2)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 2)
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][action_index]["value"],
            "new value",
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][action_index]["value"],
            "some value",
        )

    def test_apply_replace_saved_value_2(self):
        row = [
            "replace_saved_value",
            "",
            0,
            "@contact.name",
            "Bob Smith",
            "@fields.flag",
            "Bobby",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "Steve"))
        self.assertEqual(type(edit_op), ReplaceSavedValueFlowEditOp)

        input_node = copy.deepcopy(test_value_actions_node)
        action_index = edit_op._matching_save_value_action_id(input_node)
        self.assertEqual(action_index, 0)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 2)
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][action_index]["name"], "Steve"
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][action_index]["name"], "Bobby"
        )

    def test_apply_replace_saved_value_3(self):
        row = [
            "replace_saved_value",
            "",
            0,
            "@contact.language",
            "eng",
            "@fields.flag",
            "eng",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "spa"))  # Ignored
        edit_op.add_category(SwitchCategory("Cat2", "has_text", "", "fin"))
        self.assertEqual(type(edit_op), ReplaceSavedValueFlowEditOp)

        input_node = copy.deepcopy(test_value_actions_node)
        action_index = edit_op._matching_save_value_action_id(input_node)
        self.assertEqual(action_index, 1)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 2)
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][action_index]["language"],
            "eng",
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][action_index]["language"],
            "fin",
        )

    def test_apply_replace_saved_value_4(self):
        row = [
            "replace_saved_value",
            "",
            0,
            "@results.result_number_1",
            "some result",
            "@fields.flag",
            "123Default",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "Cat1999"))
        edit_op.add_category(SwitchCategory("Cat2", "has_text", "", "Cat2999"))
        self.assertEqual(type(edit_op), ReplaceSavedValueFlowEditOp)

        input_node = copy.deepcopy(test_value_actions_node)
        action_index = edit_op._matching_save_value_action_id(input_node)
        self.assertEqual(action_index, 3)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 3)
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][action_index]["value"],
            "Cat1999",
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][action_index]["value"],
            "Cat2999",
        )
        self.assertEqual(
            flow_snippet.node_variations()[2]["actions"][action_index]["value"],
            "123Default",
        )

    def test_apply_replace_flow(self):
        uuid_lookup = UUIDLookup()
        uuid_lookup.add_flow("Flow Name", "085b194c-8fb0-4362-bff8-1203a2c12162")
        uuid_lookup.add_flow("Dummy Flow", "some_legit_uuid")
        row = [
            "replace_flow",
            "",
            0,
            "Flow Name",
            "Flow Name",
            "@fields.flag",
            "Flow Name",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True, uuid_lookup=uuid_lookup
        )
        edit_op.add_category(
            SwitchCategory("Cat1", "has_text", "", "Dummy Flow"), uuid_lookup
        )
        edit_op.add_category(
            SwitchCategory("Cat2", "has_text", "", "Missing Flow"), uuid_lookup
        )
        self.assertEqual(type(edit_op), ReplaceFlowFlowEditOp)

        input_node = copy.deepcopy(test_enter_flow_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 3)
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][0]["flow"]["name"],
            "Dummy Flow",
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][0]["flow"]["name"],
            "Missing Flow",
        )
        self.assertEqual(
            flow_snippet.node_variations()[2]["actions"][0]["flow"]["name"], "Flow Name"
        )
        self.assertEqual(
            flow_snippet.node_variations()[0]["actions"][0]["flow"]["uuid"],
            "some_legit_uuid",
        )
        self.assertEqual(
            flow_snippet.node_variations()[1]["actions"][0]["flow"]["uuid"], None
        )
        self.assertEqual(
            flow_snippet.node_variations()[2]["actions"][0]["flow"]["uuid"],
            "085b194c-8fb0-4362-bff8-1203a2c12162",
        )

    def test_assign_to_group_before_save_value_node(self):
        row = [
            "assign_to_group_before_save_value_node",
            "",
            0,
            "@fields.variable",
            "some value",
            "",
            "",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False
        )
        edit_op.add_category(SwitchCategory("CatA", "has_group", ["", "GroupA"], ""))
        edit_op.add_category(SwitchCategory("CatB", "has_group", ["", "GroupB"], ""))

        input_node = copy.deepcopy(test_value_actions_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        self.assertEqual(flow_snippet.node_variations()[0], test_value_actions_node)

        # Turn snippet into complete flow and simulate it.
        flow = {"nodes": flow_snippet.nodes()}
        exp_common = [
            ("set_contact_name", "Bob Smith"),
            ("set_contact_language", "eng"),
            ("set_contact_field", "Variable"),
            ("set_run_result", "Result Number 1"),
        ]
        msgs1 = traverse_flow(flow, Context(["GroupA"]))
        self.assertEqual(msgs1, exp_common)
        msgs2 = traverse_flow(flow, Context(random_choices=[0]))
        self.assertEqual(msgs2, [("add_contact_groups", "GroupA")] + exp_common)
        msgs3 = traverse_flow(flow, Context(random_choices=[1]))
        self.assertEqual(msgs3, [("add_contact_groups", "GroupB")] + exp_common)

    def test_assign_to_fixed_group_before_save_value_node(self):
        row = [
            "assign_to_group_before_save_value_node",
            "",
            0,
            "@fields.variable",
            "some value",
            "",
            "",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row,
            "debug_str",
            has_node_for_other_category=False,
            config={"group_assignment": "always B"},
        )
        edit_op.add_category(SwitchCategory("CatA", "has_group", ["", "GroupA"], ""))
        edit_op.add_category(SwitchCategory("CatB", "has_group", ["", "GroupB"], ""))

        input_node = copy.deepcopy(test_value_actions_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 1)
        self.assertEqual(flow_snippet.node_variations()[0], test_value_actions_node)

        # Turn snippet into complete flow and simulate it.
        flow = {"nodes": flow_snippet.nodes()}
        exp_common = [
            ("add_contact_groups", "GroupB"),
            ("set_contact_name", "Bob Smith"),
            ("set_contact_language", "eng"),
            ("set_contact_field", "Variable"),
            ("set_run_result", "Result Number 1"),
        ]
        msgs1 = traverse_flow(flow, Context(["GroupA"]))
        self.assertEqual(msgs1, exp_common)
        msgs2 = traverse_flow(flow, Context(random_choices=[0]))
        self.assertEqual(msgs2, exp_common)
        msgs3 = traverse_flow(flow, Context(random_choices=[1]))
        self.assertEqual(msgs3, exp_common)

    def test_prepend_send_msg_action_to_save_value_node(self):
        row = [
            "prepend_send_msg_action_to_save_value_node",
            "",
            0,
            "@fields.variable",
            "ignored value",
            "@contact.groups",
            "Msg Q",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(
            SwitchCategory("CatA", "has_group", ["", "GroupA"], "Msg A")
        )
        edit_op.add_category(
            SwitchCategory("CatB", "has_group", ["", "GroupB"], "Msg B")
        )

        input_node = copy.deepcopy(test_value_actions_node)
        flow_snippet = edit_op._get_flow_snippet(input_node)
        self.assertEqual(len(flow_snippet.node_variations()), 3)

        # Turn snippet into complete flow and simulate it.
        flow = {"nodes": flow_snippet.nodes()}
        exp_common = [
            ("set_contact_name", "Bob Smith"),
            ("set_contact_language", "eng"),
            ("set_contact_field", "Variable"),
            ("set_run_result", "Result Number 1"),
        ]
        msgs2 = traverse_flow(flow, Context())
        self.assertEqual(msgs2, [("send_msg", "Msg Q")] + exp_common)
        msgs2 = traverse_flow(flow, Context(["GroupA"]))
        self.assertEqual(msgs2, [("send_msg", "Msg A")] + exp_common)
        msgs3 = traverse_flow(flow, Context(["GroupB"]))
        self.assertEqual(msgs3, [("send_msg", "Msg B")] + exp_common)


class TestRapidProABTestCreatorMethods(unittest.TestCase):
    def setUp(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        self.rpx = RapidProABTestCreator(filename)
        abtest1 = abtest_from_csv("testdata/Test1_Personalization.csv")
        abtest2 = abtest_from_csv("testdata/Test2_Some1337.csv")
        abtest1.parse_rows(UUIDLookup())
        abtest2.parse_rows(UUIDLookup())
        self.abtests = [abtest1, abtest2]

    def make_minimal_test_op(self, flow_name, row_id, text_content):
        dummy_row = [
            "replace_bit_of_text",
            flow_name,
            row_id,
            text_content,
            "",
            "",
            "",
            "",
        ]
        return FlowEditOp.create_edit_op(*dummy_row, "Debug_str")

    def test_find_nodes(self):
        # A valid node in given flow with given text
        nodes1 = self.rpx._find_matching_nodes(
            self.make_minimal_test_op("ABTesting_Pre", -1, "Good morning!")
        )
        self.assertEqual(nodes1, ["aa0028ce-6f67-4313-bdc1-c2dd249a227d"])
        # non-existing node text
        nodes2 = self.rpx._find_matching_nodes(
            self.make_minimal_test_op("ABTesting_Pre", -1, "LOL!")
        )
        self.assertEqual(nodes2, [])
        # non-existing flow name
        nodes3 = self.rpx._find_matching_nodes(
            self.make_minimal_test_op("Trololo", -1, "Good morning!")
        )
        self.assertEqual(nodes3, [])

    def test_generate_node_variations(self):
        test_ops = [
            self.abtests[0].edit_op(1),
            self.abtests[1].edit_op(0),
        ]

        flow = {"nodes": [copy.deepcopy(test_node)]}
        nodes = apply_editops_to_node(flow, flow["nodes"][0], test_ops)
        self.assertEqual(len(nodes), 4)
        self.assertEqual(nodes[0], test_node)  # First node should be original
        self.assertEqual(nodes[1]["actions"][0]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][0]["text"], "Good morning, Steve!")
        self.assertEqual(nodes[3]["actions"][0]["text"], "g00d m0rn1ng, Steve!")
        destination_uuid = test_node["exits"][0]["destination_uuid"]
        self.assertEqual(nodes[1]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertEqual(nodes[2]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertEqual(nodes[3]["exits"][0]["destination_uuid"], destination_uuid)
        self.assertNotEqual(test_node["uuid"], nodes[1]["uuid"])
        self.assertNotEqual(
            test_node["actions"][0]["uuid"], nodes[1]["actions"][0]["uuid"]
        )
        self.assertNotEqual(test_node["exits"][0]["uuid"], nodes[1]["exits"][0]["uuid"])
        # print(json.dumps([v.node for v in variations], indent=4))

    def test_generate_node_variations_multiple_actions(self):
        test_ops = [
            self.abtests[0].edit_op(0),
            self.abtests[1].edit_op(0),
        ]

        flow = {"nodes": [copy.deepcopy(test_node_3actions)]}
        nodes = apply_editops_to_node(flow, flow["nodes"][0], test_ops)
        self.assertEqual(nodes[0], test_node_3actions)  # First node should be original
        self.assertEqual(
            nodes[1]["actions"][0]["text"], "The first personalizable message."
        )
        self.assertEqual(
            nodes[2]["actions"][0]["text"], "The first personalizable message, Steve!"
        )
        self.assertEqual(
            nodes[3]["actions"][0]["text"], "The first personalizable message, Steve!"
        )
        self.assertEqual(nodes[1]["actions"][1]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][1]["text"], "Good morning!")
        self.assertEqual(nodes[3]["actions"][1]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[1]["actions"][2]["text"], "g00d m0rn1ng!")
        self.assertEqual(nodes[2]["actions"][2]["text"], "Good morning!")
        self.assertEqual(nodes[3]["actions"][2]["text"], "g00d m0rn1ng!")
        self.assertNotEqual(
            test_node_3actions["actions"][0]["uuid"], nodes[1]["actions"][0]["uuid"]
        )
        self.assertNotEqual(
            test_node_3actions["actions"][1]["uuid"], nodes[1]["actions"][1]["uuid"]
        )
        self.assertNotEqual(
            test_node_3actions["actions"][2]["uuid"], nodes[1]["actions"][2]["uuid"]
        )
        self.assertNotEqual(
            test_node_3actions["actions"][1]["templating"]["uuid"],
            nodes[1]["actions"][1]["templating"]["uuid"],
        )


class TestRapidProABTestCreatorLinear(unittest.TestCase):
    def setUp(self):
        abtest1 = abtest_from_csv("testdata/Test1_Personalization.csv")
        abtest2 = abtest_from_csv("testdata/Test2_Some1337.csv")
        self.abtests = [abtest1, abtest2]

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
            ("send_msg", "The first personalizable message."),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning!"),
            ("send_msg", "This is a test."),
        ]
        exp2 = [
            ("send_msg", "The first personalizable message."),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng!"),
            ("send_msg", "This is a test."),
        ]
        exp3 = [
            ("send_msg", "The first personalizable message, Steve!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng, Steve!"),
            ("send_msg", "This is a test."),
        ]
        exp4 = exp1

        # Traverse the flow with different group memberships and check the sent messages
        flows = rpx._data["flows"][0]
        groupsAA = [self.abtests[0].groupA().name, self.abtests[1].groupA().name]
        msgs1 = traverse_flow(flows, Context(groupsAA))
        self.assertEqual(msgs1, exp1)
        groupsAB = [self.abtests[0].groupA().name, self.abtests[1].groupB().name]
        msgs2 = traverse_flow(flows, Context(groupsAB))
        self.assertEqual(msgs2, exp2)
        groupsBB = [self.abtests[0].groupB().name, self.abtests[1].groupB().name]
        msgs3 = traverse_flow(flows, Context(groupsBB))
        self.assertEqual(msgs3, exp3)
        msgs4 = traverse_flow(
            flows, Context()
        )  # "Other" branch. Should be same as msgs1
        self.assertEqual(msgs4, exp4)


class TestRapidProABTestCreatorTwoFlowsWithMatchingNode(unittest.TestCase):
    def setUp(self):
        abtest1 = abtest_from_csv("testdata/RegexMatchFlowNode.csv")
        self.abtests = [abtest1]

    def test_apply_abtests(self):
        filename = "testdata/RegexMatchFlowNode.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)

        exp1B = [
            ("send_msg", "A great personalizable message, Steve!"),
            ("send_msg", "Great morning!\nNice to see you."),
        ]
        exp2B = [
            ("send_msg", "A great personalizable message, Steve!"),
            ("send_msg", "Great morning, Steve!\nNice to see you."),
        ]
        exp2A = [
            ("send_msg", "A good personalizable message."),
            ("send_msg", "Good morning!\nNice to see you."),
        ]

        flows = rpx._data["flows"][0]
        msgs1B = traverse_flow(flows, Context([self.abtests[0].groupB().name]))
        self.assertEqual(msgs1B, exp1B)

        flows = rpx._data["flows"][1]
        msgs2B = traverse_flow(flows, Context([self.abtests[0].groupB().name]))
        self.assertEqual(msgs2B, exp2B)

        flows = rpx._data["flows"][1]
        msgs2A = traverse_flow(flows, Context([self.abtests[0].groupA().name]))
        self.assertEqual(msgs2A, exp2A)


class TestRapidProABTestCreatorWaitForResponse(unittest.TestCase):
    def setUp(self):
        abtest1 = abtest_from_csv("testdata/Test_WaitForResponse.csv")
        self.abtests = [abtest1]
        filename = "testdata/WaitForResponse.json"
        self.rpx = RapidProABTestCreator(filename)
        self.rpx.apply_abtests(self.abtests)

    def test_wait_for_response_translations(self):
        flow = self.rpx._data["flows"][0]
        nodes = flow["nodes"]
        localization = flow["localization"]

        # Find the nodes where we insert a branch based on group
        abtest_nodes = []
        for node in nodes:
            if "router" in node and node["router"]["cases"][0]["type"] == "has_group":
                abtest_nodes.append(node)

        # Check variations of the send_message action (first branch)
        branch_uuids = [exit["destination_uuid"] for exit in abtest_nodes[0]["exits"]]
        self.assertEqual(len(branch_uuids), 3)
        self.assertEqual(branch_uuids[0], branch_uuids[2])
        branch_nodes = []
        for branch_uuid in branch_uuids[:2]:
            branch_nodes.append(find_node_by_uuid(flow, branch_uuid))
        uuid0 = branch_nodes[0]["actions"][0]["uuid"]
        uuid1 = branch_nodes[1]["actions"][0]["uuid"]
        for language, translations in localization.items():
            self.assertIn(uuid1, translations)
            self.assertEqual(translations[uuid0], translations[uuid1])

        # Check variations of the wait_for_response (second branch)
        branch_uuids = [exit["destination_uuid"] for exit in abtest_nodes[1]["exits"]]
        self.assertEqual(len(branch_uuids), 3)
        self.assertEqual(branch_uuids[0], branch_uuids[2])
        branch_nodes = []
        for branch_uuid in branch_uuids[:2]:
            branch_nodes.append(find_node_by_uuid(flow, branch_uuid))
        for elem in ["cases", "categories"]:
            catcases = branch_nodes[0]["router"][elem]
            for i in range(len(catcases)):
                uuid0 = branch_nodes[0]["router"][elem][i]["uuid"]
                uuid1 = branch_nodes[1]["router"][elem][i]["uuid"]
                for language, translations in localization.items():
                    if uuid0 in translations:
                        self.assertIn(uuid1, translations)
                        self.assertEqual(translations[uuid0], translations[uuid1])

    def test_wait_for_response_functionality(self):
        def make_exp(s):
            return [("send_msg", "Hello. Choose an option."), ("send_msg", s)]
        flows = self.rpx._data["flows"][0]
        groupsA = [self.abtests[0].groupA().name]
        groupsB = [self.abtests[0].groupB().name]

        msgs = traverse_flow(flows, Context(groupsA, ["Yes"]))
        self.assertEqual(msgs, make_exp("Nice, thank you!"))
        msgs = traverse_flow(flows, Context(groupsA, ["50"]))
        self.assertEqual(msgs, make_exp("You know it!"))
        msgs = traverse_flow(flows, Context(groupsA, ["no no no never"]))
        self.assertEqual(msgs, make_exp("That's too bad."))
        msgs = traverse_flow(flows, Context(groupsA, ["99", "no never"]))
        self.assertEqual(
            msgs, make_exp("I don't get it.") + make_exp("That's too bad.")
        )

        msgs = traverse_flow(flows, Context(groupsB, ["a@b.com"]))
        self.assertEqual(msgs, make_exp("Nice, thank you!"))
        msgs = traverse_flow(flows, Context(groupsB, ["something"]))
        self.assertEqual(msgs, make_exp("You know it!"))
        msgs = traverse_flow(flows, Context(groupsB, ["99"]))
        self.assertEqual(msgs, make_exp("That's too bad."))
        msgs = traverse_flow(flows, Context(groupsB, ["42", "99"]))
        self.assertEqual(
            msgs, make_exp("I don't get it.") + make_exp("That's too bad.")
        )


class TestRapidProABTestCreatorReplaceSplitOperand(unittest.TestCase):
    # def setUp(self):
    def test_wait_for_response(self):
        abtest1 = abtest_from_csv("testdata/Test_ReplaceSplitOperand.csv")
        self.abtests = [abtest1]
        filename = "testdata/SplitByExample.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)

        def make_exp(s):
            return [("send_msg", "Start"), ("send_msg", s)]

        flows = rpx._data["flows"][0]
        groupsA = [self.abtests[0].groupA().name]
        groupsB = [self.abtests[0].groupB().name]

        msgs = traverse_flow(
            flows,
            Context(
                groupsA,
                variables={"@fields.something": "Yes", "@fields.something_else": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("Yes"))
        msgs = traverse_flow(
            flows,
            Context(
                groupsA,
                variables={"@fields.something": "No", "@fields.something_else": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("No"))
        msgs = traverse_flow(
            flows,
            Context(
                groupsA,
                variables={"@fields.something": "X", "@fields.something_else": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("Other"))

        msgs = traverse_flow(
            flows,
            Context(
                groupsB,
                variables={"@fields.something_else": "Yes", "@fields.something": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("Yes"))
        msgs = traverse_flow(
            flows,
            Context(
                groupsB,
                variables={"@fields.something_else": "No", "@fields.something": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("No"))
        msgs = traverse_flow(
            flows,
            Context(
                groupsB,
                variables={"@fields.something_else": "X", "@fields.something": "X"},
            ),
        )
        self.assertEqual(msgs, make_exp("Other"))


class TestRapidProABTestCreatorPrependSendMsgActionToSaveValueNode(unittest.TestCase):
    # def setUp(self):
    def test_prepend_send_msg_action_to_save_value_node(self):
        sheet1 = floweditsheet_from_csv("testdata/FlowEdit_PrependSaveValue.csv")
        self.floweditsheets = [sheet1]

        filename = "testdata/FlowWithSaveValue.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)

        flows = rpx._data["flows"][0]

        msgs = traverse_flow(flows, Context())
        self.assertEqual(
            msgs,
            [
                ("send_msg", "First message"),
                ("send_msg", "Prepended text"),
                ("set_contact_field", "Type of Media"),
                ("send_msg", "Last message"),
            ],
        )


class TestRapidProABTestCreatorPrependSendMsgAction(unittest.TestCase):
    # def setUp(self):
    def test_wait_for_response(self):
        abtest1 = abtest_from_csv("testdata/Test_PrependSendMsgAction.csv")
        self.abtests = [abtest1]
        filename = "testdata/Linear_NodeWith3Actions.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)

        flows = rpx._data["flows"][0]
        groupsA = [self.abtests[0].groupA().name]
        groupsB = [self.abtests[0].groupB().name]

        msgs = traverse_flow(flows, Context(groupsA))
        self.assertEqual(
            msgs,
            [
                ("send_msg", "Message A"),
                ("send_msg", "The first personalizable message."),
                ("send_msg", "Some generic message."),
                ("send_msg", "Good morning!"),
                ("send_msg", "This is a test."),
            ],
        )

        msgs = traverse_flow(flows, Context(groupsB))
        self.assertEqual(
            msgs,
            [
                ("send_msg", "Message B"),
                ("send_msg", "The first personalizable message, my friend!"),
                ("send_msg", "Some generic message."),
                ("send_msg", "Good morning!"),
                ("send_msg", "This is a test."),
            ],
        )


class TestRapidProABTestCreatorBranching(unittest.TestCase):

    def set_up_branching(self, filename):
        self.abtests = [abtest_from_csv(filename)]
        filename = "testdata/Branching.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.abtests)
        self.groupA_name = self.abtests[0].groupA().name
        self.groupB_name = self.abtests[0].groupB().name
        self.flows = rpx._data["flows"][0]

    def test_apply_abtests_1(self):
        self.set_up_branching("testdata/Branching.csv")
        self.apply_abtests_1()

    def test_apply_abtests_2(self):
        self.set_up_branching("testdata/Branching.csv")
        self.apply_abtests_2()

    def test_apply_abtests_3(self):
        self.set_up_branching("testdata/Branching.csv")
        self.apply_abtests_3()

    def test_apply_abtests_4(self):
        self.set_up_branching("testdata/Branching.csv")
        self.apply_abtests_4()

    # These tests use a separate spreadsheet without an
    # assign_to_group column and instead manually inserts
    # assign_to_group operations
    def test_apply_abtests_1_equivalent(self):
        self.set_up_branching("testdata/Branching_equivalent.csv")
        self.apply_abtests_1()

    def test_apply_abtests_2_equivalent(self):
        self.set_up_branching("testdata/Branching_equivalent.csv")
        self.apply_abtests_2()

    def test_apply_abtests_3_equivalent(self):
        self.set_up_branching("testdata/Branching_equivalent.csv")
        self.apply_abtests_3()

    def test_apply_abtests_4_equivalent(self):
        self.set_up_branching("testdata/Branching_equivalent.csv")
        self.apply_abtests_4()

    def apply_abtests_1(self):
        exp1 = [
            ("send_msg", "Text1"),
            ("send_msg", "Text21"),
            ("send_msg", "Text3 replaced"),
            ("send_msg", "Text61"),
            ("send_msg", "Text61 Again replaced"),
            ("send_msg", "Text7"),
        ]
        groups1 = [self.groupB_name, "Survey Audience"]
        output1 = traverse_flow(self.flows, Context(groups1, ["Good"], []))
        self.assertEqual(output1, exp1)

        # We enforce the same group assignment with the random choice "1"
        exp2 = exp1[:2] + [("add_contact_groups", self.groupB_name)] + exp1[2:]
        groups2 = ["Survey Audience"]
        output2 = traverse_flow(self.flows, Context(groups2, ["Good"], [1]))
        self.assertEqual(output2, exp2)

    def apply_abtests_2(self):
        exp1 = [
            ("send_msg", "Text1"),
            ("send_msg", "Text23"),
            ("set_run_result", "Result 2"),
            ("send_msg", "Text23 Again replaced"),
            ("add_contact_groups", "Survey Audience"),
            ("send_msg", "Text41"),
            ("send_msg", "Text61"),
            ("send_msg", "Text61 Again replaced"),
            ("send_msg", "Text7"),
        ]
        groups1 = [self.groupB_name, "Survey Audience"]
        output1 = traverse_flow(self.flows, Context(groups1, ["Something", "Yes"], []))
        self.assertEqual(output1, exp1)

        # We enforce the same testing group assignment with the random choice "1"
        # "Survey Audience" is being added by the choice "Yes"
        exp2 = exp1[:1] + [("add_contact_groups", self.groupB_name)] + exp1[1:]
        groups2 = []
        output2 = traverse_flow(self.flows, Context(groups2, ["Something", "Yes"], [1]))
        self.assertEqual(output2, exp2)

    def apply_abtests_3(self):
        exp1 = [
            ("send_msg", "Text1"),
            ("send_msg", "Text22"),
            ("send_email", "Spam Email"),
            ("add_contact_groups", self.groupA_name),
            ("send_msg", "Text3"),
            ("send_msg", "Text62"),
            ("send_msg", "Text7"),
        ]
        groups1 = []
        output1 = traverse_flow(self.flows, Context(groups1, ["Bad"], [0]))
        self.assertEqual(output1, exp1)

    def apply_abtests_4(self):
        exp1 = [
            ("send_msg", "Text1"),
            ("add_contact_groups", self.groupB_name),
            ("send_msg", "Text23"),
            ("set_run_result", "Result 2"),
            ("send_msg", "Text23 Again replaced"),
            ("send_msg", "Text42 replaced"),
            ("send_msg", "Text62 replaced"),
            ("send_msg", "Text7"),
        ]
        groups1 = []
        output1 = traverse_flow(self.flows, Context(groups1, ["otter", "otter"], [1]))
        self.assertEqual(output1, exp1)


class TestRapidProEditsLinear(unittest.TestCase):
    def setUp(self):
        sheet1 = floweditsheet_from_csv("testdata/FlowEdit1_Gender.csv")
        sheet2 = floweditsheet_from_csv("testdata/FlowEdit2_Some1337.csv")
        self.floweditsheets = [sheet1, sheet2]

    def test_apply_abtests_linear_onenodeperaction(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)
        self.evaluate_result(rpx)

    def test_apply_abtests_linear_onenode4actions(self):
        filename = "testdata/Linear_OneNode4Actions.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)
        self.evaluate_result(rpx)

    def evaluate_result(self, rpx):
        exp1 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my person!"),
            ("send_msg", "This is a test."),
        ]
        exp2 = [
            ("send_msg", "The first personalizable message, my gal!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng, my gal!"),
            ("send_msg", "This is a test."),
        ]
        exp3 = [
            ("send_msg", "The first personalizable message, my dude!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my dude!"),
            ("send_msg", "This is a test."),
        ]
        exp4 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng, my person!"),
            ("send_msg", "This is a test."),
        ]

        # Traverse the flow with different group memberships and check the sent messages
        flows = rpx._data["flows"][0]
        msgs1 = traverse_flow(flows, Context())
        self.assertEqual(msgs1, exp1)
        variables2 = {"@fields.gender": "woman", "@fields.likes_1337": "yes"}
        msgs2 = traverse_flow(flows, Context(variables=variables2))
        self.assertEqual(msgs2, exp2)
        variables3 = {"@fields.gender": "man", "@fields.likes_1337": ""}
        msgs3 = traverse_flow(flows, Context(variables=variables3))
        self.assertEqual(msgs3, exp3)
        variables4 = {"@fields.gender": "child", "@fields.likes_1337": "yossss"}
        msgs4 = traverse_flow(flows, Context(variables=variables4))
        self.assertEqual(msgs4, exp4)


class TestMasterSheet(unittest.TestCase):
    def setUp(self):
        parser = CSVMasterSheetParser(["testdata/master_sheet.csv"])
        (self.floweditsheets,) = parser.get_flow_edit_sheet_groups()

    def test_split_master_sheet(self):
        parser = CSVMasterSheetParser(
            ["testdata/master_sheet_part1.csv", "testdata/master_sheet_part2.csv"]
        )
        (self.floweditsheets,) = parser.get_flow_edit_sheet_groups()
        self.test_apply_abtests_linear_onenodeperaction()

    def test_json_master_sheet(self):
        parser = JSONMasterSheetParser(["testdata/master_sheet.json"])
        (self.floweditsheets,) = parser.get_flow_edit_sheet_groups()
        self.test_apply_abtests_linear_onenodeperaction()

    def test_apply_abtests_linear_onenodeperaction(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)
        self.evaluate_result(rpx)
        flow = rpx._data["flows"][0]
        self.assertEqual(
            flow["localization"]["fra"]["694779d8-034d-4fb3-bf7a-c6de04efaba5"]["text"][
                0
            ],
            "Togolese message",
        )

    def test_apply_abtests_linear_onenode4actions(self):
        filename = "testdata/Linear_OneNode4Actions.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)
        self.evaluate_result(rpx)
        flow = rpx._data["flows"][0]
        self.assertEqual(
            flow["localization"]["fra"]["694779d8-034d-4fb3-bf7a-c6de04efaba5"]["text"][
                0
            ],
            "Togolese message",
        )

    def evaluate_result(self, rpx):
        self.groupA_name = self.floweditsheets[-2].groupA().name
        self.groupB_name = self.floweditsheets[-2].groupB().name
        exp1 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my person!"),
            ("send_msg", "This is a test."),
        ]
        exp2 = [
            ("send_msg", "The first personalizable message, my gal!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng, my gal!"),
            ("send_msg", "This is a test."),
        ]
        exp3 = [
            ("send_msg", "The first personalizable message, my dude!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my dude!"),
            ("send_msg", "This is a test."),
        ]
        exp4 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng, my person!"),
            ("send_msg", "This is a test."),
        ]

        # Traverse the flow with different group memberships and check the sent messages
        flows = rpx._data["flows"][0]
        msgs1 = traverse_flow(flows, Context([self.groupA_name]))
        self.assertEqual(msgs1, exp1)
        variables2 = {"@fields.gender": "woman"}
        msgs2 = traverse_flow(flows, Context([self.groupB_name], variables=variables2))
        self.assertEqual(msgs2, exp2)
        variables3 = {"@fields.gender": "man"}
        msgs3 = traverse_flow(flows, Context([self.groupA_name], variables=variables3))
        self.assertEqual(msgs3, exp3)
        variables4 = {"@fields.gender": "child"}
        msgs4 = traverse_flow(flows, Context([self.groupB_name], variables=variables4))
        self.assertEqual(msgs4, exp4)


class TestMasterSheetOrdered(unittest.TestCase):
    def setUp(self):
        parser = CSVMasterSheetParser(["testdata/master_sheet_ordered.csv"])
        self.floweditsheet_groups = parser.get_flow_edit_sheet_groups()

    def test_apply_abtests_linear(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheet_groups[0])
        rpx.apply_abtests(self.floweditsheet_groups[1])
        self.evaluate_result(rpx)

    def evaluate_result(self, rpx):
        self.groupA_name = self.floweditsheet_groups[0][0].groupA().name
        self.groupB_name = self.floweditsheet_groups[0][0].groupB().name
        exp1 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my person!"),
            ("send_msg", "This is a test."),
        ]
        # We apply the operations sequentially, unlike in TestMasterSheet.
        # Therefore, the personalization is not applied to messages that have
        # already been 1337tified
        # TODO: Also catch expected warnings
        exp2 = [
            ("send_msg", "The first personalizable message, my gal!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng!"),
            ("send_msg", "This is a test."),
        ]
        exp3 = [
            ("send_msg", "The first personalizable message, my dude!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "Good morning, my dude!"),
            ("send_msg", "This is a test."),
        ]
        # We apply the operations sequentially, unlike in TestMasterSheet.
        # Therefore, the personalization is not applied to messages that have
        # already been 1337tified
        exp4 = [
            ("send_msg", "The first personalizable message, my person!"),
            ("send_msg", "Some generic message."),
            ("send_msg", "g00d m0rn1ng!"),
            ("send_msg", "This is a test."),
        ]

        # Traverse the flow with different group memberships and check the sent messages
        flows = rpx._data["flows"][0]
        msgs1 = traverse_flow(flows, Context([self.groupA_name]))
        self.assertEqual(msgs1, exp1)
        variables2 = {"@fields.gender": "woman"}
        msgs2 = traverse_flow(flows, Context([self.groupB_name], variables=variables2))
        self.assertEqual(msgs2, exp2)
        variables3 = {"@fields.gender": "man"}
        msgs3 = traverse_flow(flows, Context([self.groupA_name], variables=variables3))
        self.assertEqual(msgs3, exp3)
        variables4 = {"@fields.gender": "child"}
        msgs4 = traverse_flow(flows, Context([self.groupB_name], variables=variables4))
        self.assertEqual(msgs4, exp4)


class TestMasterSheetWithConfig(unittest.TestCase):
    def setUp(self):
        parser = CSVMasterSheetParser(["testdata/master_sheet_cfg.csv"])
        (self.floweditsheets,) = parser.get_flow_edit_sheet_groups(
            {"Test2Assign_Some1337": {"group_assignment": "always B"}}
        )

    def test_apply_abtests_linear_onenodeperaction(self):
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_abtests(self.floweditsheets)
        self.group1A_name = self.floweditsheets[0].groupA().name
        self.group1B_name = self.floweditsheets[0].groupB().name
        self.group2A_name = self.floweditsheets[1].groupA().name
        self.group2B_name = self.floweditsheets[1].groupB().name

        exp1 = [
            ("add_contact_groups", "ABTest_Test1Assign_Personalization_Stevefied"),
            ("send_msg", "The first personalizable message, Steve!"),
            ("send_msg", "Some generic message."),
            ("add_contact_groups", "ABTest_Test2Assign_Some1337_1337"),
            ("send_msg", "g00d m0rn1ng, Steve!"),
            ("send_msg", "This is a test."),
        ]
        exp23 = [
            ("send_msg", "The first personalizable message."),
            ("send_msg", "Some generic message."),
            ("add_contact_groups", "ABTest_Test2Assign_Some1337_1337"),
            ("send_msg", "g00d m0rn1ng!"),
            ("send_msg", "This is a test."),
        ]

        # Traverse the flow with different group memberships and check the sent messages
        flows = rpx._data["flows"][0]
        msgs1 = traverse_flow(flows, Context(random_choices=[1, 0]))
        self.assertEqual(msgs1, exp1)
        msgs2 = traverse_flow(flows, Context([self.group1A_name, self.group2B_name]))
        self.assertEqual(msgs2, exp23)
        msgs3 = traverse_flow(flows, Context([self.group1A_name]))
        self.assertEqual(msgs3, exp23)
        # msgs4 = traverse_flow(flows, Context([self.group1A_name, self.group2A_name]))
        # This one is different, because the user is now in both groups A and B


class TestNodesLayout(unittest.TestCase):

    def test_make_tree_layout(self):
        nodes = [{"uuid": "node1_uuid"}, {"uuid": "node2_uuid"}, {"uuid": "node3_uuid"}]
        nodes_layout = make_tree_layout(
            "some_expression", "switch_uuid", nodes, test_node_layout
        )
        self.assertEqual(nodes_layout.layout()["node1_uuid"]["position"]["left"], 0)
        self.assertEqual(
            nodes_layout.layout()["node1_uuid"]["position"]["top"],
            NodesLayout.VERTICAL_MARGIN,
        )
        self.assertEqual(
            nodes_layout.layout()["node2_uuid"]["position"]["left"],
            NodesLayout.HORIZONTAL_MARGIN,
        )
        self.assertEqual(
            nodes_layout.layout()["node2_uuid"]["position"]["top"],
            NodesLayout.VERTICAL_MARGIN,
        )
        self.assertEqual(
            nodes_layout.layout()["node3_uuid"]["position"]["left"],
            2 * NodesLayout.HORIZONTAL_MARGIN,
        )
        self.assertEqual(
            nodes_layout.layout()["node3_uuid"]["position"]["top"],
            NodesLayout.VERTICAL_MARGIN,
        )
        self.assertEqual(
            nodes_layout.layout()["switch_uuid"]["position"]["left"],
            NodesLayout.HORIZONTAL_MARGIN,
        )
        self.assertEqual(nodes_layout.layout()["switch_uuid"]["position"]["top"], 0)

    def test_get_variation_tree_snippet(self):
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "OK"))
        edit_op.add_category(SwitchCategory("Cat2", "has_text", "", "Bad"))
        snippet = edit_op._get_variation_tree_snippet(test_node, test_node_layout)
        self.assertEqual(len(snippet.nodes()), len(snippet.nodes_layout().layout()))
        for node in snippet.nodes():
            self.assertTrue(node["uuid"] in snippet.nodes_layout().layout())

    def test_get_variation_tree_snippet_group(self):
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_group", ["", "GroupA"], "Bad"))
        edit_op.add_category(SwitchCategory("Cat2", "has_group", ["", "GroupB"], "Bad"))
        snippet = edit_op._get_variation_tree_snippet(test_node, test_node_layout)
        self.assertEqual(len(snippet.nodes()), len(snippet.nodes_layout().layout()))
        for node in snippet.nodes():
            self.assertTrue(node["uuid"] in snippet.nodes_layout().layout())

    def test_get_assigntogroup_snippet(self):
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_group", ["", "GroupA"], "Bad"))
        edit_op.add_category(SwitchCategory("Cat2", "has_group", ["", "GroupB"], "Bad"))
        snippet = edit_op._get_assigntogroup_snippet(test_node, test_node_layout)
        self.assertEqual(len(snippet.nodes()), len(snippet.nodes_layout().layout()))
        for node in snippet.nodes():
            self.assertTrue(node["uuid"] in snippet.nodes_layout().layout())

    def test_apply_edit_op(self):
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "OK"))
        node = copy.deepcopy(test_node)
        flow = {
            "nodes": [node],
            "_ui": {"nodes": {node["uuid"]: copy.deepcopy(test_node_layout)}},
        }
        edit_op.apply_operation(flow, node)
        self.assertEqual(len(flow["nodes"]), len(flow["_ui"]["nodes"]))
        positions = {
            (layout["position"]["left"], layout["position"]["top"])
            for layout in flow["_ui"]["nodes"].values()
        }
        self.assertEqual(
            positions,
            {
                (1000, 100 - NodesLayout.VERTICAL_MARGIN // 2),
                (
                    1000 - NodesLayout.HORIZONTAL_MARGIN // 2,
                    100 + NodesLayout.VERTICAL_MARGIN // 2,
                ),
                (
                    1000 + NodesLayout.HORIZONTAL_MARGIN // 2,
                    100 + NodesLayout.VERTICAL_MARGIN // 2,
                ),
            },
        )

    def test_apply_edit_op_group(self):
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=False, assign_to_group=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_group", ["", "GroupA"], "Bad"))
        edit_op.add_category(SwitchCategory("Cat2", "has_group", ["", "GroupB"], "Bad"))
        node = copy.deepcopy(test_node)
        flow = {
            "nodes": [node],
            "_ui": {"nodes": {node["uuid"]: copy.deepcopy(test_node_layout)}},
        }
        edit_op.apply_operation(flow, node)
        self.assertEqual(len(flow["_ui"]["nodes"]), len(flow["nodes"]))
        self.assertEqual(len(flow["_ui"]["nodes"]), 7)

    def test_apply_edit_op_no_ui(self):
        # Make sure it doesn't crash
        row = [
            "replace_bit_of_text",
            "",
            0,
            "Good Morning!",
            "Good",
            "@fields.flag",
            "Good",
        ]
        edit_op = FlowEditOp.create_edit_op(
            *row, "debug_str", has_node_for_other_category=True
        )
        edit_op.add_category(SwitchCategory("Cat1", "has_text", "", "OK"))
        node = copy.deepcopy(test_node)
        flow = {"nodes": [node]}
        edit_op.apply_operation(flow, node)


class TestTranslationEdits(unittest.TestCase):
    # def setUp(self):
    def test_wait_for_response(self):
        sheet1 = translationeditsheet_from_csv("testdata/Test_TranslationEdits.csv")
        self.sheets = [sheet1]
        filename = "testdata/WaitForResponse.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_translationedits(self.sheets)

        flow = rpx._data["flows"][0]
        self.assertEqual(
            flow["localization"]["aar"]["ce5e63dc-1c14-41cb-b2a3-7da7172f82bc"]["text"][
                0
            ],
            "Wut?!",
        )
        self.assertEqual(
            flow["localization"]["fra"]["ce5e63dc-1c14-41cb-b2a3-7da7172f82bc"]["text"][
                0
            ],
            "hmhmhnhn!",
        )
        self.assertEqual(
            flow["localization"]["fra"]["cee54fd0-a432-4bf6-b42a-2561627eb3b8"][
                "quick_replies"
            ],
            ["a@b.com", "99", "something"],
        )
        self.assertEqual(
            flow["localization"]["aar"]["7d3a7c7b-218a-44a8-a5fc-a80062dceacd"][
                "arguments"
            ][0],
            "yappp",
        )
        self.assertEqual(
            flow["localization"]["aar"]["ead5c97e-f960-406f-a87f-ac603b70c838"]["name"][
                0
            ],
            "Nohoho",
        )
        self.assertEqual(
            flow["localization"]["aar"]["199562fb-77f0-4c06-99d2-38de6efff8e0"]["name"][
                0
            ],
            "forty - 60",
        )


class TestTranslationCopying(unittest.TestCase):
    # def setUp(self):
    def test_get_localizable_uuids(self):
        filename = "testdata/WaitForResponse.json"
        with open(filename) as fp:
            data = json.load(fp)
        nodes = data["flows"][0]["nodes"]

        localizables0 = get_localizable_uuids(nodes[0])
        localizables0_exp = {"cee54fd0-a432-4bf6-b42a-2561627eb3b8": ["actions", 0]}
        self.assertEqual(localizables0, localizables0_exp)

        localizables1 = get_localizable_uuids(nodes[1])
        localizables1_exp = {
            "7d3a7c7b-218a-44a8-a5fc-a80062dceacd": ["router", "cases", 0],
            "9643921e-f05c-47f3-8165-8645b5a67e92": ["router", "cases", 1],
            "97a19bb7-a6a4-41c9-bf0f-c0e490ab28d1": ["router", "cases", 2],
            "d243928c-6d2c-4349-b6ff-23cfbce05c92": ["router", "categories", 0],
            "199562fb-77f0-4c06-99d2-38de6efff8e0": ["router", "categories", 1],
            "ead5c97e-f960-406f-a87f-ac603b70c838": ["router", "categories", 2],
            "177bcbae-6286-461a-a4ff-55c5fecd850a": ["router", "categories", 3],
        }
        self.assertEqual(localizables1, localizables1_exp)

    def test_basic_edits(self):
        sheet1 = floweditsheet_from_csv("testdata/FlowEdit_TranslatedMessage.csv")
        floweditsheets = [sheet1]
        filename = "testdata/Linear_OneNodePerAction.json"
        rpx = RapidProABTestCreator(filename)
        rpx.apply_editsheets(floweditsheets)
        flow = rpx._data["flows"][0]
        nodes = flow["nodes"]
        localization = flow["localization"]

        # Find the nodes where we insert a branch based on group
        for node in nodes:
            if "router" in node:
                switch_node = node
                break

        # Check variations of the send_message action (first branch)
        branch_uuids = [exit["destination_uuid"] for exit in switch_node["exits"]]
        self.assertEqual(len(branch_uuids), 3)
        branch_nodes = []
        for branch_uuid in branch_uuids:
            branch_nodes.append(find_node_by_uuid(flow, branch_uuid))
        uuid0 = branch_nodes[0]["actions"][0]["uuid"]
        uuid1 = branch_nodes[1]["actions"][0]["uuid"]
        uuid2 = branch_nodes[2]["actions"][0]["uuid"]
        for language, translations in localization.items():
            self.assertIn(uuid1, translations)
            self.assertIn(uuid2, translations)
            self.assertEqual(translations[uuid0], translations[uuid1])
            self.assertEqual(translations[uuid0], translations[uuid2])


if __name__ == "__main__":
    unittest.main()
