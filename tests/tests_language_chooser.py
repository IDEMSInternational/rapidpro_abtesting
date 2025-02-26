import logging
import unittest

from rapidpro_abtesting.language_chooser import replace_flow_with_language_chooser
from rapidpro_abtesting.sheets import load_content_from_csv
from .testing_tools import Context, traverse_flow


logging.basicConfig(filename="tests.log", level=logging.WARNING, filemode="w")


class TestLanguageChooser(unittest.TestCase):

    def setUp(self):
        self.intro_messages = [
            (
                "send_msg",
                "Hai! Terima kasih kerana mendaftar untuk menerima tip keibubapaan ini. Sila beritahu kami bahasa pilihan anda:\n\n1. Bahasa Melayu\n2. Bahasa Inggeris\n",
            ),
            (
                "send_msg",
                "Hi! Thank you for signing up to receive these parenting tips. Please tell us which language you would like:\n\n1. Malay\n2. English\n",
            ),
        ]
        self.error_messages = [
            ("send_msg", "(Sorry, I don't understand what you mean – in Malay)"),
            ("send_msg", "Sorry, I don't understand what you mean."),
        ]
        self.data = load_content_from_csv("testdata/language_choose_malaysia.csv")

    def test_get_unique_node_copy(self):
        flow = {"nodes": []}
        replace_flow_with_language_chooser(self.data, flow)

        msgs1 = traverse_flow(flow, Context(inputs=["English"]))
        exp1 = self.intro_messages + [("set_contact_language", "eng")]
        self.assertEqual(msgs1, exp1)

        msgs2 = traverse_flow(flow, Context(inputs=["spam", "ing"]))
        exp2 = (
            self.intro_messages
            + self.error_messages
            + self.intro_messages
            + [("set_contact_language", "eng")]
        )
        self.assertEqual(msgs2, exp2)

        msgs3 = traverse_flow(flow, Context(inputs=["bahasa malayu"]))
        exp3 = self.intro_messages + [("set_contact_language", "msa")]
        self.assertEqual(msgs3, exp3)

        msgs4 = traverse_flow(flow, Context(inputs=["1"]))
        exp4 = self.intro_messages + [("set_contact_language", "msa")]
        self.assertEqual(msgs4, exp4)


if __name__ == "__main__":
    unittest.main()
