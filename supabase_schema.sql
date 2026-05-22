-- Schema for ngomarketplace
CREATE TABLE IF NOT EXISTS ngos (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    category TEXT,
    subcategory TEXT,
    country TEXT,
    description TEXT,
    website TEXT,
    contact TEXT,
    verification_status TEXT,
    trust_score REAL,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password TEXT,
    provider TEXT DEFAULT 'email',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interactions (
    id SERIAL PRIMARY KEY,
    ngo_id INTEGER REFERENCES ngos(id),
    user_type TEXT,
    action_type TEXT,
    details TEXT,
    timestamp TEXT
);
