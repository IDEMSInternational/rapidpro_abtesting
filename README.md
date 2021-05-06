# RapidPro A/B Testing

...

## Notes

* Each A/B test operation is replace_bit_of_text, and refers to text within
a send_msg action. If multiple nodes match the text, the operation will
affect all of these nodes.
* The row_id from the A/B testing spreadsheets is ignored
* No ui_ output yet, RapidPro will lay everything out in a single column.
