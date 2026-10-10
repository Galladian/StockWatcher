import type { HeatSector, HeatStock, PeriodId } from "./marketsApi";

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Squarified treemap (Bruls, Huizing, van Wijk): splits `box` into rectangles whose areas are
 * proportional to `value`, keeping them as close to square as it can. Largest first.
 */
export function squarify<T extends { value: number }>(items: T[], box: Rect): Array<{ item: T } & Rect> {
  const out: Array<{ item: T } & Rect> = [];
  const sized = items.filter((i) => i.value > 0);
  const total = sized.reduce((s, i) => s + i.value, 0);
  if (sized.length === 0 || total <= 0 || box.w <= 0 || box.h <= 0) return out;

  const scale = (box.w * box.h) / total;
  const nodes = sized.slice().sort((a, b) => b.value - a.value).map((item) => ({ item, area: item.value * scale }));

  const worst = (areas: number[], side: number) => {
    const sum = areas.reduce((s, a) => s + a, 0);
    const max = Math.max(...areas);
    const min = Math.min(...areas);
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };

  const layoutRow = (row: typeof nodes, r: Rect): Rect => {
    const sum = row.reduce((s, n) => s + n.area, 0);
    if (r.w >= r.h) {
      // lay the row out as a column down the left edge
      const colW = sum / r.h;
      let y = r.y;
      for (const n of row) {
        const hh = n.area / colW;
        out.push({ item: n.item, x: r.x, y, w: colW, h: hh });
        y += hh;
      }
      return { x: r.x + colW, y: r.y, w: r.w - colW, h: r.h };
    }
    // otherwise as a row along the top edge
    const rowH = sum / r.w;
    let x = r.x;
    for (const n of row) {
      const ww = n.area / rowH;
      out.push({ item: n.item, x, y: r.y, w: ww, h: rowH });
      x += ww;
    }
    return { x: r.x, y: r.y + rowH, w: r.w, h: r.h - rowH };
  };

  let rect: Rect = { ...box };
  let row: typeof nodes = [];
  let i = 0;
  while (i < nodes.length) {
    const side = Math.min(rect.w, rect.h);
    const next = nodes[i];
    const areas = row.map((n) => n.area);
    if (row.length === 0 || worst([...areas, next.area], side) <= worst(areas, side)) {
      row.push(next);
      i++;
    } else {
      rect = layoutRow(row, rect);
      row = [];
    }
  }
  if (row.length) layoutRow(row, rect);
  return out;
}

export interface HeatCell {
  stock: HeatStock;
  rect: Rect;
}

export interface HeatGroup {
  sector: HeatSector;
  rect: Rect;
  header: number; // height reserved for the sector label (0 when the box is too small)
  cells: HeatCell[];
}

const HEADER = 16;
const PAD = 1;

/** Sectors sized by market cap, and inside each one its companies sized by market cap. */
export function layoutHeatmap(sectors: HeatSector[], width: number, height: number): HeatGroup[] {
  const groups = squarify(sectors.map((sector) => ({ value: sector.market_cap, sector })), { x: 0, y: 0, w: width, h: height });
  return groups.map((g) => {
    const header = g.h > 44 && g.w > 70 ? HEADER : 0;
    const inner: Rect = { x: g.x + PAD, y: g.y + header + PAD, w: g.w - 2 * PAD, h: g.h - header - 2 * PAD };
    const cells = squarify(g.item.sector.stocks.map((stock) => ({ value: stock.market_cap, stock })), inner).map((c) => ({
      stock: c.item.stock,
      rect: { x: c.x, y: c.y, w: c.w, h: c.h },
    }));
    return { sector: g.item.sector, rect: { x: g.x, y: g.y, w: g.w, h: g.h }, header, cells };
  });
}

/** The change that gives the strongest colour for each period. */
export const CLIP: Record<PeriodId, number> = { "1D": 3, "1W": 6, "1M": 12, "3M": 20, YTD: 30, "1Y": 40 };

type RGB = [number, number, number];
const NEUTRAL: RGB = [91, 100, 114];
const GREEN: RGB = [30, 127, 74];
const RED: RGB = [179, 38, 46];

/** Grey at zero, shading to green or red at `clip`. Every shade keeps white text readable. */
export function changeColor(pct: number, clip: number): string {
  const t = Math.min(1, Math.abs(pct) / clip);
  const to = pct >= 0 ? GREEN : RED;
  const mix = NEUTRAL.map((c, k) => Math.round(c + (to[k] - c) * t));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}
