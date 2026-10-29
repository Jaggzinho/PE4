import { expect, test } from "@playwright/test";

test("material tolerance editor and chart smoothing", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open settings" }).click();
  await page.getByRole("tab", { name: "Master Data" }).click();
  await page.getByRole("button", { name: "Tolerances" }).click();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Material").selectOption({ label: "MAT-001" });
  await dialog.getByLabel("Reference value").fill("100");
  await dialog.getByLabel("warn low", { exact: true }).fill("5");
  await dialog.getByLabel("warn low unit").selectOption("percent");
  await dialog.getByLabel("alarm low", { exact: true }).fill("10");
  await dialog.getByLabel("alarm low unit").selectOption("percent");
  await dialog.getByLabel("alarm high", { exact: true }).fill("115");
  await expect(dialog.getByText("Effective: 95")).toBeVisible();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator("tbody tr").first()).toContainText("95 (5%)");

  await page.getByRole("link", { name: "Charts", exact: true }).click();
  await page.getByLabel("Chart material").selectOption({ index: 1 });
  await expect(page.getByLabel("Chart material")).toHaveValue(/\d+/);
  await page.getByLabel("Smoothing").uncheck();
  await page.getByLabel("Smoothing").check();
  await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
});
