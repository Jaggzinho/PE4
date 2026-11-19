import { expect, test } from "@playwright/test";

test.use({ video: "off" });

test("Charts and Ratings share a four-material comparison", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByText("admin", { exact: true })).toBeVisible();

  const dates = ["2026-01-01", "2026-01-02"];
  const materials = ["101", "102", "103", "104", "105"].map(material_id => ({
    material_id, code: `QC-${material_id}`, description: material_id === "104" ? "" : `Compound ${material_id}`, active: true,
  }));
  await page.route("**/api/materials", route => route.fulfill({ json: materials }));
  await page.route("**/api/charts/panels?*", route => {
    const params = new URL(route.request().url()).searchParams;
    const id = params.get("material_id");
    if (id === "104") return route.fulfill({ status: 404, json: { message: "Material not found" } });
    const x = id === "103" ? [] : dates;
    const y = id === "103" ? [] : [20, 30];
    return route.fulfill({ json: {
      material_id: id,
      panels: [{ property_id: "1", title: "Hardness", unit: "Shore", traces: [
        { kind: "series", name: "Series", x, y, measured_x: x, measured_y: y },
        ...(params.get("avg") === "true" ? [{ kind: "avg", name: "Average", x, y }] : []),
        ...(params.get("tolerances") === "true" ? [{ kind: "reference", name: "Reference", x, y }] : []),
      ] }],
    } });
  });
  await page.route("**/api/ratings?*", route => {
    const params = new URL(route.request().url()).searchParams;
    const id = params.get("material_id");
    if (id === "104") return route.fulfill({ status: 404, json: { message: "Material not found" } });
    const points = id === "103" ? [] : dates.map(date => ({ date, rating_percent: 70 }));
    return route.fulfill({ json: {
      material_id: id, configured: true, points,
      latest_rating: points.length ? 70 : null, average_rating: points.length ? 70 : null,
    } });
  });

  await page.goto("/charts?material_id=101&date_from=2026-01-01&date_to=2026-01-03");
  const add = page.getByLabel("Add material to compare");
  await expect(add.locator('option[value="101"]')).toHaveCount(0);
  for (const id of ["102", "103", "104"]) await add.selectOption(id);
  await expect(add).toBeDisabled();
  await expect(page.getByRole("button", { name: "Remove Compound 102 from comparison" })).toHaveText("Compound 102 \u00d7");
  await expect(page.getByRole("checkbox", { name: "Tolerances" })).toBeDisabled();
  const legend = page.getByRole("group", { name: "Material legend" });
  await expect(legend.getByRole("button")).toHaveCount(2);
  await expect(page.getByText("No measurements in this date range", { exact: false })).toBeVisible();
  await expect(page.getByText("Material not found", { exact: false })).toBeVisible();
  const second = legend.getByRole("button", { name: "Compound 102" });
  const secondColor = await second.locator("span").evaluate(el => getComputedStyle(el).borderTopColor);
  const firstColor = await legend.getByRole("button", { name: "Compound 101" }).locator("span")
    .evaluate(el => getComputedStyle(el).borderTopColor);
  expect(firstColor).not.toBe(secondColor);
  await expect.poll(() => page.locator(".scatterlayer path.js-line").evaluateAll(paths =>
    paths.map(path => getComputedStyle(path).stroke))).toContain(secondColor);
  await second.click();
  await expect(second).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => page.locator(".scatterlayer path.js-line").evaluateAll(paths =>
    paths.map(path => getComputedStyle(path).stroke))).not.toContain(secondColor);

  await page.reload();
  await expect(add).toBeDisabled();
  await page.getByRole("link", { name: "Ratings", exact: true }).last().click();
  await expect(page).toHaveURL(/date_from=2026-01-01.*date_to=2026-01-03.*compare_material_id=104/);
  await expect(page.getByRole("row", { name: /Compound 102.*70.0%.*70.0%/ })).toBeVisible();
  await expect(page.getByText("No rated tests in this date range")).toBeVisible();
  await expect(legend.getByRole("button")).toHaveCount(2);
  await expect(second.locator("span")).toHaveCSS("border-top-color", secondColor);

  await page.getByRole("link", { name: "Sinottico", exact: true }).first().click();
  await page.getByRole("link", { name: "Charts", exact: true }).first().click();
  await expect(add).toBeDisabled();
  await expect(page).toHaveURL(/date_from=2026-01-01.*date_to=2026-01-03.*compare_material_id=104/);
  await page.getByRole("link", { name: "Ratings", exact: true }).first().click();
  await expect(legend.getByRole("button")).toHaveCount(2);

  for (const id of ["102", "103", "104"]) {
    await page.getByRole("button", { name: `Remove ${id === "104" ? "QC-104" : `Compound ${id}`} from comparison` }).click();
  }
  await expect(legend).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Last test" })).toBeVisible();
  await page.getByRole("link", { name: "Charts", exact: true }).last().click();
  await expect(page.getByRole("checkbox", { name: "Tolerances" })).toBeChecked();
  await expect(page.getByRole("group", { name: "Chart legend" }).getByRole("button", { name: "Reference" })).toBeVisible();
  await add.selectOption("102");
  await expect(legend.getByRole("button")).toHaveCount(2);
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("pw");
  await page.getByRole("button", { name: "Login" }).click();
  await page.getByRole("link", { name: "Charts", exact: true }).first().click();
  await expect(page.getByLabel("Chart material")).toHaveValue("");
  await expect(legend).toHaveCount(0);
});
