import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";


const WEB_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(WEB_DIR, "../..");

async function login(page: Page, username = "admin", password = "pw") {
  await page.goto("/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText(username, { exact: true })).toBeVisible();
}

test.describe.serial("built PE3 workflows", () => {
  test("login failure and permission boundaries", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Username").fill("viewer");
    await page.getByLabel("Password").fill("wrong");
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page.getByText(/Invalid username\/password/)).toBeVisible();
    await page.getByLabel("Password").fill("pw");
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page.getByText("viewer", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Import" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Master Data" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);
    await page.getByRole("button", { name: "Open settings" }).click();
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Master Data" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "Application settings" })).toHaveCount(0);
    await page.goto("/master-data");
    await expect(page.getByRole("alert")).toContainText("do not have permission");
  });

  test("QC selection survives direct navigation and related links", async ({ page }) => {
    await login(page);
    await page.goto("/sinottico");
    const materialLink = page.getByRole("link", { name: "MAT-001" }).first();
    await expect(materialLink).toBeVisible();
    await materialLink.click();
    await expect(page).toHaveURL(/\/lots\?material_id=\d+/);
    await expect(page.getByRole("heading", { name: "Lots / results" })).toBeVisible();
    await page.getByRole("button", { name: "Add", exact: true }).click();
    const newLotDialog = page.getByRole("dialog", { name: "New lot or result" });
    await expect(newLotDialog.getByLabel("Request", { exact: true })).toHaveAttribute("type", "date");
    await expect(newLotDialog.getByLabel("Prod", { exact: true })).toHaveAttribute("type", "date");
    await expect(newLotDialog.getByLabel("Analysis", { exact: true })).toHaveAttribute("type", "date");
    await newLotDialog.getByRole("button", { name: "Close" }).click();
    await expect(page.getByRole("columnheader", { name: "ID" })).toHaveCount(0);
    await page.getByRole("searchbox", { name: "Search all lots" }).fill("MAT-001");
    await expect(page).toHaveURL(/q=MAT-001/);
    await expect(page.getByRole("button", { name: /Remove Search: MAT-001 filter/ })).toBeVisible();
    await page.getByText(/Showing \d+–\d+ of \d+/).waitFor();
    await page.getByRole("button", { name: /^Request/ }).click();
    await expect(page).toHaveURL(/sort_by=request_date/);
    await page.getByText("Columns", { exact: true }).click();
    await page.getByLabel("ISO", { exact: true }).uncheck();
    await expect(page.getByRole("columnheader", { name: /^ISO/ })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("columnheader", { name: /^ISO/ })).toHaveCount(0);
    await page.locator("tbody").getByRole("button", { name: "View" }).first().click();
    await expect(page).toHaveURL(/test_id=\d+/);
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: "Close" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.locator("tbody").getByRole("link", { name: "Charts" }).first().click();
    await expect(page).toHaveURL(/\/charts\?material_id=\d+/);
    await page.getByRole("main").getByRole("link", { name: "Ratings" }).click();
    await expect(page).toHaveURL(/\/ratings\?material_id=\d+/);
    await page.getByRole("main").getByRole("link", { name: "Calendar" }).click();
    await expect(page).toHaveURL(/\/calendar\?material_id=\d+/);
  });

  test("import completes and appears in bounded history", async ({ page }) => {
    await login(page);
    await page.getByRole("button", { name: "Open settings" }).click();
    await page.locator('input[type="file"]').setInputFiles(path.join(ROOT, "CONTROLLO LASTRINE TCM RO REV2.xlsm"));
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await expect(page.getByText(/Imported:/)).toBeVisible({ timeout: 75_000 });
    await expect(page.getByRole("heading", { name: "Recent import jobs" })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toContainText("succeeded");
  });

  test("Outlook fallback and next-startup database setting", async ({ page }) => {
    await login(page);
    await page.getByRole("button", { name: "Open settings" }).click();
    await page.getByRole("tab", { name: "Application settings" }).click();
    await page.getByRole("button", { name: "Outlook" }).click();
    await page.getByRole("button", { name: "Create test draft in Outlook" }).click();
    await expect(page.getByRole("alert")).toContainText(/\.eml/);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download .eml instead" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("pe3-outlook-test.eml");

    await page.getByRole("button", { name: "Database" }).click();
    await expect(page.getByText(/Active source:/)).toBeVisible();
    await page.getByLabel("Database path for next startup").fill(path.join(ROOT, ".e2e", "next.duckdb"));
    await page.getByRole("button", { name: "Save next-startup path" }).click();
    await expect(page.getByRole("status").last()).toContainText(/Saved locally|Restart PE3/);
    await expect(page.getByText(/Restart required/)).toBeVisible();
  });

  test("rating rule save accepts an empty 204 response", async ({ page }) => {
    await login(page);
    await page.getByRole("button", { name: "Open settings" }).click();
    await page.getByRole("tab", { name: "Application settings" }).click();
    await page.getByRole("button", { name: "Ratings", exact: true }).click();

    await page.locator("tbody").getByRole("button", { name: "Edit…" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Clear" }).click();
    await dialog.getByLabel("Max points").fill("23");
    await dialog.getByLabel("Points for band 1").fill("7");

    const saveResponse = page.waitForResponse((response) =>
      response.request().method() === "PUT" && /\/api\/settings\/ratings\/\d+\/rule$/.test(response.url()),
    );
    await dialog.getByRole("button", { name: "Save" }).click();
    expect((await saveResponse).status()).toBe(204);
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);

    await page.reload();
    await page.getByRole("button", { name: "Ratings", exact: true }).click();
    await page.locator("tbody").getByRole("button", { name: "Edit…" }).first().click();
    const savedDialog = page.getByRole("dialog");
    await expect(savedDialog.getByLabel("Max points")).toHaveValue("23");
    await expect(savedDialog.getByLabel("Points for band 1")).toHaveValue("7");
  });
});
