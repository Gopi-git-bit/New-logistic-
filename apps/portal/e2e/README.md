# Portal E2E smoke tests

Playwright (Chromium) smoke tests for `apps/portal`, run in CI by `.github/workflows/ci-frontend-e2e.yml`.

## Run locally

From the repository root (pnpm 9.14.0, Node >= 20):

```bash
pnpm install --frozen-lockfile
pnpm --filter @zippy/portal exec playwright install --with-deps chromium
pnpm --filter @zippy/portal build
pnpm --filter @zippy/portal test:e2e
```

The config serves the built portal with `next start` on `http://127.0.0.1:3210` and opens the HTML report in `apps/portal/playwright-report`. Vitest (`pnpm --filter @zippy/portal test`) excludes `e2e/`.

## Scope and limitations

- Covers only what exists today: the minimal non-business home page (`src/app/page.tsx`), 404 handling, and the Razorpay webhook **rejection** paths (missing/invalid signature, wrong method).
- Uses synthetic data and a test-only placeholder webhook secret. No Supabase, Razorpay, or other live services and no real credentials are used.
- **This is not full booking, auth, or shipment E2E coverage.** Those journeys do not exist in the portal yet.
