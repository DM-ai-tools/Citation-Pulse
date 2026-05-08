import { describe, expect, it } from "vitest";
import { applyScanEvent, parseScanEvent } from "./scanEvents";
import type { ScanSnapshot } from "@/types/scan";

const base: ScanSnapshot = {
  scan_id: "s1",
  status: "running",
  submitted_url: "https://x.com",
  locale: "en-US",
  engines: ["chatgpt"],
  score_overall: null,
  brand: null,
  prompts: [{ id: "p1", text: "q", locale: "en-US" }],
  matrix: { cells: [{ promptId: "p1", engine: "chatgpt", status: "queued" }] },
  progress: { per_engine: { chatgpt: { done: 0, total: 1 } } },
};

describe("applyScanEvent", () => {
  it("updates cell", () => {
    const next = applyScanEvent(base, {
      type: "cell.update",
      promptId: "p1",
      engine: "chatgpt",
      status: "cited",
      position: 2,
    });
    expect(next.matrix.cells[0].status).toBe("cited");
    expect(next.matrix.cells[0].position).toBe(2);
  });

  it("marks completed", () => {
    const next = applyScanEvent(base, { type: "scan.completed", score: 88 });
    expect(next.status).toBe("completed");
    expect(next.score_overall).toBe(88);
  });

  it("parses valid JSON", () => {
    expect(parseScanEvent(JSON.stringify({ type: "scan.eta", etaSeconds: 12 }))).toEqual({
      type: "scan.eta",
      etaSeconds: 12,
    });
  });
});
