"""Create standalone sandbox datasets (25 total, 5 per database type)."""

from django.core.management.base import BaseCommand
from courses.models import Dataset


DATASETS = [
    # ── SQLite (5) ──────────────────────────────────────────────
    {
        'name': 'E-commerce Store',
        'database_type': 'sqlite',
        'description': 'Online store with products, customers, and orders.',
        'schema_sql': (
            "CREATE TABLE customers (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  email TEXT UNIQUE NOT NULL,\n"
            "  city TEXT\n"
            ");\n\n"
            "CREATE TABLE products (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  price DECIMAL(10,2) NOT NULL,\n"
            "  category TEXT,\n"
            "  stock INTEGER DEFAULT 0\n"
            ");\n\n"
            "CREATE TABLE orders (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  customer_id INTEGER REFERENCES customers(id),\n"
            "  order_date DATE NOT NULL,\n"
            "  total DECIMAL(10,2)\n"
            ");\n\n"
            "CREATE TABLE order_items (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  order_id INTEGER REFERENCES orders(id),\n"
            "  product_id INTEGER REFERENCES products(id),\n"
            "  quantity INTEGER NOT NULL,\n"
            "  price DECIMAL(10,2) NOT NULL\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO customers (name, email, city) VALUES\n"
            "  ('Alice Johnson', 'alice@example.com', 'New York'),\n"
            "  ('Bob Smith', 'bob@example.com', 'Los Angeles'),\n"
            "  ('Carol White', 'carol@example.com', 'Chicago'),\n"
            "  ('David Brown', 'david@example.com', 'Houston'),\n"
            "  ('Eve Davis', 'eve@example.com', 'Phoenix');\n\n"
            "INSERT INTO products (name, price, category, stock) VALUES\n"
            "  ('Laptop', 999.99, 'Electronics', 50),\n"
            "  ('Headphones', 79.99, 'Electronics', 200),\n"
            "  ('Desk Chair', 249.99, 'Furniture', 30),\n"
            "  ('Notebook', 12.99, 'Stationery', 500),\n"
            "  ('Backpack', 59.99, 'Accessories', 100);\n\n"
            "INSERT INTO orders (customer_id, order_date, total) VALUES\n"
            "  (1, '2025-01-15', 1079.98),\n"
            "  (2, '2025-01-16', 79.99),\n"
            "  (3, '2025-01-17', 262.98),\n"
            "  (1, '2025-01-20', 59.99),\n"
            "  (4, '2025-01-22', 999.99);\n\n"
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES\n"
            "  (1, 1, 1, 999.99),\n"
            "  (1, 2, 1, 79.99),\n"
            "  (2, 2, 1, 79.99),\n"
            "  (3, 3, 1, 249.99),\n"
            "  (3, 4, 1, 12.99),\n"
            "  (4, 5, 1, 59.99),\n"
            "  (5, 1, 1, 999.99);"
        ),
    },
    {
        'name': 'Library System',
        'database_type': 'sqlite',
        'description': 'Library with books, authors, members, and loans.',
        'schema_sql': (
            "CREATE TABLE authors (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  country TEXT\n"
            ");\n\n"
            "CREATE TABLE books (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  title TEXT NOT NULL,\n"
            "  author_id INTEGER REFERENCES authors(id),\n"
            "  genre TEXT,\n"
            "  published_year INTEGER,\n"
            "  isbn TEXT UNIQUE\n"
            ");\n\n"
            "CREATE TABLE members (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  email TEXT UNIQUE,\n"
            "  join_date DATE\n"
            ");\n\n"
            "CREATE TABLE loans (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  book_id INTEGER REFERENCES books(id),\n"
            "  member_id INTEGER REFERENCES members(id),\n"
            "  loan_date DATE NOT NULL,\n"
            "  return_date DATE\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO authors (name, country) VALUES\n"
            "  ('George Orwell', 'UK'),\n"
            "  ('Harper Lee', 'USA'),\n"
            "  ('Gabriel Garcia Marquez', 'Colombia'),\n"
            "  ('Jane Austen', 'UK');\n\n"
            "INSERT INTO books (title, author_id, genre, published_year, isbn) VALUES\n"
            "  ('1984', 1, 'Dystopian', 1949, '978-0451524935'),\n"
            "  ('Animal Farm', 1, 'Satire', 1945, '978-0451526342'),\n"
            "  ('To Kill a Mockingbird', 2, 'Fiction', 1960, '978-0061120084'),\n"
            "  ('One Hundred Years of Solitude', 3, 'Magical Realism', 1967, '978-0060883287'),\n"
            "  ('Pride and Prejudice', 4, 'Romance', 1813, '978-0141439518');\n\n"
            "INSERT INTO members (name, email, join_date) VALUES\n"
            "  ('John Doe', 'john@library.com', '2024-01-10'),\n"
            "  ('Jane Roe', 'jane@library.com', '2024-03-15'),\n"
            "  ('Sam Park', 'sam@library.com', '2024-06-01');\n\n"
            "INSERT INTO loans (book_id, member_id, loan_date, return_date) VALUES\n"
            "  (1, 1, '2025-01-01', '2025-01-15'),\n"
            "  (3, 2, '2025-01-05', NULL),\n"
            "  (5, 1, '2025-01-10', '2025-01-20'),\n"
            "  (2, 3, '2025-01-12', NULL);"
        ),
    },
    {
        'name': 'School Database',
        'database_type': 'sqlite',
        'description': 'School with students, teachers, courses, and grades.',
        'schema_sql': (
            "CREATE TABLE teachers (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  subject TEXT,\n"
            "  hire_date DATE\n"
            ");\n\n"
            "CREATE TABLE students (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  grade_level INTEGER,\n"
            "  enrollment_date DATE\n"
            ");\n\n"
            "CREATE TABLE classes (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  teacher_id INTEGER REFERENCES teachers(id),\n"
            "  room TEXT\n"
            ");\n\n"
            "CREATE TABLE grades (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  student_id INTEGER REFERENCES students(id),\n"
            "  class_id INTEGER REFERENCES classes(id),\n"
            "  score DECIMAL(5,2),\n"
            "  semester TEXT\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO teachers (name, subject, hire_date) VALUES\n"
            "  ('Ms. Thompson', 'Mathematics', '2015-08-20'),\n"
            "  ('Mr. Garcia', 'Science', '2018-01-10'),\n"
            "  ('Mrs. Patel', 'English', '2020-09-01');\n\n"
            "INSERT INTO students (name, grade_level, enrollment_date) VALUES\n"
            "  ('Emma Wilson', 10, '2023-09-01'),\n"
            "  ('Liam Chen', 10, '2023-09-01'),\n"
            "  ('Olivia Kim', 11, '2022-09-01'),\n"
            "  ('Noah Martinez', 11, '2022-09-01'),\n"
            "  ('Ava Robinson', 12, '2021-09-01');\n\n"
            "INSERT INTO classes (name, teacher_id, room) VALUES\n"
            "  ('Algebra II', 1, 'Room 201'),\n"
            "  ('Biology', 2, 'Lab 3'),\n"
            "  ('English Lit', 3, 'Room 105');\n\n"
            "INSERT INTO grades (student_id, class_id, score, semester) VALUES\n"
            "  (1, 1, 92.5, 'Fall 2024'),\n"
            "  (1, 2, 88.0, 'Fall 2024'),\n"
            "  (2, 1, 78.5, 'Fall 2024'),\n"
            "  (3, 3, 95.0, 'Fall 2024'),\n"
            "  (4, 2, 85.5, 'Fall 2024'),\n"
            "  (5, 3, 91.0, 'Fall 2024');"
        ),
    },
    {
        'name': 'Hospital Records',
        'database_type': 'sqlite',
        'description': 'Hospital with patients, doctors, appointments, and prescriptions.',
        'schema_sql': (
            "CREATE TABLE doctors (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  specialty TEXT,\n"
            "  phone TEXT\n"
            ");\n\n"
            "CREATE TABLE patients (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  date_of_birth DATE,\n"
            "  blood_type TEXT\n"
            ");\n\n"
            "CREATE TABLE appointments (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  patient_id INTEGER REFERENCES patients(id),\n"
            "  doctor_id INTEGER REFERENCES doctors(id),\n"
            "  appointment_date DATETIME,\n"
            "  diagnosis TEXT\n"
            ");\n\n"
            "CREATE TABLE prescriptions (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  appointment_id INTEGER REFERENCES appointments(id),\n"
            "  medication TEXT NOT NULL,\n"
            "  dosage TEXT,\n"
            "  duration_days INTEGER\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO doctors (name, specialty, phone) VALUES\n"
            "  ('Dr. Sarah Lee', 'Cardiology', '555-0101'),\n"
            "  ('Dr. James Wilson', 'Orthopedics', '555-0102'),\n"
            "  ('Dr. Maria Santos', 'Pediatrics', '555-0103');\n\n"
            "INSERT INTO patients (name, date_of_birth, blood_type) VALUES\n"
            "  ('Tom Hardy', '1985-06-15', 'A+'),\n"
            "  ('Lisa Ray', '1990-03-22', 'O-'),\n"
            "  ('Mike Chang', '1978-11-08', 'B+'),\n"
            "  ('Anna Bell', '2010-07-30', 'AB+');\n\n"
            "INSERT INTO appointments (patient_id, doctor_id, appointment_date, diagnosis) VALUES\n"
            "  (1, 1, '2025-01-10 09:00', 'Hypertension'),\n"
            "  (2, 2, '2025-01-11 10:30', 'Sprained ankle'),\n"
            "  (3, 1, '2025-01-12 14:00', 'Arrhythmia'),\n"
            "  (4, 3, '2025-01-13 11:00', 'Common cold');\n\n"
            "INSERT INTO prescriptions (appointment_id, medication, dosage, duration_days) VALUES\n"
            "  (1, 'Lisinopril', '10mg daily', 30),\n"
            "  (2, 'Ibuprofen', '400mg twice daily', 7),\n"
            "  (3, 'Metoprolol', '25mg daily', 90),\n"
            "  (4, 'Amoxicillin', '250mg three times daily', 10);"
        ),
    },
    {
        'name': 'Music Collection',
        'database_type': 'sqlite',
        'description': 'Music database with artists, albums, songs, and playlists.',
        'schema_sql': (
            "CREATE TABLE artists (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  genre TEXT,\n"
            "  country TEXT\n"
            ");\n\n"
            "CREATE TABLE albums (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  title TEXT NOT NULL,\n"
            "  artist_id INTEGER REFERENCES artists(id),\n"
            "  release_year INTEGER,\n"
            "  tracks INTEGER\n"
            ");\n\n"
            "CREATE TABLE songs (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  title TEXT NOT NULL,\n"
            "  album_id INTEGER REFERENCES albums(id),\n"
            "  duration_seconds INTEGER,\n"
            "  track_number INTEGER\n"
            ");\n\n"
            "CREATE TABLE playlists (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL,\n"
            "  song_id INTEGER REFERENCES songs(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO artists (name, genre, country) VALUES\n"
            "  ('The Beatles', 'Rock', 'UK'),\n"
            "  ('Miles Davis', 'Jazz', 'USA'),\n"
            "  ('Daft Punk', 'Electronic', 'France');\n\n"
            "INSERT INTO albums (title, artist_id, release_year, tracks) VALUES\n"
            "  ('Abbey Road', 1, 1969, 17),\n"
            "  ('Kind of Blue', 2, 1959, 5),\n"
            "  ('Random Access Memories', 3, 2013, 13);\n\n"
            "INSERT INTO songs (title, album_id, duration_seconds, track_number) VALUES\n"
            "  ('Come Together', 1, 259, 1),\n"
            "  ('Here Comes The Sun', 1, 185, 7),\n"
            "  ('So What', 2, 562, 1),\n"
            "  ('Blue in Green', 2, 327, 3),\n"
            "  ('Get Lucky', 3, 369, 8),\n"
            "  ('Instant Crush', 3, 337, 5);\n\n"
            "INSERT INTO playlists (name, song_id) VALUES\n"
            "  ('Chill Vibes', 4),\n"
            "  ('Chill Vibes', 2),\n"
            "  ('Party Mix', 5),\n"
            "  ('Party Mix', 1),\n"
            "  ('Classics', 3);"
        ),
    },

    # ── PostgreSQL (5) ──────────────────────────────────────────
    {
        'name': 'HR System',
        'database_type': 'postgresql',
        'description': 'Human resources with employees, departments, and salaries.',
        'schema_sql': (
            "CREATE TABLE departments (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  location VARCHAR(100)\n"
            ");\n\n"
            "CREATE TABLE employees (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  email VARCHAR(255) UNIQUE,\n"
            "  department_id INTEGER REFERENCES departments(id),\n"
            "  hire_date DATE,\n"
            "  salary NUMERIC(10,2)\n"
            ");\n\n"
            "CREATE TABLE salary_history (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  employee_id INTEGER REFERENCES employees(id),\n"
            "  old_salary NUMERIC(10,2),\n"
            "  new_salary NUMERIC(10,2),\n"
            "  change_date DATE\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO departments (name, location) VALUES\n"
            "  ('Engineering', 'Floor 3'),\n"
            "  ('Marketing', 'Floor 2'),\n"
            "  ('HR', 'Floor 1'),\n"
            "  ('Sales', 'Floor 2');\n\n"
            "INSERT INTO employees (name, email, department_id, hire_date, salary) VALUES\n"
            "  ('Alice Martin', 'alice@company.com', 1, '2020-03-15', 95000),\n"
            "  ('Bob Turner', 'bob@company.com', 1, '2021-06-01', 85000),\n"
            "  ('Carol Diaz', 'carol@company.com', 2, '2019-01-20', 72000),\n"
            "  ('Dan Foster', 'dan@company.com', 3, '2022-09-10', 65000),\n"
            "  ('Eva Novak', 'eva@company.com', 4, '2023-04-01', 70000),\n"
            "  ('Frank Wu', 'frank@company.com', 1, '2018-07-15', 110000);\n\n"
            "INSERT INTO salary_history (employee_id, old_salary, new_salary, change_date) VALUES\n"
            "  (1, 80000, 95000, '2023-01-01'),\n"
            "  (6, 95000, 110000, '2023-01-01'),\n"
            "  (3, 65000, 72000, '2024-01-01');"
        ),
    },
    {
        'name': 'Banking Database',
        'database_type': 'postgresql',
        'description': 'Banking system with accounts, customers, and transactions.',
        'schema_sql': (
            "CREATE TABLE customers (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  email VARCHAR(255) UNIQUE,\n"
            "  phone VARCHAR(20)\n"
            ");\n\n"
            "CREATE TABLE accounts (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  customer_id INTEGER REFERENCES customers(id),\n"
            "  account_type VARCHAR(20) NOT NULL,\n"
            "  balance NUMERIC(12,2) DEFAULT 0,\n"
            "  opened_date DATE\n"
            ");\n\n"
            "CREATE TABLE transactions (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  account_id INTEGER REFERENCES accounts(id),\n"
            "  amount NUMERIC(12,2) NOT NULL,\n"
            "  transaction_type VARCHAR(20),\n"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO customers (name, email, phone) VALUES\n"
            "  ('John Banks', 'john@bank.com', '555-1001'),\n"
            "  ('Mary Gold', 'mary@bank.com', '555-1002'),\n"
            "  ('Peter Cash', 'peter@bank.com', '555-1003');\n\n"
            "INSERT INTO accounts (customer_id, account_type, balance, opened_date) VALUES\n"
            "  (1, 'checking', 5200.50, '2022-01-15'),\n"
            "  (1, 'savings', 15000.00, '2022-01-15'),\n"
            "  (2, 'checking', 3400.75, '2023-06-01'),\n"
            "  (3, 'savings', 28000.00, '2021-03-20');\n\n"
            "INSERT INTO transactions (account_id, amount, transaction_type) VALUES\n"
            "  (1, -500.00, 'withdrawal'),\n"
            "  (1, 2300.00, 'deposit'),\n"
            "  (2, 1000.00, 'deposit'),\n"
            "  (3, -200.00, 'withdrawal'),\n"
            "  (4, 5000.00, 'deposit'),\n"
            "  (3, 1500.00, 'deposit');"
        ),
    },
    {
        'name': 'Real Estate',
        'database_type': 'postgresql',
        'description': 'Real estate with properties, agents, and sales.',
        'schema_sql': (
            "CREATE TABLE agents (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  phone VARCHAR(20),\n"
            "  license_number VARCHAR(50)\n"
            ");\n\n"
            "CREATE TABLE properties (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  address VARCHAR(255) NOT NULL,\n"
            "  city VARCHAR(100),\n"
            "  property_type VARCHAR(50),\n"
            "  bedrooms INTEGER,\n"
            "  price NUMERIC(12,2),\n"
            "  listed_date DATE\n"
            ");\n\n"
            "CREATE TABLE sales (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  property_id INTEGER REFERENCES properties(id),\n"
            "  agent_id INTEGER REFERENCES agents(id),\n"
            "  sale_price NUMERIC(12,2),\n"
            "  sale_date DATE\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO agents (name, phone, license_number) VALUES\n"
            "  ('Rachel Green', '555-2001', 'RE-1001'),\n"
            "  ('Ross Geller', '555-2002', 'RE-1002');\n\n"
            "INSERT INTO properties (address, city, property_type, bedrooms, price, listed_date) VALUES\n"
            "  ('123 Maple St', 'Springfield', 'House', 3, 350000, '2024-06-01'),\n"
            "  ('456 Oak Ave', 'Springfield', 'Condo', 2, 220000, '2024-07-15'),\n"
            "  ('789 Pine Rd', 'Shelbyville', 'House', 4, 480000, '2024-08-01'),\n"
            "  ('101 Elm Dr', 'Springfield', 'Apartment', 1, 150000, '2024-09-10'),\n"
            "  ('202 Birch Ln', 'Shelbyville', 'House', 5, 620000, '2024-10-01');\n\n"
            "INSERT INTO sales (property_id, agent_id, sale_price, sale_date) VALUES\n"
            "  (1, 1, 340000, '2024-08-15'),\n"
            "  (3, 2, 465000, '2024-10-20'),\n"
            "  (4, 1, 148000, '2024-11-05');"
        ),
    },
    {
        'name': 'Social Network',
        'database_type': 'postgresql',
        'description': 'Social network with users, posts, comments, and friendships.',
        'schema_sql': (
            "CREATE TABLE users (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  username VARCHAR(50) UNIQUE NOT NULL,\n"
            "  display_name VARCHAR(100),\n"
            "  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
            ");\n\n"
            "CREATE TABLE posts (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  user_id INTEGER REFERENCES users(id),\n"
            "  content TEXT NOT NULL,\n"
            "  likes INTEGER DEFAULT 0,\n"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
            ");\n\n"
            "CREATE TABLE comments (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  post_id INTEGER REFERENCES posts(id),\n"
            "  user_id INTEGER REFERENCES users(id),\n"
            "  content TEXT NOT NULL,\n"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
            ");\n\n"
            "CREATE TABLE friendships (\n"
            "  user_id INTEGER REFERENCES users(id),\n"
            "  friend_id INTEGER REFERENCES users(id),\n"
            "  PRIMARY KEY (user_id, friend_id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO users (username, display_name) VALUES\n"
            "  ('alice_w', 'Alice Walker'),\n"
            "  ('bob_m', 'Bob Miller'),\n"
            "  ('carol_j', 'Carol Jones'),\n"
            "  ('dave_k', 'Dave Kim');\n\n"
            "INSERT INTO posts (user_id, content, likes) VALUES\n"
            "  (1, 'Just learned PostgreSQL joins!', 12),\n"
            "  (2, 'Beautiful sunset today', 25),\n"
            "  (3, 'Working on a new project', 8),\n"
            "  (1, 'Coffee and coding', 15);\n\n"
            "INSERT INTO comments (post_id, user_id, content) VALUES\n"
            "  (1, 2, 'Nice! Keep it up!'),\n"
            "  (1, 3, 'SQL is awesome'),\n"
            "  (2, 1, 'Gorgeous!'),\n"
            "  (3, 4, 'What stack are you using?');\n\n"
            "INSERT INTO friendships (user_id, friend_id) VALUES\n"
            "  (1, 2), (2, 1),\n"
            "  (1, 3), (3, 1),\n"
            "  (2, 4), (4, 2);"
        ),
    },
    {
        'name': 'Logistics Tracker',
        'database_type': 'postgresql',
        'description': 'Logistics with warehouses, shipments, and inventory.',
        'schema_sql': (
            "CREATE TABLE warehouses (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  city VARCHAR(100),\n"
            "  capacity INTEGER\n"
            ");\n\n"
            "CREATE TABLE products (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  sku VARCHAR(50) UNIQUE,\n"
            "  weight_kg NUMERIC(8,2)\n"
            ");\n\n"
            "CREATE TABLE inventory (\n"
            "  warehouse_id INTEGER REFERENCES warehouses(id),\n"
            "  product_id INTEGER REFERENCES products(id),\n"
            "  quantity INTEGER DEFAULT 0,\n"
            "  PRIMARY KEY (warehouse_id, product_id)\n"
            ");\n\n"
            "CREATE TABLE shipments (\n"
            "  id SERIAL PRIMARY KEY,\n"
            "  from_warehouse INTEGER REFERENCES warehouses(id),\n"
            "  to_warehouse INTEGER REFERENCES warehouses(id),\n"
            "  product_id INTEGER REFERENCES products(id),\n"
            "  quantity INTEGER,\n"
            "  shipped_at TIMESTAMP,\n"
            "  status VARCHAR(20) DEFAULT 'pending'\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO warehouses (name, city, capacity) VALUES\n"
            "  ('West Hub', 'Los Angeles', 10000),\n"
            "  ('East Hub', 'New York', 8000),\n"
            "  ('Central', 'Chicago', 12000);\n\n"
            "INSERT INTO products (name, sku, weight_kg) VALUES\n"
            "  ('Widget A', 'WGT-001', 0.5),\n"
            "  ('Widget B', 'WGT-002', 1.2),\n"
            "  ('Gadget X', 'GDG-001', 2.8),\n"
            "  ('Gadget Y', 'GDG-002', 0.3);\n\n"
            "INSERT INTO inventory (warehouse_id, product_id, quantity) VALUES\n"
            "  (1, 1, 500), (1, 2, 300),\n"
            "  (2, 1, 200), (2, 3, 150),\n"
            "  (3, 2, 400), (3, 4, 600);\n\n"
            "INSERT INTO shipments (from_warehouse, to_warehouse, product_id, quantity, shipped_at, status) VALUES\n"
            "  (1, 2, 1, 100, '2025-01-10 08:00', 'delivered'),\n"
            "  (3, 1, 2, 50, '2025-01-12 10:00', 'in_transit'),\n"
            "  (2, 3, 3, 75, '2025-01-14 14:00', 'pending');"
        ),
    },

    # ── MariaDB (5) ─────────────────────────────────────────────
    {
        'name': 'Restaurant Manager',
        'database_type': 'mariadb',
        'description': 'Restaurant with menus, orders, tables, and staff.',
        'schema_sql': (
            "CREATE TABLE staff (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  role VARCHAR(50),\n"
            "  hourly_rate DECIMAL(6,2)\n"
            ");\n\n"
            "CREATE TABLE tables_info (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  table_number INT UNIQUE,\n"
            "  seats INT,\n"
            "  section VARCHAR(50)\n"
            ");\n\n"
            "CREATE TABLE menu_items (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  category VARCHAR(50),\n"
            "  price DECIMAL(8,2)\n"
            ");\n\n"
            "CREATE TABLE orders (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  table_id INT,\n"
            "  staff_id INT,\n"
            "  order_time DATETIME,\n"
            "  total DECIMAL(10,2),\n"
            "  FOREIGN KEY (table_id) REFERENCES tables_info(id),\n"
            "  FOREIGN KEY (staff_id) REFERENCES staff(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO staff (name, role, hourly_rate) VALUES\n"
            "  ('Chef Marco', 'chef', 28.50),\n"
            "  ('Waiter Amy', 'waiter', 15.00),\n"
            "  ('Waiter Ben', 'waiter', 15.00);\n\n"
            "INSERT INTO tables_info (table_number, seats, section) VALUES\n"
            "  (1, 2, 'window'), (2, 4, 'center'),\n"
            "  (3, 6, 'patio'), (4, 2, 'bar');\n\n"
            "INSERT INTO menu_items (name, category, price) VALUES\n"
            "  ('Margherita Pizza', 'main', 14.99),\n"
            "  ('Caesar Salad', 'starter', 9.99),\n"
            "  ('Tiramisu', 'dessert', 8.99),\n"
            "  ('Spaghetti Carbonara', 'main', 16.99),\n"
            "  ('Espresso', 'drink', 3.99);\n\n"
            "INSERT INTO orders (table_id, staff_id, order_time, total) VALUES\n"
            "  (1, 2, '2025-01-15 12:30:00', 24.98),\n"
            "  (2, 3, '2025-01-15 13:00:00', 41.97),\n"
            "  (3, 2, '2025-01-15 19:00:00', 53.96);"
        ),
    },
    {
        'name': 'Gym Membership',
        'database_type': 'mariadb',
        'description': 'Gym with members, trainers, classes, and attendance.',
        'schema_sql': (
            "CREATE TABLE trainers (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  specialty VARCHAR(100),\n"
            "  certified BOOLEAN DEFAULT TRUE\n"
            ");\n\n"
            "CREATE TABLE members (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  email VARCHAR(255) UNIQUE,\n"
            "  membership_type VARCHAR(50),\n"
            "  join_date DATE\n"
            ");\n\n"
            "CREATE TABLE classes (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  trainer_id INT,\n"
            "  day_of_week VARCHAR(20),\n"
            "  start_time TIME,\n"
            "  max_capacity INT,\n"
            "  FOREIGN KEY (trainer_id) REFERENCES trainers(id)\n"
            ");\n\n"
            "CREATE TABLE attendance (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  member_id INT,\n"
            "  class_id INT,\n"
            "  attended_date DATE,\n"
            "  FOREIGN KEY (member_id) REFERENCES members(id),\n"
            "  FOREIGN KEY (class_id) REFERENCES classes(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO trainers (name, specialty, certified) VALUES\n"
            "  ('Jake Power', 'Weightlifting', TRUE),\n"
            "  ('Luna Flex', 'Yoga', TRUE),\n"
            "  ('Max Sprint', 'Cardio', TRUE);\n\n"
            "INSERT INTO members (name, email, membership_type, join_date) VALUES\n"
            "  ('Anna Fit', 'anna@gym.com', 'premium', '2024-01-10'),\n"
            "  ('Brian Strong', 'brian@gym.com', 'basic', '2024-03-15'),\n"
            "  ('Carla Run', 'carla@gym.com', 'premium', '2024-06-01'),\n"
            "  ('Derek Lift', 'derek@gym.com', 'basic', '2024-08-20');\n\n"
            "INSERT INTO classes (name, trainer_id, day_of_week, start_time, max_capacity) VALUES\n"
            "  ('Morning Yoga', 2, 'Monday', '07:00', 20),\n"
            "  ('Power Lifting', 1, 'Wednesday', '18:00', 15),\n"
            "  ('HIIT Cardio', 3, 'Friday', '17:00', 25);\n\n"
            "INSERT INTO attendance (member_id, class_id, attended_date) VALUES\n"
            "  (1, 1, '2025-01-06'), (1, 2, '2025-01-08'),\n"
            "  (2, 2, '2025-01-08'), (3, 3, '2025-01-10'),\n"
            "  (4, 2, '2025-01-08'), (1, 3, '2025-01-10');"
        ),
    },
    {
        'name': 'Hotel Booking',
        'database_type': 'mariadb',
        'description': 'Hotel with rooms, guests, and reservations.',
        'schema_sql': (
            "CREATE TABLE room_types (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(50) NOT NULL,\n"
            "  base_price DECIMAL(8,2),\n"
            "  max_guests INT\n"
            ");\n\n"
            "CREATE TABLE rooms (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  room_number VARCHAR(10) UNIQUE,\n"
            "  room_type_id INT,\n"
            "  floor INT,\n"
            "  FOREIGN KEY (room_type_id) REFERENCES room_types(id)\n"
            ");\n\n"
            "CREATE TABLE guests (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  email VARCHAR(255),\n"
            "  phone VARCHAR(20)\n"
            ");\n\n"
            "CREATE TABLE reservations (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  guest_id INT,\n"
            "  room_id INT,\n"
            "  check_in DATE,\n"
            "  check_out DATE,\n"
            "  total_price DECIMAL(10,2),\n"
            "  FOREIGN KEY (guest_id) REFERENCES guests(id),\n"
            "  FOREIGN KEY (room_id) REFERENCES rooms(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO room_types (name, base_price, max_guests) VALUES\n"
            "  ('Standard', 99.00, 2),\n"
            "  ('Deluxe', 179.00, 3),\n"
            "  ('Suite', 299.00, 4);\n\n"
            "INSERT INTO rooms (room_number, room_type_id, floor) VALUES\n"
            "  ('101', 1, 1), ('102', 1, 1),\n"
            "  ('201', 2, 2), ('202', 2, 2),\n"
            "  ('301', 3, 3);\n\n"
            "INSERT INTO guests (name, email, phone) VALUES\n"
            "  ('Emily Stone', 'emily@mail.com', '555-3001'),\n"
            "  ('Jack River', 'jack@mail.com', '555-3002'),\n"
            "  ('Sophie Lake', 'sophie@mail.com', '555-3003');\n\n"
            "INSERT INTO reservations (guest_id, room_id, check_in, check_out, total_price) VALUES\n"
            "  (1, 3, '2025-02-10', '2025-02-13', 537.00),\n"
            "  (2, 1, '2025-02-12', '2025-02-14', 198.00),\n"
            "  (3, 5, '2025-02-14', '2025-02-17', 897.00);"
        ),
    },
    {
        'name': 'Cinema Database',
        'database_type': 'mariadb',
        'description': 'Cinema with movies, screens, showtimes, and tickets.',
        'schema_sql': (
            "CREATE TABLE movies (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  title VARCHAR(200) NOT NULL,\n"
            "  genre VARCHAR(50),\n"
            "  duration_min INT,\n"
            "  rating VARCHAR(10)\n"
            ");\n\n"
            "CREATE TABLE screens (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(50) NOT NULL,\n"
            "  capacity INT\n"
            ");\n\n"
            "CREATE TABLE showtimes (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  movie_id INT,\n"
            "  screen_id INT,\n"
            "  show_date DATE,\n"
            "  show_time TIME,\n"
            "  price DECIMAL(6,2),\n"
            "  FOREIGN KEY (movie_id) REFERENCES movies(id),\n"
            "  FOREIGN KEY (screen_id) REFERENCES screens(id)\n"
            ");\n\n"
            "CREATE TABLE tickets (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  showtime_id INT,\n"
            "  seat_number VARCHAR(10),\n"
            "  customer_name VARCHAR(100),\n"
            "  FOREIGN KEY (showtime_id) REFERENCES showtimes(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO movies (title, genre, duration_min, rating) VALUES\n"
            "  ('The Matrix', 'Sci-Fi', 136, 'R'),\n"
            "  ('Toy Story', 'Animation', 81, 'G'),\n"
            "  ('Inception', 'Sci-Fi', 148, 'PG-13');\n\n"
            "INSERT INTO screens (name, capacity) VALUES\n"
            "  ('Screen 1', 200), ('Screen 2', 150), ('Screen 3', 100);\n\n"
            "INSERT INTO showtimes (movie_id, screen_id, show_date, show_time, price) VALUES\n"
            "  (1, 1, '2025-02-15', '14:00', 12.99),\n"
            "  (1, 1, '2025-02-15', '20:00', 15.99),\n"
            "  (2, 2, '2025-02-15', '11:00', 9.99),\n"
            "  (3, 3, '2025-02-15', '19:00', 14.99);\n\n"
            "INSERT INTO tickets (showtime_id, seat_number, customer_name) VALUES\n"
            "  (1, 'A1', 'Tom'), (1, 'A2', 'Jerry'),\n"
            "  (2, 'B5', 'Anna'), (3, 'C3', 'Max'),\n"
            "  (4, 'D1', 'Lily'), (4, 'D2', 'Sam');"
        ),
    },
    {
        'name': 'Car Dealership',
        'database_type': 'mariadb',
        'description': 'Car dealership with vehicles, customers, and sales.',
        'schema_sql': (
            "CREATE TABLE vehicles (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  make VARCHAR(50) NOT NULL,\n"
            "  model VARCHAR(50) NOT NULL,\n"
            "  year INT,\n"
            "  color VARCHAR(30),\n"
            "  price DECIMAL(10,2),\n"
            "  mileage INT,\n"
            "  is_new BOOLEAN DEFAULT TRUE\n"
            ");\n\n"
            "CREATE TABLE customers (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  name VARCHAR(100) NOT NULL,\n"
            "  phone VARCHAR(20),\n"
            "  email VARCHAR(255)\n"
            ");\n\n"
            "CREATE TABLE sales (\n"
            "  id INT AUTO_INCREMENT PRIMARY KEY,\n"
            "  vehicle_id INT,\n"
            "  customer_id INT,\n"
            "  sale_price DECIMAL(10,2),\n"
            "  sale_date DATE,\n"
            "  FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),\n"
            "  FOREIGN KEY (customer_id) REFERENCES customers(id)\n"
            ");"
        ),
        'seed_sql': (
            "INSERT INTO vehicles (make, model, year, color, price, mileage, is_new) VALUES\n"
            "  ('Toyota', 'Camry', 2025, 'Silver', 28000, 0, TRUE),\n"
            "  ('Honda', 'Civic', 2024, 'Blue', 24000, 5000, FALSE),\n"
            "  ('Ford', 'Mustang', 2025, 'Red', 42000, 0, TRUE),\n"
            "  ('Tesla', 'Model 3', 2024, 'White', 38000, 12000, FALSE),\n"
            "  ('BMW', 'X5', 2023, 'Black', 55000, 20000, FALSE);\n\n"
            "INSERT INTO customers (name, phone, email) VALUES\n"
            "  ('Mike Johnson', '555-4001', 'mike@mail.com'),\n"
            "  ('Sara Lee', '555-4002', 'sara@mail.com'),\n"
            "  ('Tom Baker', '555-4003', 'tom@mail.com');\n\n"
            "INSERT INTO sales (vehicle_id, customer_id, sale_price, sale_date) VALUES\n"
            "  (2, 1, 22500, '2025-01-10'),\n"
            "  (4, 2, 36000, '2025-01-15'),\n"
            "  (5, 3, 51000, '2025-01-20');"
        ),
    },

    # ── MongoDB (5) ─────────────────────────────────────────────
    {
        'name': 'Blog Platform',
        'database_type': 'mongodb',
        'description': 'Blog with posts, authors, comments, and tags.',
        'schema_sql': '',
        'seed_sql': (
            'db.authors.insertMany([\n'
            '  { name: "Alice Writer", bio: "Tech blogger", joined: new Date("2024-01-01") },\n'
            '  { name: "Bob Journalist", bio: "Freelance writer", joined: new Date("2024-03-15") }\n'
            ']);\n\n'
            'db.posts.insertMany([\n'
            '  { title: "Getting Started with MongoDB", author: "Alice Writer", content: "MongoDB is a document database...", tags: ["mongodb", "tutorial"], likes: 42, created: new Date("2025-01-05") },\n'
            '  { title: "NoSQL vs SQL", author: "Bob Journalist", content: "Comparing database paradigms...", tags: ["nosql", "sql", "comparison"], likes: 28, created: new Date("2025-01-08") },\n'
            '  { title: "Advanced Aggregation", author: "Alice Writer", content: "Let us explore the aggregation pipeline...", tags: ["mongodb", "advanced"], likes: 15, created: new Date("2025-01-12") }\n'
            ']);\n\n'
            'db.comments.insertMany([\n'
            '  { post_title: "Getting Started with MongoDB", user: "Charlie", text: "Great intro!", created: new Date("2025-01-06") },\n'
            '  { post_title: "Getting Started with MongoDB", user: "Diana", text: "Very helpful", created: new Date("2025-01-07") },\n'
            '  { post_title: "NoSQL vs SQL", user: "Charlie", text: "Fair comparison", created: new Date("2025-01-09") }\n'
            ']);'
        ),
    },
    {
        'name': 'IoT Sensor Data',
        'database_type': 'mongodb',
        'description': 'IoT sensor readings from various devices and locations.',
        'schema_sql': '',
        'seed_sql': (
            'db.devices.insertMany([\n'
            '  { device_id: "TEMP-001", type: "temperature", location: "Building A", status: "active" },\n'
            '  { device_id: "HUM-001", type: "humidity", location: "Building A", status: "active" },\n'
            '  { device_id: "TEMP-002", type: "temperature", location: "Building B", status: "active" },\n'
            '  { device_id: "MOTION-001", type: "motion", location: "Entrance", status: "inactive" }\n'
            ']);\n\n'
            'db.readings.insertMany([\n'
            '  { device_id: "TEMP-001", value: 22.5, unit: "celsius", timestamp: new Date("2025-01-15T10:00:00") },\n'
            '  { device_id: "TEMP-001", value: 23.1, unit: "celsius", timestamp: new Date("2025-01-15T11:00:00") },\n'
            '  { device_id: "HUM-001", value: 45.2, unit: "percent", timestamp: new Date("2025-01-15T10:00:00") },\n'
            '  { device_id: "TEMP-002", value: 19.8, unit: "celsius", timestamp: new Date("2025-01-15T10:00:00") },\n'
            '  { device_id: "TEMP-002", value: 20.3, unit: "celsius", timestamp: new Date("2025-01-15T11:00:00") },\n'
            '  { device_id: "MOTION-001", value: 1, unit: "detected", timestamp: new Date("2025-01-15T09:30:00") }\n'
            ']);'
        ),
    },
    {
        'name': 'Game Scores',
        'database_type': 'mongodb',
        'description': 'Game leaderboard with players, scores, and achievements.',
        'schema_sql': '',
        'seed_sql': (
            'db.players.insertMany([\n'
            '  { username: "DragonSlayer", level: 45, xp: 128000, class: "warrior", joined: new Date("2024-06-01") },\n'
            '  { username: "ShadowMage", level: 38, xp: 95000, class: "mage", joined: new Date("2024-07-15") },\n'
            '  { username: "SwiftArcher", level: 42, xp: 115000, class: "ranger", joined: new Date("2024-06-20") },\n'
            '  { username: "IronShield", level: 50, xp: 200000, class: "tank", joined: new Date("2024-05-01") }\n'
            ']);\n\n'
            'db.scores.insertMany([\n'
            '  { username: "DragonSlayer", game: "Arena", score: 1250, duration_sec: 300, date: new Date("2025-01-14") },\n'
            '  { username: "ShadowMage", game: "Arena", score: 1100, duration_sec: 280, date: new Date("2025-01-14") },\n'
            '  { username: "SwiftArcher", game: "Raid", score: 3200, duration_sec: 600, date: new Date("2025-01-14") },\n'
            '  { username: "IronShield", game: "Arena", score: 1500, duration_sec: 320, date: new Date("2025-01-14") },\n'
            '  { username: "DragonSlayer", game: "Raid", score: 2800, duration_sec: 550, date: new Date("2025-01-15") }\n'
            ']);\n\n'
            'db.achievements.insertMany([\n'
            '  { username: "IronShield", name: "First Blood", description: "Win first arena match", earned: new Date("2024-05-02") },\n'
            '  { username: "DragonSlayer", name: "Dragon Slayer", description: "Defeat the dragon boss", earned: new Date("2024-12-25") },\n'
            '  { username: "SwiftArcher", name: "Sharpshooter", description: "100 headshots", earned: new Date("2025-01-10") }\n'
            ']);'
        ),
    },
    {
        'name': 'Product Catalog',
        'database_type': 'mongodb',
        'description': 'Product catalog with categories, reviews, and inventory.',
        'schema_sql': '',
        'seed_sql': (
            'db.categories.insertMany([\n'
            '  { name: "Electronics", slug: "electronics", description: "Gadgets and devices" },\n'
            '  { name: "Clothing", slug: "clothing", description: "Apparel and accessories" },\n'
            '  { name: "Books", slug: "books", description: "Physical and digital books" }\n'
            ']);\n\n'
            'db.products.insertMany([\n'
            '  { name: "Wireless Earbuds", category: "electronics", price: 49.99, stock: 150, specs: { battery_hours: 6, bluetooth: "5.0", waterproof: true } },\n'
            '  { name: "Running Shoes", category: "clothing", price: 89.99, stock: 75, specs: { sizes: ["8", "9", "10", "11"], material: "mesh" } },\n'
            '  { name: "Python Handbook", category: "books", price: 34.99, stock: 200, specs: { pages: 450, format: "paperback", isbn: "978-1234567890" } },\n'
            '  { name: "Smart Watch", category: "electronics", price: 199.99, stock: 50, specs: { battery_days: 7, display: "AMOLED", gps: true } },\n'
            '  { name: "Denim Jacket", category: "clothing", price: 69.99, stock: 40, specs: { sizes: ["S", "M", "L", "XL"], material: "denim" } }\n'
            ']);\n\n'
            'db.reviews.insertMany([\n'
            '  { product: "Wireless Earbuds", user: "TechFan", rating: 5, text: "Amazing sound quality!", date: new Date("2025-01-10") },\n'
            '  { product: "Wireless Earbuds", user: "MusicLover", rating: 4, text: "Good but bass could be better", date: new Date("2025-01-12") },\n'
            '  { product: "Running Shoes", user: "Runner42", rating: 5, text: "Super comfortable", date: new Date("2025-01-08") },\n'
            '  { product: "Smart Watch", user: "TechFan", rating: 4, text: "Great battery life", date: new Date("2025-01-14") }\n'
            ']);'
        ),
    },
    {
        'name': 'Chat Messages',
        'database_type': 'mongodb',
        'description': 'Chat application with rooms, users, and messages.',
        'schema_sql': '',
        'seed_sql': (
            'db.rooms.insertMany([\n'
            '  { name: "general", description: "General discussion", created: new Date("2024-01-01"), members: ["alice", "bob", "carol", "dave"] },\n'
            '  { name: "tech-talk", description: "Technology discussions", created: new Date("2024-02-01"), members: ["alice", "carol"] },\n'
            '  { name: "random", description: "Off-topic chat", created: new Date("2024-03-01"), members: ["bob", "dave"] }\n'
            ']);\n\n'
            'db.users.insertMany([\n'
            '  { username: "alice", display_name: "Alice", status: "online", last_seen: new Date("2025-01-15T14:00:00") },\n'
            '  { username: "bob", display_name: "Bob", status: "offline", last_seen: new Date("2025-01-15T12:00:00") },\n'
            '  { username: "carol", display_name: "Carol", status: "online", last_seen: new Date("2025-01-15T14:05:00") },\n'
            '  { username: "dave", display_name: "Dave", status: "away", last_seen: new Date("2025-01-15T13:30:00") }\n'
            ']);\n\n'
            'db.messages.insertMany([\n'
            '  { room: "general", from: "alice", text: "Hey everyone!", timestamp: new Date("2025-01-15T10:00:00") },\n'
            '  { room: "general", from: "bob", text: "Hi Alice!", timestamp: new Date("2025-01-15T10:01:00") },\n'
            '  { room: "general", from: "carol", text: "Good morning!", timestamp: new Date("2025-01-15T10:02:00") },\n'
            '  { room: "tech-talk", from: "alice", text: "Anyone tried the new MongoDB 8?", timestamp: new Date("2025-01-15T11:00:00") },\n'
            '  { room: "tech-talk", from: "carol", text: "Yes, the vector search is amazing", timestamp: new Date("2025-01-15T11:05:00") },\n'
            '  { room: "random", from: "dave", text: "Check out this meme", timestamp: new Date("2025-01-15T12:00:00") }\n'
            ']);'
        ),
    },

    # ── Redis (5) ───────────────────────────────────────────────
    {
        'name': 'Session Store',
        'database_type': 'redis',
        'description': 'User session management with tokens and metadata.',
        'schema_sql': '',
        'seed_sql': (
            "SET session:user:1001 '{\"user_id\":1001,\"username\":\"alice\",\"role\":\"admin\",\"login_time\":\"2025-01-15T10:00:00\"}'\n"
            "EXPIRE session:user:1001 3600\n"
            "SET session:user:1002 '{\"user_id\":1002,\"username\":\"bob\",\"role\":\"user\",\"login_time\":\"2025-01-15T10:30:00\"}'\n"
            "EXPIRE session:user:1002 3600\n"
            "SET session:user:1003 '{\"user_id\":1003,\"username\":\"carol\",\"role\":\"user\",\"login_time\":\"2025-01-15T11:00:00\"}'\n"
            "EXPIRE session:user:1003 3600\n"
            "SADD active_sessions session:user:1001 session:user:1002 session:user:1003\n"
            "HSET user:1001 name Alice email alice@example.com logins 42\n"
            "HSET user:1002 name Bob email bob@example.com logins 15\n"
            "HSET user:1003 name Carol email carol@example.com logins 28"
        ),
    },
    {
        'name': 'Leaderboard',
        'database_type': 'redis',
        'description': 'Game leaderboard using sorted sets.',
        'schema_sql': '',
        'seed_sql': (
            "ZADD leaderboard:global 1500 player:dragon_slayer\n"
            "ZADD leaderboard:global 1350 player:shadow_mage\n"
            "ZADD leaderboard:global 1420 player:swift_archer\n"
            "ZADD leaderboard:global 1280 player:iron_shield\n"
            "ZADD leaderboard:global 1600 player:fire_wizard\n"
            "ZADD leaderboard:weekly 800 player:dragon_slayer\n"
            "ZADD leaderboard:weekly 920 player:fire_wizard\n"
            "ZADD leaderboard:weekly 750 player:swift_archer\n"
            "HSET player:dragon_slayer name DragonSlayer level 45 class warrior\n"
            "HSET player:shadow_mage name ShadowMage level 38 class mage\n"
            "HSET player:swift_archer name SwiftArcher level 42 class ranger\n"
            "HSET player:iron_shield name IronShield level 50 class tank\n"
            "HSET player:fire_wizard name FireWizard level 47 class mage"
        ),
    },
    {
        'name': 'Cache Layer',
        'database_type': 'redis',
        'description': 'Application cache with various data structures.',
        'schema_sql': '',
        'seed_sql': (
            "SET cache:page:/home '{\"title\":\"Home\",\"content\":\"Welcome!\",\"cached_at\":\"2025-01-15T10:00:00\"}'\n"
            "EXPIRE cache:page:/home 300\n"
            "SET cache:page:/about '{\"title\":\"About\",\"content\":\"About us page\",\"cached_at\":\"2025-01-15T10:00:00\"}'\n"
            "EXPIRE cache:page:/about 300\n"
            "HSET cache:user:100 name Alice email alice@example.com avatar /img/alice.png\n"
            "EXPIRE cache:user:100 600\n"
            "HSET cache:user:200 name Bob email bob@example.com avatar /img/bob.png\n"
            "EXPIRE cache:user:200 600\n"
            "LPUSH cache:recent_products product:500 product:401 product:322 product:299 product:188\n"
            "SET cache:stats:visitors 15432\n"
            "SET cache:stats:page_views 84210"
        ),
    },
    {
        'name': 'Rate Limiter',
        'database_type': 'redis',
        'description': 'API rate limiting with counters and sliding windows.',
        'schema_sql': '',
        'seed_sql': (
            "SET ratelimit:api:/login:192.168.1.1 5\n"
            "EXPIRE ratelimit:api:/login:192.168.1.1 60\n"
            "SET ratelimit:api:/login:192.168.1.2 2\n"
            "EXPIRE ratelimit:api:/login:192.168.1.2 60\n"
            "SET ratelimit:api:/search:192.168.1.1 18\n"
            "EXPIRE ratelimit:api:/search:192.168.1.1 60\n"
            "HSET ratelimit:config:/login max_requests 10 window_seconds 60 block_duration 300\n"
            "HSET ratelimit:config:/search max_requests 30 window_seconds 60 block_duration 120\n"
            "HSET ratelimit:config:/api max_requests 100 window_seconds 60 block_duration 60\n"
            "SADD ratelimit:blocked 192.168.1.50 10.0.0.99\n"
            "SET ratelimit:blocked:192.168.1.50 'Too many login attempts'\n"
            "EXPIRE ratelimit:blocked:192.168.1.50 300"
        ),
    },
    {
        'name': 'Task Queue',
        'database_type': 'redis',
        'description': 'Background task queue with priorities and status tracking.',
        'schema_sql': '',
        'seed_sql': (
            "LPUSH queue:high '{\"id\":\"task-001\",\"type\":\"email\",\"payload\":{\"to\":\"user@example.com\",\"subject\":\"Welcome\"}}'\n"
            "LPUSH queue:high '{\"id\":\"task-002\",\"type\":\"notification\",\"payload\":{\"user_id\":100,\"message\":\"New message\"}}'\n"
            "LPUSH queue:low '{\"id\":\"task-003\",\"type\":\"report\",\"payload\":{\"report_type\":\"weekly\",\"format\":\"pdf\"}}'\n"
            "LPUSH queue:low '{\"id\":\"task-004\",\"type\":\"cleanup\",\"payload\":{\"target\":\"temp_files\",\"older_than_days\":7}}'\n"
            "HSET task:status:task-001 status pending created_at 2025-01-15T10:00:00 retries 0\n"
            "HSET task:status:task-002 status pending created_at 2025-01-15T10:01:00 retries 0\n"
            "HSET task:status:task-003 status pending created_at 2025-01-15T09:00:00 retries 0\n"
            "HSET task:status:task-004 status pending created_at 2025-01-15T09:30:00 retries 0\n"
            "SET queue:stats:processed 1523\n"
            "SET queue:stats:failed 12\n"
            "SET queue:stats:avg_time_ms 245"
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed 25 standalone sandbox datasets (5 per database type)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing standalone datasets before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            count, _ = Dataset.objects.filter(course__isnull=True).delete()
            self.stdout.write(f'Deleted {count} existing standalone datasets.')

        created = 0
        for data in DATASETS:
            _, was_created = Dataset.objects.get_or_create(
                name=data['name'],
                course=None,
                defaults={
                    'database_type': data['database_type'],
                    'description': data['description'],
                    'schema_sql': data['schema_sql'],
                    'seed_sql': data['seed_sql'],
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'  Created: {data["name"]} ({data["database_type"]})')
            else:
                self.stdout.write(f'  Exists:  {data["name"]} ({data["database_type"]})')

        self.stdout.write(self.style.SUCCESS(f'\nDone! Created {created} new datasets.'))
