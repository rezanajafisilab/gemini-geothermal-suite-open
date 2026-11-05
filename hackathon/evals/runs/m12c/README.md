# Measurement of the 5 Nov fixes (rn/fix12c)

The released code (04179bb) with these fixes, on qwen3.5:9b, all three suites. Chat ran on one GPU; unclear and the conversations ran on the other.

1. The context packer puts back what fits after cutting. The picks list was being dropped even when it fitted.
2. Each search pick says, by code, why it is not the best overall: not N-1, routine flaring, or dearer with CO2 at the long-term price.
3. Each what-if is shown before → after against the design it was run on, and a new search's pick is marked as a different design.
4. Code decides when a message refers to nothing, such as a bare number or "the setting we talked about" in an empty chat.
5. A recall followed by a question counts as an answer.
6. The test rules allow the search's picks and the runs already shown.

The answer prompt is as released. A prompt edit tried for fixes 4 and 5 (rn/fix12, ee15b88) lost nine other cases and was left out.

| Code | Chat | Unclear | Conversation turns (checks) |
|---|---|---|---|
| Release (04179bb, tools off) | 181/185 | 48/52 | 61/65 (206/210) |
| rn/fix12 (with the prompt edit) | 181/185 | 49/52 | 61/65 (205/210) |
| **rn/fix12c (this)** | **184/185** | **51/52** | **64/65 (209/210)** |

- **Against the release:** nine cases gained and none lost. The gains are T03.w3, M04.w2, N03.w1, U21.w2, U23.w2, U32.w3, C3.t1, C4.t6 and C4.t10.
- **Still failing:**
  - T04.w1: the model gives a CO2 reason for not picking the cheapest design.
  - U31.w1: "is that a lot?" is asked back.
  - C3.t4: the right value is given without naming the design.
- **Files:** `chat/`, `unclear/` and `conv/` hold the summaries.
