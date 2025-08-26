# Create API Gateway service

# API Gateway Dockerfile
api_dockerfile = '''
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs

EXPOSE 3000

CMD ["npm", "start"]
'''

# API Gateway package.json
api_package_json = '''{
  "name": "media-api-gateway",
  "version": "1.0.0",
  "description": "API Gateway for Media Stack",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "helmet": "^7.1.0",
    "morgan": "^1.10.0",
    "axios": "^1.6.2",
    "@supabase/supabase-js": "^2.38.4",
    "neo4j-driver": "^5.15.0",
    "redis": "^4.6.10",
    "multer": "^1.4.5-lts.1",
    "express-rate-limit": "^7.1.5",
    "jsonwebtoken": "^9.0.2",
    "dotenv": "^16.3.1",
    "ws": "^8.14.2"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}'''

# API Gateway server
api_server = '''
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const { createClient } = require('@supabase/supabase-js');
const neo4j = require('neo4j-driver');
const Redis = require('redis');
const axios = require('axios');
const WebSocket = require('ws');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3001'],
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

// Logging
app.use(morgan('combined'));

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Initialize clients
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

const neo4jDriver = neo4j.driver(
  process.env.NEO4J_URI,
  neo4j.auth.basic(process.env.NEO4J_USER, process.env.NEO4J_PASSWORD)
);

const redisClient = Redis.createClient({
  url: process.env.REDIS_URL || 'redis://redis:6379'
});

redisClient.connect();

// WebSocket server for real-time updates
const wss = new WebSocket.Server({ port: 3002 });

wss.on('connection', (ws) => {
  console.log('Client connected to WebSocket');
  
  ws.on('close', () => {
    console.log('Client disconnected from WebSocket');
  });
});

// Broadcast to all connected clients
function broadcast(data) {
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(data));
    }
  });
}

// Routes

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Get media library with analysis
app.get('/api/media', async (req, res) => {
  try {
    const { page = 1, limit = 20, type, genre } = req.query;
    const offset = (page - 1) * limit;
    
    let query = supabase
      .from('media')
      .select(`
        *,
        media_analysis (
          ai_description,
          ai_analysis,
          audio_features
        )
      `)
      .range(offset, offset + limit - 1);
    
    if (type) query = query.eq('type', type);
    
    const { data, error } = await query;
    
    if (error) throw error;
    
    res.json({
      data,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: data.length
      }
    });
    
  } catch (error) {
    console.error('Error fetching media:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get media item details
app.get('/api/media/:id', async (req, res) => {
  try {
    const { id } = req.params;
    
    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .eq('id', id)
      .single();
    
    if (error) throw error;
    
    res.json(data);
    
  } catch (error) {
    console.error('Error fetching media item:', error);
    res.status(500).json({ error: error.message });
  }
});

// Search media using Neo4j
app.get('/api/search', async (req, res) => {
  try {
    const { q, type = 'similarity' } = req.query;
    
    if (!q) {
      return res.status(400).json({ error: 'Query parameter required' });
    }
    
    const session = neo4jDriver.session();
    
    let cypher;
    if (type === 'similarity') {
      cypher = `
        MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
        WHERE a.ai_description CONTAINS $query OR m.name CONTAINS $query
        RETURN m, a
        LIMIT 20
      `;
    } else {
      cypher = `
        MATCH (m:Media)
        WHERE m.name CONTAINS $query
        RETURN m
        LIMIT 20
      `;
    }
    
    const result = await session.run(cypher, { query: q });
    const records = result.records.map(record => ({
      media: record.get('m').properties,
      analysis: record.has('a') ? record.get('a').properties : null
    }));
    
    await session.close();
    
    res.json({ results: records, query: q });
    
  } catch (error) {
    console.error('Error searching:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get recommendations based on audio features
app.get('/api/recommendations/:mediaId', async (req, res) => {
  try {
    const { mediaId } = req.params;
    
    const session = neo4jDriver.session();
    
    const cypher = `
      MATCH (m:Media {id: $mediaId})-[:HAS_FEATURES]->(f:AudioFeatures)
      MATCH (other:Media)-[:HAS_FEATURES]->(otherF:AudioFeatures)
      WHERE m.id <> other.id
      WITH m, other, 
           abs(f.tempo - otherF.tempo) as tempoDiff,
           abs(f.spectral_centroid_mean - otherF.spectral_centroid_mean) as spectralDiff
      WHERE tempoDiff < 20 AND spectralDiff < 1000
      RETURN other
      ORDER BY tempoDiff + spectralDiff
      LIMIT 10
    `;
    
    const result = await session.run(cypher, { mediaId });
    const recommendations = result.records.map(record => 
      record.get('other').properties
    );
    
    await session.close();
    
    res.json({ recommendations });
    
  } catch (error) {
    console.error('Error getting recommendations:', error);
    res.status(500).json({ error: error.message });
  }
});

// Trigger analysis for specific media
app.post('/api/analyze/:mediaId', async (req, res) => {
  try {
    const { mediaId } = req.params;
    
    // Add to processing queue
    await redisClient.lPush('analysis_queue', mediaId);
    
    // Broadcast update
    broadcast({
      type: 'analysis_queued',
      mediaId,
      timestamp: new Date().toISOString()
    });
    
    res.json({ message: 'Analysis queued', mediaId });
    
  } catch (error) {
    console.error('Error queueing analysis:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get analytics dashboard data
app.get('/api/analytics', async (req, res) => {
  try {
    const session = neo4jDriver.session();
    
    // Get various analytics
    const queries = {
      totalMedia: `MATCH (m:Media) RETURN count(m) as count`,
      analyzedMedia: `MATCH (m:Media)-[:HAS_ANALYSIS]->() RETURN count(m) as count`,
      avgTempo: `MATCH ()-[:HAS_FEATURES]->(f:AudioFeatures) RETURN avg(f.tempo) as avg`,
      genreDistribution: `
        MATCH (m:Media)-[:HAS_ANALYSIS]->(a:Analysis)
        RETURN a.ai_analysis.genre as genre, count(*) as count
        ORDER BY count DESC
        LIMIT 10
      `
    };
    
    const results = {};
    
    for (const [key, query] of Object.entries(queries)) {
      const result = await session.run(query);
      results[key] = result.records.map(record => 
        Object.fromEntries(record.keys.map(key => [key, record.get(key)]))
      );
    }
    
    await session.close();
    
    res.json(results);
    
  } catch (error) {
    console.error('Error getting analytics:', error);
    res.status(500).json({ error: error.message });
  }
});

// Export data for content creation
app.get('/api/export/:format', async (req, res) => {
  try {
    const { format } = req.params;
    const { mediaIds } = req.query;
    
    if (!mediaIds) {
      return res.status(400).json({ error: 'mediaIds required' });
    }
    
    const ids = mediaIds.split(',');
    
    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .in('id', ids);
    
    if (error) throw error;
    
    if (format === 'json') {
      res.json(data);
    } else if (format === 'csv') {
      // Simple CSV export
      const csv = data.map(item => 
        `"${item.name}","${item.type}","${item.media_analysis?.[0]?.ai_description || ''}"`
      ).join('\\n');
      
      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename="media_export.csv"');
      res.send(`Name,Type,Description\\n${csv}`);
    } else {
      res.status(400).json({ error: 'Unsupported format' });
    }
    
  } catch (error) {
    console.error('Error exporting data:', error);
    res.status(500).json({ error: error.message });
  }
});

// YouTube integration for content creation
app.post('/api/youtube/analyze', async (req, res) => {
  try {
    const { videoUrl, mediaIds } = req.body;
    
    if (!videoUrl || !mediaIds) {
      return res.status(400).json({ error: 'videoUrl and mediaIds required' });
    }
    
    // Get media analysis for comparison
    const { data, error } = await supabase
      .from('media')
      .select(`
        *,
        media_analysis (*)
      `)
      .in('id', mediaIds);
    
    if (error) throw error;
    
    // This would integrate with YouTube API and AI analysis
    // For now, return structured data for content creation
    const contentSuggestions = {
      videoUrl,
      relatedMedia: data,
      suggestions: {
        title: `Music Analysis: ${data.length} Tracks Compared`,
        description: `Analysis of ${data.map(m => m.name).join(', ')}`,
        tags: [...new Set(data.flatMap(m => 
          m.media_analysis?.[0]?.ai_analysis?.tags || []
        ))],
        timestamps: data.map((m, i) => ({
          time: `${i * 30}:00`,
          description: m.media_analysis?.[0]?.ai_description || m.name
        }))
      }
    };
    
    res.json(contentSuggestions);
    
  } catch (error) {
    console.error('Error analyzing for YouTube:', error);
    res.status(500).json({ error: error.message });
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('API Error:', error);
  res.status(500).json({ 
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'development' ? error.message : undefined
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Start server
app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
  console.log(`WebSocket server running on port 3002`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('Shutting down gracefully...');
  await neo4jDriver.close();
  await redisClient.disconnect();
  process.exit(0);
});
'''

# Create API Gateway files
os.makedirs('api-gateway', exist_ok=True)

with open('api-gateway/Dockerfile', 'w') as f:
    f.write(api_dockerfile)

with open('api-gateway/package.json', 'w') as f:
    f.write(api_package_json)

with open('api-gateway/server.js', 'w') as f:
    f.write(api_server)

print("API Gateway files created:")
print("- api-gateway/Dockerfile")
print("- api-gateway/package.json")
print("- api-gateway/server.js")