// Fitting a React Flow canvas to its graph once every node has been measured (React Flow's own
// `fitView` can fire on the first measured node and zoom to it), and again when asked.

import { useEffect, useRef, type CSSProperties } from "react";
import { ControlButton, Controls, useNodesInitialized, useReactFlow, type FitViewOptions, type PanelPosition } from "@xyflow/react";

/** Fits the view once all nodes are measured, then again each time `again` changes. */
export function FitWhenReady({ padding, minZoom, again }: { padding: FitViewOptions["padding"]; minZoom?: number; again?: string }) {
  const ready = useNodesInitialized();
  const { fitView } = useReactFlow();
  const done = useRef<string | null>(null);
  useEffect(() => {
    if (!ready) return;
    const key = again ?? "";
    if (done.current === key) return;
    done.current = key;
    const id = requestAnimationFrame(() => void fitView({ padding, minZoom }));
    return () => cancelAnimationFrame(id);
    // The padding is read when `again` changes; a new object each render must not refit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, again, minZoom, fitView]);
  return null;
}

/**
 * Zoom in, zoom out and "fit the drawing": React Flow's own fit button draws four corners, the
 * same as Full screen beside it, so this one draws a frame around a centred plant instead. With
 * `padding` it fits as the view does (clear of the panels over the canvas).
 */
export function FitControls({ position, style, orientation, padding = 0.08, minZoom }: { position: PanelPosition; style?: CSSProperties; orientation?: "horizontal" | "vertical"; padding?: FitViewOptions["padding"]; minZoom?: number }) {
  const { fitView } = useReactFlow();
  return (
    <Controls showInteractive={false} showFitView={false} position={position} style={style} orientation={orientation}>
      <ControlButton onClick={() => void fitView({ padding, minZoom, duration: 200 })} title="Fit the drawing to the view" aria-label="Fit the drawing to the view">
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
          <rect x="1.5" y="1.5" width="13" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeDasharray="2.2 1.8" />
          <rect x="5" y="5" width="6" height="6" rx="1" fill="currentColor" />
        </svg>
      </ControlButton>
    </Controls>
  );
}
