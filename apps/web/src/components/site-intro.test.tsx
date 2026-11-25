import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SiteIntro } from "./site-intro";

describe("SiteIntro", () => {
  it("renders the site title as the page heading", () => {
    render(<SiteIntro />);
    expect(screen.getByRole("heading", { level: 1, name: "Provenance" })).toBeInTheDocument();
  });
});
