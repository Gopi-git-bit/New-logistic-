# PRD — Frontend (§18 Customer Portal & Driver PWA)

> Source of truth for all frontend specifications.

## 1. Customer Portal (`apps/portal/`)

**Stack**: Next.js 15 App Router, TypeScript, Tailwind CSS, Supabase client

### Navigation Structure
- **Bottom tab bar** with 5 sections: Home, Book Shipment, Track Orders, Payments, Profile
- **Stack navigation** within each tab
- **Modal navigation** for order details, document viewer, communication hub

### Core Screens

#### Registration Screen
- Company Information Form (name, category, GST/PAN, phone, email)
- Email + phone verification via OTP
- Submit button disabled until all fields verified

#### Home Screen
- Header with company logo + notification bell (badge count)
- Welcome banner with personalized greeting
- Quick Actions: "Book New Shipment" CTA, "Track Active Order"
- Recent Orders Summary (last 7 days)
- Account Status (payment, verification)

#### Book Shipment Form
- Progress indicator (4 steps: Details → Vehicle → Locations → Payment)
- Shipment Details: product type (autocomplete), description, weight/volume, special requirements
- Vehicle Requirements: count, type (Closed/Open Body), tonnage (LCV/MCV/HCV)
- Pickup & Delivery: locations with map selector, schedule options
- Consignee Information: name, address, contact
- Document Upload: optional, camera capture
- Payment Section: mode selection (Part/Full/ToPay), price estimation
- Terms & Conditions checkbox

#### Order Tracking Screen
- Real-time map view with vehicle location
- Order Status Timeline (6 stages)
- Driver details + contact options
- ETA display
- Action buttons: Contact Provider, Report Issue, Cancel/Reschedule

#### Payment Hub Screen
- Payment summary card
- Payment methods management
- Transaction history
- Invoice list with download

### Real-time Features
- Supabase Realtime subscriptions for order status
- WebSocket for live tracking
- Push notifications for order updates

## 2. Driver PWA (`apps/console/driver/*`)

**Stack**: Vite 6 + React 19, TypeScript, Tailwind CSS

### Navigation
- Bottom tab: Home, Orders, Inventory, Notifications, Profile/Settings

### Core Screens

#### Home Screen
- Vehicle Status Card (name/number, Online/Offline toggle, location)
- Quick Stats (today's earnings, orders completed, active order)
- Action Buttons: "View Orders", "Check Inventory"

#### Order Screen
- Tab bar: "Current Order" and "Order History"
- Current Order: status indicator, consignor/consignee cards, shipment value, payment status, action buttons (Accept/Reject/Cancel)
- Order History: date range selector, filters, order list

#### Profile Screen
- Profile photo upload
- Personal info form (name, DOB, mobile, email, address)
- Professional info (vehicle type, experience, driver status)
- Document verification status

## 3. Admin Console (`apps/console/admin/*`)

**Stack**: Vite 6 + React 19, TypeScript, Tailwind CSS

### Navigation
- Sidebar with hierarchical menu
- Tab-based secondary navigation
- Floating action buttons for common tasks
- Breadcrumb navigation

### Core Sections

#### Dashboard Overview
- System Health Panel (server status, API response times, error rates)
- Activity Metrics (active users, order volume, utilization)
- Alert Center (critical/warning/info alerts)
- Quick Actions (system-wide notifications, emergency cancellation, user suspension)

#### Participant Management
- User Directory (searchable, filterable by type/status/location)
- User Analytics (acquisition, retention, behavior patterns)
- Account Actions (suspend/activate, verify, password reset)

#### Order Management
- Order Monitoring Dashboard (real-time status, flow visualization, exceptions)
- Order Intervention Tools (cancel, refund, modify, manual assign)
- Suspicious Order Detection (AI anomaly detection, risk scoring)

#### Fleet Management
- Vehicle Tracking (real-time map, status indicators, route visualization)
- Route Monitoring (active routes, deviation alerts, ETA accuracy)
- Maintenance Oversight (schedules, service history, compliance)
- Utilization Analytics

#### Financial Oversight
- Transaction Monitoring (real-time, payment status, failures)
- Payment Issues (failed alerts, refund queue, disputes)
- Revenue Analytics (trends, commission tracking, forecasting)

#### AI Agent Supervision
- Agent Performance Dashboard (accuracy, response time, errors)
- Hallucination Detection (anomaly detection, confidence scoring)
- Model Retraining (triggers, versioning, A/B testing)

#### Compliance & Security
- Policy Enforcement (rule config, violations, penalties)
- Security Monitoring (access logs, threats, incidents)
- Audit Logs (comprehensive logging, compliance reporting)

## 4. Design System

### Color Palette
- Primary: Teal (#009688)
- Customer Role: Orange (#FF9800)
- Provider Role: Purple (#9C27B0)
- Network: Indigo (#3F51B5)
- Service Fee: Amber (#FFC107)
- Status colors: Success (green), Warning (yellow), Error (red)

### Typography
- Font: Inter (system fallback: -apple-system, BlinkMacSystemFont, 'Segoe UI')
- Sizes: xs (12px), sm (14px), base (16px), lg (18px), xl (20px), 2xl (24px)

### Accessibility
- Minimum touch target: 44×44px
- Screen reader labels on all interactive elements
- High contrast mode support
- Voice commands for key actions
