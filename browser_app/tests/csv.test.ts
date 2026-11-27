import { expect, it } from "vitest";
import { toCsv } from "../web/src/csv";

it("quotes CSV cells", () => {
  expect(toCsv(["a", "b"], [{ a: 'x,"y"', b: 1 }, { a: null, b: 2.5 }])).toBe('a,b\r\n"x,""y""",1\r\n,2.5\r\n');
});
