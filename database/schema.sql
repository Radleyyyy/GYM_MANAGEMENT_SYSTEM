-- DROP (children first)
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS expiration_records;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS memberships;
DROP TABLE IF EXISTS payment_methods;
DROP TABLE IF EXISTS membership_plans;
DROP TABLE IF EXISTS members;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

CREATE TABLE courses (
    course_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN
        ('Administrator','Gym Manager','Receptionist','Cashier','Trainer','Report Officer')),
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE members (
    member_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    member_number     TEXT NOT NULL UNIQUE,
    first_name        TEXT NOT NULL,
    last_name         TEXT NOT NULL,
    gender            TEXT NOT NULL CHECK (gender IN ('Male','Female','Other')),
    date_of_birth     TEXT NOT NULL,
    contact_number    TEXT NOT NULL UNIQUE,
    email             TEXT NOT NULL UNIQUE,
    address           TEXT,
    emergency_contact TEXT,
    course_id         INTEGER REFERENCES courses(course_id),
    registration_date TEXT NOT NULL DEFAULT (date('now')),
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived'))
);

CREATE TABLE membership_plans (
    plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_code       TEXT NOT NULL UNIQUE,
    plan_name       TEXT NOT NULL,
    duration_months INTEGER NOT NULL CHECK (duration_months > 0),
    price           REAL NOT NULL CHECK (price >= 0),
    description     TEXT,
    benefits        TEXT,
    access_type     TEXT NOT NULL DEFAULT 'Full Access',
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived'))
);

CREATE TABLE memberships (
    membership_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      INTEGER NOT NULL REFERENCES members(member_id),
    plan_id        INTEGER NOT NULL REFERENCES membership_plans(plan_id),
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    membership_fee REAL NOT NULL CHECK (membership_fee >= 0),
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
        ('pending','active','expired','suspended','cancelled')),
    is_renewal     INTEGER NOT NULL DEFAULT 0 CHECK (is_renewal IN (0,1)),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date > start_date)
);
-- A member can have only one active membership at a time
CREATE UNIQUE INDEX ux_one_active_membership
    ON memberships(member_id) WHERE status = 'active';

CREATE TABLE payment_methods (
    method_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    method_name TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive'))
);

CREATE TABLE payments (
    payment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_number  TEXT NOT NULL UNIQUE,
    member_id       INTEGER NOT NULL REFERENCES members(member_id),
    membership_id   INTEGER NOT NULL REFERENCES memberships(membership_id),
    method_id       INTEGER NOT NULL REFERENCES payment_methods(method_id),
    received_by     INTEGER REFERENCES users(user_id),
    payment_date    TEXT NOT NULL DEFAULT (date('now')),
    plan_price      REAL NOT NULL CHECK (plan_price >= 0),
    discount        REAL NOT NULL DEFAULT 0 CHECK (discount >= 0),
    additional_charges REAL NOT NULL DEFAULT 0 CHECK (additional_charges >= 0),
    amount_due      REAL NOT NULL CHECK (amount_due >= 0),
    amount_paid     REAL NOT NULL CHECK (amount_paid >= 0),
    balance         REAL NOT NULL CHECK (balance >= 0),
    payment_status  TEXT NOT NULL CHECK (payment_status IN ('unpaid','partial','paid')),
    CHECK (amount_paid <= amount_due)
);

CREATE TABLE attendance (
    attendance_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id        INTEGER NOT NULL REFERENCES members(member_id),
    membership_id    INTEGER NOT NULL REFERENCES memberships(membership_id),
    check_in_time    TEXT NOT NULL,
    check_out_time   TEXT,
    duration_minutes INTEGER CHECK (duration_minutes >= 0),
    CHECK (check_out_time IS NULL OR check_out_time >= check_in_time)
);
-- A member can have only one open (not checked-out) visit
CREATE UNIQUE INDEX ux_one_open_visit
    ON attendance(member_id) WHERE check_out_time IS NULL;

CREATE TABLE expiration_records (
    expiration_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id   INTEGER NOT NULL UNIQUE REFERENCES memberships(membership_id),
    expiration_date TEXT NOT NULL,
    expiry_status   TEXT NOT NULL CHECK (expiry_status IN ('active','expiring','expired')),
    last_checked    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notifications (
    notification_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id         INTEGER NOT NULL REFERENCES members(member_id),
    membership_id     INTEGER NOT NULL REFERENCES memberships(membership_id),
    notification_type TEXT NOT NULL CHECK (notification_type IN
        ('30_days','7_days','1_day','expired')),
    message           TEXT NOT NULL,
    is_read           INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0,1)),
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (membership_id, notification_type)
);

-- ===== SAMPLE DATA =====
INSERT INTO payment_methods (method_name) VALUES ('Cash'),('Bank Transfer'),('E-wallet'),('Card');
INSERT INTO courses (course_name) VALUES ('BSIT'),('BSBA'),('BSED'),('BSN'),('BEED');

INSERT INTO membership_plans (plan_code, plan_name, duration_months, price, description, benefits) VALUES
('MON','Monthly',1,1000,'1-month access','Gym floor access'),
('QTR','Quarterly',3,2700,'3-month access','Gym floor + 1 free session'),
('SEM','Semi-Annual',6,5000,'6-month access','Gym floor + 3 free sessions'),
('ANN','Annual',12,9000,'12-month access','Gym floor + 6 free sessions + locker');

INSERT INTO members (member_number, first_name, last_name, gender, date_of_birth, contact_number, email, address, emergency_contact) VALUES
('GYM-0001','Juan','Dela Cruz','Male','2000-05-14','09171234567','juan@example.com','Bayombong, Nueva Vizcaya','Maria Dela Cruz 09181234567'),
('GYM-0002','Maria','Santos','Female','1998-11-02','09172345678','maria@example.com','Solano, Nueva Vizcaya','Jose Santos 09182345678'),
('GYM-0003','Pedro','Reyes','Male','1995-03-21','09173456789','pedro@example.com','Bambang, Nueva Vizcaya','Ana Reyes 09183456789');
UPDATE members SET course_id = 1 WHERE member_id = 1;
UPDATE members SET course_id = 2 WHERE member_id = 2;
UPDATE members SET course_id = 3 WHERE member_id = 3;

INSERT INTO memberships (member_id, plan_id, start_date, end_date, membership_fee, status) VALUES
(1,1,date('now','-10 days'),date('now','+20 days'),1000,'active'),
(2,2,date('now','-100 days'),date('now','-10 days'),2700,'expired'),
(3,1,date('now','-25 days'),date('now','+5 days'),1000,'active');

INSERT INTO payments (payment_number, member_id, membership_id, method_id, plan_price, amount_due, amount_paid, balance, payment_status) VALUES
('PAY-0001',1,1,1,1000,1000,1000,0,'paid'),
('PAY-0002',2,2,3,2700,2700,2700,0,'paid'),
('PAY-0003',3,3,1,1000,1000,500,500,'partial');

INSERT INTO attendance (member_id, membership_id, check_in_time, check_out_time, duration_minutes) VALUES
(1,1,datetime('now','-1 day','-2 hours'),datetime('now','-1 day'),120),
(1,1,datetime('now','-1 hours'),NULL,NULL),
(3,3,datetime('now','-2 days','-90 minutes'),datetime('now','-2 days'),90);

INSERT INTO expiration_records (membership_id, expiration_date, expiry_status) VALUES
(1,date('now','+20 days'),'active'),
(2,date('now','-10 days'),'expired'),
(3,date('now','+5 days'),'expiring');

INSERT INTO notifications (member_id, membership_id, notification_type, message) VALUES
(3,3,'7_days','Reminder: Your gym membership will expire in 7 days. Please renew your membership to continue accessing the gym.');