import { test, expect } from "@playwright/test";

test("landing shows hero and scan form", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Know where AI cites you/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Run free scan/i })).toBeVisible();
});
