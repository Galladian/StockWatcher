import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CURRENCIES, fetchMe, logout } from "./portfolioApi";
import { usePrefs } from "./prefs";
import { useTheme, type ThemeChoice } from "./theme";

const THEME_OPTIONS: { id: ThemeChoice; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "system", label: "Match my device" },
];

export default function SettingsMenu() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { choice, setChoice } = useTheme();
  const { defaultCurrency, setDefaultCurrency } = usePrefs();

  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: Infinity });
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      qc.setQueryData(["me"], { username: null });
      for (const key of ["transactions", "summary", "breakdown", "history"]) qc.removeQueries({ queryKey: [key] });
      setOpen(false);
    },
  });

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const username = me.data?.username;

  return (
    <div className="settings" ref={ref}>
      <button className="navbtn" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Settings
      </button>
      {open && (
        <div className="settings-panel" role="dialog" aria-label="Settings">
          <fieldset className="settings-section">
            <legend>Appearance</legend>
            {THEME_OPTIONS.map((o) => (
              <label className="radio" key={o.id}>
                <input type="radio" name="theme" checked={choice === o.id} onChange={() => setChoice(o.id)} />
                {o.label}
              </label>
            ))}
          </fieldset>

          <div className="settings-section">
            <label className="settings-label" htmlFor="default-currency">Default currency</label>
            <select id="default-currency" value={defaultCurrency} onChange={(e) => setDefaultCurrency(e.target.value)}>
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <p className="settings-hint">Used when you open your portfolio. You can still switch currency there for a moment.</p>
          </div>

          <div className="settings-section">
            <div className="settings-label">Account</div>
            {username ? (
              <>
                <p className="account-line">Signed in as <b>{username}</b></p>
                <button onClick={() => signOut.mutate()} disabled={signOut.isPending}>
                  {signOut.isPending ? "Logging out…" : "Log out"}
                </button>
              </>
            ) : (
              <p className="settings-hint">You're not logged in. Log in from the Portfolio page.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
