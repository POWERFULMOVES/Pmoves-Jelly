# Jellyfin AI Media Stack for PMOVES

This repository contains the Jellyfin AI Media Stack, a comprehensive, Docker-based media analysis and intelligence platform. It is designed to serve as a core "specialized AI muscle" within the broader [PMOVES (Powerful Moves)](https://github.com/POWERFULMOVES) autonomous agent ecosystem.

The stack ingests local media files and YouTube content, performs advanced AI-powered analysis, generates structured metadata, and creates a rich, queryable knowledge graph of your media library.

## ✨ Features

-   **AI-Powered Media Analysis**: Performs deep analysis on audio and video files, including transcription, diarization, emotion recognition, and object detection.
-   **Automated Plugin Installation**: On first launch, a script automatically installs and configures essential Jellyfin plugins for analytics, automation (webhooks), and metadata.
-   **Knowledge Graph Backend**: Uses Neo4j to store and query complex relationships between media, artists, topics, and extracted entities.
-   **Centralized Data with Supabase**: Integrates with Supabase for user data, media metadata, and vector storage, unifying it with the main PMOVES data backend.
-   **Extensible Microservice Architecture**: Built with a suite of services including the Jellyfin server, AI workers, a Redis queue, and an API gateway.
-   **Content Creation Workflows**: Provides tools and data to assist in creating new content, such as identifying key moments and generating tags from your media library.
-   **Deployment Ready**: Designed for easy deployment with Docker Compose and can be integrated with the [Cataclysm Provisioning Bundle](https://github.com/POWERFULMOVES/Cataclysm_Provisioning_Bundle) for mass deployment.

## 🚀 Getting Started

Follow these steps to get the Jellyfin AI Media Stack running on your local machine.

### Prerequisites

-   [Git](https://git-scm.com/)
-   [Docker](https://www.docker.com/products/docker-desktop/) & Docker Compose

### Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/POWERFULMOVES/Pmoves-Jelly.git
    cd Pmoves-Jelly
    ```

2.  **Navigate to the stack directory:**
    ```sh
    cd jellyfin-ai-media-stack-guide
    ```

3.  **Create your environment file:**
    Copy the template to a new `.env` file.
    ```sh
    cp .env.template .env
    ```
    Now, edit the `.env` file with your specific credentials. You **must** provide your Supabase URL and keys.

    ```dotenv
    # Supabase Configuration
    SUPABASE_URL=https://your-project.supabase.co
    SUPABASE_ANON_KEY=your-anon-key
    SUPABASE_SERVICE_KEY=your-service-role-key

    # Security (change these!)
    JWT_SECRET=your-super-secret-jwt-key
    NEO4J_PASSWORD=a-strong-password-for-neo4j
    ```

4.  **Launch the stack:**
    From the `jellyfin-ai-media-stack-guide` directory, run:
    ```sh
    docker-compose up -d
    ```

### Accessing Services

Once the containers are running, you can access the services at these URLs:

-   **Jellyfin Web UI**: `http://localhost:8096`
-   **Neo4j Browser**: `http://localhost:7474`
-   **API Gateway**: `http://localhost:3000`
-   **Dashboard**: `http://localhost:3001`

## 🔌 Automated Plugin Installation

The stack includes a script (`install_plugins.sh`) that runs automatically when the Jellyfin container starts. This script installs and configures the following essential plugins:

-   Webhook
-   Playback Reporting
-   Reports
-   Fanart
-   TMDb Box Sets
-   Trakt
-   Open Subtitles
-   LrcLib
-   Discogs

For advanced customization, you can pre-configure these plugins by placing your own configuration files in the `./jellyfin/config/plugins` directory after the first run.

## ⚙️ Advanced Deployment

This stack is designed for robust, automated deployment using the **Cataclysm Provisioning Bundle**. For detailed information on the architecture and its integration with the PMOVES ecosystem, please see the [**GEMINI.md**](./jellyfin-ai-media-stack-guide/gemini.md) guide.
