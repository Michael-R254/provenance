import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SiteIntro } from "./site-intro";

describe("SiteIntro", () => {
  it("names the guide's subject in the main heading", () => {
    render(<SiteIntro projectCount={2} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Michael Rollinson");
    expect(screen.getByRole("link", { name: "Browse 2 project write-ups" })).toHaveAttribute(
      "href",
      "/projects",
    );
  });

  it("does not link to an empty project list", () => {
    render(<SiteIntro projectCount={0} />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
