BEGIN;

DROP TABLE IF EXISTS zippy.pod_documents;
DROP TABLE IF EXISTS zippy.trip_location_history;
DROP TABLE IF EXISTS zippy.trip_milestones;
DROP TABLE IF EXISTS zippy.trip_assignments;
DROP TABLE IF EXISTS zippy.trips;
DROP TABLE IF EXISTS zippy.dispatch_offers;
DROP TABLE IF EXISTS zippy.transaction_participants;
DROP TABLE IF EXISTS zippy.order_stops;
DROP TABLE IF EXISTS zippy.orders;
DROP TABLE IF EXISTS zippy.quotes;
DROP TABLE IF EXISTS zippy.vehicle_documents;
DROP TABLE IF EXISTS zippy.vehicles;
DROP TABLE IF EXISTS zippy.vehicle_models;

DROP TYPE IF EXISTS zippy.milestone_kind;
DROP TYPE IF EXISTS zippy.trip_status;
DROP TYPE IF EXISTS zippy.offer_status;
DROP TYPE IF EXISTS zippy.participant_role;
DROP TYPE IF EXISTS zippy.order_status;
DROP TYPE IF EXISTS zippy.vehicle_status;

COMMIT;