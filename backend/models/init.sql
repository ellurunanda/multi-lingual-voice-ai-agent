-- Voice AI Clinical Appointment System - Database Initialization
-- This script seeds initial data for doctors and schedules

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Insert sample doctors
INSERT INTO doctors (id, name, specialization, phone, email, hospital, consultation_duration, languages_spoken, is_available)
VALUES
  (uuid_generate_v4()::text, 'Dr. Rajesh Sharma', 'Cardiologist', '+91-9876543210', 'rajesh.sharma@apollo.com', 'Apollo Hospital', 30, '["en", "hi"]', true),
  (uuid_generate_v4()::text, 'Dr. Priya Nair', 'Dermatologist', '+91-9876543211', 'priya.nair@apollo.com', 'Apollo Hospital', 20, '["en", "ta", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Suresh Kumar', 'Orthopedist', '+91-9876543212', 'suresh.kumar@fortis.com', 'Fortis Hospital', 30, '["en", "hi", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Anitha Reddy', 'Neurologist', '+91-9876543213', 'anitha.reddy@care.com', 'Care Hospital', 45, '["en", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Mohammed Ali', 'General Physician', '+91-9876543214', 'ali@maxhospital.com', 'Max Hospital', 15, '["en", "hi", "ta", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Lakshmi Devi', 'Gynecologist', '+91-9876543215', 'lakshmi@rainbow.com', 'Rainbow Hospital', 30, '["en", "ta", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Venkat Rao', 'Pediatrician', '+91-9876543216', 'venkat@childrens.com', 'Childrens Hospital', 20, '["en", "te"]', true),
  (uuid_generate_v4()::text, 'Dr. Kavitha Menon', 'Ophthalmologist', '+91-9876543217', 'kavitha@eye.com', 'Eye Care Center', 20, '["en", "ta"]', true)
ON CONFLICT DO NOTHING;

-- Insert sample patients
INSERT INTO patients (id, name, phone, email, preferred_language, preferred_hospital, medical_history)
VALUES
  (uuid_generate_v4()::text, 'Arjun Patel', '+91-9000000001', 'arjun@email.com', 'en', 'Apollo Hospital', '{"conditions": ["hypertension"], "allergies": ["penicillin"]}'),
  (uuid_generate_v4()::text, 'Meera Krishnan', '+91-9000000002', 'meera@email.com', 'ta', 'Apollo Hospital', '{"conditions": [], "allergies": []}'),
  (uuid_generate_v4()::text, 'Ravi Shankar', '+91-9000000003', 'ravi@email.com', 'hi', 'Fortis Hospital', '{"conditions": ["diabetes"], "allergies": []}'),
  (uuid_generate_v4()::text, 'Sunita Reddy', '+91-9000000004', 'sunita@email.com', 'te', 'Care Hospital', '{"conditions": [], "allergies": ["sulfa"]}')
ON CONFLICT DO NOTHING;