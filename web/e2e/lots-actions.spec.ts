import { expect, test } from "@playwright/test";

test.use({ video: "off" });

test("lot actions stay in the viewport while data columns scroll", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();
  await page.goto("/lots");
  const actions = page.locator("td.lots-actions").first();
  await expect(actions).toBeVisible();

  const scroll = page.locator(".lots-table-scroll");
  expect(await scroll.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true);
  for (const theme of ["dark", "light"]) {
    await page.evaluate((value) => { document.documentElement.dataset.theme = value; }, theme);
    for (const position of [0, 500, 10000]) {
      await scroll.evaluate((el, value) => { el.scrollLeft = value; }, position);
      for (const label of ["View", "Delete"]) {
        await expect(actions.getByRole("button", { name: label, exact: true })).toBeInViewport({ ratio: 1 });
      }
      const box = await actions.boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(1280);
    }
  }
});
