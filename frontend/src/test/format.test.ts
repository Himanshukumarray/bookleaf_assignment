import { describe, expect, it } from "vitest";

import { formatDate, formatINR, formatPercent, formatRoyalty, orText, textSimilarity, timeAgo } from "../utils/format";

describe("formatting never leaks null/undefined/NaN", () => {
  it("formats rupees in Indian grouping", () => {
    expect(formatINR(125000)).toBe("₹1,25,000");
    expect(formatINR(85.5)).toBe("₹85.5");
  });

  it("handles missing money", () => {
    expect(formatINR(null)).toBe("Not assigned");
    expect(formatINR(undefined, "n/a")).toBe("n/a");
    expect(formatINR(Number.NaN)).toBe("Not assigned");
    expect(formatRoyalty(null)).toBe("₹0");
    expect(formatRoyalty(0)).toBe("₹0");
  });

  it("handles missing and invalid dates", () => {
    expect(formatDate(null, "Not published yet")).toBe("Not published yet");
    expect(formatDate("not-a-date")).toBe("—");
    expect(formatDate("2024-06-01")).toContain("2024");
  });

  it("handles percentages and blank text", () => {
    expect(formatPercent(0.964)).toBe("96%");
    expect(formatPercent(null)).toBe("—");
    expect(orText("  ", "Not assigned")).toBe("Not assigned");
    expect(orText(null, "Not assigned")).toBe("Not assigned");
  });

  it("renders relative time", () => {
    const now = new Date("2026-01-10T12:00:00Z");
    expect(timeAgo("2026-01-10T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-01-10T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-01-07T12:00:00Z", now)).toBe("3d ago");
    expect(timeAgo(null)).toBe("—");
  });
});

describe("textSimilarity (AI-assisted detection)", () => {
  const draft = "Hi Priya, thanks for reaching out. Your pending royalty is below the threshold so it rolls over.";
  it("treats light edits as the same draft", () => {
    expect(textSimilarity(draft + " Warm regards", draft)).toBeGreaterThan(0.3);
  });
  it("treats a full rewrite as different", () => {
    expect(textSimilarity("We will look into the printing defect and arrange a reprint.", draft)).toBeLessThan(0.3);
  });
  it("is zero for empty input", () => {
    expect(textSimilarity("", draft)).toBe(0);
  });
});
