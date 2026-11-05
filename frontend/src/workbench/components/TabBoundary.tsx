// Catches a tab that throws while rendering (or whose chunk fails to load after a rebuild), so
// one tab's bug shows a notice instead of blanking the app. App.tsx keys it by the tab.

import { Component, type ErrorInfo, type ReactNode } from "react";

import { ErrorState } from "./TabFrame";

interface State {
  error: Error | null;
}

export class TabBoundary extends Component<{ name: string; children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`The ${this.props.name} tab crashed:`, error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const chunk = /dynamically imported module|Failed to fetch|Loading chunk/i.test(error.message);
    return (
      <div className="wb-frame">
        <ErrorState
          message={chunk ? "The page was rebuilt since you opened it: reload to get the new version." : `${this.props.name}: ${error.message}`}
          onRetry={chunk ? () => window.location.reload() : () => this.setState({ error: null })}
        />
      </div>
    );
  }
}
