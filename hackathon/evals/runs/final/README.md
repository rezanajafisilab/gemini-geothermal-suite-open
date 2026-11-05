# Final measurement (5 Nov 2026)

The same code (rn/final 220714f: the fixed agent, the memory layer and the tool fixes merged) on
qwen3.5:9b, all three suites, two lanes at once, one per GPU. The lanes differ only in the
three tool flags.

| File | Lane | Suite | Passed |
|---|---|---|---|
| `20261105T060217Z_qwen3.5-9b_auto.jsonl` | tools off | chat | 181/185 |
| `20261105T060218Z_qwen3.5-9b_auto.jsonl` | tools on | chat | 181/185 |
| `20261105T065508Z_qwen3.5-9b_auto.jsonl` | tools off | unclear | 48/52 |
| `20261105T065740Z_qwen3.5-9b_auto.jsonl` | tools on | unclear | 47/52 |
| `conversations_20261105T070343Z_qwen3.5-9b_auto_off-conv.jsonl` | tools off | conversations | 61/65 turns, 206/210 checks |
| `conversations_20261105T070608Z_qwen3.5-9b_auto_on-conv.jsonl` | tools on | conversations | 61/65 turns, 205/210 checks |

- **Tools on:** the defaults then: value answers written by code and the reply check on,
  thinking off.
- **Tools off:** `DIOSCURI_CODE_FACTS=0 DIOSCURI_REPLY_CHECK=0 DIOSCURI_THINK=0`.
- **Time:** the median chat turn took 15.6 s with the tools off and 16.1 s with them on
  (27,820 and 28,514 tokens).

All three tools are off by default since this measurement.

## Earlier runs on the same suites

| Code | Chat | Unclear | Conversation turns |
|---|---|---|---|
| Before the fixes (4 Nov) | 175 | 30 | 47 |
| Fixed agent (d470d7a) | 178 | 43 | 56 |
| Merged, tools off | 181 | 48 | 61 |
| Merged, tools on | 181 | 47 | 61 |
