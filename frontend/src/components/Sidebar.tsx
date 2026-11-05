import { useEffect, useRef, useState } from "react";

import { chatStatus } from "../agent/reducer";
import { menuProps } from "../menu";
import { CHALLENGE_ID, type Project } from "../state/projects";
import type { StoreState } from "../state/store";
import { ChatIcon, Cross, FileGlyph, Plus, Spinner } from "./Icons";
import { Spark } from "./ProjectDialogs";
import { ProjectMemory } from "./ProjectMemory";

interface Props {
  state: StoreState;
  projects: Project[];
  project: Project;
  current: string | null;
  open: boolean;
  /** The server answers, so projects can be added. */
  canAddProjects: boolean;
  onClose: () => void;
  onPickProject: (id: string) => void;
  onNewProject: () => void;
  onRemoveProject: (project: Project) => void;
  onOpenFile: (name: string) => void;
  onNewChat: () => void;
  onPickChat: (threadId: string) => void;
  onDeleteChat: (threadId: string) => void;
  onRenameChat: (threadId: string, title: string) => void;
}

function when(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const day = 864e5;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (ts >= start) return "Today";
  if (ts >= start - day) return "Yesterday";
  if (ts >= start - 6 * day) return d.toLocaleDateString("en-GB", { weekday: "short" });
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function Sidebar({
  state,
  projects,
  project,
  current,
  open,
  canAddProjects,
  onClose,
  onPickProject,
  onNewProject,
  onRemoveProject,
  onOpenFile,
  onNewChat,
  onPickChat,
  onDeleteChat,
  onRenameChat,
}: Props) {
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const chats = state.index[project.id] ?? [];

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [menu]);

  return (
    <>
      <div className={`scrim${open ? " open" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`side${open ? " open" : ""}`} aria-label="Projects and chats">
        <div style={{ position: "relative" }} ref={menuRef}>
          <button
            type="button"
            className="proj-btn ta-btn"
            aria-haspopup="true"
            aria-expanded={menu}
            aria-controls="projects-menu"
            onClick={() => setMenu(!menu)}
          >
            <span className="avatar" style={{ width: 28, height: 28, background: project.bg, color: project.ink, fontSize: 12 }}>
              {project.initials}
            </span>
            <span style={{ flex: "1 1 auto", minWidth: 0, display: "flex", flexDirection: "column", lineHeight: 1.25 }}>
              <span style={{ fontSize: 11.5, color: "#66727C" }}>Project</span>
              <strong style={{ fontSize: 14, fontWeight: 650, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{project.name}</strong>
            </span>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
              <path d="M5 6.2 8 3.4l3 2.8M5 9.8 8 12.6l3-2.8" fill="none" stroke="#66727C" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {menu && (
            <div id="projects-menu" className="proj-menu ta-rise" role="menu">
              {projects.map((p) => {
                const n = (state.index[p.id] ?? []).length;
                const on = p.id === project.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="menuitemradio"
                    aria-checked={on}
                    className="proj-item ta-btn ta-soft"
                    title={p.name}
                    style={{ background: on ? "#EEF5F5" : "transparent" }}
                    onClick={() => {
                      setMenu(false);
                      onPickProject(p.id);
                    }}
                  >
                    <span className="avatar" style={{ width: 24, height: 24, borderRadius: 7, background: p.bg, color: p.ink, fontSize: 11 }}>
                      {p.initials}
                    </span>
                    <span style={{ flex: "1 1 auto", minWidth: 0, display: "flex", flexDirection: "column", lineHeight: 1.25 }}>
                      <span style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.name}</span>
                      <span style={{ fontSize: 12, color: "#66727C" }}>
                        {p.builtin && p.id !== CHALLENGE_ID ? "Real project · " : ""}
                        {plural(n, "chat", "chats")} · {p.files.length ? plural(p.files.length, "file", "files") : "no data yet"}
                      </span>
                    </span>
                    {on && (
                      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
                        <path d="M3.5 8.5 6.5 11.5 12.5 5" fill="none" stroke="#0A6F7C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                );
              })}
              <span style={{ height: 1, background: "rgba(17,24,28,.07)", margin: "4px 6px" }} />
              <button
                type="button"
                role="menuitem"
                className="proj-item ta-btn ta-soft"
                disabled={!canAddProjects}
                title={canAddProjects ? "A district from its demand files and reservoir" : "Needs the agent server"}
                onClick={() => {
                  setMenu(false);
                  onNewProject();
                }}
              >
                <span className="proj-new-icon">
                  <Plus size={12} color="#0A6F7C" />
                </span>
                New project
                {!canAddProjects && (
                  <span className="tag tag-grey" style={{ marginLeft: "auto" }}>
                    offline
                  </span>
                )}
              </button>
            </div>
          )}
        </div>

        <button type="button" className="new-chat ta-btn ta-soft" onClick={onNewChat}>
          <Plus />
          New chat
        </button>

        <nav aria-label={`Chats in ${project.name}`} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <h2>Chats</h2>
          {chats.length === 0 && (
            <p style={{ margin: 0, padding: "6px 8px", fontSize: 13, lineHeight: 1.45, color: "#66727C" }}>No chats yet.</p>
          )}
          {chats.map((m) => {
            if (renaming === m.threadId)
              return <RenameRow key={m.threadId} title={m.title} onDone={(t) => (setRenaming(null), t != null && onRenameChat(m.threadId, t))} />;
            const chat = state.chats[m.threadId];
            const status = chat ? chatStatus(chat) : "idle";
            const isCurrent = m.threadId === current;
            const note =
              status === "running"
                ? { text: "Working", ink: "#0A6F7C" }
                : status === "waiting"
                  ? { text: "Needs your answer", ink: "#8A5A00" }
                  : status === "error"
                    ? { text: "Error", ink: "#A12C22" }
                    : m.replay
                      ? { text: "Replay", ink: "#66727C" }
                      : null;
            return (
              <div
                key={m.threadId}
                role="button"
                tabIndex={0}
                className="chat-row ta-row ta-soft"
                aria-current={isCurrent}
                title={`${m.title} (double-click to rename)`}
                onClick={() => onPickChat(m.threadId)}
                onDoubleClick={(e) => {
                  e.preventDefault();
                  setRenaming(m.threadId);
                }}
                {...menuProps({ kind: "chat", title: m.title, rename: () => setRenaming(m.threadId), remove: () => onDeleteChat(m.threadId) }, {
                  onKeyDown: (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onPickChat(m.threadId);
                    } else if (e.key === "F2") {
                      e.preventDefault();
                      setRenaming(m.threadId);
                    }
                  },
                })}
              >
                <span style={{ height: 18, display: "inline-flex", alignItems: "center" }}>
                  {status === "running" ? <Spinner size={14} /> : status === "waiting" ? <WaitingDot /> : <ChatIcon />}
                </span>
                <span style={{ display: "flex", flexDirection: "column", minWidth: 0, lineHeight: 1.35 }}>
                  <span className="chat-title" style={{ fontWeight: isCurrent ? 650 : 500 }}>
                    {m.title}
                  </span>
                  <span className="chat-sub">
                    {note && (
                      <>
                        <span style={{ color: note.ink, fontWeight: 550 }}>{note.text}</span>
                        <span aria-hidden="true">·</span>
                      </>
                    )}
                    <span>{when(m.updatedAt)}</span>
                  </span>
                </span>
                <button
                  type="button"
                  className="del ta-soft"
                  aria-label={`Remove the chat "${m.title}"`}
                  title="Remove this chat, with its designs and runs"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteChat(m.threadId);
                  }}
                >
                  <Cross />
                </button>
              </div>
            );
          })}
        </nav>

        <ProjectMemory projectId={project.id} current={current} />
        <ProjectCard project={project} onOpenFile={onOpenFile} onRemove={() => onRemoveProject(project)} />
      </aside>
    </>
  );
}

/** A chat's name being edited in place: Enter or a click away keeps it, Escape leaves it as it was. */
function RenameRow({ title, onDone }: { title: string; onDone: (title: string | null) => void }) {
  const [draft, setDraft] = useState(title);
  const input = useRef<HTMLInputElement>(null);
  const done = useRef(false);
  useEffect(() => {
    input.current?.focus();
    input.current?.select();
  }, []);
  const finish = (t: string | null) => {
    if (done.current) return;
    done.current = true;
    onDone(t);
  };
  return (
    <div className="chat-row chat-rename">
      <label className="sr-only" htmlFor="chat-rename-input">
        Rename chat
      </label>
      <input
        id="chat-rename-input"
        ref={input}
        value={draft}
        maxLength={90}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => finish(draft.trim() ? draft : null)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            finish(draft.trim() ? draft : null);
          } else if (e.key === "Escape") {
            e.preventDefault();
            finish(null);
          }
        }}
      />
    </div>
  );
}

const fmt = (v: number, d = 1) => v.toLocaleString("en-GB", { maximumFractionDigits: d });

/** The project's data at a glance: its demand over the year, its reservoir, its files. */
function ProjectCard({ project, onOpenFile, onRemove }: { project: Project; onOpenFile: (name: string) => void; onRemove: () => void }) {
  const info = project.info;
  return (
    <section className="side-data" aria-label="Data in this project">
      <h2>Data in this project</h2>
      {info && (
        <div className="pc-demand">
          {(
            [
              ["Heat", "var(--heat)", info.weekly_mw.heat, info.totals.annual_heat_gwh, info.totals.peak_heat_mw],
              ["Cold", "var(--cold)", info.weekly_mw.cool, info.totals.annual_cool_gwh, info.totals.peak_cool_mw],
            ] as const
          ).map(([label, color, weekly, total, peak]) => (
            <div key={label} className="pc-line" title={`${label}: ${fmt(total)} GWh a year, peak ${fmt(peak)} MW (weekly means)`}>
              <span className="pc-label">{label}</span>
              {total > 0 ? (
                <>
                  <Spark values={[...weekly]} color={color} width={86} height={22} />
                  <span className="pc-num">
                    <span className="pc-total">
                      <b>{fmt(total)}</b> GWh
                    </span>
                    <span>peak {fmt(peak)} MW</span>
                  </span>
                </>
              ) : (
                <span className="pc-none">No {label === "Cold" ? "cooling" : "heating"} demand</span>
              )}
            </div>
          ))}
        </div>
      )}
      {info && (
        <dl className="pc-facts">
          <dt>Reservoir</dt>
          <dd>
            {fmt(info.reservoir.depth_m, 0)} m · {fmt(info.reservoir.temperature_c)} °C · {fmt(info.reservoir.permeability_md, 0)} mD
          </dd>
          <dt>Networks</dt>
          <dd>
            {fmt(info.heating.supply_c)}/{fmt(info.heating.return_c)} °C
            {info.totals.annual_cool_gwh ? ` · ${fmt(info.cooling.supply_c)}/${fmt(info.cooling.return_c)} °C` : " heating only"}
          </dd>
        </dl>
      )}
      <div className="pc-files">
        {project.files.map((f) => (
          <button key={f} type="button" className="file-row file-btn ta-soft" title={`Open ${f}`} onClick={() => onOpenFile(f)}>
            <FileGlyph name={f} size={13} />
            <span>{f}</span>
          </button>
        ))}
      </div>
      {!project.builtin && (
        <button type="button" className="link-btn pc-remove" onClick={onRemove}>
          Remove this project
        </button>
      )}
    </section>
  );
}

function WaitingDot() {
  return (
    <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#FBF1DC", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#D99A1E" }} />
    </span>
  );
}
