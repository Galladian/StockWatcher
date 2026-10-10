import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchIndices, PERIODS, type IndexRow, type PeriodId } from "./marketsApi";
import { isoToDmy } from "./dates";

const signedPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const tone = (v: number | null) => (v === null ? "" : v >= 0 ? "pos" : "neg");
const level = (v: number) => v.toLocaleString("en-NZ", { maximumFractionDigits: 2 });

function Bar({ pct, max }: { pct: number; max: number }) {
  const width = `${Math.min(50, (Math.abs(pct) / max) * 50)}%`;
  return (
    <span className="idx-bar" aria-hidden="true">
      <span className={`idx-fill ${pct >= 0 ? "pos" : "neg"}`} style={pct >= 0 ? { left: "50%", width } : { right: "50%", width }} />
    </span>
  );
}

export default function WorldMarkets({ period }: { period: PeriodId }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ["indices", period],
    queryFn: () => fetchIndices(period),
    staleTime: 60_000,
    refetchInterval: 120_000,
    placeholderData: (prev) => prev,
  });

  const stats = useMemo(() => {
    const rows = (data?.regions ?? []).flatMap((r) => r.items);
    const valid = rows.filter((r): r is IndexRow & { change_pct: number } => r.change_pct !== null);
    if (valid.length === 0) return null;
    const sorted = valid.slice().sort((a, b) => b.change_pct - a.change_pct);
    return {
      best: sorted[0],
      worst: sorted[sorted.length - 1],
      up: valid.filter((r) => r.change_pct > 0).length,
      down: valid.filter((r) => r.change_pct < 0).length,
      total: valid.length,
      max: Math.max(0.01, ...valid.map((r) => Math.abs(r.change_pct))),
      latest: valid.map((r) => r.date ?? "").sort().pop() ?? "",
    };
  }, [data]);

  if (isLoading) return <p className="muted">Loading world markets…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load world markets"}</p>;
  if (!stats) return <div className="empty">No index data came back. Try again in a moment.</div>;

  const phrase = PERIODS.find((p) => p.id === period)!.phrase;

  return (
    <>
      <div className="stats">
        <div className="card stat">
          <div className="label">Best, {phrase}</div>
          <div className="value pos">{signedPct(stats.best.change_pct)}</div>
          <div className="sub">{stats.best.name}, {stats.best.country}</div>
        </div>
        <div className="card stat">
          <div className="label">Worst, {phrase}</div>
          <div className="value neg">{signedPct(stats.worst.change_pct)}</div>
          <div className="sub">{stats.worst.name}, {stats.worst.country}</div>
        </div>
        <div className="card stat">
          <div className="label">Markets up and down</div>
          <div className="value">
            <span className="pos">{stats.up}</span> / <span className="neg">{stats.down}</span>
          </div>
          <div className="sub">of {stats.total} indexes</div>
        </div>
      </div>

      {data.regions.map((region) => (
        <section key={region.name} className="idx-region">
          <h2>{region.name}</h2>
          <div className="card table-wrap">
            <table className="ledger idx-table">
              <thead>
                <tr>
                  <th>Index</th>
                  <th>Country</th>
                  <th className="num">Level</th>
                  <th className="num">Change</th>
                  <th className="idx-bar-col" />
                  <th>As at</th>
                </tr>
              </thead>
              <tbody>
                {region.items.map((r) => {
                  const behind = r.date !== null && stats.latest !== "" && r.date < stats.latest;
                  return (
                    <tr key={r.symbol}>
                      <td><b>{r.name}</b></td>
                      <td className="muted">{r.country}</td>
                      <td className="num">{r.last === null ? "–" : level(r.last)}</td>
                      <td className={`num ${tone(r.change_pct)}`}>{r.change_pct === null ? "–" : signedPct(r.change_pct)}</td>
                      <td className="idx-bar-col">{r.change_pct !== null && <Bar pct={r.change_pct} max={stats.max} />}</td>
                      <td className={behind ? "muted" : ""} title={behind ? "This market hasn't traded since this date, so it's closed or on a holiday" : undefined}>
                        {r.date ? isoToDmy(r.date) : "–"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <p className="foot">
        Change is the latest close against the close at the start of the period, in each index's own currency. Markets that
        are still open show their live level. Dates shown in grey are markets that haven't traded since then.
      </p>
    </>
  );
}
