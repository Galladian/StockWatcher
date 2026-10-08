import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import { CURRENCIES } from "./portfolioApi";

// The key is the one the portfolio already used for "last chosen currency", so existing choices carry over.
const KEY = "portfolioCurrency";

function read(): string {
  try {
    const v = localStorage.getItem(KEY);
    return v && CURRENCIES.includes(v) ? v : "NZD";
  } catch {
    return "NZD";
  }
}

interface Prefs {
  defaultCurrency: string;
  setDefaultCurrency: (c: string) => void;
}

const PrefsContext = createContext<Prefs>({ defaultCurrency: "NZD", setDefaultCurrency: () => {} });
export const usePrefs = () => useContext(PrefsContext);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [defaultCurrency, set] = useState(read);
  const value = useMemo<Prefs>(
    () => ({
      defaultCurrency,
      setDefaultCurrency: (c) => {
        set(c);
        try { localStorage.setItem(KEY, c); } catch { /* ignore */ }
      },
    }),
    [defaultCurrency]
  );
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}
