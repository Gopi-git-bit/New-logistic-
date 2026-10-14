import { expect, test } from "@playwright/test";

test.describe("portal smoke", () => {
  test("home page renders", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle("Zippy Portal");
    await expect(page.getByRole("heading", { name: "Zippy Portal" })).toBeVisible();
    await expect(page.getByTestId("portal-status")).toBeVisible();
  });

  test("unknown route returns 404", async ({ page }) => {
    const response = await page.goto("/this-route-does-not-exist");
    expect(response?.status()).toBe(404);
  });
});

// Rejection paths only: no valid signature is sent, so no database/payment call is reached.
test.describe("razorpay webhook rejection", () => {
  const url = "/api/webhooks/razorpay";

  test("rejects a missing signature with 401", async ({ request }) => {
    const res = await request.post(url, { data: '{"id":"evt_synthetic"}', headers: { "content-type": "application/json" } });
    expect(res.status()).toBe(401);
    expect(await res.json()).toEqual({ error: "invalid signature" });
  });

  test("rejects an invalid signature with 401", async ({ request }) => {
    const res = await request.post(url, {
      data: '{"id":"evt_synthetic"}',
      headers: { "content-type": "application/json", "x-razorpay-signature": "deadbeef" },
    });
    expect(res.status()).toBe(401);
  });

  test("does not allow GET", async ({ request }) => {
    const res = await request.get(url);
    expect(res.status()).toBe(405);
  });
});
