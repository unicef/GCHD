import { describe, expect, it } from "vitest";
import { clipRing, Ring, tilesFor, zoomFor } from "../web/src/geo";
import { makeGrid, rasterizeZones, zonalExposure } from "../web/src/raster/grid";

const square = (x0: number, y0: number, x1: number, y1: number): Ring => [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]];

describe("grid and rasterization", () => {
  it("caps the number of cells", () => {
    const g = makeGrid([0, 0, 10, 10], 0.001, 10_000);
    expect(g.width * g.height).toBeLessThanOrEqual(10_400);
    expect(makeGrid([0, 0, 1, 1], 0.1, 1e6).width).toBe(10);
  });
  it("burns polygons by cell centre, with holes", () => {
    const g = makeGrid([0, 0, 10, 10], 1, 1e6);
    const z = rasterizeZones(g, [[[square(0, 0, 10, 10), square(2, 2, 4, 4)]], [[square(2, 2, 4, 4)]]]);
    const count = (v: number) => z.filter((x) => x === v).length;
    expect(count(1)).toBe(96);     // 100 cells minus the 2x2 hole
    expect(count(2)).toBe(4);
  });
  it("exposure: share of population in exposed cells", () => {
    const g = makeGrid([0, 0, 2, 1], 1, 1e6);                     // two cells
    const zones = rasterizeZones(g, [[[square(0, 0, 2, 1)]]]);
    const pop = new Float32Array([30, 10]);
    const haz = new Float32Array([0.6, 0.1]);
    const [r] = zonalExposure(zones, 1, pop, [{ code: "f", values: haz, valid: { op: ">", value: -1000 }, op: ">", threshold: 0.5 }], "all");
    expect(r.pixelPop).toBe(40);
    expect(r.exposedPixelPop).toBe(30);
    expect(r.hazMax).toBeCloseTo(0.6);
  });
  it("any / all combine and nodata", () => {
    const g = makeGrid([0, 0, 3, 1], 1, 1e6);
    const zones = rasterizeZones(g, [[[square(0, 0, 3, 1)]]]);
    const pop = new Float32Array([1, 2, 4]);
    const a = { code: "a", values: new Float32Array([1, 0, NaN]), valid: { op: ">" as const, value: -1 }, op: ">" as const, threshold: 0.5 };
    const b = { code: "b", values: new Float32Array([1, 1, 1]), valid: { op: ">" as const, value: -1 }, op: ">" as const, threshold: 0.5 };
    expect(zonalExposure(zones, 1, pop, [a, b], "any")[0].exposedPixelPop).toBe(7);
    expect(zonalExposure(zones, 1, pop, [a, b], "all")[0].exposedPixelPop).toBe(1);
  });
});

describe("tiles and clipping", () => {
  it("clips a ring to a rectangle", () => {
    const r = clipRing(square(-1, -1, 1, 1), [0, 0, 2, 2]);
    const xs = r.map((p) => p[0]), ys = r.map((p) => p[1]);
    expect(Math.min(...xs)).toBe(0); expect(Math.max(...xs)).toBe(1);
    expect(Math.min(...ys)).toBe(0); expect(Math.max(...ys)).toBe(1);
    expect(clipRing(square(5, 5, 6, 6), [0, 0, 2, 2])).toEqual([]);
  });
  it("chooses a zoom within the tile budget", () => {
    const kenya: [number, number, number, number] = [33.9, -4.7, 41.9, 5.0];
    const z = zoomFor(kenya, 160);
    expect(tilesFor(kenya, z).length).toBeLessThanOrEqual(160);
    expect(tilesFor(kenya, z + 1).length).toBeGreaterThan(160);
  });
});
