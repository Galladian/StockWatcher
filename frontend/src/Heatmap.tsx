import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchHeatmap, PERIODS, type HeatStock, type PeriodId } from "./marketsApi";
import { changeColor, CLIP, layoutHeatmap, type Rect } from "./treemap";
import { isoToDmy } from "./dates";

const signedPct = (v: number, d = 2) => `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
const tone = (v: number) => (v >= 0 ? "pos" : "neg");
const bigMoney = (v: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }).format(v);

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0].contentRect;
      setSize({ w: Math.floor(r.width), h: Math.floor(r.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

/** What fits inside a cell: the ticker, and under it the change, sized to the box. */
function labelFor(rect: Rect, symbol: string) {
  const fit = (rect.w - 4) / (symbol.length * 0.62); // widest font that keeps the ticker inside the box
  const size = Math.min(24, Math.sqrt(rect.w * rect.h) / 4.2, fit);
  if (size < 8 || rect.h < size * 1.4) return null;
  return { size, showChange: rect.h >= size * 2.4 && rect.w >= size * 3.4 };
}

function tooltip(s: HeatStock) {
  return `${s.symbol}: ${s.name}\n${signedPct(s.change_pct)}\nPrice $${s.price.toFixed(2)}\nMarket cap ${bigMoney(s.market_cap)}\nClick to open the chart`;
}

export default function Heatmap({ period }: { period: PeriodId }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ["heatmap", period],
    queryFn: () => fetchHeatmap(period),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
    refetchInterval: (q) => (q.state.data?.partial ? 4000 : 120_000), // keep filling in while sizes load
  });
  const [ref, size] = useSize<HTMLDivElement>();
  const groups = useMemo(
    () => (data && size.w > 0 && size.h > 0 ? layoutHeatmap(data.sectors, size.w, size.h) : []),
    [data, size.w, size.h]
  );

  if (isLoading) return <p className="muted">Building the heatmap. The first load can take a minute while company sizes are looked up…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load the heatmap"}</p>;

  const clip = CLIP[period];
  const phrase = PERIODS.find((p) => p.id === period)!.phrase;
  const fallback = data.source.startsWith("built-in");

  return (
    <>
      <div className="hm-head">
        <div>
          <span className="muted">S&amp;P 500, {phrase}: </span>
          {data.index_change_pct !== null ? (
            <b className={tone(data.index_change_pct)}>{signedPct(data.index_change_pct)}</b>
          ) : (
            <span className="muted">–</span>
          )}
          {data.as_of && <span className="muted"> &nbsp;as at {isoToDmy(data.as_of)}</span>}
        </div>
        <div className="hm-legend" aria-label={`Colour scale: -${clip}% to +${clip}%`}>
          <span>-{clip}%</span>
          <span
            className="hm-gradient"
            style={{ background: `linear-gradient(90deg, ${changeColor(-clip, clip)}, ${changeColor(0, clip)}, ${changeColor(clip, clip)})` }}
          />
          <span>+{clip}%</span>
        </div>
      </div>

      {data.partial && (
        <div className="notice">Still looking up company sizes ({data.loaded} of {data.total} shown). The map fills in by itself.</div>
      )}
      {fallback && (
        <div className="notice">Couldn't read the full S&amp;P 500 list, so this shows about {data.total} of the largest US companies instead.</div>
      )}

      <div className="hm-wrap" ref={ref}>
        {groups.map((g) => (
          <div key={g.sector.name}>
            {g.header > 0 && (
              <div className="hm-sector" style={{ left: g.rect.x, top: g.rect.y, width: g.rect.w, height: g.header }}>
                {g.sector.name} <span className={tone(g.sector.change_pct)}>{signedPct(g.sector.change_pct)}</span>
              </div>
            )}
            {g.cells.map(({ stock, rect }) => {
              const label = labelFor(rect, stock.symbol);
              return (
                <Link
                  key={stock.symbol}
                  to={`/?t=${encodeURIComponent(stock.symbol)}`}
                  className="hm-cell"
                  style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h, background: changeColor(stock.change_pct, clip) }}
                  title={tooltip(stock)}
                  aria-label={`${stock.symbol} ${signedPct(stock.change_pct)}`}
                >
                  {label && (
                    <>
                      <b style={{ fontSize: label.size }}>{stock.symbol}</b>
                      {label.showChange && <span style={{ fontSize: Math.max(9, label.size * 0.72) }}>{signedPct(stock.change_pct)}</span>}
                    </>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </div>

      <p className="foot">
        Each box is a company, sized by market value and coloured by its price change. Boxes are grouped by sector. Hover for
        details, or click to open its chart. Market values are share counts times the latest price. List source: {data.source}.
      </p>
    </>
  );
}
