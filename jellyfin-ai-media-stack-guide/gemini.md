# Gemini Agent Implementation Guide: Jellyfin AI Media Stack

## 1. Project Goal

The objective is to implement the fully-featured, Docker-based media analysis stack as described in `jellyfin-ai-media-stack-guide.md`. This involves orchestrating Jellyfin, Neo4j, Supabase, Redis, and custom AI/API services to create a system that can automatically analyze media files, store rich metadata and relationships, and provide an API for interaction.

## 2. Current State Analysis

The directory contains a mix of final code, Dockerfiles, and Python scripts that generate other necessary files. The core components are present but are disconnected and not structured for a direct `docker-compose up` execution.

- **`docker-compose.yml`**: A comprehensive docker-compose file exists and correctly defines the services outlined in the guide (jellyfin, neo4j, qwen-audio, audio-processor, redis, api-gateway, dashboard). However, it references build contexts (`./audio-processor`, `./api-gateway`, `./dashboard`) that do not exist in the root of the `jellyfin-ai-media-stack-guide` directory.
- **Service Code**:
    - **`main.py`**: This appears to be the heart of the `audio-processor` service. It contains logic to connect to Jellyfin, Qwen, Neo4j, and Supabase to process media files.
    - **`server.js`**: This is the implementation of the `api-gateway`. It defines the REST API endpoints described in the guide.
    - **`script_*.py` files**: These are code-generation scripts. They create the `docker-compose.yml`, the service directories (`audio-processor`, `api-gateway`), and the database setup files. This is redundant as the final files are also present.
- **Configuration**:
    - **`supabase-setup.sql` & `neo4j-setup.cypher`**: These files contain the necessary database schemas and are complete.
    - **`setup.sh`**: A setup script exists to create directories and initialize the system. It incorrectly tries to build docker images from contexts that don't exist at the root.
- **Inconsistencies & Missing Pieces**:
    - The primary issue is the file and directory structure. The `docker-compose.yml` and `setup.sh` assume a project structure (e.g., `./audio-processor/Dockerfile`) that isn't present. The necessary code (`main.py`, `Dockerfile`, `server.js`, etc.) is all in the parent directory instead of organized into the service subdirectories (`audio-processor`, `api-gateway`).
    - The `dashboard` service is defined in the `docker-compose.yml` but no corresponding code, Dockerfile, or generator script exists for it. This is a missing component.

## 3. Implementation Plan for Agent

The agent must restructure the project, consolidate the code, and create the missing dashboard component to make the stack deployable and functional.

**Step 1: Clean Up and Restructure Project**

1.  **Delete Redundant Scripts**: Remove the generator scripts: `script.py`, `script_1.py`, `script_2.py`, `script_3.py`. The final code they generate is already present.
2.  **Create Service Directories**: Create the following directories:
    - `audio-processor`
    - `api-gateway`
    - `dashboard`
3.  **Move Files into Service Directories**:
    - **`audio-processor`**: Move `main.py`, `Dockerfile`, `entrypoint.sh`, and `requirements.txt` into the `audio-processor/` directory.
    - **`api-gateway`**: Move `server.js`, `Dockerfile_1` (and rename it to `Dockerfile`), and `package.json` into the `api-gateway/` directory.
4.  **Verify Dockerfile Paths**: Ensure the `build.context` paths in the `docker-compose.yml` correctly point to the newly created service directories.

**Step 2: Implement the Missing Dashboard Service**

1.  **Create Dashboard Files**: Inside the `dashboard/` directory, create the following files:
    - **`Dockerfile`**: A simple Nginx or Node-based server to serve static files.
    - **`package.json`**: With dependencies for a simple React application (e.g., `react`, `react-dom`).
    - **`src/App.js`**: A basic React component that displays a title like "Media Analysis Dashboard" and has placeholders for future analytics. It should attempt to connect to the `/api/analytics` endpoint from the gateway and display the raw JSON.
    - **`public/index.html`**: A basic HTML file for the React app.

**Step 3: Refine Configuration and Setup**

1.  **Update `setup.sh`**:
    - Remove the `docker build` commands, as `docker-compose up --build` will handle this.
    - Ensure the directory creation logic matches the final required structure.
    - Correct the `cypher-shell` command to run against the Docker container, not a local install, or instruct the user to run it via the Neo4j browser. Example: `docker-compose exec neo4j cypher-shell -u neo4j -p mediapassword123 < neo4j-setup.cypher`.
2.  **Final Review**: Read through the `docker-compose.yml`, all `Dockerfile`s, and the `setup.sh` script one last time to ensure all paths and commands are consistent with the new, organized project structure.

**Step 4: Final Instructions**

Provide the user with the final commands to run the stack:
1.  `./setup.sh` (after making it executable with `chmod +x setup.sh`).
2.  Edit the `.env` file with their credentials.
3.  `docker-compose up --build -d`.
4.  Provide URLs for Jellyfin, the Neo4j Browser, and the new Dashboard.
