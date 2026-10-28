import { describe, expect, test } from "vitest";
import { bundles, realBundle, stressBundle } from "../fixtures";
import type { MetricDesc } from "./types";
import { limitText, metricDeviation, metricText, orderItems, reasonText, signed, ticks, toneOf, worst } from "./format";

const metric = (key: string, b = realBundle): MetricDesc => {
  const m = b.schema.metrics.find((x) => x.key === key);
  if (!m) throw new Error(`metric ${key} missing from fixture`);
  return m;
};

describe("signed", () => {
  test("negative zero prints as plain zero", () => {
    expect(signed(-0.0001, 1)).toBe("0.0");
    expect(signed(0, 2)).toBe("0.00");
  });
  test("uses U+2212 for negatives and + for positives", () => {
    expect(signed(-1.234, 2)).toBe("−1.23");
    expect(signed(1.25, 1)).toBe("+1.3");
  });
});

describe("metricText", () => {
  const items = realBundle.items[realBundle.current];

  test("missing or unavailable reading prints n/a", () => {
    const m = metric("nex");
    const mv = items[0].metrics.nex;
    expect(metricText(m, { ...mv, available: false })).toBe("n/a");
    expect(metricText(m, undefined)).toBe("n/a");
  });

  test("z display shows signed z, unit and CI", () => {
    const m = metric("nex");
    let checked = 0;
    for (const it of items) {
      const mv = it.metrics.nex;
      if (mv?.available && mv.z !== null && mv.ci) {
        expect(metricText(m, mv)).toMatch(/^[+−]\d\.\d\d IQR \[[+−]/);
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(0);
  });

  test("value display glues % and spaces other units", () => {
    const sat = metric("sat31");
    expect(metricText(sat, { ...items[0].metrics.sat31, value: 1.68 })).toBe("1.7%");
    const dmu = metric("delta_mu");
    expect(metricText(dmu, { ...items[0].metrics.delta_mu, value: -0.5 })).toBe("-0.50 IQR");
  });

  test("available reading with no finite value or z prints n/a (real fixture)", () => {
    const byKey = new Map(realBundle.schema.metrics.map((m) => [m.key, m]));
    let checked = 0;
    for (const list of Object.values(realBundle.items)) {
      for (const it of list) {
        for (const [key, mv] of Object.entries(it.metrics)) {
          if (mv.available && mv.value === null && mv.z === null) {
            expect(metricText(byKey.get(key)!, mv)).toBe("n/a");
            checked++;
          }
        }
      }
    }
    expect(checked).toBeGreaterThan(0);
  });
});

describe("limitText", () => {
  test("per limit kind", () => {
    expect(limitText(metric("sat31"), "reject")).toBe("–");
    expect(limitText(metric("sat31"), "review")).toBe("> 15%");
    expect(limitText(metric("ll"), "review")).toBe("|z| > 1");
    expect(limitText(metric("delta_mu"), "review")).toMatch(/^\|x\| > 0\.31\d*$/);
    expect(limitText({ ...metric("ll"), limits: null }, "review")).toBe("–");
    expect(limitText({ ...metric("sat31"), limits: { kind: "below", review: 3, reject: null } }, "review")).toBe("< 3%");
  });
});

describe("reasonText", () => {
  test.each(Object.entries(bundles))("never prints null/undefined/NaN (%s)", (_name, b) => {
    const byKey = new Map(b.schema.metrics.map((m) => [m.key, m]));
    let n = 0;
    for (const list of Object.values(b.items)) {
      for (const it of list) {
        for (const r of it.reasons) {
          const t = reasonText(byKey.get(r.metric)!, r);
          expect(t).not.toMatch(/null|undefined|NaN/);
          n++;
        }
      }
    }
    expect(n).toBeGreaterThan(0);
  });

  test("templates", () => {
    const m = metric("nex");
    const base = { axis: "texture", metric: "nex", status: "review" as const, ci: null, note: null };
    expect(reasonText(m, { ...base, value: null, z: null, limit: null, limit_value: null, direction: null, note: "no reading" })).toBe(
      `${m.label}: no reading.`,
    );
    expect(reasonText(m, { ...base, value: 1.5, z: 1.5, ci: [1.1, 2], limit: "review", limit_value: null, direction: "higher" })).toBe(
      `${m.label} is higher than real: +1.50 IQR [+1.10, +2.00], past the review limit (1).`,
    );
    const sat = metric("sat31");
    expect(reasonText(sat, { ...base, metric: "sat31", value: 20, z: null, limit: "review", limit_value: null, direction: "higher" })).toBe(
      `${sat.label} reads 20.0%, above the review limit (15%).`,
    );
    // edge: no value, no threshold and no direction still produce a clean sentence
    const t = reasonText(sat, { ...base, metric: "sat31", value: null, z: null, limit: "reject", limit_value: null, direction: null });
    expect(t).not.toMatch(/null|undefined|NaN/);
  });
});

describe("ticks", () => {
  test("rounded steps covering the range", () => {
    expect(ticks(0, 269)).toEqual([0, 50, 100, 150, 200, 250, 300]);
    expect(ticks(0, 1)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1]);
    const t = ticks(-3.2, 7.9);
    expect(t[0]).toBeLessThanOrEqual(-3.2);
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(7.9);
  });
});

describe("tone and ordering", () => {
  test("toneOf reads schema.statuses", () => {
    expect(toneOf(stressBundle.schema, "rejected")).toBe("bad");
    expect(toneOf(stressBundle.schema, "approved")).toBe("good");
    expect(toneOf(stressBundle.schema, "nope" as never)).toBe("neutral");
  });

  test.each(Object.entries(bundles))("orderItems puts rejected before review before approved (%s)", (_name, b) => {
    const items = b.items[b.current];
    const sev = (s: string) => ({ rejected: 0, review: 1, inconclusive: 2, approved: 3 })[s] ?? 9;
    for (const axis of b.schema.axes) {
      const ordered = orderItems(items, axis.key, b.schema);
      expect(ordered).toHaveLength(items.length);
      const ranks = ordered.map((i) => sev(i.verdicts[axis.key]));
      expect(ranks).toEqual([...ranks].sort((a, c) => a - c));
      // within a status, worst deviation descends
      for (let k = 1; k < ordered.length; k++) {
        if (ordered[k].verdicts[axis.key] === ordered[k - 1].verdicts[axis.key]) {
          expect(worst(ordered[k - 1], axis.key, b.schema)).toBeGreaterThanOrEqual(worst(ordered[k], axis.key, b.schema));
        }
      }
    }
  });
});

describe("metricDeviation", () => {
  const items = realBundle.items[realBundle.current];

  test("|z| when z is read, |value| ÷ review limit otherwise, null when unread or unavailable", () => {
    const nex = metric("nex");
    const withZ = items.find((it) => typeof it.metrics.nex?.z === "number")!;
    expect(metricDeviation(nex, withZ.metrics.nex)).toBeCloseTo(Math.abs(withZ.metrics.nex.z!));
    expect(metricDeviation(nex, { ...withZ.metrics.nex, available: false })).toBeNull();
    expect(metricDeviation(nex, undefined)).toBeNull();
    const sat = metric("sat31");
    const v = items[0].metrics.sat31;
    expect(metricDeviation(sat, v)).toBeCloseTo(Math.abs(v.value!) / sat.limits!.review!);
    expect(metricDeviation(sat, { ...v, value: null })).toBeNull();
  });

  test("worst is the largest metricDeviation of the axis and ignores unavailable readings", () => {
    for (const b of Object.values(bundles)) {
      for (const it of b.items[b.current]) {
        for (const axis of b.schema.axes) {
          const devs = b.schema.metrics
            .filter((m) => m.axis === axis.key)
            .map((m) => metricDeviation(m, it.metrics[m.key]) ?? 0);
          expect(worst(it, axis.key, b.schema)).toBe(Math.max(0, ...devs));
        }
      }
    }
    const it = items[0];
    const m = realBundle.schema.metrics.find((x) => x.key === "nex")!;
    const off = { ...it, metrics: Object.fromEntries(Object.entries(it.metrics).map(([k, v]) => [k, { ...v, available: false }])) };
    expect(worst(off, m.axis, realBundle.schema)).toBe(0);
  });
});
