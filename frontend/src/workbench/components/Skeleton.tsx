// Loading placeholders: a shimmering block, and the frame's default page of them.

import type { CSSProperties } from "react";

import "./workbench.css";

export function Skeleton({ width = "100%", height = 16, radius, style }: { width?: number | string; height?: number | string; radius?: number; style?: CSSProperties }) {
  return <span className="wb-skel" aria-hidden="true" style={{ width, height, borderRadius: radius, ...style }} />;
}

/** A tab loading: a row of tiles and a large card. */
export function PageSkeleton() {
  return (
    <div className="wb-body" role="status" aria-label="Loading">
      <div className="wb-skel-tiles">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="wb-skel-card" style={{ borderRadius: 18, padding: "14px 16px" }}>
            <Skeleton width="55%" height={12} />
            <Skeleton width="40%" height={24} radius={8} />
            <Skeleton height={6} radius={3} />
          </div>
        ))}
      </div>
      <div className="wb-skel-card">
        <Skeleton width="30%" height={14} />
        <Skeleton height={220} radius={14} />
        <Skeleton width="70%" height={12} />
      </div>
    </div>
  );
}
