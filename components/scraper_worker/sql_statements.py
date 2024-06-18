POSTGRES_CREATE_TABLE_POSTS = """
CREATE TABLE IF NOT EXISTS {table_name} (
  id SERIAL PRIMARY KEY,
  scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  post_id TEXT UNIQUE,
  platform TEXT,
  url TEXT,
  text TEXT,
  posted_at TEXT,
  is_classified BOOLEAN,
  is_civic BOOLEAN,
  bridging_score REAL,
  is_bridging BOOLEAN,
  recommended_to TEXT DEFAULT '[]'
);
"""

POSTGRES_CREATE_INDEXES_POSTS = """
CREATE INDEX IF NOT EXISTS idx_scraped_at ON {table_name}(scraped_at);
CREATE INDEX IF NOT EXISTS idx_post_id ON {table_name}(post_id);
CREATE INDEX IF NOT EXISTS idx_platform ON {table_name}(platform);
CREATE INDEX IF NOT EXISTS idx_posted_at ON {table_name}(posted_at);
"""

POSTGRES_CREATE_TABLE_CHANGES = """
CREATE TABLE IF NOT EXISTS changes (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  platform TEXT,
  timestamp TIMESTAMP WITH TIME ZONE,
  id_removed TEXT,
  id_inserted TEXT,
  bridging_score_removed REAL,
  bridging_score_inserted REAL
);
"""

POSTGRES_CREATE_TABLE_REQUESTS = """
CREATE TABLE IF NOT EXISTS requests (
  id SERIAL PRIMARY KEY,
  user_id TEXT,
  platform TEXT,
  timestamp TIMESTAMP WITH TIME ZONE,
  inventory_available INTEGER,
  inventory_required INTEGER
);
"""

POSTGRES_CREATE_TABLE_SCRAPER_ERRORS = """
CREATE TABLE IF NOT EXISTS {table_name} (
  id SERIAL PRIMARY KEY,
  occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  platform TEXT,
  message TEXT
);
"""

POSTGRES_CREATE_INDEXES_SCRAPER_ERRORS = """
CREATE INDEX IF NOT EXISTS idx_occurred_at ON {table_name}(occurred_at);
CREATE INDEX IF NOT EXISTS idx_platform ON {table_name}(platform);
"""
