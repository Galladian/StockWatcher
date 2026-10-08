import { useEffect, useRef, useState } from "react";
import { useTheme, type ThemeChoice } from "./theme";

const OPTIONS: { id: ThemeChoice; label: string }[] = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "system", label: "Match my device" },
];

export default function SettingsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { choice, setChoice } = useTheme();

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

  return (
    <div className="settings" ref={ref}>
      <button className="navbtn" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Settings
      </button>
      {open && (
        <div className="settings-panel" role="dialog" aria-label="Settings">
          <fieldset>
            <legend>Appearance</legend>
            {OPTIONS.map((o) => (
              <label className="radio" key={o.id}>
                <input type="radio" name="theme" checked={choice === o.id} onChange={() => setChoice(o.id)} />
                {o.label}
              </label>
            ))}
          </fieldset>
        </div>
      )}
    </div>
  );
}
