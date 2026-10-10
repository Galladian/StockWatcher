import { useState } from "react";
import Heatmap from "./Heatmap";
import WorldMarkets from "./WorldMarkets";
import { PERIODS, type PeriodId } from "./marketsApi";

type View = "heatmap" | "world";

export default function Overview() {
  const [view, setView] = useState<View>("heatmap");
  const [period, setPeriod] = useState<PeriodId>("1D");

  return (
    <div className="scroll">
      <div className="wrap wide">
        <h1>Overview</h1>
        <p className="lede">How the market is doing right now: a map of the S&amp;P 500, or the main stock indexes around the world.</p>

        <div className="overview-controls">
          <div className="tabs" role="group" aria-label="View">
            <button className={view === "heatmap" ? "active" : ""} onClick={() => setView("heatmap")}>S&amp;P 500 heatmap</button>
            <button className={view === "world" ? "active" : ""} onClick={() => setView("world")}>World markets</button>
          </div>
          <div className="tabs" role="group" aria-label="Period">
            {PERIODS.map((p) => (
              <button key={p.id} className={period === p.id ? "active" : ""} onClick={() => setPeriod(p.id)}>{p.label}</button>
            ))}
          </div>
        </div>

        {view === "heatmap" ? <Heatmap period={period} /> : <WorldMarkets period={period} />}
      </div>
    </div>
  );
}
