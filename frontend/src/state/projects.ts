// The projects in the switcher, from the server (GET /api/projects): the organisers' challenge
// district first, the real projects built in beside it, then the districts added with "New
// project" (src/gemini_agent/projects.py).
// Without a server (fixture replays, or before it answers) the list is the challenge district.

import { useCallback, useEffect, useState } from "react";

import { fetchProjects, type ProjectInfo } from "../agent/client";

export interface Project {
  id: string;
  name: string;
  initials: string;
  bg: string;
  ink: string;
  files: string[];
  /** Built into the server (the challenge district and the real projects): never removed. */
  builtin: boolean;
  /** The server's record (totals, reservoir, weekly demand); null until the server answers. */
  info: ProjectInfo | null;
}

export const CHALLENGE_ID = "challenge";

export const CHALLENGE: Project = {
  id: CHALLENGE_ID,
  name: "Challenge district 2027",
  initials: "CD",
  bg: "#E2F3F5",
  ink: "#0A6F7C",
  files: ["GEMINI_Heating_Demand_Daily_2027.csv", "GEMINI_Cooling_Demand_Daily_2027.csv", "GEMINI_Hackathon_Challenge_Requirements.docx.pdf"],
  builtin: true,
  info: null,
};

const TINTS = [
  { bg: "#EFEAFB", ink: "#5B3FA6" },
  { bg: "#FCEDE6", ink: "#C24E1C" },
  { bg: "#E8EFFB", ink: "#2363A6" },
  { bg: "#E3F5EA", ink: "#0F7A3D" },
  { bg: "#FBF1DC", ink: "#8A5A00" },
];

/** Two letters for a project's avatar: the first two words' initials, or one word's first two. */
export function initialsOf(name: string): string {
  const words = name.split(/[\s_-]+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
  if (!words.length) return "P";
  return (words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)).toUpperCase();
}

/** The same tint for a project on every load (from its id). */
function tint(id: string) {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export function toProject(info: ProjectInfo): Project {
  if (info.id === CHALLENGE_ID) return { ...CHALLENGE, name: info.name, files: info.files, info };
  // The real projects built in beside it (Trias Westland, HAL Leyweg) keep their own ids.
  return { id: info.id, name: info.name, initials: initialsOf(info.name), ...tint(info.id), files: info.files, builtin: info.builtin, info };
}

export type ProjectsState = "loading" | "ready" | "offline";

/** The server's projects, with add and remove for the dialogs; `refresh` asks again. */
export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([CHALLENGE]);
  const [state, setState] = useState<ProjectsState>("loading");
  const refresh = useCallback(async () => {
    try {
      const infos = await fetchProjects();
      setProjects(infos.length ? infos.map(toProject) : [CHALLENGE]);
      setState("ready");
    } catch {
      setState("offline");
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const add = useCallback((info: ProjectInfo) => setProjects((list) => [...list.filter((p) => p.id !== info.id), toProject(info)]), []);
  const remove = useCallback((id: string) => setProjects((list) => list.filter((p) => p.id !== id)), []);
  return { projects, state, refresh, add, remove };
}

export interface Example {
  title: string;
  sub: string;
  text: string;
  icon: string;
  tint: string;
  stroke: string;
}

export const EXAMPLES: Example[] = [
  {
    title: "Design heating and cooling",
    sub: "1-3 doublets, every cap checked every day",
    text: "Design a geothermal heating and cooling system for this district.",
    icon: "M8 2v5M5 5l3 2 3-2M3 10h10M4 13h8",
    tint: "#FCEDE6",
    stroke: "#C24E1C",
  },
  {
    title: "Lowest CO₂",
    sub: "Rank the designs by emissions, not cost",
    text: "Which design gives the lowest CO2 for the district?",
    icon: "M4 2v12M12 2v12M4 9h8",
    tint: "#E8EFFB",
    stroke: "#2363A6",
  },
  {
    title: "Compare depths",
    sub: "The 2,500 m aquifer or deeper, hotter wells",
    text: "Compare a 2.5 km doublet with a 3.5 km doublet for this district.",
    icon: "M2.5 4h11M8 2v2M5 4c0 4 3 7 7 8M11 4c0 4-3 7-7 8",
    tint: "#E2F3F5",
    stroke: "#0A6F7C",
  },
];

const km = (m: number) => `${+(m / 1000).toFixed(2)} km`;

/** The examples for a project: the depth comparison starts at its own reservoir; heat only
 * when it has no cold to deliver. */
export function examplesFor(project: Project): Example[] {
  const depth = project.info?.reservoir.depth_m;
  const heatOnly = project.info != null && !project.info.totals.annual_cool_gwh;
  if ((!depth || depth === 2500) && !heatOnly) return EXAMPLES;
  return EXAMPLES.map((ex) => {
    if (ex.title === "Compare depths" && depth && depth !== 2500)
      return {
        ...ex,
        sub: `The ${depth.toLocaleString("en-GB")} m aquifer or deeper, hotter wells`,
        text: `Compare a ${km(depth)} doublet with a ${km(depth + 1000)} doublet for this district.`,
      };
    if (ex.title === "Design heating and cooling" && heatOnly)
      return { ...ex, title: "Design the heating", text: "Design a geothermal heating system for this district." };
    return ex;
  });
}
