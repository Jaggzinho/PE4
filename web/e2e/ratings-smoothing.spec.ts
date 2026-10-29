import { expect, test } from "@playwright/test";

test("ratings smoothing changes only the overall line", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();

  await page.route("**/api/ratings?*", async (route) => {
    const materialId = new URL(route.request().url()).searchParams.get("material_id");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        material_id: materialId, configured: true,
        date_min: "2026-01-01", date_max: "2026-01-03",
        date_from: "2026-01-01", date_to: "2026-01-03",
        points: [
          { date: "2026-01-01", rating_percent: 20 },
          { date: "2026-01-02", rating_percent: 80 },
          { date: "2026-01-03", rating_percent: 40 },
        ],
        latest_rating: 40, average_rating: 140 / 3,
      }),
    });
  });
  await page.goto("/ratings");
  const toggle = page.getByRole("checkbox", { name: "Smoothing" });
  await expect(toggle).toBeChecked();
  const line = page.locator(".scatterlayer path.js-line");
  await expect(line).toBeVisible();
  const smoothed = await line.getAttribute("d");
  await toggle.uncheck();
  await expect.poll(() => line.getAttribute("d")).not.toBe(smoothed);
  await expect(page.getByText("40.0%", { exact: true })).toBeVisible();
  await toggle.check();
  await expect.poll(() => line.getAttribute("d")).toBe(smoothed);
});
