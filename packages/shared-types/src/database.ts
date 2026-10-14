/**
 * Zippy Logistics database types.
 * Hand-maintained for M1; will be automated via `supabase gen types` in M2+.
 */

// -----------------------------------------------------------------------------
// Enums
// -----------------------------------------------------------------------------

export type UserBaseRole = "customer" | "driver" | "transport_company" | "admin";
export type UserActiveRole = "customer" | "provider";

export type CustomerCategory = "MSME" | "Warehouse" | "Enterprise";
export type VerificationStatus = "pending" | "verified" | "rejected";

export type DriverStatus = "Salaried Driver" | "Vehicle Owner";

export type VehicleType = "LCV" | "MCV" | "HCV" | "Mini Truck";
export type BodyType = "Open Body" | "Closed Body";
export type VehicleStatus = "online" | "offline" | "in_transition" | "maintenance";
export type OwnershipType = "personal" | "company";

export type OrderStatus =
  | "pending"
  | "inventory_confirmed"
  | "payment_succeeded"
  | "driver_assigned"
  | "in_transit"
  | "delivered"
  | "cancelled"
  | "payment_settled";

export type PaymentStatus = "pending" | "processing" | "completed" | "failed" | "cancelled" | "refunded" | "partial";
export type PaymentMode = "full" | "partial" | "to_pay";
export type PaymentGateway = "razorpay" | "stripe" | "paypal" | "cash";
export type TransactionType = "payment" | "refund" | "commission" | "service_fee";
export type TransactionStatus = "pending" | "processing" | "completed" | "failed";

export type ProviderType = "driver" | "transport_company";

export type AdminActionType =
  | "suppress_alert"
  | "allow_user_with_pending_payment"
  | "cancel_suspicious_order"
  | "suspend_user"
  | "lift_suspension"
  | "override_system"
  | "regulate_ai_agent";

export type TargetType = "user" | "order" | "alert" | "ai_agent";

export type AlertType = "long_halt" | "route_deviation" | "breakdown" | "accident";
export type AlertStatus = "active" | "acknowledged" | "suppressed" | "resolved";

export type AgentActivityStatus = "pending" | "completed" | "failed" | "interrupted";
export type InterventionType = "hallucination" | "error_correction" | "performance_issue" | "anomaly_detection";
export type InterventionStatus = "detected" | "corrected" | "escalated" | "resolved";

export type NotificationChannel = "push" | "sms" | "email" | "in_app";

export type EventSource = "customer_app" | "admin_panel" | "driver_app" | "transport_app" | "worker" | "system";

// -----------------------------------------------------------------------------
// Tables
// -----------------------------------------------------------------------------

export interface User {
  user_id: string;
  email: string;
  phone_number: string;
  password_hash: string;
  first_name: string;
  last_name: string;
  base_role: UserBaseRole;
  active_role: UserActiveRole | null;
  is_active: boolean;
  email_verified: boolean;
  phone_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
  profile_image_url: string | null;
  preferred_language: string;
  payment_hold: boolean;
  payment_hold_reason: string | null;
}

export interface CustomerProfile {
  customer_id: string;
  user_id: string;
  company_name: string | null;
  customer_category: CustomerCategory | null;
  gst_pan_number: string | null;
  company_phone: string | null;
  company_email: string | null;
  verification_status: VerificationStatus;
  kyc_documents: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DriverProfile {
  driver_id: string;
  user_id: string;
  date_of_birth: string | null;
  years_of_experience: number;
  driver_status: DriverStatus | null;
  license_number: string | null;
  license_verified: boolean;
  rating: number;
  documents: Record<string, unknown>;
  bank_account: Record<string, unknown>;
  emergency_contact: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TransportCompany {
  transport_company_id: string;
  user_id: string;
  company_name: string;
  gst_number: string | null;
  pan_number: string | null;
  service_areas: string[] | null;
  specializations: string[] | null;
  reliability_score: number;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleModel {
  model_id: string;
  brand: string | null;
  model: string;
  vehicle_type: VehicleType;
  body_type: BodyType | null;
  capacity_tons: number | null;
  length_ft: number | null;
  width_ft: number | null;
  height_ft: number | null;
  created_at: string;
}

export interface Vehicle {
  vehicle_id: string;
  owner_id: string;
  model_id: string | null;
  assigned_driver_id: string | null;
  registration_number: string;
  vehicle_type: VehicleType;
  body_type: BodyType | null;
  capacity_tons: number | null;
  current_status: VehicleStatus;
  current_location: string | null; // GeoJSON / WKT
  last_seen_at: string | null;
  is_active: boolean;
  ownership_type: OwnershipType;
  documents: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface VehicleTelemetry {
  telemetry_id: string;
  vehicle_id: string;
  driver_id: string | null;
  latitude: number;
  longitude: number;
  speed_kmph: number | null;
  heading: number | null;
  location: string | null;
  recorded_at: string;
  metadata: Record<string, unknown>;
}

export interface Order {
  order_id: string;
  order_number: string;
  customer_id: string;
  provider_id: string | null;
  provider_type: ProviderType | null;
  driver_id: string | null;
  transport_company_id: string | null;
  vehicle_id: string | null;
  order_status: OrderStatus;
  previous_status: string | null;
  status_changed_at: string | null;
  status_changed_by: string | null;

  pickup_address_line1: string;
  pickup_address_line2: string | null;
  pickup_city: string;
  pickup_state: string;
  pickup_postal_code: string;
  pickup_latitude: number | null;
  pickup_longitude: number | null;
  pickup_location: string | null;

  delivery_address_line1: string;
  delivery_address_line2: string | null;
  delivery_city: string;
  delivery_state: string;
  delivery_postal_code: string;
  delivery_latitude: number | null;
  delivery_longitude: number | null;
  delivery_location: string | null;

  consignee_name: string;
  consignee_phone: string;
  consignee_email: string | null;

  cargo_description: string | null;
  cargo_weight: number | null;
  cargo_volume: number | null;
  special_instructions: string | null;
  special_requirements: string[] | null;

  scheduled_pickup_time: string | null;
  scheduled_delivery_time: string | null;
  actual_pickup_time: string | null;
  actual_delivery_time: string | null;

  estimated_distance: number | null;
  estimated_duration: number | null;
  route_polyline: string | null;

  base_amount: number;
  tax_amount: number;
  total_amount: number;
  commission_amount: number;
  commission_rate: number;
  service_fee: number;
  service_fee_rate: number;
  cancellation_fee: number;

  payment_status: PaymentStatus;
  payment_method: string | null;
  payment_mode: PaymentMode;

  cancellation_reason: string | null;
  cancelled_at: string | null;
  cancelled_by: string | null;

  assigned_at: string | null;
  assigned_by: string | null;

  created_at: string;
  updated_at: string;
}

export interface OrderEventLog {
  event_id: string;
  order_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  source: EventSource;
  emitted_by: string | null;
  created_at: string;
}

export interface Payment {
  payment_id: string;
  order_id: string;
  amount: number;
  currency: string;
  payment_status: PaymentStatus;
  payment_method: string | null;
  payment_gateway: PaymentGateway | null;
  gateway_payment_id: string | null;
  gateway_response: Record<string, unknown>;
  processed_at: string | null;
  idempotency_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaymentTransaction {
  transaction_id: string;
  order_id: string;
  payment_id: string | null;
  transaction_type: TransactionType;
  amount: number;
  currency: string;
  transaction_status: TransactionStatus;
  gateway_transaction_id: string | null;
  gateway_response: Record<string, unknown>;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminAction {
  action_id: string;
  admin_id: string;
  action_type: AdminActionType;
  target_type: TargetType;
  target_id: string | null;
  action_details: Record<string, unknown>;
  reason: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface DriverAlert {
  alert_id: string;
  driver_id: string;
  vehicle_id: string | null;
  order_id: string | null;
  alert_type: AlertType;
  alert_status: AlertStatus;
  latitude: number | null;
  longitude: number | null;
  alert_details: Record<string, unknown>;
  created_at: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  suppressed_at: string | null;
  suppressed_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface AIAgentActivity {
  activity_id: string;
  agent_name: string;
  agent_type: string;
  activity_type: string;
  activity_details: Record<string, unknown>;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  confidence_score: number | null;
  execution_time_ms: number | null;
  status: AgentActivityStatus;
  error_message: string | null;
  created_at: string;
  order_id: string | null;
  user_id: string | null;
}

export interface AIAgentIntervention {
  intervention_id: string;
  agent_name: string;
  intervention_type: InterventionType;
  detection_method: string;
  intervention_details: Record<string, unknown>;
  original_output: Record<string, unknown>;
  corrected_output: Record<string, unknown>;
  confidence_score_before: number | null;
  confidence_score_after: number | null;
  status: InterventionStatus;
  detected_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  order_id: string | null;
  user_id: string | null;
}

export interface NotificationLog {
  notification_id: string;
  user_id: string;
  channel: NotificationChannel;
  notification_type: string;
  title: string | null;
  body: string | null;
  payload: Record<string, unknown>;
  is_read: boolean;
  sent_at: string | null;
  delivered_at: string | null;
  failed_at: string | null;
  failure_reason: string | null;
  external_id: string | null;
  idempotency_key: string | null;
  created_at: string;
}

export interface WebhookEvent {
  webhook_id: string;
  provider: string;
  event_type: string;
  payload: Record<string, unknown>;
  signature: string | null;
  processed: boolean;
  processing_attempts: number;
  last_processed_at: string | null;
  error_message: string | null;
  idempotency_key: string | null;
  created_at: string;
}

export interface SOPSection {
  id: string;
  sop_version: string;
  section_id: string;
  section_title: string;
  agent: string | null;
  workflow_category: string | null;
  procedure: Record<string, unknown>;
  key_rules: string[] | null;
  inputs: string[] | null;
  outputs: string[] | null;
  related_tables: string[] | null;
  related_apis: string[] | null;
  related_agents: string[] | null;
  vector_embedding: number[] | null;
  created_at: string;
}

// -----------------------------------------------------------------------------
// Database response helpers
// -----------------------------------------------------------------------------

export type Tables = {
  users: User;
  customer_profiles: CustomerProfile;
  driver_profiles: DriverProfile;
  transport_companies: TransportCompany;
  vehicle_models: VehicleModel;
  vehicles: Vehicle;
  vehicle_telemetry: VehicleTelemetry;
  orders: Order;
  order_event_log: OrderEventLog;
  payments: Payment;
  payment_transactions: PaymentTransaction;
  admin_actions: AdminAction;
  driver_alerts: DriverAlert;
  ai_agent_activities: AIAgentActivity;
  ai_agent_interventions: AIAgentIntervention;
  notification_log: NotificationLog;
  webhook_events: WebhookEvent;
  sop_sections: SOPSection;
};

export type TableName = keyof Tables;
