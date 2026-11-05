import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { deleteProject, fetchHealth, liveTransport, sleep, type Device, type Health, type Size } from "./agent/client";
import { pickDevice, pickSize } from "./agent/models";
import { ZERO, chatTotals } from "./agent/reducer";
import { ChatView } from "./components/ChatView";
import type { ComposerHandle } from "./components/Composer";
import { CommandPalette } from "./components/CommandPalette";
import { Header } from "./components/Header";
import { REVEAL_TOP } from "./components/InputsCard";
import { FilePreview } from "./components/Modal";
import { NewProjectDialog, RemoveProjectDialog } from "./components/ProjectDialogs";
import { RemoveChatDialog } from "./components/RemoveChatDialog";
import { Sidebar } from "./components/Sidebar";
import { SCENES, fixtureTransport, turnSteps } from "./fixtures/scenes";
import { CHALLENGE_ID, useProjects, type Project } from "./state/projects";
import { newThreadId, store, useStore } from "./state/store";
import { TAB_PAGES } from "./tabs";
import { onAsk, onSendAsk } from "./workbench/ask";
import { PageSkeleton } from "./workbench/components/Skeleton";
import { TabBoundary } from "./workbench/components/TabBoundary";
import { TAB_META, go, useRoute } from "./workbench/route";
import { useWorkbench, useWorkbenchSync, workbench } from "./workbench/store";

const params = new URLSearchParams(window.location.search);
const FIXTURE = params.get("fixture");
const SCENE = FIXTURE ? SCENES[FIXTURE] : undefined;
const HEALTH_OVERRIDE = (params.get("health") ?? SCENE?.health) as Health["state"] | undefined;
store.pace = params.get("pace") !== "0";
const REPLAY_ID = FIXTURE && SCENE ? `replay-${FIXTURE}-${Date.now().toString(36)}` : null;
let replayStarted = false;

const PREF = "dioscuri.v2.prefs";
function readPrefs(): { project: string; open: Record<string, string | null> } {
  try {
    const p = JSON.parse(localStorage.getItem(PREF) || "{}");
    return { project: typeof p.project === "string" ? p.project : CHALLENGE_ID, open: p.open ?? {} };
  } catch {
    return { project: CHALLENGE_ID, open: {} };
  }
}


function useHealth() {
  const [health, setHealth] = useState<Health>({ state: "checking" });
  const [checking, setChecking] = useState(false);
  const check = useCallback(async () => {
    setChecking(true);
    const h = await fetchHealth();
    setHealth(HEALTH_OVERRIDE ? { ...h, state: HEALTH_OVERRIDE, model: h.model ?? "qwen3:1.7b" } : h);
    setChecking(false);
  }, []);
  useEffect(() => {
    void check();
    const id = setInterval(check, 15000);
    const onFocus = () => void check();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [check]);
  return { health, checking, check };
}

export default function App() {
  const state = useStore();
  const prefs = useMemo(readPrefs, []);
  const { projects, state: projectsState, refresh: refreshProjects, add: addProject, remove: forgetProject } = useProjects();
  const [projectId, setProjectId] = useState(REPLAY_ID ? CHALLENGE_ID : prefs.project);
  const [openByProject, setOpenByProject] = useState<Record<string, string | null>>(
    REPLAY_ID ? { ...prefs.open, [CHALLENGE_ID]: REPLAY_ID } : prefs.open,
  );
  const [newProject, setNewProject] = useState(false);
  const [removing, setRemoving] = useState<Project | null>(null);
  // The chat whose removal waits for the user's yes (the sidebar's cross or menu).
  const [removingChat, setRemovingChat] = useState<{ id: string; projectId: string } | null>(null);
  const [sideFile, setSideFile] = useState<string | null>(null);
  // Each tab keeps its scroll position per chat; clicking the tab on show again reloads it.
  const tabPanel = useRef<HTMLElement>(null);
  const tabScroll = useRef<Record<string, number>>({});
  const [reloads, setReloads] = useState(0);
  const [fresh, setFresh] = useState(newThreadId);
  const [draft, setDraft] = useState("");
  const [drawer, setDrawer] = useState(false);
  const { health, checking, check } = useHealth();
  // The project list comes from the server: ask again when it is back.
  useEffect(() => {
    if (projectsState === "offline" && (health.state === "ok" || health.state === "model-offline")) void refreshProjects();
  }, [health.state, projectsState, refreshProjects]);
  // The GPU | CPU pick lasts for this visit: each load starts on the GPU when the server found
  // one (the server's default), else on the CPU.
  const [devicePick, setDevicePick] = useState<Device | null>(null);
  const device = pickDevice(devicePick, health);
  const chooseDevice = (d: Device) => setDevicePick(d);
  useEffect(() => {
    store.device = device;
  }, [device]);
  // The Auto | 9B | 4B pick, for this visit too: auto takes the first model that fits.
  const [sizePick, setSizePick] = useState<Size | null>(null);
  const size = pickSize(sizePick, health);
  useEffect(() => {
    store.size = size;
  }, [size]);
  const composer = useRef<ComposerHandle>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  // The question the chat holds in view while its answer is written (a turn id), the number of
  // questions when one was just sent (until it shows), and whether to scroll it into place.
  const anchor = useRef<string | null>(null);
  const pending = useRef<number | null>(null);
  const scrollToIt = useRef(false);
  const held = useRef(0); // where the reader is while a question is held in view
  const userScroll = useRef(0); // when the reader last scrolled by hand
  // Until when the view moves on its own (after a card's button): the wheel's momentum and the
  // glide's own scroll events are not the reader's (3 Nov: Run left the view on empty space).
  const gliding = useRef(0);
  const byHand = () => {
    const now = performance.now();
    if (now > gliding.current) userScroll.current = now;
  };
  const questions = () => scroller.current?.querySelectorAll(".user-row[data-turn]").length ?? 0;
  const chatScroll = useRef(0);
  // Well above the latest content (not the room kept under it): the composer offers "Latest".
  const [far, setFar] = useState(false);
  const route = useRoute();
  const onChat = route.tab === "chat";
  const onChatRef = useRef(onChat);
  onChatRef.current = onChat;

  // A project removed elsewhere (or not listed yet) shows the challenge district.
  const project = projects.find((p) => p.id === projectId) ?? projects[0];
  const wanted = openByProject[project.id];
  const current = wanted && state.chats[wanted] ? wanted : null;
  const threadId = current ?? fresh;
  const chat = current ? state.chats[current] : null;
  const running = store.isRunning(threadId);
  const totals = chat ? chatTotals(chat) : ZERO;

  // The tabs read this chat's designs; the header's tab links carry the design picked.
  useWorkbenchSync(threadId, route);
  const { selectedId } = useWorkbench();

  // "Ask about this" on a tab: the chat, with the question in the composer (not sent).
  const [asked, setAsked] = useState(0);
  useEffect(
    () =>
      onAsk((text) => {
        setDraft(text);
        setAsked((n) => n + 1);
      }),
    [],
  );
  useEffect(() => {
    if (!asked || !onChat) return;
    stick.current = true;
    anchor.current = null;
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "instant" });
    composer.current?.focus();
  }, [asked, onChat]);

  // The chat stays mounted (out of sight, not display: none, so its cards don't animate in again)
  // while a tab shows; back on it, it is where you left it.
  useLayoutEffect(() => {
    const el = scroller.current;
    if (onChat && el) el.scrollTop = stick.current ? el.scrollHeight : chatScroll.current;
  }, [onChat]);

  // Back on a tab: return to where the reader left it. Its data may still be loading, so the
  // position is applied as the page grows, until reached or the reader scrolls first.
  const restoring = useRef(false);
  useLayoutEffect(() => {
    const el = tabPanel.current;
    if (onChat || !el) return;
    const target = tabScroll.current[`${threadId}:${route.tab}`] ?? 0;
    el.scrollTop = 0;
    if (target <= 0) return;
    restoring.current = true;
    let frame = 0;
    const until = performance.now() + 4000;
    const stop = () => {
      restoring.current = false;
      cancelAnimationFrame(frame);
      el.removeEventListener("wheel", stop);
      el.removeEventListener("touchstart", stop);
      el.removeEventListener("keydown", stop);
    };
    const step = () => {
      el.scrollTop = target;
      if (Math.abs(el.scrollTop - target) < 2 || performance.now() > until) return stop();
      frame = requestAnimationFrame(step);
    };
    el.addEventListener("wheel", stop, { passive: true });
    el.addEventListener("touchstart", stop, { passive: true });
    el.addEventListener("keydown", stop);
    step();
    return stop;
  }, [onChat, route.tab, reloads, threadId]);

  useEffect(() => {
    try {
      const open = Object.fromEntries(Object.entries(openByProject).filter(([, id]) => id && !id.startsWith("replay-")));
      localStorage.setItem(PREF, JSON.stringify({ project: projectId, open }));
    } catch {
      /* storage blocked */
    }
  }, [projectId, openByProject]);

  const select = useCallback(
    (id: string | null) => {
      setOpenByProject((o) => ({ ...o, [project.id]: id }));
      setDrawer(false);
      stick.current = true;
    },
    [project.id],
  );
  // Picking or starting a chat from the drawer shows the chat.
  const openChat = (id: string | null) => {
    select(id);
    go("chat");
  };

  // Fixture replay: play a recorded scene into its own chat (never saved), no backend needed.
  useEffect(() => {
    if (!SCENE || !REPLAY_ID || replayStarted) return;
    replayStarted = true;
    const id = REPLAY_ID;
    const queue = SCENE.turns.flatMap((t) => turnSteps(t).fixtures);
    const upto = Number(params.get("upto")) || undefined;
    store.setTransport(id, fixtureTransport(queue, liveTransport, { upto }));
    void (async () => {
      for (const turn of SCENE.turns) {
        await store.send(CHALLENGE_ID, id, turn.message, { replay: true, reasoning: turn.reasoning });
        if (params.get("auto") !== "0") {
          for (const answers of turnSteps(turn).answers) {
            await sleep(700);
            await store.answer(id, answers);
          }
        }
        await sleep(400);
      }
    })();
  }, []);

  // The server keeps a thread's attachments; take its list when a chat opens.
  useEffect(() => {
    if (current && !current.startsWith("replay-")) void store.syncFiles(current);
  }, [current]);

  // A sent question goes to the top of the view and stays there while its answer grows below
  // it: the chat never jumps to the end of a reply being written, so the reader starts at the
  // question and the start of the answer. The spacer under the last answer makes the room, and
  // grows back when the answer shrinks (its steps fold away at the end), so nothing moves.
  const fitAnchor = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    const spacer = el.querySelector<HTMLElement>("[data-chat-spacer]");
    if (!anchor.current) {
      if (spacer && spacer.offsetHeight) spacer.style.height = "0px";
      return;
    }
    const row = el.querySelector<HTMLElement>(`.user-row[data-turn="${CSS.escape(anchor.current)}"]`);
    if (!row) return;
    const top = Math.max(0, row.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop - 16);
    const room = spacer ? spacer.offsetHeight : 0;
    const content = el.scrollHeight - room;
    // Enough room to show the question at the top, and to stay where the reader is.
    const need = Math.max(0, top + el.clientHeight - content, held.current + el.clientHeight - content);
    if (spacer && Math.abs(need - room) > 0.5) spacer.style.height = `${need}px`;
    if (!scrollToIt.current && el.scrollTop < held.current - 1) el.scrollTop = held.current;
    return top;
  }, []);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const rows = el.querySelectorAll<HTMLElement>(".user-row[data-turn]");
    const sent = pending.current;
    if (sent !== null && rows.length > sent) {
      pending.current = null;
      anchor.current = rows[rows.length - 1].dataset.turn ?? null;
      scrollToIt.current = true;
    }
    if (!anchor.current) {
      fitAnchor();
      if (stick.current && sent === null) el.scrollTo({ top: el.scrollHeight, behavior: "instant" });
      return;
    }
    const top = fitAnchor();
    if (scrollToIt.current && top !== undefined) {
      scrollToIt.current = false;
      held.current = top;
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      el.scrollTo({ top, behavior: reduce ? "instant" : "smooth" });
    }
  }, [chat, fitAnchor]);
  useEffect(() => {
    const main = scroller.current?.firstElementChild;
    if (!main || typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(() => fitAnchor());
    watch.observe(main);
    return () => watch.disconnect();
  }, [fitAnchor, onChat]);
  // When the work finishes, the chat goes to the start of the latest response, wherever the
  // reader scrolled meanwhile: the question just above it (or, for a long question, the
  // response's first line at the top).
  const wasRunning = useRef(false);
  const toLatest = useCallback(() => {
    const el = scroller.current;
    if (!el || !onChatRef.current) return;
    const rows = el.querySelectorAll<HTMLElement>(".user-row[data-turn]");
    const row = rows[rows.length - 1];
    if (!row) return;
    const start = (row.nextElementSibling as HTMLElement | null) ?? row;
    const box = el.getBoundingClientRect().top - el.scrollTop;
    const longQuestion = row.offsetHeight > el.clientHeight * 0.4;
    const target = Math.max(0, (longQuestion ? start : row).getBoundingClientRect().top - box - 16);
    anchor.current = row.dataset.turn ?? anchor.current;
    held.current = target;
    userScroll.current = 0;
    gliding.current = performance.now() + 1200;
    fitAnchor();
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: target, behavior: reduce ? "instant" : "smooth" });
  }, [fitAnchor]);
  useEffect(() => {
    const was = wasRunning.current;
    wasRunning.current = running;
    if (!was || running) return;
    toLatest();
  }, [running, toLatest]);
  // A card asks for its top in view (REVEAL_TOP: the inputs card's Next). The place the chat
  // holds moves with it, so the card's new page growing or shrinking does not pull it back.
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const onReveal = (e: Event) => {
      const card = e.target as HTMLElement | null;
      if (!card || !onChatRef.current) return;
      e.preventDefault();
      const target = Math.max(0, card.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop - 12);
      held.current = target;
      userScroll.current = 0;
      gliding.current = performance.now() + 1200;
      fitAnchor();
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      el.scrollTo({ top: target, behavior: reduce ? "instant" : "smooth" });
    };
    el.addEventListener(REVEAL_TOP, onReveal);
    return () => el.removeEventListener(REVEAL_TOP, onReveal);
  }, [fitAnchor]);

  // Another chat: start from its end, with no room kept for an earlier question.
  useEffect(() => {
    anchor.current = null;
    pending.current = null;
    stick.current = true;
  }, [threadId]);

  // The quick-ask box's Send (menu/QuickAsk.tsx): sent here with its @ picks, unless a reply is
  // still being written.
  const sendRef = useRef<(text: string, designs?: { id: string; text: string }[]) => void>(() => undefined);
  const runningRef = useRef(running);
  runningRef.current = running;
  useEffect(
    () =>
      onSendAsk((text, designs) => {
        if (runningRef.current) return false;
        sendRef.current(text, designs);
        return true;
      }),
    [],
  );

  // The store sends the files attached since the last message with it (and empties the chips).
  const send = (text: string, designs?: { id: string; text: string }[]) => {
    const t = text.trim();
    if (!t) return;
    setDraft("");
    stick.current = false;
    pending.current = questions();
    if (!current) {
      setOpenByProject((o) => ({ ...o, [project.id]: threadId }));
      setFresh(newThreadId());
    }
    void store.send(project.id, threadId, t, designs?.length ? { designs } : {});
  };
  sendRef.current = send;

  const Page = onChat ? null : TAB_PAGES[route.tab as Exclude<typeof route.tab, "chat">];
  return (
    <div className={`shell${onChat ? "" : " on-tab"}`}>
      <CommandPalette
        onNewChat={() => {
          openChat(null);
          setDraft("");
          setTimeout(() => composer.current?.focus(), 0);
        }}
      />
      <Header
        tab={route.tab}
        designId={selectedId}
        device={device}
        onDevice={chooseDevice}
        size={size}
        onSize={setSizePick}
        running={running}
        projectName={project.name}
        exampleData={project.id === CHALLENGE_ID}
        health={health}
        totals={totals}
        onMenu={() => setDrawer(true)}
        onHome={() => openChat(null)}
        onReselect={(t) => {
          if (t === "chat") {
            stick.current = true;
            anchor.current = null;
            scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
            return;
          }
          tabScroll.current[`${threadId}:${t}`] = 0;
          void workbench.refresh();
          setReloads((n) => n + 1);
        }}
      />
      <div className="body">
        <Sidebar
          state={state}
          projects={projects}
          project={project}
          current={current}
          open={drawer}
          canAddProjects={projectsState === "ready"}
          onClose={() => setDrawer(false)}
          onPickProject={(id) => {
            setProjectId(id);
            setDrawer(false);
          }}
          onNewProject={() => setNewProject(true)}
          onRemoveProject={(p) => setRemoving(p)}
          onOpenFile={(name) => setSideFile(name)}
          onNewChat={() => {
            openChat(null);
            setDraft("");
            setTimeout(() => composer.current?.focus(), 0);
          }}
          onPickChat={(id) => openChat(id)}
          onDeleteChat={(id) => setRemovingChat({ id, projectId: project.id })}
          onRenameChat={(id, title) => store.renameChat(project.id, id, title)}
        />
        <div
          className={`content${onChat ? "" : " away"}`}
          id="chat-panel"
          role="tabpanel"
          aria-labelledby="nav-tab-chat"
          aria-hidden={!onChat || undefined}
          inert={!onChat || undefined}
          ref={scroller}
          onScroll={(e) => {
            if (!onChatRef.current) return;
            const el = e.currentTarget;
            stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
            chatScroll.current = el.scrollTop;
            const room = el.querySelector<HTMLElement>("[data-chat-spacer]")?.offsetHeight ?? 0;
            const below = el.scrollHeight - room - el.scrollTop - el.clientHeight;
            if (below > 420 !== far) setFar(below > 420);
            // Only the reader's own scrolling moves the held place (not the browser's clamp).
            const now = performance.now();
            if (!anchor.current || (now > gliding.current && now - userScroll.current < 800)) held.current = el.scrollTop;
          }}
          onWheel={byHand}
          onTouchMove={byHand}
          onKeyDown={(e) => {
            // Keys that scroll the chat, not typing in a box.
            const typing = (e.target as HTMLElement).closest?.("input, textarea, [contenteditable]");
            if (!typing && ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(e.key)) byHand();
          }}
          onPointerDown={(e) => {
            // The scroll bar (the panel itself), not a button or a card inside it.
            if (e.target === e.currentTarget) byHand();
          }}
        >
          <ChatView
            chat={chat}
            project={project}
            running={running}
            health={health}
            checking={checking}
            draft={draft}
            onDraft={setDraft}
            onRecheck={() => void check()}
            onSend={send}
            onAnswer={(answers) => {
              // A card's button: the card folds and the work goes on in the same turn, so the
              // view goes back up to the turn's steps (2 Nov: it stayed down on empty space).
              stick.current = false;
              userScroll.current = 0;
              gliding.current = performance.now() + 1500;
              const rows = scroller.current?.querySelectorAll<HTMLElement>(".user-row[data-turn]");
              const last = rows?.[rows.length - 1];
              if (last && !anchor.current) anchor.current = last.dataset.turn ?? null;
              void store.answer(threadId, answers);
              requestAnimationFrame(() => requestAnimationFrame(toLatest));
            }}
            onStop={() => store.stop(threadId)}
            onJump={
              far
                ? () => {
                    const el = scroller.current;
                    if (!el) return;
                    const room = el.querySelector<HTMLElement>("[data-chat-spacer]")?.offsetHeight ?? 0;
                    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
                    el.scrollTo({ top: Math.max(0, el.scrollHeight - room - el.clientHeight), behavior: reduce ? "instant" : "smooth" });
                  }
                : null
            }
            composerRef={composer}
            device={device}
            attachments={state.files[threadId] ?? []}
            onAttach={(files) => void store.attach(threadId, files, health.attachments, project.id)}
            onDismiss={(name) => store.dismissFile(threadId, name)}
          />
        </div>
        {Page && (
          <main
            className="content tab-scroll"
            id="tab-panel"
            role="tabpanel"
            aria-labelledby={`nav-tab-${route.tab}`}
            key={`${route.tab}:${reloads}`}
            ref={tabPanel}
            onScroll={(e) => {
              if (!restoring.current) tabScroll.current[`${threadId}:${route.tab}`] = e.currentTarget.scrollTop;
            }}
          >
            <TabBoundary name={TAB_META[route.tab].label}>
              <Suspense
                fallback={
                  <div className="wb-frame">
                    <PageSkeleton />
                  </div>
                }
              >
                <Page />
              </Suspense>
            </TabBoundary>
          </main>
        )}
      </div>
      {newProject && (
        <NewProjectDialog
          onClose={() => setNewProject(false)}
          onCreated={(info) => {
            addProject(info);
            setNewProject(false);
            setProjectId(info.id);
            setOpenByProject((o) => ({ ...o, [info.id]: null }));
            go("chat");
            setTimeout(() => composer.current?.focus(), 0);
          }}
        />
      )}
      {removing && (
        <RemoveProjectDialog
          project={removing}
          chats={(state.index[removing.id] ?? []).length}
          onClose={() => setRemoving(null)}
          onRemoved={async () => {
            await deleteProject(removing.id);
            for (const m of state.index[removing.id] ?? []) workbench.forgetThread(m.threadId);
            void store.removeProject(removing.id);
            forgetProject(removing.id);
            setOpenByProject(({ [removing.id]: _gone, ...rest }) => rest);
            if (projectId === removing.id) setProjectId(CHALLENGE_ID);
            setRemoving(null);
          }}
        />
      )}
      {removingChat && (
        <RemoveChatDialog
          title={store.meta(removingChat.id)?.title ?? "this chat"}
          running={store.isRunning(removingChat.id)}
          onClose={() => setRemovingChat(null)}
          onRemoved={async () => {
            const { id, projectId: pid } = removingChat;
            await store.removeChat(pid, id);
            workbench.forgetThread(id);
            if (id === current) select(null);
            setRemovingChat(null);
          }}
        />
      )}
      {sideFile && <FilePreview key={sideFile} name={sideFile} threadId={threadId} projectId={project.id} onClose={() => setSideFile(null)} />}
    </div>
  );
}
