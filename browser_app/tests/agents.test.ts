import { expect, it } from "vitest";
import { mdSections } from "../web/src/catalog";

const md = `# X\n\n## Overview\nabout\n\n## Data quality & usage notes\n\n- note one\n- note two\n\n## Related collections\n- rel\n\n## Additional notes\n\nhand note\n`;

it("extracts named AGENTS.md sections in the order asked", () => {
  const s = mdSections(md, ["Data quality & usage notes", "Additional notes", "Missing"]);
  expect(s).toBe("### Data quality & usage notes\n- note one\n- note two\n\n### Additional notes\nhand note");
  expect(s).not.toContain("about");
});
