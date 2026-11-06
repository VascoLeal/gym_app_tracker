import { describe, expect, it, vi } from "vitest";
import { waitForServer } from "./serverStatus";

describe("waitForServer", () => {
  it("keeps checking until the server answers", async () => {
    const check = vi
      .fn<() => Promise<boolean>>()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);

    await expect(waitForServer({ check, intervalMs: 1, timeoutMs: 1_000 })).resolves.toBe(true);
    expect(check).toHaveBeenCalledTimes(3);
  });

  it("gives up after the timeout", async () => {
    const check = vi.fn<() => Promise<boolean>>().mockResolvedValue(false);

    await expect(waitForServer({ check, intervalMs: 5, timeoutMs: 20 })).resolves.toBe(false);
    expect(check.mock.calls.length).toBeGreaterThan(1);
  });
});
