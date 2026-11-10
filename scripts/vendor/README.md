# Replay parser

`recfile.py` is from BigManJohn000/aoe4-replay-viewer, commit
`98649e9d150fa065ab238946490e7468425d0c00`, `tools/recfile.py`.
The accompanying MIT license is in `RECFILE-LICENSE`.

The rankings collector uses the binary reader and command layout only. It adds
strict choice-command boundary checks and joins results from the official API.
It never launches the game or invokes the upstream recorder.

Local change: `command_data` decodes high-bit extended payload lengths as
`((prefix & 0x7f) << 8) | next_byte`, rather than handling only prefix `0x80`.
Current-build commands with `0x81` and `0x82` contain payloads larger than 255
bytes, including field-siege construction. Receiver and payload truncation now
raise `ValueError`. Checked against 77 previously unresolved build commands:
every corrected length ended exactly at the command boundary and every decoded
blueprint matched the installed 17.0.12260 catalog. Regression coverage is in
`scripts/test_recfile_lengths.py`.
