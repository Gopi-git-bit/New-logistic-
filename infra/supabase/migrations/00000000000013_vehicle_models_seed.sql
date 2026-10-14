-- =============================================================================
-- M13: Vehicle Models — Schema Extension + India Market Seed Data
-- Adds fuel type, GVW, cargo dimensions (meters), engine specs, source URLs.
-- Seeds 123 verified vehicle models from Indian OEMs (Tata, Ashok Leyland,
-- Eicher, BharatBenz, Mahindra, Maruti Suzuki, Force Motors).
-- =============================================================================

-- 1. Extend vehicle_models with rich specification columns
ALTER TABLE public.vehicle_models
    ADD COLUMN IF NOT EXISTS fuel_type        VARCHAR(30),
    ADD COLUMN IF NOT EXISTS engine_cc        INTEGER,
    ADD COLUMN IF NOT EXISTS mileage          VARCHAR(30),       -- text: "14 km/L", "23.24 km/kg"
    ADD COLUMN IF NOT EXISTS gvw_tons         NUMERIC(6,2),      -- Gross Vehicle Weight / GCW
    ADD COLUMN IF NOT EXISTS cargo_length_m   NUMERIC(5,2),      -- cargo body length in meters
    ADD COLUMN IF NOT EXISTS cargo_width_m    NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS cargo_height_m   NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS overall_length_m NUMERIC(5,2),      -- overall vehicle length
    ADD COLUMN IF NOT EXISTS overall_width_m  NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS overall_height_m NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS source_url       TEXT,
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified','range_confirmed','model_confirmed','specs_confirmed')),
    ADD COLUMN IF NOT EXISTS notes            TEXT;

-- 2. Widen vehicle_type CHECK to include Pickup, Cargo Van (Indian market segments)
--    on vehicle_models
ALTER TABLE public.vehicle_models
    DROP CONSTRAINT IF EXISTS vehicle_models_vehicle_type_check;

ALTER TABLE public.vehicle_models
    ADD CONSTRAINT vehicle_models_vehicle_type_check
    CHECK (vehicle_type IN (
        'Mini Truck','Pickup','LCV','MCV','HCV',
        'Cargo Van','Cargo/Crew'
    ));

--    on vehicles (same expansion)
ALTER TABLE public.vehicles
    DROP CONSTRAINT IF EXISTS vehicles_vehicle_type_check;

ALTER TABLE public.vehicles
    ADD CONSTRAINT vehicles_vehicle_type_check
    CHECK (vehicle_type IN (
        'Mini Truck','Pickup','LCV','MCV','HCV',
        'Cargo Van','Cargo/Crew'
    ));

-- 3. Seed: 123 vehicle models from Zippy India Vehicle Master 2026
--    Source: manufacturer websites, verified Aug 2026
DELETE FROM public.vehicle_models WHERE source_url IS NOT NULL;

INSERT INTO public.vehicle_models (
    brand, model, vehicle_type, body_type, capacity_tons,
    fuel_type, engine_cc, mileage, gvw_tons,
    cargo_length_m, cargo_width_m, cargo_height_m,
    overall_length_m, overall_width_m, overall_height_m,
    source_url, verification_status, notes
) VALUES
-- ===== TATA MOTORS =====
('Tata Motors','Ace Gold Petrol CX','Mini Truck',NULL,0.75,'Petrol',694,NULL,1.51,2.20,1.49,0.30,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Ace Gold CNG','Mini Truck',NULL,0.66,'CNG',694,NULL,1.63,2.20,1.49,0.30,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Ace Gold Diesel','Mini Truck',NULL,0.75,'Diesel',702,NULL,1.67,2.20,1.49,0.30,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Ace Gold CNG Plus','Mini Truck',NULL,0.61,'CNG',694,NULL,1.63,2.20,1.49,0.30,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Ace EV','Mini Truck',NULL,0.60,'Electric',NULL,NULL,1.84,2.16,1.47,0.30,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Ace Pro Bi-Fuel','Mini Truck',NULL,0.75,'CNG + Petrol',694,NULL,1.61,NULL,NULL,NULL,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Intra V10','Pickup',NULL,1.00,'Diesel',798,NULL,2.12,2.51,1.60,0.40,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Intra V20 Bi-Fuel','Pickup',NULL,1.00,'CNG + Petrol',1199,NULL,2.29,2.45,1.60,0.40,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Intra V30','Pickup',NULL,1.30,'Diesel',1496,NULL,2.57,2.70,1.61,0.40,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Intra V50','Pickup',NULL,1.50,'Diesel',1496,NULL,2.94,2.96,1.62,0.40,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','Intra V70','Pickup',NULL,2.00,'Diesel',1497,NULL,3.21,3.10,1.75,0.40,NULL,NULL,NULL,'https://smalltrucks.tatamotors.com','range_confirmed','Range confirmed; verify variant brochure'),
('Tata Motors','407 Gold SFC','LCV',NULL,NULL,'Diesel',NULL,NULL,4.45,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','510 SFC TT','LCV',NULL,NULL,'Diesel',NULL,NULL,5.30,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','610 SFC TT','LCV',NULL,NULL,'Diesel',NULL,NULL,6.25,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','710 SFC','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.7','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.9','MCV',NULL,NULL,'Diesel',NULL,NULL,8.75,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.11','MCV',NULL,NULL,'Diesel',NULL,NULL,11.28,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.12','MCV',NULL,NULL,'Diesel',NULL,NULL,11.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.14','MCV',NULL,NULL,'Diesel',NULL,NULL,14.01,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Ultra T.16','MCV',NULL,NULL,'Diesel',NULL,NULL,16.02,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 709','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 810','MCV',NULL,NULL,'Diesel',NULL,NULL,8.75,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 1112','MCV',NULL,NULL,'Diesel',NULL,NULL,11.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 1512','MCV',NULL,NULL,'Diesel',NULL,NULL,16.02,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 1612','MCV',NULL,NULL,'Diesel',NULL,NULL,16.02,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT 1916','HCV',NULL,NULL,'Diesel',NULL,NULL,18.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Signa 2821.T','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Signa 3118.T','HCV',NULL,NULL,'Diesel',NULL,NULL,31.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT/Signa 3521.T','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT/Signa 3523.T','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Signa 4221.T','HCV',NULL,NULL,'Diesel',NULL,NULL,42.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Signa 4825.T','HCV',NULL,NULL,'Diesel',NULL,NULL,47.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','LPT/Signa 4932.T','HCV',NULL,NULL,'Diesel',NULL,NULL,49.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
('Tata Motors','Signa 5521.S 4x2','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://trucks.tatamotors.com','model_confirmed','Model confirmed; variant specs pending'),
-- ===== ASHOK LEYLAND =====
('Ashok Leyland','Dost Lite','Mini Truck',NULL,1.25,'Diesel',1478,NULL,2.59,2.44,1.62,0.38,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Dost Strong','Mini Truck',NULL,1.35,'Diesel',1478,NULL,2.59,2.50,1.62,0.38,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Dost+','Mini Truck',NULL,1.50,'Diesel',1478,NULL,2.80,2.64,1.62,0.38,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Bada Dost i2','Pickup',NULL,1.43,'Diesel',1478,NULL,2.88,2.59,1.75,0.44,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Bada Dost i3+','Pickup',NULL,1.50,'Diesel',1478,NULL,2.99,2.95,1.75,0.44,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Bada Dost i4','Pickup',NULL,1.86,'Diesel',1478,NULL,3.49,2.95,1.75,0.49,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Bada Dost i5','Pickup',NULL,1.82,'Diesel',1478,NULL,3.49,2.95,1.75,0.49,NULL,NULL,NULL,'https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-i5/specification','specs_confirmed','Official specs confirmed'),
('Ashok Leyland','Bada Dost i6','Pickup',NULL,2.36,'Diesel',1478,NULL,4.10,3.25,1.75,0.49,NULL,NULL,NULL,'https://www.ashokleyland.com/in/lightvehicles/smallcommercialvechicles/bada-dost-i6/specification','specs_confirmed','CBC payload is 2.567 t; listed payload is FSD LX'),
('Ashok Leyland','Partner 4 Tyre','LCV',NULL,NULL,'Diesel',NULL,NULL,6.25,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','Partner 6 Tyre','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1115','MCV',NULL,NULL,'Diesel',NULL,NULL,11.12,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1215','MCV',NULL,NULL,'Diesel',NULL,NULL,12.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1415','MCV',NULL,NULL,'Diesel',NULL,NULL,14.05,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1615','MCV',NULL,NULL,'Diesel',NULL,NULL,16.10,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1815','MCV',NULL,NULL,'Diesel',NULL,NULL,17.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','ecomet STAR 1915','HCV',NULL,NULL,'Diesel',NULL,NULL,18.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 1920 4x2','HCV',NULL,NULL,'Diesel',NULL,NULL,19.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 2820 6x2','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 2820 6x4','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 3520 8x2','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 4220 10x2','HCV',NULL,NULL,'Diesel',NULL,NULL,42.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 4825 10x2','HCV',NULL,NULL,'Diesel',NULL,NULL,47.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
('Ashok Leyland','AVTR 5525 4x2 Tractor','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.ashokleyland.com/in/trucks','model_confirmed','Model confirmed; variant specs pending'),
-- ===== EICHER =====
('Eicher','Pro 2049','LCV',NULL,NULL,'Diesel',NULL,NULL,4.995,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2050','LCV',NULL,NULL,'Diesel',NULL,NULL,5.40,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2055','LCV',NULL,NULL,'Diesel',NULL,NULL,6.25,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2059','LCV',NULL,NULL,'Diesel',NULL,NULL,6.95,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2060','LCV',NULL,NULL,'Diesel',NULL,NULL,6.95,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2075','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2080XP','MCV',NULL,NULL,'Diesel',NULL,NULL,8.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2090','MCV',NULL,NULL,'Diesel',NULL,NULL,8.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2095XP','MCV',NULL,NULL,'Diesel',NULL,NULL,11.10,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2110XP','MCV',NULL,NULL,'Diesel',NULL,NULL,12.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2114XP','MCV',NULL,NULL,'Diesel',NULL,NULL,14.25,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3012','MCV',NULL,NULL,'Diesel',NULL,NULL,11.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3014','MCV',NULL,NULL,'Diesel',NULL,NULL,14.25,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3015','MCV',NULL,NULL,'Diesel',NULL,NULL,16.37,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3016','MCV',NULL,NULL,'Diesel',NULL,NULL,16.37,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3018','MCV',NULL,NULL,'Diesel',NULL,NULL,17.75,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3019','HCV',NULL,NULL,'Diesel',NULL,NULL,18.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 2055 EV','LCV',NULL,NULL,'Electric',NULL,NULL,5.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 3015 CNG','MCV',NULL,NULL,'CNG',NULL,NULL,16.37,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 6028','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 6035','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 6042','HCV',NULL,NULL,'Diesel',NULL,NULL,42.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 6048','HCV',NULL,NULL,'Diesel',NULL,NULL,47.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
('Eicher','Pro 6055 4x2 Tractor','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.eichertrucksandbuses.com/light-medium-duty-trucks/medium-duty','model_confirmed','Model confirmed; variant specs pending'),
-- ===== BHARATBENZ =====
('BharatBenz','1015R','MCV',NULL,NULL,'Diesel',NULL,NULL,10.60,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','1215R','MCV',NULL,NULL,'Diesel',NULL,NULL,11.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','1215RE','MCV',NULL,NULL,'Diesel',NULL,NULL,12.80,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','1415R','MCV',NULL,NULL,'Diesel',NULL,NULL,14.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','1617R','MCV',NULL,NULL,'Diesel',NULL,NULL,16.20,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','1917R','HCV',NULL,NULL,'Diesel',NULL,NULL,18.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','2826R','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','3528R','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','4228R','HCV',NULL,NULL,'Diesel',NULL,NULL,42.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','4828R','HCV',NULL,NULL,'Diesel',NULL,NULL,47.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','4832R','HCV',NULL,NULL,'Diesel',NULL,NULL,47.50,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks/hdt-r-specifications-4832r-95','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','5528TT Tractor','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','5532T Tractor','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','2823C Tipper','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
('BharatBenz','3528C Tipper','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.bharatbenz.com/trucks','model_confirmed','Model confirmed; variant specs pending'),
-- ===== MAHINDRA =====
('Mahindra','Jeeto Strong Diesel','Mini Truck',NULL,0.82,'Diesel',670,NULL,1.605,2.26,1.49,0.30,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Supro Profit Truck Mini','Mini Truck',NULL,0.90,'Diesel',909,NULL,1.80,2.28,1.54,0.33,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Supro Profit Truck Maxi','Mini Truck',NULL,1.05,'Diesel',909,NULL,2.13,2.50,1.54,0.33,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Bolero MaXX Pik-Up City 1.3','Pickup',NULL,1.30,'Diesel',2523,NULL,2.825,2.50,1.70,0.46,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Bolero MaXX Pik-Up HD 1.7','Pickup',NULL,1.70,'Diesel',2523,NULL,3.40,3.05,1.80,0.46,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Jayo','LCV',NULL,NULL,'Diesel',NULL,NULL,4.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Loadking Optimo','LCV',NULL,NULL,'Diesel',NULL,NULL,6.95,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 7','LCV',NULL,NULL,'Diesel',NULL,NULL,6.95,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 8','LCV',NULL,NULL,'Diesel',NULL,NULL,7.49,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 11','MCV',NULL,NULL,'Diesel',NULL,NULL,11.28,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 12','MCV',NULL,NULL,'Diesel',NULL,NULL,11.99,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 14','MCV',NULL,NULL,'Diesel',NULL,NULL,14.05,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 16','MCV',NULL,NULL,'Diesel',NULL,NULL,16.02,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Furio 17','MCV',NULL,NULL,'Diesel',NULL,NULL,17.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/light-commercial-vehicles/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Blazo X 28','HCV',NULL,NULL,'Diesel',NULL,NULL,28.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Blazo X 35','HCV',NULL,NULL,'Diesel',NULL,NULL,35.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Blazo X 42','HCV',NULL,NULL,'Diesel',NULL,NULL,42.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Blazo X 49','HCV',NULL,NULL,'Diesel',NULL,NULL,49.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
('Mahindra','Blazo X 55 Tractor','HCV',NULL,NULL,'Diesel',NULL,NULL,55.00,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.mahindratruckandbus.com/english/index.aspx','model_confirmed','Model confirmed; variant specs pending'),
-- ===== MARUTI SUZUKI =====
('Maruti Suzuki','Super Carry Petrol','Mini Truck',NULL,0.75,'Petrol',1196,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.marutisuzukicommercial.com/super-carry','model_confirmed','Payload confirmed; GVW/dimensions pending brochure'),
('Maruti Suzuki','Super Carry CNG','Mini Truck',NULL,0.63,'CNG + Petrol',1196,'23.24 km/kg',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.marutisuzukicommercial.com/super-carry-cng','specs_confirmed','Certified efficiency 23.24 km/kg; do not store as km/l'),
('Maruti Suzuki','Eeco Cargo','Cargo Van',NULL,0.92,'Petrol / CNG',1197,NULL,NULL,NULL,NULL,NULL,3.68,1.48,1.83,'https://www.marutisuzukicommercial.com/eeco-cargo','specs_confirmed','Overall dimensions 3.675 x 1.475 x 1.825 m'),
-- ===== FORCE MOTORS =====
('Force Motors','Trax Crew Van','Cargo/Crew',NULL,1.00,'Diesel',2596,NULL,2.99,NULL,NULL,NULL,5.12,1.82,2.03,'https://www.forcemotors.com/vehicles/trax-crew-van/','specs_confirmed','Official specs confirmed; Overall dimensions 5.120 x 1.818 x 2.027 m'),
('Force Motors','Traveller Delivery Van 3050WB','Cargo Van',NULL,1.54,'Diesel',2596,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.forcemotors.com/vehicles/traveller-dv-3050wb/','model_confirmed','Official payload/engine confirmed'),
('Force Motors','Traveller Delivery Van 3350WB','Cargo Van',NULL,1.50,'Diesel',2596,NULL,3.98,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.forcemotors.com/vehicles/traveller-dv-3350wb/','specs_confirmed','Official specs confirmed'),
('Force Motors','Traveller Delivery Van 4020WB','Cargo Van',NULL,1.69,'Diesel',2596,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'https://www.forcemotors.com/vehicles/traveller-dv-4020wb/','model_confirmed','Official payload/engine confirmed')
ON CONFLICT DO NOTHING;

-- 4. Index for fast matching by vehicle_type + capacity
CREATE INDEX IF NOT EXISTS idx_vehicle_models_type_capacity
    ON public.vehicle_models (vehicle_type, capacity_tons);

CREATE INDEX IF NOT EXISTS idx_vehicle_models_brand
    ON public.vehicle_models (brand);
