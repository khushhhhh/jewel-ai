/**
 * Jewel AI — API Client
 * 
 * Typed fetch wrapper for all backend endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Demo workspace/user IDs (from seed script — will be replaced by auth)
let WORKSPACE_ID = '';
let USER_ID = '';

export function setAuthContext(workspaceId: string, userId: string) {
  WORKSPACE_ID = workspaceId;
  USER_ID = userId;
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Workspace-Id': WORKSPACE_ID,
    'X-User-Id': USER_ID,
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || 'Request failed');
  }

  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// ── Types ─────────────────────────────────────────────────────

export interface UploadResponse {
  asset_id: string;
  presigned_put_url: string;
  s3_key: string;
  expires_in: number;
}

export interface ProcessResponse {
  job_id: string;
  status: string;
  credits_charged: number;
  estimated_completion_seconds: number;
}

export interface StageProgress {
  stage: string;
  completed: boolean;
  s3_url: string | null;
}

export interface StatusResponse {
  job_id: string;
  status: string;
  progress_pct: number;
  stages: StageProgress[];
  final_cdn_url: string | null;
  variants?: { variant_name: string; prompt_used: string; s3_key: string; cdn_url: string }[] | null;
  failure_reason: string | null;
  failed_step: string | null;
}

export interface ImageItem {
  id: string;
  status: string;
  raw_s3_key: string;
  background_preset: string | null;
  cdn_url: string | null;
  credits_charged: number | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface WorkspaceInfo {
  id: string;
  name: string;
  slug: string;
  plan_tier: string;
  credit_balance: number;
  user_id: string | null;
}

// ── API Methods ───────────────────────────────────────────────

export const api = {
  /** Create a workspace (dev/onboarding) */
  async createWorkspace(data: {
    name: string;
    slug: string;
    owner_email: string;
  }) {
    return apiFetch<{
      workspace_id: string;
      user_id: string;
      name: string;
      slug: string;
      plan_tier: string;
      credit_balance: number;
    }>('/api/v1/workspaces/', { method: 'POST', body: JSON.stringify(data) });
  },

  /** Get workspace by slug */
  async getWorkspace(slug: string) {
    return apiFetch<WorkspaceInfo>(`/api/v1/workspaces/${slug}`);
  },

  /** Request a presigned S3 upload URL */
  async requestUpload(data: {
    filename: string;
    content_type: string;
    file_size_bytes: number;
  }) {
    return apiFetch<UploadResponse>('/api/v1/images/upload', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** Upload file directly through API proxy (avoids MinIO CORS in local dev) */
  async uploadDirect(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {
      'X-Workspace-Id': WORKSPACE_ID,
      'X-User-Id': USER_ID,
    };

    const res = await fetch(`${API_BASE}/api/v1/images/upload-direct`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, error.detail || 'Upload failed');
    }

    return res.json() as Promise<{ asset_id: string; s3_key: string }>;
  },

  /** Submit image for AI processing */
  async processImage(data: {
    asset_id: string;
    background_preset: string;
    output_aspect_ratios?: string[];
    output_resolution_tier?: string;
  }) {
    return apiFetch<ProcessResponse>('/api/v1/images/process', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** Get job status */
  async getStatus(jobId: string) {
    return apiFetch<StatusResponse>(`/api/v1/images/status/${jobId}`);
  },

  /** List all images for workspace */
  async listImages(limit = 50, offset = 0) {
    return apiFetch<{ items: ImageItem[]; total: number }>(
      `/api/v1/images/?limit=${limit}&offset=${offset}`,
    );
  },

  /** Health check */
  async health() {
    return apiFetch<{ status: string }>('/health');
  },
};

// ── Polling Helper ────────────────────────────────────────────

export function pollJobStatus(
  jobId: string,
  onUpdate: (status: StatusResponse) => void,
  intervalMs = 3000,
  maxAttempts = 100,
): () => void {
  let attempts = 0;
  let timeoutId: ReturnType<typeof setTimeout>;
  let cancelled = false;

  const poll = async () => {
    if (cancelled) return;
    try {
      const status = await api.getStatus(jobId);
      onUpdate(status);

      if (status.status === 'COMPLETED' || status.status === 'FAILED') {
        return; // Stop polling
      }
    } catch (err) {
      console.error('Poll error:', err);
    }

    attempts++;
    if (attempts < maxAttempts && !cancelled) {
      // Exponential backoff: 3s → 4.5s → 6.75s → max 10s
      const nextInterval = Math.min(intervalMs * Math.pow(1.5, Math.floor(attempts / 5)), 10000);
      timeoutId = setTimeout(poll, nextInterval);
    }
  };

  poll();

  return () => {
    cancelled = true;
    clearTimeout(timeoutId);
  };
}
