// The Design tab: the plant of the design in the picker, in two views.
//   Plant           the plant on a canvas, driven through the year by a player; inspect a part,
//                   or edit the design and run it as a new one (tabs/design/PlantView.tsx).
//   GEMINI project  the project GEMINI's solver ran, as an editable graph you can run again,
//                   against GEMINI as released too (tabs/design/ProjectView.tsx).
// Both canvases go full screen (F; Esc leaves) with their tools floating over them
// (tabs/design/fullscreen.tsx). What you did on the tab (the day, the part picked, the project as
// edited, its run) is kept per design while you switch tabs (tabs/design/remember.ts).

import "@xyflow/react/dist/style.css";
import "./DesignTab.css";

import { useMemo, useRef } from "react";

import { AskButton, TabFrame, designTitle, useWorkbench } from "../workbench";
import { FullScreenProvider, ViewSwitch, useFullScreenState, type FullScreen, type View } from "./design/fullscreen";
import { PlantView } from "./design/PlantView";
import { ProjectView } from "./design/ProjectView";
import { useRemembered } from "./design/remember";

export default function DesignTab() {
  const wb = useWorkbench();
  const design = wb.selected;
  const [view, setView] = useRemembered<View>("*", "view", "plant");
  const viewRef = useRef<HTMLDivElement>(null);
  const { full, enter, exit } = useFullScreenState(viewRef);
  const scope = design ? `${wb.threadId}/${design.id}` : "";
  const detail = wb.workbench?.gemini ? `GEMINI ${wb.workbench.gemini.version} with ${wb.workbench.gemini.patches.length} fixes` : undefined;
  const fs = useMemo<FullScreen | null>(() => (design ? { full, enter, exit, view, setView, design } : null), [full, enter, exit, view, setView, design]);

  const toolbar = fs && (
    <FullScreenProvider value={fs}>
      <div className="dz-toolbar">
        <ViewSwitch />
        <span className="dz-toolbar-note">
          {view === "plant"
            ? "Play the year or pick a day; pick a part to inspect it, or edit the design and run it."
            : "Edit GEMINI's own project and run it, against GEMINI as released too."}{" "}
          <kbd>F</kbd> for full screen.
        </span>
      </div>
    </FullScreenProvider>
  );

  return (
    <TabFrame
      scope="design"
      className="tab-design"
      title="Design"
      lead="The plant as GEMINI's solver ran it, with Dioscuri's cooling and the district around it."
      actions={design && <><AskButton context={`the plant of ${designTitle(design)}`} /></>}
      toolbar={toolbar}
    >
      {fs && design && (
        <FullScreenProvider value={fs}>
          <div
            ref={viewRef}
            id="dz-view"
            role="tabpanel"
            aria-labelledby={`dz-tab-${view}`}
            aria-label={full ? `${design.code}, ${view === "plant" ? "plant" : "GEMINI project"}, full screen` : undefined}
            className={`dz-view${full ? " is-full" : ""}`}
          >
            {view === "plant" ? <PlantView key={scope} design={design} scope={scope} geminiDetail={detail} /> : <ProjectView key={scope} design={design} scope={scope} />}
          </div>
        </FullScreenProvider>
      )}
    </TabFrame>
  );
}
