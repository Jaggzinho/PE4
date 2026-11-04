import { expect, test } from "@playwright/test";
import type { LotsPage } from "../src/api/lots";

test.use({ video: "off" });

test("lot results show AST conformity beside the resistivity reading", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();

  const readings = ["999999999", "1000000000", "1,2E9", null, "-", " "];
  await page.route("**/api/lots?*", async (route) => {
    const response = await route.fetch();
    const data: LotsPage = await response.json();
    expect(data.items.length).toBeGreaterThan(0);
    const items = readings.map((reading, index) => ({
      ...data.items[0],
      test_id: String(index + 1),
      resistivita_superficiale: reading,
    }));
    await route.fulfill({ response, json: { ...data, items, total: items.length, has_next: false } });
  });
  await page.goto("/lots");

  const results = page.getByRole("region", { name: "Lots results" });
  const resistivityHeader = results.getByRole("columnheader", { name: /Resistività Superficiale/ });
  await expect(resistivityHeader.locator("+ th")).toHaveText("Conformità AST");
  await expect(results.locator("tbody strong")).toHaveText(["OK", "NOT OK", "NOT OK", "-", "-", "-"]);
  await expect(results.locator("tbody .ast-ok")).toHaveCount(1);
  await expect(results.locator("tbody .ast-not-ok")).toHaveCount(2);
  await expect(results.locator("tbody strong.muted")).toHaveCount(3);
});

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
