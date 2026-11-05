# ADR-0006: Code shows the data; the model describes it and cites it

- Status: **accepted** (28 Oct 2026). Builds on [ADR-0005](ADR-0005-answerer-and-roles.md).
- Evidence: the probe of 28 Oct below, `src/gemini_agent/files.py`, `answer.py` (`cite`,
  `keep_sourced`, `drop_copies`) and `unit_test/gemini_agent/test_files.py`.

## Context

The user asked for "the table of heating_profile.csv" and got a table the model had made up.
The example project only listed that file name; there was no file on the server. Every number
in the made-up rows appeared somewhere in the context, so the number check passed. The chat
also showed the model's Markdown as plain text, and file names were plain words with no link.
The user asked that the chat retrieve any kind of data and show it properly, images included.

## Decision

1. **The example project's files exist.** `data/example_district/` holds the daily heat and
   cold demand for 2025 and the reservoir. These files are synthetic and written from the toy
   model, so they agree with every design (61.8 GWh of heat, 13.7 GWh of cold), and every view
   says they are synthetic. The organisers' data will replace them.
2. **Code reads files; the model never retypes them.**
   - A message that names a file opens it with the `read_file` tool. The name can be exact or
     in words: "the heating profile", "the subsurface data", or "this picture" when there is
     one image.
   - The chat gets the view as CUSTOM `file`. It is one of:
     - a table with its columns, units, first 200 rows, statistics, and energy over the file for
       power columns with a regular time step;
     - a chart, averaged down to 400 points;
     - a text or JSON preview;
     - the image.
   - The answerer gets a summary block of kind `data` and describes what matters.
   - A Markdown table in the reply that copies the file's columns is removed.
3. **Markdown and citations.**
   - The answerer may use bullets, a small table and bold.
   - It ends a sentence with the block it relies on (`[doc1]`, `[data1]`). Code turns these
     into `[^n]`, the number of the source card, and removes citations of blocks with no card.
   - The number check works per table row and per list item, so one bad cell drops its row
     and leaves the table standing.
   - Source cards carry their `kind`, a `file` to open and the figures of the documentation
     section they come from.
4. **Images.**
   - Uploads may be images, and Excel files are accepted too.
   - A question about an image goes to a model that can see it: `qwen3.5:9b` on the GPU, or
     `qwen3.5:4b` on the CPU, since the 1.7B reader cannot see images.
   - The image is sent with the message, never as text.
   - `GET /api/files` serves project files and uploads (`view=1` gives the chat's view);
     `GET /api/doc-image` serves figures from the documentation folders only.

## Consequences

- Probe on 28 Oct, GPU with the 9B answerer:
  - The table, chart, JSON and image requests were all answered by the model in 2.5–6.7 s,
    with no unsourced numbers.
  - Before the copy rule, the model pasted two rows of the file into a table it called
    "complete". The rule and a sharper prompt line (answer_v3) removed that.
  - The image of GEMINI's logo was described correctly.
- Eval runs of 28 Oct, 25 scenarios each, with the answer_v3 prompt:
  - GPU: 24 of 25. The miss was S15: "Hello!" took a retry, because the 9B model wrote the
    reservoir at "250 m" instead of 2,500 m and the number check caught it.
  - CPU (1.7B answers): 24 of 25. The miss was S14: a new rule for polite requests read
    "what can **you** do" as politeness.
  - Earlier in the day, a first run found four more regressions:
    - S03: "a heating profile of 40 GWh" opened the file instead of designing.
    - S16: a dropped source name cost a retry.
    - S21: "give me instructions" was declined.
    - S23: "could you explain …" was read as a question about Dioscuri.
  - Each regression got a rule and a unit test:
    - a file named only in words needs a request to see it;
    - a missing source name is added back without a retry;
    - a reply understood as being about Dioscuri is never declined;
    - only "could you explain/tell/show …" counts as politeness;
    - a greeting matched by pattern gets only the self card, at about 1,570 tokens instead of
      3,565.
  - The affected scenarios were then re-run on both devices, and all passed.
- A file the project lists but the server does not have is reported as missing, never filled
  in.
- Limits:
  - The statistics are those of the file as it is (daily means here), and hourly peaks need
    hourly data.
  - The summary covers the first 12 columns and 8 statistics.
  - A PDF preview is its text, not its pages.
