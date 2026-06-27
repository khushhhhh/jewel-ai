# Jewel AI 💎

An AI-powered luxury jewelry photo enhancement and background generation pipeline. 

Jewel AI takes raw, unedited jewelry photos and runs them through a professional studio-grade AI compositing pipeline. It isolates the product, feathers the edges, bakes in photorealistic drop shadows, and composites it seamlessly into high-end generated environments using state-of-the-art open-source AI models.

## 🌟 Features

- **Automated Background Removal:** Flawlessly isolates jewelry from raw images.
- **Smart Edge Feathering:** Softens mask boundaries to eliminate the "cutout" look.
- **Dynamic Baked Shadows:** Automatically generates and bakes warm, dispersed drop shadows (55% opacity, 20px blur) to ground the product.
- **AI Background Generation:** Uses `FLUX.1-schnell` via Hugging Face for ultra-realistic studio environments (infinity coves, marble, dark velvet, etc.).
- **Resilient Pipeline:** Built-in failovers (e.g., falls back to Pollinations.ai if Hugging Face API limits are reached).
- **Modern Dashboard:** Next.js frontend to upload, monitor job status, and view side-by-side comparisons of raw vs. enhanced images.

## 🏗️ Architecture

- **Frontend:** Next.js 14, React, Tailwind CSS, TypeScript
- **Backend API:** FastAPI, Python, SQLAlchemy
- **Database & Queue:** PostgreSQL, Redis, Celery (via Mock Async Workers for local dev)
- **Storage:** MinIO (Local S3-compatible storage)
- **AI Pipeline Tools:** Pillow (Image filtering and compositing), Hugging Face Hub (FLUX.1-schnell)

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Docker and Docker Compose
- Python 3.10+
- Node.js 18+
- [Hugging Face Access Token](https://huggingface.co/settings/tokens) (Free)

### 2. Infrastructure Setup (MinIO, Postgres, Redis)
```bash
docker compose up -d
```
*Note: This automatically provisions the local `jewel-raw-uploads` and `jewel-processed` buckets with public download policies.*

### 3. Backend Setup (FastAPI)
Navigate to the `apps/api` directory:
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your Hugging Face token: HF_TOKEN=your_token_here

# Run the API
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup (Next.js)
Navigate to the `apps/web` directory:
```bash
cd apps/web
npm install
npm run dev
```

### 5. Access the App
Open your browser and navigate to `http://localhost:3001` (or whichever port Next.js binds to) to upload your first jewelry image!

## 🧠 Pipeline Overview

1. **Masking (`masking.py`):** Uses AI to remove the background and output a transparent PNG.
2. **Cleaning (`cleaning.py`):** Applies a 1.5px Gaussian blur to the alpha channel to soften harsh edges. Applies color, contrast, and sharpness enhancements.
3. **Upscaling & Shadows (`upscaling.py`):** Bakes a 20px blurred, warm drop shadow into the transparent image before compositing.
4. **Background Gen (`background.py`):** Fetches a photorealistic background using FLUX.1-schnell and composites the shadowed product over it.

## 📝 License
MIT License
