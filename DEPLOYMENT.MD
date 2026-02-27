### GitHub App Configuration

Web deployment uses GitHub App authentication for secure repository access:

#### 1. Create GitHub App
1. Go to https://github.com/settings/apps
2. Click "New GitHub App"
3. Configure:
   - **App name**: "Around the Grounds Deployer" (or similar)
   - **Homepage URL**: Your repository URL
   - **Repository permissions**:
     - Contents: Read & Write
     - Metadata: Read
   - **Where can this GitHub App be installed?**: Only on this account
4. **Generate private key** and download the `.pem` file
5. Note the **App ID** from the app settings page

#### 2. Install App on Repository
1. Go to your GitHub App settings
2. Click "Install App" 
3. Select your target repositories (e.g., `atg-ballard-food-trucks`, `atg-park-slope-music`, `atg-childrens-events`)
4. The installation ID will be automatically retrieved by the system

#### 3. Configure Environment Variables
```bash
# Copy template
cp .env.example .env

# Add GitHub App credentials to .env:
GITHUB_APP_ID=123456
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_APP_PRIVATE_KEY_B64=$(base64 -i path/to/your-app.private-key.pem)

# Optional: AI vision analysis
ANTHROPIC_API_KEY=your-anthropic-api-key
```

**Note:** The system includes working defaults for `GITHUB_APP_ID` and `GITHUB_CLIENT_ID`. You only need to override these if you're using a different GitHub App. The installation ID is automatically retrieved via the GitHub API - you don't need to configure it manually.

#### 4. Target Repository Setup

The system pushes a complete static website to **separate target repositories** which are served by GitHub Pages:

**Two-Repository Architecture**:
- **Source repo** (this one): Contains scraping code, parsers, site configs, per-site templates
- **Target repos**: Each site has its own target repo configured in `config/sites/<key>.json`

**Configured Target Repos**:
| Site | Target Repo |
|------|-------------|
| `ballard-food-trucks` | `jredding/atg-ballard-food-trucks` |
| `park-slope-music` | `jredding/atg-park-slope-music` |
| `childrens-events` | `jredding/atg-childrens-events` |

**Deploy a specific site**:
```bash
uv run around-the-grounds --site park-slope-music --deploy
```

**Deploy all sites**:
```bash
uv run around-the-grounds --site all --deploy
```

**Override target repo via CLI**:
```bash
uv run around-the-grounds --deploy --git-repo https://github.com/username/custom-repo.git
```

**Configuration Precedence**:
1. CLI argument (`--git-repo`)
2. Environment variable (`GIT_REPOSITORY_URL`)
3. Site config `target_repo` field

#### 5. Deployment Workflow

When you run `--deploy`, the system:
1. **Scrapes** all venue websites for the selected site
2. **Copies** site-specific templates from `public_templates/<template>/` to a temp directory
3. **Generates** web-friendly JSON data (`data.json`) in the temp directory
4. **Authenticates** using GitHub App JWT credentials
5. **git init** + **force pushes** complete website to target repository's main branch
6. **GitHub Pages** serves the site automatically from the repo root

### Temporal Workflow Execution

The system supports multiple Temporal deployment scenarios through environment-based configuration:

#### Local Development (Default)
```bash
# No configuration needed - connects to localhost:7233

# Method 1: Run worker in background (for testing)
# Start Temporal worker (run in separate terminal - runs continuously, not good for agents)
uv run python -m around_the_grounds.temporal.worker

# Method 2: Test with timeout (recommended for development and agents)
# Start workflow first, then run worker with timeout to process it
uv run python -m around_the_grounds.temporal.starter --deploy --verbose &
timeout 60s uv run python -m around_the_grounds.temporal.worker

# Execute workflow manually
uv run python -m around_the_grounds.temporal.starter --deploy --verbose

# Execute workflow with custom configuration
uv run python -m around_the_grounds.temporal.starter --config /path/to/config.json --deploy

# Execute workflow with custom ID for tracking
uv run python -m around_the_grounds.temporal.starter --workflow-id daily-update-2025 --deploy
```

**Note:** The Temporal worker runs as a foreground service and will not exit until manually stopped (Ctrl+C). For testing purposes, use `timeout 60s` to limit worker execution time, allowing enough time for the full scraping and deployment workflow (~90-60s).

#### Temporal Cloud Deployment
```bash
# Set environment variables for Temporal Cloud
export TEMPORAL_ADDRESS="your-namespace.acct.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_API_KEY="your-api-key"

# Start worker - automatically connects to Temporal Cloud (runs continuously)
uv run python -m around_the_grounds.temporal.worker

# Execute workflows - uses cloud configuration
uv run python -m around_the_grounds.temporal.starter --deploy --verbose
```

### Production Deployment via Cloud Run

The current production setup uses Google Cloud Run Jobs with Cloud Scheduler:

```bash
# 3 Cloud Run Jobs (one per site), triggered daily by Cloud Scheduler:
#   - atg-ballard-food-trucks  (8:00 AM PT daily)
#   - atg-park-slope-music     (8:15 AM ET daily)
#   - atg-childrens-events     (8:30 AM ET daily)
#
# Each job runs:
#   /bin/sh -c "/usr/local/bin/uv run around-the-grounds --site <key> --deploy"
#
# Image: us-central1-docker.pkg.dev/event-curation/around-the-grounds/app:latest
# Secrets: GITHUB_APP_PRIVATE_KEY_B64, ANTHROPIC_API_KEY (from Secret Manager)
```

**Cloud Run Workflow:**
1. **Cloud Scheduler** triggers Cloud Run Job at configured time
2. **Cloud Run** spins up container, runs scrape + deploy, exits
3. **GitHub Pages** serves updated site automatically

### Alternative: Temporal Worker + Docker

For Temporal-based scheduling with Docker and Watchtower:

1. **Code changes** → GitHub Actions → Docker Hub
2. **Watchtower** detects new image → pulls and restarts worker
3. **Temporal schedules** trigger workflows → worker executes deployment
4. **Data deploys** automatically to target repository → live website updates

#### Custom Server with mTLS
```bash
# Set environment variables for custom server with certificate authentication
export TEMPORAL_ADDRESS="your-server.example.com:7233"
export TEMPORAL_NAMESPACE="production"
export TEMPORAL_TLS_CERT="/path/to/cert.pem"
export TEMPORAL_TLS_KEY="/path/to/key.pem"

# Start worker and execute workflows
uv run python -m around_the_grounds.temporal.worker
uv run python -m around_the_grounds.temporal.starter --deploy
```

#### Environment Configuration
Create a `.env` file (based on `.env.example`) for persistent configuration:
```bash
# Copy the template
cp .env.example .env

# Edit with your Temporal configuration
# TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
# TEMPORAL_API_KEY=your-api-key
# etc.
```

#### Legacy CLI Arguments (Deprecated)
```bash
# CLI arguments still work but show deprecation warnings
uv run python -m around_the_grounds.temporal.starter --temporal-address production:7233 --deploy
# Warning: --temporal-address is deprecated, use TEMPORAL_ADDRESS environment variable
```