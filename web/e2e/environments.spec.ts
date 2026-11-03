import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, environment: string) {
  await page.goto("/login");
  const selector = page.getByRole("combobox", { name: "Environment" });
  await expect(selector).toBeEnabled();
  await selector.click();
  await expect(page.getByRole("option")).toHaveText([
    "TCM Romania", "WAM Romania", "TCM Italia", "WAM WuXi",
  ]);
  await page.getByRole("option", { name: environment, exact: true }).click();
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await expect(page.locator(".sidebar")).toContainText(environment);
}

test("four environments, local flags, keyboard selection and independent tabs", async ({ context, page }) => {
  await page.goto("/login");
  const selector = page.getByRole("combobox", { name: "Environment" });
  await expect(selector).toBeEnabled();
  await selector.focus();
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await expect(selector).toContainText("WAM WuXi");
  const flag = selector.locator("img");
  expect(await flag.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);

  await signIn(page, "TCM Romania");
  await expect(page.getByRole("link", { name: "MAT-001", exact: true }).first()).toBeVisible();
  const second = await context.newPage();
  await signIn(second, "TCM Italia");
  await expect(second.getByRole("link", { name: "MAT-001", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".sidebar")).toContainText("TCM Romania");
  await expect(page.getByRole("link", { name: "MAT-001", exact: true }).first()).toBeVisible();
  await second.reload();
  await expect(second.locator(".sidebar")).toContainText("TCM Italia");
  await second.getByRole("button", { name: "Logout" }).click();
  await expect(second.getByRole("combobox", { name: "Environment" })).toContainText("TCM Italia");
  await expect(page.locator(".sidebar")).toContainText("TCM Romania");

  for (const environment of ["WAM Romania", "WAM WuXi"]) {
    await signIn(second, environment);
    await second.getByRole("button", { name: "Open settings" }).click();
    await expect(second.getByText("Import destination:")).toContainText(environment);
    await second.getByRole("button", { name: "Logout" }).click();
  }
});

test("logout clears cached QC data before entering an empty environment", async ({ page }) => {
  await signIn(page, "TCM Romania");
  await page.locator(".nav").getByRole("link", { name: "Calendar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Calendar", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Logout" }).click();
  await signIn(page, "TCM Italia");
  await page.locator(".nav").getByRole("link", { name: "Calendar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Calendar", exact: true })).toBeVisible();
  await expect(page.getByText("MAT-001", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("pe3_access_token"))).toBeNull();
  expect(await page.evaluate(() => sessionStorage.getItem("pe3_access_token"))).not.toBeNull();
});
