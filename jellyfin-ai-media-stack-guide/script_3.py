# Create setup and database initialization scripts

# Database setup SQL for Supabase
supabase_sql = '''
-- Media table for storing Jellyfin media information
CREATE TABLE IF NOT EXISTS media (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    jellyfin_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    path TEXT,
    type TEXT,
    duration DECIMAL,
    size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Media analysis table for AI-generated content
CREATE TABLE IF NOT EXISTS media_analysis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    media_id UUID REFERENCES media(id) ON DELETE CASCADE,
    ai_description TEXT,
    ai_analysis JSONB,
    audio_features JSONB,
    processing_status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content creation projects
CREATE TABLE IF NOT EXISTS content_projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    media_ids UUID[] DEFAULT '{}',
    project_type TEXT, -- 'youtube', 'podcast', 'mix', etc.
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- YouTube content tracking
CREATE TABLE IF NOT EXISTS youtube_content (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID REFERENCES content_projects(id) ON DELETE CASCADE,
    video_id TEXT,
    title TEXT,
    description TEXT,
    tags TEXT[],
    thumbnail_url TEXT,
    upload_status TEXT DEFAULT 'draft',
    analytics_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User preferences and settings
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processing queue for async operations
CREATE TABLE IF NOT EXISTS processing_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    operation_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_media_jellyfin_id ON media(jellyfin_id);
CREATE INDEX IF NOT EXISTS idx_media_type ON media(type);
CREATE INDEX IF NOT EXISTS idx_media_analysis_media_id ON media_analysis(media_id);
CREATE INDEX IF NOT EXISTS idx_media_analysis_status ON media_analysis(processing_status);
CREATE INDEX IF NOT EXISTS idx_content_projects_type ON content_projects(project_type);
CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_processing_queue_priority ON processing_queue(priority DESC);

-- Update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_media_updated_at BEFORE UPDATE ON media
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_media_analysis_updated_at BEFORE UPDATE ON media_analysis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_projects_updated_at BEFORE UPDATE ON content_projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_youtube_content_updated_at BEFORE UPDATE ON youtube_content
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_queue_updated_at BEFORE UPDATE ON processing_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies
ALTER TABLE media ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE youtube_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to read all media
CREATE POLICY "Allow authenticated read access" ON media
    FOR SELECT TO authenticated USING (true);

-- Allow authenticated users to insert/update their own content
CREATE POLICY "Allow authenticated write access" ON media
    FOR ALL TO authenticated USING (true);

-- Apply similar policies to other tables
CREATE POLICY "Allow authenticated access" ON media_analysis
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow authenticated access" ON content_projects
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow authenticated access" ON youtube_content
    FOR ALL TO authenticated USING (true);

CREATE POLICY "Allow user settings access" ON user_settings
    FOR ALL TO authenticated USING (auth.uid() = user_id);
'''

# Neo4j setup Cypher queries
neo4j_setup = '''
// Create constraints for better performance and data integrity
CREATE CONSTRAINT media_id_unique IF NOT EXISTS FOR (m:Media) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT analysis_media_id_unique IF NOT EXISTS FOR (a:Analysis) REQUIRE a.media_id IS UNIQUE;
CREATE CONSTRAINT features_media_id_unique IF NOT EXISTS FOR (f:AudioFeatures) REQUIRE f.media_id IS UNIQUE;

// Create indexes for common queries
CREATE INDEX media_name_index IF NOT EXISTS FOR (m:Media) ON (m.name);
CREATE INDEX media_type_index IF NOT EXISTS FOR (m:Media) ON (m.type);
CREATE INDEX features_tempo_index IF NOT EXISTS FOR (f:AudioFeatures) ON (f.tempo);
CREATE INDEX features_genre_index IF NOT EXISTS FOR (a:Analysis) ON (a.genre);

// Create sample data structure relationships
MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
MATCH (m)-[:HAS_FEATURES]->(f:AudioFeatures)
WHERE f.tempo IS NOT NULL AND a.ai_analysis IS NOT NULL
WITH m, a, f
CREATE (g:Genre {name: coalesce(a.ai_analysis.genre, 'Unknown')})
MERGE (m)-[:BELONGS_TO_GENRE]->(g);

// Create similarity relationships based on audio features
MATCH (m1:Media)-[:HAS_FEATURES]->(f1:AudioFeatures)
MATCH (m2:Media)-[:HAS_FEATURES]->(f2:AudioFeatures)
WHERE m1.id <> m2.id 
  AND abs(f1.tempo - f2.tempo) < 10
  AND abs(f1.spectral_centroid_mean - f2.spectral_centroid_mean) < 500
CREATE (m1)-[:SIMILAR_TO {score: 1.0 / (1.0 + abs(f1.tempo - f2.tempo) + abs(f1.spectral_centroid_mean - f2.spectral_centroid_mean) / 1000)}]->(m2);

// Create playlists based on content analysis
MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
WHERE a.ai_analysis.mood IS NOT NULL
WITH a.ai_analysis.mood as mood, collect(m) as media_items
CREATE (p:Playlist {name: mood + ' Playlist', mood: mood, created_at: datetime()})
FOREACH (media IN media_items | CREATE (p)-[:CONTAINS]->(media));

// Create artist relationships (if available in metadata)
MATCH (m:Media)
WHERE m.artist IS NOT NULL
MERGE (artist:Artist {name: m.artist})
CREATE (artist)-[:PERFORMED]->(m);

// Create album relationships (if available in metadata)
MATCH (m:Media)
WHERE m.album IS NOT NULL
MERGE (album:Album {name: m.album})
CREATE (album)-[:CONTAINS]->(m);
'''

# Setup script
setup_script = '''#!/bin/bash
set -e

echo "🎵 Setting up Media Analysis Stack..."

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p media/{music,videos,podcasts}
mkdir -p jellyfin/{config,cache}
mkdir -p neo4j/{data,logs,import,plugins}
mkdir -p qwen/{models,cache}
mkdir -p output
mkdir -p logs
mkdir -p redis/data

# Set permissions
print_status "Setting directory permissions..."
sudo chown -R $USER:$USER jellyfin/ neo4j/ qwen/ output/ logs/ redis/
chmod -R 755 jellyfin/ neo4j/ qwen/ output/ logs/ redis/

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating environment file..."
    cp .env.template .env
    print_warning "Please edit .env file with your actual configuration values!"
fi

# Download Neo4j plugins
print_status "Setting up Neo4j plugins..."
NEO4J_PLUGINS_DIR="./neo4j/plugins"
if [ ! -f "$NEO4J_PLUGINS_DIR/neo4j-graph-data-science.jar" ]; then
    print_status "Downloading Neo4j Graph Data Science plugin..."
    wget -O "$NEO4J_PLUGINS_DIR/neo4j-graph-data-science-2.5.0.jar" \\
        "https://github.com/neo4j/graph-data-science/releases/download/2.5.0/neo4j-graph-data-science-2.5.0.jar"
fi

# Build custom Docker images
print_status "Building custom Docker images..."
docker build -t media-audio-processor ./audio-processor/
docker build -t media-api-gateway ./api-gateway/

# Start Supabase (if using local instance)
if grep -q "localhost" .env; then
    print_status "Starting Supabase local development..."
    if command -v supabase &> /dev/null; then
        supabase start
    else
        print_warning "Supabase CLI not found. Using remote instance from .env"
    fi
fi

# Start the stack
print_status "Starting the media stack..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 30

# Check service health
print_status "Checking service health..."
services=("jellyfin:8096" "neo4j:7474" "api-gateway:3000")

for service in "${services[@]}"; do
    IFS=':' read -ra ADDR <<< "$service"
    service_name="${ADDR[0]}"
    service_port="${ADDR[1]}"
    
    if curl -f -s "http://localhost:$service_port" > /dev/null; then
        print_status "$service_name is running ✓"
    else
        print_warning "$service_name might not be ready yet"
    fi
done

# Setup Neo4j database
print_status "Setting up Neo4j database..."
if command -v cypher-shell &> /dev/null; then
    cypher-shell -u neo4j -p mediapassword123 < neo4j-setup.cypher || print_warning "Neo4j setup script failed. You may need to run it manually."
else
    print_warning "cypher-shell not found. Please run neo4j-setup.cypher manually in Neo4j browser."
fi

echo ""
print_status "🎉 Setup complete!"
echo ""
echo "Service URLs:"
echo "  📺 Jellyfin:        http://localhost:8096"
echo "  🌐 Neo4j Browser:   http://localhost:7474"
echo "  🚀 API Gateway:     http://localhost:3000"
echo "  📊 Dashboard:       http://localhost:3001"
echo ""
echo "Next steps:"
echo "  1. Configure Jellyfin by visiting http://localhost:8096"
echo "  2. Add your media files to ./media/ directories"
echo "  3. Update .env file with your Supabase credentials"
echo "  4. Check logs with: docker-compose logs -f"
echo ""
print_warning "Remember to configure your .env file with actual API keys and credentials!"
'''

# Create files
with open('supabase-setup.sql', 'w') as f:
    f.write(supabase_sql)

with open('neo4j-setup.cypher', 'w') as f:
    f.write(neo4j_setup)

with open('setup.sh', 'w') as f:
    f.write(setup_script)

# Make setup script executable
import stat
os.chmod('setup.sh', os.stat('setup.sh').st_mode | stat.S_IEXEC)

print("Setup files created:")
print("- supabase-setup.sql")
print("- neo4j-setup.cypher") 
print("- setup.sh (executable)")