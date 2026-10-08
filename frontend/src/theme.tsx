import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

export type ThemeChoice = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";
const KEY = "theme";

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "system" || v === "dark" ? v : "dark";
  } catch {
    return "dark";
  }
}

const query = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: light)") : null;

interface ThemeValue {
  choice: ThemeChoice;
  resolved: ResolvedTheme; // what is actually showing
  setChoice: (c: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeValue>({ choice: "dark", resolved: "dark", setChoice: () => {} });
export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [systemLight, setSystemLight] = useState(() => query()?.matches ?? false);

  // follow the device setting while "Match my device" is chosen
  useEffect(() => {
    const mq = query();
    if (!mq) return;
    const onChange = () => setSystemLight(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const resolved: ResolvedTheme = choice === "system" ? (systemLight ? "light" : "dark") : choice;

  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);

  const value = useMemo<ThemeValue>(
    () => ({
      choice,
      resolved,
      setChoice: (c) => {
        setChoiceState(c);
        try { localStorage.setItem(KEY, c); } catch { /* ignore */ }
      },
    }),
    [choice, resolved]
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
