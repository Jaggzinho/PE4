import { expect, test, type Page } from "@playwright/test";
import { formatDate, formatDateTime, parseDisplayDate } from "../src/dateFormat";

test("date formatting preserves calendar days and validates leap years", () => {
  expect(formatDate("2026-01-02")).toBe("02-01-2026");
  expect(formatDate("2026-01-02T00:00:00Z")).toBe("02-01-2026");
  expect(formatDate(null)).toBe("—");
  expect(formatDate("", "…")).toBe("…");
  expect(formatDateTime("2026-01-02T10:03:04")).toBe("02-01-2026 10:03:04");
  expect(parseDisplayDate("29-02-2024")).toBe("2024-02-29");
  for (const invalid of ["29-02-2025", "31-04-2026", "00-01-2026", "02-13-2026", "02-01-0000", "2-1-2026"]) {
    expect(parseDisplayDate(invalid)).toBeNull();
  }
});

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();
}

test("date inputs validate calendar dates, retain ISO filters and block invalid saves", async ({ page }) => {
  await login(page);
  await page.goto("/lots");
  await expect(page.locator("tbody")).toContainText("02-01-2026");
  const from = page.getByLabel("Date from", { exact: true });
  // Exercise the real native popup, then simulate its change event to check the shared state.
  await page.evaluate(() => {
    const original = HTMLInputElement.prototype.showPicker;
    HTMLInputElement.prototype.showPicker = function () {
      original.call(this);
      this.dataset.opened = "true";
    };
  });
  await page.getByRole("button", { name: "Open calendar for Date from", exact: true }).click();
  const picker = page.locator('input[type="date"][data-opened="true"]');
  await expect(picker).toHaveCount(1);
  await page.keyboard.press("Escape");
  await picker.evaluate((element: HTMLInputElement) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    setter.call(element, "2024-02-29");
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await expect(from).toHaveValue("29-02-2024");
  await expect(page).toHaveURL(/date_from=2024-02-29/);
  await from.fill("29-02-2024");
  await expect(page).toHaveURL(/date_from=2024-02-29/);
  await from.fill("29-02-2025");
  await expect(from).toHaveAttribute("aria-invalid", "true");
  await expect(page).toHaveURL(/date_from=2024-02-29/);
  await from.fill("31-04-2026");
  await expect(from).toHaveAttribute("aria-invalid", "true");
  await from.fill("02-01-2026");
  await expect(page).toHaveURL(/date_from=2026-01-02/);
  await page.reload();
  await expect(from).toHaveValue("02-01-2026");
  await from.fill("");
  await expect(page).not.toHaveURL(/date_from=/);

  await page.locator("td.lots-actions").first().getByRole("button", { name: "View" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: /^Open calendar for/ })).toHaveCount(3);
  const request = dialog.getByLabel("Request", { exact: true });
  await expect(request).toHaveValue("02-01-2026");
  await request.fill("31-02-2026");
  let writes = 0;
  page.on("request", (req) => {
    if (req.method() === "PUT" && req.url().includes("/api/lots/")) writes++;
  });
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(request).toBeFocused();
  expect(writes).toBe(0);
  await request.fill("02-01-2026");
  const saved = page.waitForRequest((req) => req.method() === "PUT" && req.url().includes("/api/lots/"));
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  expect((await saved).postDataJSON().request_date).toBe("2026-01-02");
  await expect(dialog).toHaveCount(0);
  await expect(page.locator("tbody")).toContainText("02-01-2026");
});

test("charts and ratings show request dates and formatted axes without production dates", async ({ page }) => {
  await login(page);
  await page.goto("/sinottico");
  await page.getByRole("link", { name: "MAT-001", exact: true }).first().click();
  const materialId = new URL(page.url()).searchParams.get("material_id")!;
  await page.goto(`/charts?material_id=${materialId}&date_from=2026-01-01&date_to=2026-01-31`);
  await expect(page.getByRole("button", { name: /^Open calendar for/ })).toHaveCount(2);
  await expect(page.locator(".xtick text").first()).toHaveText(/\d{2}-\d{2}-\d{4}/);
  await expect(page.getByRole("textbox", { name: "Chart from date", exact: true })).toHaveValue("01-01-2026");
  await page.getByLabel("Smoothing", { exact: true }).uncheck();
  await expect(page.locator(".xtick text").first()).toBeVisible();

  // Enable scoring for the disposable server's seeded material.
  // Use the normal login endpoint to obtain credentials without depending on storage keys.
  const auth = await page.request.post("/api/auth/login", { data: { username: "admin", password: "pw" } });
  const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };
  const configured = await page.request.put("/api/settings/ratings/10/weight", { headers, data: { weight: 1 } });
  expect(configured.ok()).toBeTruthy();
  await page.goto(`/ratings?material_id=${materialId}`);
  await expect(page.getByRole("button", { name: /^Open calendar for/ })).toHaveCount(2);
  await expect(page.locator(".xtick text").first()).toHaveText(/\d{2}-\d{2}-\d{4}/);
  const from = page.getByLabel("From", { exact: true });
  await expect(from).toHaveValue("02-01-2026");
  await from.fill("01-01-2026");
  await expect(from).toHaveAttribute("aria-invalid", "true");
  await expect(page).not.toHaveURL(/date_from=2026-01-01/);
});
