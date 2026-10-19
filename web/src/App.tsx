import { LinkProvider } from "@astryxdesign/core/Link";
import { Theme } from "@astryxdesign/core/theme";
import { ToastViewport } from "@astryxdesign/core/Toast";
import { neutralTheme } from "@astryxdesign/theme-neutral/built";
import { useCallback } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RouterLink } from "./components/RouterLink";
import { Shell, type ColorMode } from "./components/Shell";
import { LibraryProvider } from "./lib/library";
import { STORAGE_KEYS, useStoredState } from "./lib/storage";
import { BookDetailPage } from "./pages/BookDetail";
import { BrowsePage } from "./pages/Browse";
import { HomePage } from "./pages/Home";
import { NotFoundPage } from "./pages/NotFound";

export function App() {
  const [storedMode, setStoredMode] = useStoredState<ColorMode | null>(STORAGE_KEYS.theme, null);
  const mode: ColorMode = storedMode ?? "light";
  const toggleMode = useCallback(() => setStoredMode(mode === "dark" ? "light" : "dark"), [mode, setStoredMode]);

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Theme theme={neutralTheme} mode={mode}>
        <LinkProvider component={RouterLink}>
          <ToastViewport position="bottomEnd">
            <LibraryProvider>
              <Shell mode={mode} onToggleMode={toggleMode}>
                <Routes>
                  <Route path="/" element={<Navigate to="/home" replace />} />
                  <Route path="/home" element={<HomePage />} />
                  <Route path="/browse" element={<BrowsePage />} />
                  <Route path="/book/:id" element={<BookDetailPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Shell>
            </LibraryProvider>
          </ToastViewport>
        </LinkProvider>
      </Theme>
    </BrowserRouter>
  );
}
