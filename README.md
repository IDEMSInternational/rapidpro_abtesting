# RapidPro A/B Testing

Setup:

```
pip install -e .
python -m rapidpro_abtesting.main --help
```

Run tests:

```
python -m unittest
```

# Notes

* The row_id from the A/B testing spreadsheets is ignored
* ui_ output is WIP and expands the nodes more than necessary.

Supported operations:
* `replace_bit_of_text`
* `replace_quick_replies`
* `replace_attachments`
* `remove_attachments`
* `replace_saved_value`
* `assign_to_group_before_msg_node`
* `assign_to_group_before_save_value_node`
* `replace_flow`
* `replace_wait_for_response_cases`
* `replace_split_operand`
* `prepend_send_msg_action`
* `prepend_send_msg_action_to_save_value_node`
