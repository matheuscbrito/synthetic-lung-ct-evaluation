import { describe, expect, test } from "vitest";
import { realBundle, stressBundle, type Bundle } from "../fixtures";
import { focusAxis, stripData } from "./strip";

const current = (b: Bundle) => b.items[b.current];

describe("stripData", () => {
  test("real fixture: one bar per item", () => {
    const items = current(realBundle);
    const axis = realBundle.schema.axes[0].key;
    const data = stripData(items, axis, realBundle.schema);
    expect(data.bars.kind).toBe("items");
    if (data.bars.kind !== "items") throw new Error("unreachable");
    expect(data.bars.bars).toHaveLength(items.length);
    expect(items.length).toBeLessThanOrEqual(60);
  });

  test("stress fixture: 30-bin histogram whose counts sum to the item count", () => {
    const items = current(stressBundle);
    const axis = stressBundle.schema.axes[0].key;
    const data = stripData(items, axis, stressBundle.schema);
    expect(items.length).toBeGreaterThan(60);
    expect(data.bars.kind).toBe("histogram");
    if (data.bars.kind !== "histogram") throw new Error("unreachable");
    expect(data.bars.bins).toHaveLength(30);
    const total = data.bars.bins.reduce((s, b) => s + b.total, 0);
    expect(total).toBe(items.length);
    for (const bin of data.bars.bins) {
      expect(Object.values(bin.counts).reduce((s, n) => s + (n ?? 0), 0)).toBe(bin.total);
    }
  });

  test("counts per status sum to the item count and match the verdicts", () => {
    for (const b of [realBundle, stressBundle]) {
      for (const axis of b.schema.axes) {
        const items = current(b);
        const data = stripData(items, axis.key, b.schema);
        const sum = Object.values(data.counts).reduce((s, n) => s + n, 0);
        expect(sum).toBe(items.length);
        for (const st of b.schema.statuses) {
          expect(data.counts[st.key]).toBe(items.filter(i => i.verdicts[axis.key] === st.key).length);
        }
      }
    }
  });

  test("out of range: count and `only` follow the technique statuses of the axis", () => {
    for (const b of [realBundle, stressBundle]) {
      for (const axis of b.schema.axes) {
        const items = current(b);
        const data = stripData(items, axis.key, b.schema);
        const keys = data.outOfRange.map(o => o.technique);
        // techniques in schema order, only those present on the axis
        const schemaOrder = b.schema.techniques.map(t => t.key).filter(k => keys.includes(k));
        expect(keys.slice(0, schemaOrder.length)).toEqual(schemaOrder);
        for (const o of data.outOfRange) {
          const flagged = items.filter(i => (i.techniques[axis.key]?.[o.technique] ?? "approved") !== "approved");
          const alone = flagged.filter(i =>
            Object.entries(i.techniques[axis.key] ?? {}).every(([t, s]) => t === o.technique || s === "approved"),
          );
          expect(o.count).toBe(flagged.length);
          expect(o.only).toBe(alone.length);
          expect(o.label).toBe(b.schema.techniques.find(t => t.key === o.technique)?.label ?? o.technique);
          expect(Object.values(o.byStatus).reduce((s, n) => s + (n ?? 0), 0)).toBe(o.count);
        }
      }
    }
  });
});

describe("focusAxis", () => {
  test("is the axis with most non-approved verdicts", () => {
    for (const b of [realBundle, stressBundle]) {
      const items = current(b);
      const bad = (k: string) => items.filter(i => i.verdicts[k] !== "approved").length;
      const best = Math.max(...b.schema.axes.map(a => bad(a.key)));
      expect(bad(focusAxis(items, b.schema))).toBe(best);
    }
  });
});

test("techniques the schema does not describe are still counted, by key", () => {
  const b = realBundle;
  const schema = { ...b.schema, techniques: [] };
  const items = current(b);
  const axis = b.schema.axes[0].key;
  const data = stripData(items, axis, schema);
  const keys = [...new Set(items.flatMap(i => Object.keys(i.techniques[axis] ?? {})))];
  expect(data.outOfRange.map(o => o.technique)).toEqual(keys);
  expect(data.outOfRange.every(o => o.label === o.technique)).toBe(true);
});
