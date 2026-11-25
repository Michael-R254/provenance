import { describe, expect, it } from "vitest";

import { isRole, orderForRole, ROLES, STARTERS } from "./recruiter";

describe("recruiter mode", () => {
  it("has starter questions for every role", () => {
    for (const role of ROLES) expect(STARTERS[role.id].length).toBeGreaterThan(0);
  });

  it("reorders projects by type without dropping any, keeping ties stable", () => {
    const items = [
      { slug: "a", type: "coursework" },
      { slug: "b", type: "personal" },
      { slug: "c", type: "work" },
      { slug: "d", type: "personal" },
    ];
    expect(orderForRole(items, "engineer").map((i) => i.slug)).toEqual(["b", "d", "c", "a"]);
    expect(orderForRole(items, "recruiter").map((i) => i.slug)).toEqual(["c", "b", "d", "a"]);
    expect(orderForRole(items, "browsing")).toEqual(items);
  });

  it("validates stored role values", () => {
    expect(isRole("engineer")).toBe(true);
    expect(isRole("admin")).toBe(false);
  });
});
