import { expect, test } from "@playwright/test";

test.use({ video: "off" });

test("material tolerance editor and chart smoothing", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("combobox", { name: "Environment" }).click();
  await page.getByRole("option", { name: "WAM WuXi", exact: true }).click();
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open settings" }).click();
  await page.getByRole("tab", { name: "Master Data" }).click();
  await page.getByRole("button", { name: "Tolerances" }).click();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const material = dialog.getByLabel("Material");
  const materialId = await material.getByRole("option", { name: /^MAT-001(?:\s|$)/ }).getAttribute("value");
  await material.selectOption(materialId!);
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

  await page.locator("tbody tr").first().getByRole("button", { name: "Edit", exact: true }).click();
  await expect(dialog.getByLabel("alarm high", { exact: true })).toHaveValue("115");
  await expect(dialog.getByLabel("alarm high unit")).toHaveValue("absolute");
  await dialog.getByLabel("alarm high unit").selectOption("offset");
  await dialog.getByLabel("alarm high", { exact: true }).fill("15");
  await expect(dialog.getByText("Effective: 115")).toBeVisible();
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toHaveCount(0);
  await page.locator("tbody tr").first().getByRole("button", { name: "Edit", exact: true }).click();
  await expect(dialog.getByLabel("alarm high", { exact: true })).toHaveValue("15");
  await expect(dialog.getByLabel("alarm high unit")).toHaveValue("offset");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByRole("link", { name: "Charts", exact: true }).click();
  await page.getByLabel("Chart material").selectOption({ index: 1 });
  await expect(page.getByLabel("Chart material")).toHaveValue(/\d+/);
  await page.getByLabel("Smoothing").uncheck();
  await page.getByLabel("Smoothing").check();
  await expect(page.locator(".js-plotly-plot").first()).toBeVisible();
});
