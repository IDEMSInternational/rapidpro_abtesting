import logging

from rapidpro_abtesting.uuid_tools import generate_random_uuid


logger = logging.getLogger(__name__)
FIRST_SPELLING_COLID = 3


def get_send_msg_node(uuid, text):
    node = {
        "uuid": uuid,
        "actions": [
            {
                "attachments": [],
                "text": text,
                "type": "send_msg",
                "all_urns": False,
                "quick_replies": [],
                "uuid": generate_random_uuid(),
            }
        ],
        "exits": [
            {"uuid": generate_random_uuid(), "destination_uuid": generate_random_uuid()}
        ],
    }
    next_node_uuid = node["exits"][0]["destination_uuid"]
    return node, next_node_uuid


def make_nodes(languages, data):
    # Create the nodes to set the contact language
    set_contact_nodes = []
    for lang in languages:
        node = {
            "actions": [
                {
                    "language": lang,
                    "type": "set_contact_language",
                    "uuid": generate_random_uuid(),
                }
            ],
            "exits": [{"destination_uuid": None, "uuid": generate_random_uuid()}],
            "uuid": generate_random_uuid(),
        }
        set_contact_nodes.append(node)

    # Template for the node processing the user choice
    switcher_node = {
        "uuid": "TEMP",
        "actions": [],
        "router": {
            "type": "switch",
            "cases": [],
            "categories": [],
            "default_category_uuid": generate_random_uuid(),
            "operand": "@input.text",
            "wait": {"type": "msg"},
            "result_name": "Language",
        },
        "exits": [],
    }

    nodes = []
    next_node_uuid = "TEMP"
    error_nodes = []
    error_next_node_uuid = generate_random_uuid()
    for lid, lang in enumerate(languages):
        rowid = lid + 1

        # Node with main message and language names in that language
        main_message = data[rowid][1]
        language_names_msg = ""
        for lid2, lang2 in enumerate(languages):
            rowid2 = lid2 + 1
            language_names_msg += (
                f"{rowid2}. {data[rowid2][lid+FIRST_SPELLING_COLID]}\n"
            )
        node, next_node_uuid = get_send_msg_node(
            next_node_uuid, main_message + "\n\n" + language_names_msg
        )
        nodes.append(node)

        # Error message node
        node, error_next_node_uuid = get_send_msg_node(
            error_next_node_uuid, data[rowid][2]
        )
        error_nodes.append(node)

        # Make an exit for this language in the switcher node
        exit_uuid = generate_random_uuid()
        switcher_node["exits"].append(
            {"uuid": exit_uuid, "destination_uuid": set_contact_nodes[lid]["uuid"]}
        )

        # Make a category for this language in the switcher node
        category_uuid = generate_random_uuid()
        switcher_node["router"]["categories"].append(
            {
                "uuid": category_uuid,
                "name": lang,
                "exit_uuid": exit_uuid,
            }
        )

        # Cases for setting the language
        # The language number should work
        switcher_node["router"]["cases"].append(
            {
                "uuid": generate_random_uuid(),
                "type": "has_phrase",
                "arguments": [str(rowid)],
                "category_uuid": category_uuid,
            }
        )
        # And any of the provided spellings
        for spelling in data[rowid][FIRST_SPELLING_COLID:]:
            if spelling:
                switcher_node["router"]["cases"].append(
                    {
                        "uuid": generate_random_uuid(),
                        "type": "has_phrase",
                        "arguments": [spelling],
                        "category_uuid": category_uuid,
                    }
                )

    # Add default exit and category to router
    # (which goes to the error messages)
    exit_uuid = generate_random_uuid()
    switcher_node["exits"].append(
        {"uuid": exit_uuid, "destination_uuid": error_nodes[0]["uuid"]}
    )

    switcher_node["router"]["categories"].append(
        {
            "uuid": switcher_node["router"]["default_category_uuid"],
            "name": "Other",
            "exit_uuid": exit_uuid,
        }
    )

    # The last main message node should lead to the switcher node
    switcher_node["uuid"] = next_node_uuid
    # The last error node should lead back to the start
    nodes[0]["uuid"] = error_next_node_uuid

    return nodes + [switcher_node] + error_nodes + set_contact_nodes


def replace_flow_with_language_chooser(data, flow):
    languages = []
    for row in data[1:]:
        languages.append(row[0])

    header = (
        ["Language", "Main message", "Error message"]
        + ["Language name in {}".format(s) for s in languages]
        + ["Alternative Spellings"]
    )
    if data[0][: len(header)] != header:
        logger.error("Invalid header row. Should be ", header)
        return

    # Replace the entire set of nodes.
    flow["nodes"] = make_nodes(languages, data)
    # If there was layout information, remove it.
    flow.pop("_ui", None)
