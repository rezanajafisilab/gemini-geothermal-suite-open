// The conversation: the empty state, then one block per turn (question, steps, clarification,
// answer, result card, suggestions), and the composer.

import { Fragment, useEffect, useMemo, useRef, useState, type RefObject } from "react";

import { fileUrl, type Device, type Health } from "../agent/client";
import { FILE_NAME } from "../agent/markdown";
import { designCodeIn, sourcesFor, splitOptions, splitSources } from "../agent/numbers";
import { asksOf, behaviour, confirmReplyOf, leftOut, replyChips, runClaims, runComparison, runCompares, runConfirm, runDecisions, runFailures, runReports, runPlan, runUncertainties, runFiles, runReply, runResults, runSearch, runSources, runText, withoutLeftOut, type ConfirmReply } from "../agent/reducer";
import type { OptionLine } from "../agent/numbers";
import type { Ask, CardOut, ChatState, FileView, OfferDetail, Step, Turn, TurnAttachment } from "../agent/types";
import { attachmentLabel, pendingFiles, type Attachment } from "../state/attachments";
import { KEEP_OPEN } from "../state/flags";
import { EXAMPLES, examplesFor, type Project } from "../state/projects";
import { onAskPicks, sentDesigns } from "../workbench/ask";
import { designItems, type DesignItem } from "../workbench/designList";
import { ID_SEPARATOR } from "../tabs/compare/link";
import { go, hrefFor } from "../workbench/route";
import { useWorkbench, workbench as workbenchStore } from "../workbench/store";
import { DesignsStrip } from "./DesignsStrip";
import { CandidatesCard } from "./CandidatesCard";
import { AnswersBubble, ChoiceBubble, ChoiceCard, ClarifyCard, DecisionCard } from "./ClarifyCard";
import { ComparisonCard } from "./ComparisonCard";
import { Composer, type ComposerHandle } from "./Composer";
import { FileCard } from "./FileCard";
import { FilesContext, useFiles, type FilesApi } from "./filesContext";
import { Arrow, FileGlyph, FileIcon, Spinner } from "./Icons";
import { InputsCard, afterInputs, confirmOptions } from "./InputsCard";
import { LogoLarge } from "./Logo";
import { Markdown, NumberText, type SourceFns } from "./Markdown";
import { MenuButton, answerTarget, menuProps, type MenuTarget } from "../menu";
import { FilePreview, ImageModal } from "./Modal";
import { ApprovalCard, OfferCard, OperatingPoints } from "./ModelGen";
import { CompareCard } from "./CompareCard";
import { DecisionTable } from "./DecisionTable";
import { ReportCard } from "./ReportCard";
import { PlanCard } from "./PlanCard";
import { UncertaintyCard } from "./UncertaintyCard";
import { FailureCard } from "./FailureCard";
import { ResultCard } from "./ResultCard";
import { ErrorCard, FallbackNotice, LeftOutCard, OfflineBanner, OfflineStrip, ReplyChips, StateTag, UnavailableCard } from "./StatusCards";
import { StepsGroup } from "./StepsGroup";
import { InjectionNote, SourceCards, citeId, splitInjectionNote } from "./Sources";

interface Props {
  /** The reader is well above the latest content: a button above the composer takes them down. */
  onJump?: (() => void) | null;
  chat: ChatState | null;
  project: Project;
  running: boolean;
  health: Health;
  checking: boolean;
  draft: string;
  onDraft: (v: string) => void;
  onRecheck: () => void;
  onSend: (text: string, designs?: { id: string; text: string }[]) => void;
  onAnswer: (answers: Record<string, string>) => void;
  onStop: () => void;
  composerRef: RefObject<ComposerHandle | null>;
  device: Device;
  /** Every file of the thread: the composer shows the ones not sent yet, the bubbles their own. */
  attachments: Attachment[];
  onAttach: (files: File[]) => void;
  onDismiss: (name: string) => void;
}


function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, [active]);
  return active ? now : Date.now();
}

export function ChatView({ chat, project, running, health, checking, draft, onDraft, onRecheck, onSend, onAnswer, onStop, onJump, composerRef, device, attachments, onAttach, onDismiss }: Props) {
  const turns = chat?.turns ?? [];
  const last = turns[turns.length - 1];
  const now = useNow(last?.status === "running");
  const offline = health.state === "model-offline" || health.state === "server-offline";

  // File previews and full-size images, opened from anywhere in the answers.
  const [preview, setPreview] = useState<string | null>(null);
  const [image, setImage] = useState<{ url: string; caption?: string } | null>(null);
  const files = useMemo<FilesApi>(() => ({ open: setPreview, showImage: setImage }), []);
  // The conversation's designs: the strip at the top and the composer's @ list.
  const wb = useWorkbench();
  const designs = useMemo(() => designItems(wb.workbench), [wb.workbench]);
  // The chat reads the conversation's designs too (the strip, the @ list): fetched once a turn
  // ends with something to show, not only when a design tab is opened.
  const hasDesigns = turns.some((t) => (t.cards?.length ?? 0) > 0 || !!t.result);
  useEffect(() => {
    if (chat?.threadId && hasDesigns && last?.status !== "running") void workbenchStore.load(chat.threadId, { force: true });
  }, [chat?.threadId, hasDesigns, last?.status, turns.length]);
  const [picked, setPicked] = useState<DesignItem[]>([]);
  useEffect(() => setPicked([]), [chat?.threadId]);
  // The quick-ask box's @ picks, when its question comes to the composer unsent.
  useEffect(() => onAskPicks(setPicked), []);
  const send = (text: string) => {
    onSend(text, sentDesigns(picked));
    setPicked([]);
  };
  // After "Change an input first" the agent waits for the change: the composer takes it.
  const focusComposer = () => setTimeout(() => composerRef.current?.focus(), 0);
  // Files the chat's runs already opened are shown from their events, with no request.
  const known = useMemo(() => {
    const map = new Map<string, FileView>();
    for (const t of turns) for (const f of t.files ?? []) map.set(f.file.name.toLowerCase(), f.file);
    return map;
  }, [turns]);
  // A sent image's thumbnail: the upload's own preview this visit, else the file on the server
  // (a replayed scene has no server; its chips keep the plain glyph).
  const thumb = (name: string): string | undefined => {
    const own = attachments.find((f) => f.name === name)?.preview;
    if (own) return own;
    const id = chat?.threadId;
    return id && !id.startsWith("replay-") ? fileUrl(id, name) : undefined;
  };

  // A new chat starts empty in every project (5 Nov): the examples, and no design until the
  // user runs one. The challenge's recommended design is no longer put in front of it.
  return (
    <FilesContext.Provider value={files}>
      <main className="main">
        {offline && turns.length === 0 && <OfflineBanner health={health} checking={checking} onRetry={onRecheck} />}

        {turns.length === 0 && (
          <section className="empty ta-rise">
            <LogoLarge />
            <h1>What should we design today?</h1>
            <div className="examples">
              {examplesFor(project).map((ex, i) => (
                <button
                  key={ex.title}
                  type="button"
                  className="example ta-btn ta-chip"
                  onClick={() => {
                    onDraft(ex.text);
                    setTimeout(() => composerRef.current?.focus(), 0);
                  }}
                >
                  <span className="icon-box" style={{ background: ex.tint }}>
                    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                      <path d={ex.icon} fill="none" stroke={ex.stroke} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>{ex.title}</span>
                  <span style={{ fontSize: 13, color: "#66727C" }}>{i === 0 && !project.files.length ? "Attach the demand profiles first" : ex.sub}</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {turns.map((t, i) => (
          <TurnView
            key={t.id}
            turn={t}
            isLast={i === turns.length - 1}
            now={now}
            running={running}
            onAnswer={onAnswer}
            onSend={onSend}
            thumb={thumb}
            reply={confirmReplyOf(turns[i + 1])}
          />
        ))}

        {/* Room below the last answer, so a new question can sit at the top of the view while its
            answer grows under it (App.tsx sizes it). */}
        <div className="chat-spacer" data-chat-spacer aria-hidden="true" />

        <Composer
          ref={composerRef}
          draft={draft}
          onDraft={onDraft}
          running={running}
          waiting={last?.status === "waiting"}
          placeholder={last && changingInput(last) ? "Type what to change, e.g. a 50 °C heating return" : undefined}
          onSend={send}
          designs={designs}
          picked={picked}
          onPicked={setPicked}
          onCompare={(ids) => go("compare", ids.join(ID_SEPARATOR))}
          onStop={onStop}
          onJump={onJump}
          health={health}
          device={device}
          attachments={pendingFiles(attachments)}
          onAttach={onAttach}
          onDismiss={onDismiss}
          notice={offline && turns.length > 0 && !last?.unavailable ? <OfflineStrip health={health} checking={checking} onRetry={onRecheck} /> : null}
          footer={
            designs.length > 0 && turns.length > 0 ? (
              <DesignsStrip
                items={designs}
                attempts={wb.workbench?.attempts ?? []}
                turns={turns}
                onAsk={(d) => {
                  setPicked((p) => [...p.filter((x) => x.id !== d.id), d]);
                  focusComposer();
                }}
              />
            ) : null
          }
        />
      </main>
      {preview && <FilePreview key={preview} name={preview} threadId={chat?.threadId} known={known.get(preview.toLowerCase())} onClose={() => setPreview(null)} />}
      {image && <ImageModal url={image.url} caption={image.caption} onClose={() => setImage(null)} />}
    </FilesContext.Provider>
  );
}

/** The turn waits for the change after "Change an input first" on its inputs card. */
function changingInput(turn: Turn): boolean {
  if (turn.status !== "waiting") return false;
  const asks = asksOf(turn);
  const a = asks[asks.length - 1];
  if (a?.value.kind !== "confirm" || !a.answers) return false;
  const [, change] = confirmOptions(a, runConfirm(turn, a.run)?.value);
  return Object.values(a.answers).includes(change);
}

interface TurnProps {
  turn: Turn;
  isLast: boolean;
  now: number;
  running: boolean;
  onAnswer: (answers: Record<string, string>) => void;
  onSend: (text: string) => void;
  thumb: (name: string) => string | undefined;
  /** How the agent read the next message, when it answered this turn's inputs card. */
  reply?: ConfirmReply;
}

export function TurnView({ turn, isLast, now, running, onAnswer, onSend, thumb, reply }: TurnProps) {
  // The steps stay folded while the agent works (their head says what it is doing); open on an
  // error, or when the user opens them.
  const [open, setOpen] = useState(turn.status === "error");
  const [focus, setFocus] = useState<string | null>(null);
  const prev = useRef(turn.status);
  const focusTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Folded while working or asking (the head says what is going on), open on an error, and as
  // set once the answer is in.
  useEffect(() => {
    if (prev.current !== turn.status) {
      if (turn.status === "done") setOpen(KEEP_OPEN);
      else if (turn.status === "error") setOpen(true);
      prev.current = turn.status;
    }
  }, [turn.status]);
  useEffect(() => () => void (focusTimer.current && clearTimeout(focusTimer.current)), []);

  const b = behaviour(turn);
  // The model was unavailable: that run's notice is its answer. With a fallback (rules decided
  // instead of the reasoning model) the run goes on to a normal answer.
  const blockedRun = turn.unavailable && !turn.unavailable.fallback ? (turn.unavailable.run ?? 0) : -1;
  const asks = asksOf(turn);
  const lastAsk = asks[asks.length - 1];
  const decisionAsk = [...asks].reverse().find((a) => a.value.kind === "decision");
  // An approval belongs to the offer with the same generation id (by order for older streams).
  const offerFor = (a: Ask): OfferDetail | undefined => {
    const offers = asks.filter((x) => x.value.kind === "offer");
    const same = a.value.generation_id ? offers.find((x) => x.value.generation_id === a.value.generation_id) : undefined;
    return (same ?? [...offers].reverse().find((x) => x.run <= a.run))?.value.details as OfferDetail | undefined;
  };
  const cards: CardOut[] = turn.cards?.length
    ? turn.cards
    : turn.result
      ? [{ run: Math.max(0, turn.runs.length - 1), result: turn.result, checks: turn.checks }]
      : [];

  // Open the steps group, scroll to one step and flash it.
  const showStep = (step: Step) => {
    setOpen(true);
    setFocus(step.key);
    if (focusTimer.current) clearTimeout(focusTimer.current);
    focusTimer.current = setTimeout(() => setFocus(null), 2400);
    setTimeout(() => {
      document.getElementById(`step-${turn.id}-${step.key.replace(/[^\w-]/g, "_")}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 60);
  };
  const showSource = (unit: string, after: string) => {
    for (const name of sourcesFor(unit, after)) {
      const step = [...turn.steps].reverse().find((s) => s.name === name && s.status === "done");
      if (step) return showStep(step);
    }
  };
  const hasSource = (unit: string, after: string) =>
    sourcesFor(unit, after).some((name) => turn.steps.some((s) => s.name === name && s.status === "done"));

  const askBlock = (a: Ask, i: number) => {
    const active = turn.status === "waiting" && isLast && a === lastAsk && !a.answers;
    const skipped = !a.answers && (a.skipped || turn.skipped || a !== lastAsk || turn.status !== "waiting");
    const kind = a.value.kind ?? "inputs";
    if (kind === "confirm") {
      // The inputs card: its rows, or the agent's Markdown table when the rows didn't come.
      return (
        <InputsCard
          key={`ask-${i}`}
          ask={a}
          inputs={runConfirm(turn, a.run)?.value}
          after={afterInputs(turn, a.run)}
          id={`inputs-${turn.id}-${i}`}
          active={active}
          skipped={!a.answers && !!(a.skipped || turn.skipped)}
          reply={a === lastAsk ? reply : undefined}
          running={running}
          onAnswer={onAnswer}
          onSend={onSend}
        />
      );
    }
    if (kind === "offer" || kind === "approval") {
      return (
        <Fragment key={`ask-${i}`}>
          {kind === "offer" ? (
            <OfferCard ask={a} active={active} onSubmit={onAnswer} />
          ) : (
            <ApprovalCard ask={a} generation={turn.generation} offer={offerFor(a)} active={active} onSubmit={onAnswer} />
          )}
          {a.answers && <ChoiceBubble ask={a} />}
        </Fragment>
      );
    }
    if (kind === "choice") {
      // The model's question stays in the conversation as its reply; the pick follows as yours.
      if (active) return <ChoiceCard key={`ask-${i}-${turn.runs.length}`} ask={a} id={`${turn.id}-${i}`} onSubmit={onAnswer} />;
      return (
        <Fragment key={`ask-${i}`}>
          <p className="choice-asked ta-rise">{a.value.intro || a.value.questions[0]?.label}</p>
          {a.answers ? (
            <ChoiceBubble ask={a} />
          ) : skipped ? (
            <p className="muted-line">
              <span className="sq" style={{ background: "#66727C" }} />
              Not picked: you asked something else.
            </p>
          ) : null}
        </Fragment>
      );
    }
    if (active)
      return kind === "decision" ? (
        <DecisionCard key={`ask-${i}-${turn.runs.length}`} turn={turn} onSubmit={onAnswer} />
      ) : (
        <ClarifyCard key={`ask-${i}-${turn.runs.length}`} turn={turn} onSubmit={onAnswer} />
      );
    if (a.answers) return kind === "decision" ? <ChoiceBubble key={`ask-${i}`} ask={a} /> : <AnswersBubble key={`ask-${i}`} ask={a} />;
    if (skipped)
      return (
        <p key={`ask-${i}`} className="muted-line">
          <span className="sq" style={{ background: "#66727C" }} />
          {kind === "decision" ? "Decision skipped" : "Question skipped"}: you asked something else.
        </p>
      );
    return null;
  };

  const runCount = Math.max(1, turn.runs.length);
  // The run being worked on shows nothing until it is done: its answer appears whole, not word by
  // word with cards arriving under it (earlier runs of the turn, such as the inputs card, stay).
  const working = turn.status === "running" ? runCount - 1 : -1;
  // The message's context menu: edit and resend, resend on the other device, copy.
  const message: MenuTarget = { kind: "message", text: turn.message, resend: () => onSend(turn.message) };
  return (
    <>
      <div className="user-row ta-rise" data-turn={turn.id}>
        <MenuButton small target={message} label="More for your message: edit, resend, copy" className="msg-more" />
        <p className="bubble" {...menuProps(message)}>
          {turn.designs && turn.designs.length > 0 && (
            <span className="bubble-designs" aria-label="About these designs">
              {turn.designs.map((d) => (
                <span key={d.id} className="bubble-design">
                  @{d.text}
                </span>
              ))}
            </span>
          )}
          {turn.message}
          {turn.attachments && turn.attachments.length > 0 && <SentFiles files={turn.attachments} thumb={thumb} />}
        </p>
      </div>

      {(turn.steps.length > 0 || turn.status === "running") && (
        <StepsGroup turn={turn} open={open} onToggle={() => setOpen(!open)} focusKey={focus} now={now} />
      )}

      {Array.from({ length: runCount }, (_, r) => (
        <Fragment key={r}>
          {r !== blockedRun && r !== working && (
            <RunOutput
              turn={turn}
              run={r}
              cards={cards.filter((c) => c.run === r)}
              optionsInCard={!!decisionAsk && r === decisionAsk.run}
              picked={!!decisionAsk?.answers && r > decisionAsk.run}
              hasSource={hasSource}
              onSource={showSource}
              onShowStep={showStep}
            />
          )}
          {r === blockedRun && r !== working && <UnavailableCard value={turn.unavailable!} canRetry={isLast && !running} onRetry={() => onSend(turn.message)} />}
          {r !== working && asks.map((a, i) => (a.run === r ? askBlock(a, i) : null))}
        </Fragment>
      ))}

      {turn.status === "error" && turn.error && (
        <ErrorCard turn={turn} canRetry={isLast && !running} onRetry={() => onSend(turn.message)} />
      )}

      {turn.status === "stopped" && (
        <p className="muted-line ta-rise">
          <span className="sq" style={{ background: "#66727C" }} />
          Stopped. Nothing more was reported; ask again when you're ready.
        </p>
      )}

      {isLast && turn.status === "done" && turn.suggestions && turn.suggestions.length > 0 && (
        <Suggestions items={turn.suggestions} routes={b === "refuse" || b === "nonsense"} disabled={running} onPick={onSend} />
      )}
    </>
  );
}

/**
 * What one run said: its state tag, text (numbers as chips, sources and any injection note
 * apart), the passages it cited, left-out designs, cards and a generated model's results.
 */
function RunOutput({
  turn,
  run,
  cards,
  optionsInCard,
  hasSource,
  onSource,
  onShowStep,
  picked,
}: { turn: Turn; run: number; cards: CardOut[]; optionsInCard: boolean; picked: boolean; onShowStep: (step: Step) => void } & SourceFns) {
  const [showDraft, setShowDraft] = useState(false);
  const [citeFocus, setCiteFocus] = useState<{ n: number; at: number } | null>(null);
  const summary = turn.runs[run]?.summary;
  const dropped = leftOut(turn, run);
  const draft = summary?.draft;
  let text = runText(turn, run);
  if (showDraft && draft) text = draft;
  if (dropped.length) text = withoutLeftOut(text);
  const injection = splitInjectionNote(text);
  const split = splitSources(injection.text);
  const body = split.text;
  // The reasoning model may reword "Source: ..." away; the template keeps it, so take it from there.
  const sources = split.sources.length || !draft ? split.sources : splitSources(draft).sources;
  const parts = splitOptions(body);
  // A decision's options are drawn in its card, so the text keeps only the lead.
  const options = optionsInCard ? [] : parts.options;
  const notice = turn.unavailable?.fallback && (turn.unavailable.run ?? 0) === run ? turn.unavailable : null;
  const passages = runSources(turn, run);
  const docsStep = turn.steps.find((s) => s.run === run && s.name === "docs");
  const results = runResults(turn, run);
  const files = runFiles(turn, run);
  const evaluated = results.length > 0;
  // How the answerer read the message: general background, outside the scope, not a question,
  // or the checked template. A chip under the text replaces a state tag that would say the same
  // ("Off-topic") or the opposite ("From the project data").
  const chips = replyChips(runReply(turn, run));
  // Sentences the claim checker took out of the reply: a chip that opens its step.
  const claims = runClaims(turn, run);
  const removed = claims && !claims.skipped ? claims.removed : 0;
  const comparison = runComparison(turn, run);
  const search = runSearch(turn, run);
  const failures = runFailures(turn, run);
  const compares = runCompares(turn, run);
  const plan = runPlan(turn, run);
  const decisions = runDecisions(turn, run);
  const reports = runReports(turn, run);
  const uncertainties = runUncertainties(turn, run);
  // A reply that names a design but shows no card still links to that design's tabs.
  const code = cards.length ? undefined : designCodeIn(body);
  let tag = answerKind(summary?.behaviour ?? undefined, !!docsStep, !!evaluated, turn.steps.some((s) => s.run === run && s.name === "lookup"));
  if (chips.some((c) => c !== "fallback") && (tag === "refuse" || tag === "answer" || tag === "answer_docs")) tag = undefined;
  if (!body && !cards.length && !comparison && !search && !notice && !dropped.length && !passages.length && !results.length && !files.length && !failures.length && !compares.length && !plan && !decisions.length && !uncertainties.length && !reports.length) return null;
  // A [^n] chip: scroll to source card n, open it and flash it.
  const citePrefix = `cite-${turn.id}-${run}`;
  const showCite = (n: number) => {
    setCiteFocus({ n, at: Date.now() });
    setTimeout(() => document.getElementById(citeId(citePrefix, n))?.scrollIntoView({ block: "center", behavior: "smooth" }), 30);
  };
  return (
    <article className="answer" aria-label="Answer">
      {notice && <FallbackNotice value={notice} />}
      {plan && <PlanCard value={plan} />}
      {body && <StateTag behaviour={tag} />}
      {body && <Markdown className="answer-text ta-rise" text={parts.lead} hasSource={hasSource} onSource={onSource} cites={passages.length} onCite={showCite} rootProps={menuProps(() => answerTarget(text))} />}
      {injection.note && <InjectionNote note={injection.note} />}
      {sources.length > 0 && (
        <div className="sources" aria-label="Sources">
          {sources.map((src) => (
            <SourceChip key={src} text={src} />
          ))}
        </div>
      )}
      {body && (chips.length > 0 || removed > 0) && (
        <ReplyChips chips={chips} removed={removed} onRemoved={claims?.step ? () => onShowStep(claims.step!) : undefined} />
      )}
      {draft && (
        <div className="answer-foot">
          <span className="tag tag-teal">{showDraft ? "template" : `reworded by ${modelOf(turn, "write") ?? modelOf(turn, "answer") ?? "the reasoning model"}`}</span>
          <button type="button" className="link-btn" onClick={() => setShowDraft(!showDraft)} aria-pressed={showDraft}>
            {showDraft ? "Show the reworded answer" : "Show the template"}
          </button>
          <span className="note" style={{ fontSize: 12.5 }}>
            {showDraft ? "The answer the code wrote; the model only rewords it." : "Same numbers, checked against the tools."}
          </span>
        </div>
      )}
      {body && (
        <div className="answer-actions">
          <MenuButton small target={() => answerTarget(text)} label="More for this answer: copy as Markdown, flag a statement" />
        </div>
      )}
      {code && (
        <nav className="card-links reply-links" aria-label={`${code} in the tabs`}>
          <a href={hrefFor("design", code)}>
            Open in Design <Arrow size={12} />
          </a>
          <a href={hrefFor("economics", code)}>
            Economics <Arrow size={12} />
          </a>
        </nav>
      )}
      {files.map((f) => (
        <FileCard key={f.name} file={f} />
      ))}
      {results.map((r, i) => (
        <OperatingPoints key={i} result={r} />
      ))}
      {options.length > 0 && <OptionsCard options={options} hasSource={hasSource} onSource={onSource} />}
      {dropped.length > 0 && <LeftOutCard items={dropped} />}
      {cards.map((c, i) => (
        <ResultCard key={i} card={c.result} checks={c.checks} picked={picked} />
      ))}
      {failures.map((f, i) => (
        <FailureCard key={`f${i}`} value={f} />
      ))}
      {compares.map((c, i) => (
        <CompareCard key={`c${i}`} value={c} />
      ))}
      {decisions.map((d, i) => (
        <DecisionTable key={`d${i}`} value={d} />
      ))}
      {uncertainties.map((u, i) => (
        <UncertaintyCard key={`u${i}`} value={u} />
      ))}
      {reports.map((r, i) => (
        <ReportCard key={`r${i}`} value={r} />
      ))}
      {search && search.chosen && search.show && <CandidatesCard value={search} />}
      {comparison && <ComparisonCard value={comparison} />}
      {passages.length > 0 && (
        <SourceCards
          passages={passages}
          backend={typeof docsStep?.meta.backend === "string" ? docsStep.meta.backend : undefined}
          idPrefix={citePrefix}
          focus={citeFocus}
        />
      )}
    </article>
  );
}

/** "answer" covers lookups, document answers, a generated model's results and plain replies. */
function answerKind(b: string | undefined, docs: boolean, model: boolean, lookup: boolean): string | undefined {
  if (b !== "answer") return b;
  if (model) return "answer_model";
  if (docs) return "answer_docs";
  return lookup ? "answer" : undefined;
}

function modelOf(turn: Turn, purpose: string): string | undefined {
  return [...turn.usage].reverse().find((u) => u.purpose === purpose && u.ok)?.model;
}

/**
 * The files sent with a message, as chips under its text. They stay with this message only: the
 * agent keeps searching them for the rest of the chat, but later bubbles don't repeat them.
 */
function SentFiles({ files, thumb }: { files: TurnAttachment[]; thumb: (name: string) => string | undefined }) {
  return (
    <span className="bubble-files" aria-label="Sent with this message">
      {files.map((a) => {
        const label = a.uploading ? "uploading" : attachmentLabel(a.kind, a.chunks);
        return (
          <span key={a.name} className="file-chip sent" title={a.uploading ? `${a.name}: still uploading; the agent reads it once it's in` : a.name}>
            {a.uploading ? <Spinner size={13} light /> : a.kind === "image" ? <Thumb url={thumb(a.name)} /> : <FileIcon />}
            <span>{a.name}</span>
            {label && <em>{label}</em>}
          </span>
        );
      })}
    </span>
  );
}

/** An image chip's thumbnail; the plain file glyph when there is none or it doesn't load. */
function Thumb({ url }: { url?: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) return <FileIcon />;
  return <img className="file-thumb" src={url} alt="" onError={() => setFailed(true)} />;
}

/** A "Source: …" chip under a lookup answer; one that names a file opens it. */
function SourceChip({ text }: { text: string }) {
  const files = useFiles();
  const name = text.match(FILE_NAME)?.[0];
  if (!name)
    return (
      <span className="source">
        <FileIcon />
        {text}
      </span>
    );
  return (
    <button type="button" className="source source-open ta-btn ta-chip" title={`Open ${name}`} onClick={() => files.open(name)}>
      <FileGlyph name={name} />
      {text}
    </button>
  );
}

/** An infeasible answer's options, one row each: what it is, how much heat it covers, its cost. */
function OptionsCard({ options, ...fns }: { options: OptionLine[] } & SourceFns) {
  return (
    <section className="card options ta-rise" style={{ animationDelay: ".08s" }} aria-label="Designs that would work">
      <span className="options-title">Ways to meet the brief</span>
      {options.map((o) => (
        <div key={o.label} className="option-row">
          <span className="option-label">{o.label}</span>
          <span className="option-bar" role="img" aria-label={`${o.coverage ?? 0}% of the heat covered`}>
            <span className="ta-grow" style={{ width: `${Math.min(100, o.coverage ?? 0)}%`, background: (o.coverage ?? 0) >= 99.95 ? "#C24E1C" : "#E3A33B" }} />
          </span>
          <span className="option-detail">
            <NumberText text={o.detail.replace(/\.$/, "")} {...fns} />
          </span>
        </div>
      ))}
    </section>
  );
}

const ROUTE_ICONS = [
  { icon: EXAMPLES[0].icon, tint: EXAMPLES[0].tint, stroke: EXAMPLES[0].stroke },
  { icon: EXAMPLES[1].icon, tint: EXAMPLES[1].tint, stroke: EXAMPLES[1].stroke },
  { icon: "M8 1.8v12.4M2.6 4.9l10.8 6.2M2.6 11.1l10.8-6.2", tint: "#E2F3F5", stroke: "#0A6F7C" },
];

function Suggestions({ items, routes, disabled, onPick }: { items: string[]; routes: boolean; disabled: boolean; onPick: (t: string) => void }) {
  if (routes)
    return (
      <div role="group" aria-label="Back to the design" className="ta-rise" style={{ animationDelay: ".2s", display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((s, i) => {
          const r = ROUTE_ICONS[i % ROUTE_ICONS.length];
          return (
            <button key={s} type="button" className="route ta-btn ta-chip" disabled={disabled} onClick={() => onPick(s)}>
              <span className="icon-box" style={{ background: r.tint }}>
                <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
                  <path d={r.icon} fill="none" stroke={r.stroke} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{s}</span>
              <span style={{ marginLeft: "auto", color: "#66727C", display: "inline-flex" }}>
                <Arrow />
              </span>
            </button>
          );
        })}
      </div>
    );
  return (
    <div className="followups ta-rise" style={{ animationDelay: ".32s" }}>
      {items.map((s) => (
        <button key={s} type="button" className="followup ta-btn ta-chip" disabled={disabled} onClick={() => onPick(s)}>
          {s}
        </button>
      ))}
    </div>
  );
}
