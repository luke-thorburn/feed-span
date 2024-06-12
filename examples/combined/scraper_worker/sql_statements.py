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
  recommended_to TEXT
);
"""

POSTGRES_CREATE_INDEXES_POSTS = """
CREATE INDEX IF NOT EXISTS idx_scraped_at ON {table_name}(scraped_at);
CREATE INDEX IF NOT EXISTS idx_post_id ON {table_name}(post_id);
CREATE INDEX IF NOT EXISTS idx_platform ON {table_name}(platform);
CREATE INDEX IF NOT EXISTS idx_posted_at ON {table_name}(posted_at);
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
