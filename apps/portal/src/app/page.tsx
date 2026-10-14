// Minimal non-business smoke surface so the skeletal portal builds and serves.
// Not a booking/auth/payment UI; replace when real portal pages land.
export default function HomePage() {
  return (
    <main>
      <h1>Zippy Portal</h1>
      <p data-testid="portal-status">Portal skeleton is running.</p>
    </main>
  );
}
