# Deployment Guide - Hybrid Approach

This guide walks you through deploying the Legal Multi-Agent RAG app using:
- **Frontend**: Vercel (Next.js)
- **Backend**: Railway (FastAPI)
- **Infrastructure**: Managed services (Qdrant Cloud, Supabase, Upstash)

---

## Prerequisites

1. GitHub account with this repository
2. Vercel account (free tier available)
3. Railway account (free trial, then $5/month)
4. Accounts for managed services (all have free tiers)

---

## Step 1: Set Up Managed Infrastructure Services

### 1.1 Qdrant Cloud (Vector Database)

1. Go to https://cloud.qdrant.io
2. Sign up for free account
3. Create a new cluster
4. Copy the cluster URL (e.g., `https://xxxxx-xxxxx.qdrant.io`)
5. Note your API key

**Environment variable needed:**
```
QDRANT_URL=https://xxxxx-xxxxx.qdrant.io
QDRANT_API_KEY=your-api-key
```

### 1.2 Supabase (PostgreSQL Database)

1. Go to https://supabase.com
2. Create a new project
3. Wait for database to provision (~2 minutes)
4. Go to Settings → Database
5. Copy the connection string (use "Connection pooling" mode)

**Environment variable needed:**
```
POSTGRES_DSN=postgresql+asyncpg://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### 1.3 Upstash (Redis)

1. Go to https://upstash.com
2. Create a new Redis database
3. Choose a region close to your backend
4. Copy the REST URL

**Environment variable needed:**
```
REDIS_URL=redis://default:password@xxxxx.upstash.io:6379
```

---

## Step 2: Deploy Backend to Railway

### 2.1 Prepare Backend

The following files are already created:
- `Procfile` (in repo root) - Tells Railway how to run the app
- `railway.json` - Railway build configuration
- `requirements.txt` (in repo root) - Points to backend dependencies (helps Railway detect Python)
- `runtime.txt` (in repo root) - Python version
- `backend/setup.py` - Package configuration for editable install
- `backend/requirements.txt` - Python dependencies

### 2.2 Deploy on Railway

1. Go to https://railway.app
2. Sign up/login (GitHub OAuth recommended)
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your repository
6. Railway will auto-detect it's a Python project

### 2.3 Configure Railway

1. **Set Root Directory:**
   - Go to Settings → Source
   - **Leave Root Directory EMPTY** (use repository root, not `backend`)
   - Railway will use the `Procfile` in the repo root which handles the backend directory

2. **Add PostgreSQL Service (Recommended):**
   - In your Railway project, click "+ New" → "Database" → "Add PostgreSQL"
   - Railway will automatically create a PostgreSQL database
   - Railway will automatically set the `DATABASE_URL` environment variable
   - **Important**: You need to map `DATABASE_URL` to `POSTGRES_DSN`:
     - Go to your PostgreSQL service → Variables tab
     - Copy the `DATABASE_URL` value (it will be in format `postgresql://user:pass@host:port/db`)
     - Go to your backend service → Variables tab
     - Add: `POSTGRES_DSN` = (paste the DATABASE_URL value)
     - **Note**: The code automatically converts `postgresql://` to `postgresql+asyncpg://` if needed
   - **Alternative**: Use Supabase (see Step 1.2) and set `POSTGRES_DSN` manually

3. **Add Environment Variables:**
   - Go to your backend service → Variables tab
   - Add all these variables:

```
OPENAI_API_KEY=sk-your-openai-key
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large
QDRANT_URL=https://your-cluster.qdrant.io
POSTGRES_DSN=<use DATABASE_URL from PostgreSQL service, or Supabase connection string>
REDIS_URL=redis://default:pass@host:6379
AUTH_SECRET=generate-a-random-secret-key-here
LOG_LEVEL=INFO
AUTH_OPTIONAL=false
```

   **Note**: If you added PostgreSQL via Railway, the `DATABASE_URL` is auto-set. You need to copy it to `POSTGRES_DSN`.

4. **Set Port (if needed):**
   - Railway auto-assigns PORT, but ensure it's set
   - The Procfile uses `$PORT` automatically

5. **Deploy:**
   - Railway will automatically deploy on push
   - Or click "Deploy" button
   - Wait for build to complete (~3-5 minutes)

6. **Get Backend URL:**
   - Once deployed, go to Settings → Networking
   - Generate a public domain (e.g., `legal-backend.railway.app`)
   - Copy this URL - you'll need it for frontend

### 2.4 Run Database Migrations

After first deployment, you may need to run migrations:

1. In Railway, go to your service
2. Click "Deployments" → Latest deployment
3. Click "View Logs"
4. Or use Railway CLI:
   ```bash
   railway run alembic upgrade head
   ```

---

## Step 3: Deploy Frontend to Vercel

### 3.1 Prepare Frontend

The following files are already created:
- `vercel.json` - Vercel configuration

### 3.2 Deploy on Vercel

**Option A: Using Vercel CLI (Recommended)**

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Login:
   ```bash
   vercel login
   ```

3. Deploy:
   ```bash
   cd frontend
   vercel
   ```
   - Follow prompts
   - Set root directory: `frontend`
   - Don't override build settings (they're in vercel.json)

**Option B: Using Vercel Dashboard**

1. Go to https://vercel.com
2. Sign up/login (GitHub OAuth recommended)
3. Click "Add New Project"
4. Import your GitHub repository
5. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Build Command**: `pnpm install && pnpm build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)

### 3.3 Configure Environment Variables

1. In Vercel project dashboard, go to Settings → Environment Variables
2. Add:

```
NEXT_PUBLIC_API_BASE_URL=https://your-backend.railway.app
```

Replace `your-backend.railway.app` with your actual Railway backend URL.

3. **Important**: After adding env vars, redeploy:
   - Go to Deployments
   - Click "..." on latest deployment
   - Click "Redeploy"

---

## Step 4: Test Deployment

### 4.1 Test Backend

1. Visit: `https://your-backend.railway.app/health`
2. Should return: `{"status":"ok"}`

### 4.2 Test Frontend

1. Visit your Vercel URL (e.g., `https://legal-multi-agent.vercel.app`)
2. Should load the chat interface
3. Try uploading a document
4. Try asking a question

### 4.3 Verify CORS

If you get CORS errors:
- Backend already allows all origins (`allow_origins=["*"]`)
- For production, update `backend/api/main.py` to restrict origins:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://your-frontend.vercel.app"],
      ...
  )
  ```

---

## Step 5: Post-Deployment Checklist

- [ ] Backend health check returns 200
- [ ] Frontend loads without errors
- [ ] Can upload documents via frontend
- [ ] Can ask questions and get responses
- [ ] Citations appear in responses
- [ ] Check Railway logs for any errors
- [ ] Check Vercel logs for any errors

---

## Troubleshooting

### Backend Issues

**Port binding error:**
- Ensure `Procfile` uses `$PORT`
- Railway auto-assigns PORT

**Database connection error:**
- Verify `POSTGRES_DSN` is correct
- Use connection pooling URL from Supabase
- Check if database is accessible (Supabase dashboard)

**Qdrant connection error:**
- Verify `QDRANT_URL` includes protocol (`https://`)
- Check API key is correct
- Ensure cluster is running (Qdrant Cloud dashboard)

**Redis connection error:**
- Verify `REDIS_URL` format
- Check Upstash database is active

### Frontend Issues

**API calls failing:**
- Verify `NEXT_PUBLIC_API_BASE_URL` is set correctly
- Check browser console for CORS errors
- Ensure backend URL is accessible

**Build errors:**
- Check Vercel build logs
- Ensure `pnpm` is used (not npm)
- Verify all dependencies in `package.json`

---

## Cost Estimate

**Free Tier Available:**
- Vercel: Free (Hobby plan) - unlimited deployments
- Railway: $5/month (or free trial credits)
- Qdrant Cloud: Free tier (1GB storage)
- Supabase: Free tier (500MB database, 2GB bandwidth)
- Upstash: Free tier (10K commands/day, 256MB storage)

**Total**: ~$5/month (or free with trials)

---

## Updating Deployment

### Backend Updates
1. Push changes to GitHub
2. Railway auto-deploys on push
3. Check deployment logs

### Frontend Updates
1. Push changes to GitHub
2. Vercel auto-deploys on push
3. Check deployment logs

---

## Security Notes

1. **Environment Variables**: Never commit `.env` files
2. **API Keys**: Store in Railway/Vercel environment variables
3. **CORS**: Update to restrict origins in production
4. **Auth**: The current auth is a stub - implement proper OAuth for production
5. **HTTPS**: Both Vercel and Railway provide HTTPS automatically

---

## Support

- Railway Docs: https://docs.railway.app
- Vercel Docs: https://vercel.com/docs
- Qdrant Cloud: https://qdrant.tech/documentation/cloud/
- Supabase Docs: https://supabase.com/docs
- Upstash Docs: https://docs.upstash.com

