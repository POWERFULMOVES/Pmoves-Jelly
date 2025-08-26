# Create a comprehensive docker-compose.yml for the media stack with Jellyfin, Supabase, Neo4j, and AI services
docker_compose_content = '''
version: '3.8'

networks:
  media-stack:
    driver: bridge
  supabase-network:
    external: true
    name: supabase_default

services:
  # Jellyfin Media Server
  jellyfin:
    image: lscr.io/linuxserver/jellyfin:latest
    container_name: jellyfin
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - JELLYFIN_PublishedServerUrl=http://localhost:8096
    volumes:
      - ./jellyfin/config:/config
      - ./jellyfin/cache:/cache
      - ./media/music:/media/music
      - ./media/videos:/media/videos
      - ./media/podcasts:/media/podcasts
      - ./output:/output  # For AI-processed content
    ports:
      - "8096:8096"      # HTTP
      - "8920:8920"      # HTTPS (optional)
      - "7359:7359/udp"  # Client discovery
      - "1900:1900/udp"  # DLNA discovery
    networks:
      - media-stack
    restart: unless-stopped
    depends_on:
      - neo4j
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8096/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Neo4j Graph Database
  neo4j:
    image: neo4j:5.15
    container_name: neo4j
    environment:
      - NEO4J_AUTH=neo4j/mediapassword123
      - NEO4J_dbms_security_procedures_unrestricted=gds.*
      - NEO4J_dbms_security_procedures_allowlist=gds.*
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
      - ./neo4j/import:/var/lib/neo4j/import
      - ./neo4j/plugins:/plugins
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    networks:
      - media-stack
      - supabase-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "mediapassword123", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Qwen Audio Analysis Service
  qwen-audio:
    image: qwen/qwen-audio:latest
    container_name: qwen-audio
    environment:
      - MODEL_NAME=Qwen/Qwen-Audio-Chat
      - DEVICE=cpu  # Change to 'cuda' if you have GPU support
      - MAX_LENGTH=2048
      - TEMPERATURE=0.7
    volumes:
      - ./qwen/models:/app/models
      - ./qwen/cache:/app/cache
      - ./media:/app/input
      - ./output:/app/output
    ports:
      - "8000:8000"
    networks:
      - media-stack
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G

  # Audio Processing Worker
  audio-processor:
    build:
      context: ./audio-processor
      dockerfile: Dockerfile
    container_name: audio-processor
    environment:
      - JELLYFIN_URL=http://jellyfin:8096
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=mediapassword123
      - QWEN_AUDIO_URL=http://qwen-audio:8000
      - PROCESSING_INTERVAL=300  # Process every 5 minutes
    volumes:
      - ./media:/app/media
      - ./output:/app/output
      - ./logs:/app/logs
    networks:
      - media-stack
      - supabase-network
    restart: unless-stopped
    depends_on:
      - jellyfin
      - neo4j
      - qwen-audio

  # Redis for job queue and caching
  redis:
    image: redis:7-alpine
    container_name: redis
    command: redis-server --appendonly yes
    volumes:
      - ./redis/data:/data
    ports:
      - "6379:6379"
    networks:
      - media-stack
    restart: unless-stopped

  # Web API Gateway
  api-gateway:
    build:
      context: ./api-gateway
      dockerfile: Dockerfile
    container_name: api-gateway
    environment:
      - PORT=3000
      - JELLYFIN_URL=http://jellyfin:8096
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=mediapassword123
      - REDIS_URL=redis://redis:6379
    ports:
      - "3000:3000"
    networks:
      - media-stack
      - supabase-network
    restart: unless-stopped
    depends_on:
      - jellyfin
      - neo4j
      - redis

  # Content Analysis Dashboard
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    container_name: dashboard
    environment:
      - REACT_APP_API_URL=http://localhost:3000
      - REACT_APP_JELLYFIN_URL=http://localhost:8096
      - REACT_APP_NEO4J_URL=http://localhost:7474
    ports:
      - "3001:80"
    networks:
      - media-stack
    restart: unless-stopped
    depends_on:
      - api-gateway

volumes:
  jellyfin-config:
  jellyfin-cache:
  neo4j-data:
  neo4j-logs:
  redis-data:
'''

# Create environment file template
env_template = '''
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Optional: Custom domains
JELLYFIN_DOMAIN=localhost
API_DOMAIN=localhost

# Security (change these!)
JWT_SECRET=your-jwt-secret-here
NEO4J_PASSWORD=mediapassword123

# AI Configuration
OPENAI_API_KEY=your-openai-key-if-needed
HUGGINGFACE_TOKEN=your-hf-token-if-needed

# YouTube API (for content creation features)
YOUTUBE_API_KEY=your-youtube-api-key
'''

# Write the files
with open('docker-compose.yml', 'w') as f:
    f.write(docker_compose_content)

with open('.env.template', 'w') as f:
    f.write(env_template)

print("Docker Compose configuration created successfully!")
print("\nFiles created:")
print("- docker-compose.yml")
print("- .env.template")