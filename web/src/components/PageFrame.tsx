import type { ReactNode } from "react";

interface PageFrameProps {
  children: ReactNode;
  width?: "default" | "narrow" | "wide";
}

export function PageFrame({ children, width = "default" }: PageFrameProps) {
  return <div className={`page-frame page-frame-${width}`}>{children}</div>;
}
