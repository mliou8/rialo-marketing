-- Content Pipeline table (replaces Notion Content Pipeline database)
CREATE TABLE IF NOT EXISTS content_pipeline (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    topic TEXT NOT NULL,
    original_url TEXT,
    status TEXT DEFAULT 'Inspiration' CHECK (status IN ('Inspiration', 'Drafted', 'Approved', 'Published')),
    draft TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Twitter Calendar table (replaces Notion Twitter Calendar database)
CREATE TABLE IF NOT EXISTS twitter_calendar (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    topic TEXT NOT NULL,
    draft TEXT,
    scheduled_date DATE,
    status TEXT DEFAULT 'Pending' CHECK (status IN ('Pending', 'Drafted', 'Scheduled', 'Published')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster status queries
CREATE INDEX IF NOT EXISTS idx_content_pipeline_status ON content_pipeline(status);
CREATE INDEX IF NOT EXISTS idx_twitter_calendar_status ON twitter_calendar(status);
CREATE INDEX IF NOT EXISTS idx_twitter_calendar_scheduled ON twitter_calendar(scheduled_date);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to both tables
DROP TRIGGER IF EXISTS update_content_pipeline_updated_at ON content_pipeline;
CREATE TRIGGER update_content_pipeline_updated_at
    BEFORE UPDATE ON content_pipeline
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_twitter_calendar_updated_at ON twitter_calendar;
CREATE TRIGGER update_twitter_calendar_updated_at
    BEFORE UPDATE ON twitter_calendar
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
