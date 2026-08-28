/**
 * M2 deterministic business-core types: pricing, matching, payment plans.
 * Mirrors DB functions in migrations 07–09.
 */

// -----------------------------------------------------------------------------
// Pricing reference data
// -----------------------------------------------------------------------------

export type VehicleClass = "Mini Truck" | "LCV" | "MCV" | "HCV";

export interface PricingRateBand {
  vehicle_class: VehicleClass;
  min_tons: number;
  max_tons: number;
  min_rate_per_km: number;
  max_rate_per_km: number;
}

export interface PricingTollBand {
  band_order: number;
  max_km: number | null; // null = open-ended highest band
  toll_amount: number;
}

export interface Quote {
  vehicle_class: VehicleClass;
  rate_per_km: number;
  freight_amount: number;
  toll_amount: number;
  loading_amount: number; // 3% of freight
  tax_amount: number;     // GST 5% on freight+toll+loading
  total_amount: number;   // freight + toll + loading + tax
}

// -----------------------------------------------------------------------------
// Matching (D-05: user_id is the assignment identity)
// -----------------------------------------------------------------------------

export interface NearbyDriverMatch {
  user_id: string;               // D-05 identity — matches orders.provider_id
  driver_id: string;
  driver_name: string;
  rating: number;
  vehicle_id: string;
  registration_number: string;
  vehicle_type: VehicleClass;
  capacity_tons: number;
  distance_m: number;
  score: number;                 // rating*10 - distance_km*0.05
  assigned_order_count: number;
}

// -----------------------------------------------------------------------------
// Payment plans
// -----------------------------------------------------------------------------

export type PaymentMode = "full" | "partial" | "to_pay";

/** Mirrors DB validate_payment_plan(): throws-equivalent via isPlanValid. */
export function isPaymentPlanValid(
  mode: PaymentMode,
  totalAmount: number,
  advanceAmount: number
): boolean {
  if (!(totalAmount > 0)) return false;
  if (mode === "full") return advanceAmount === totalAmount;
  if (mode === "partial") return advanceAmount >= totalAmount * 0.5;
  return advanceAmount === 0; // to_pay
}
