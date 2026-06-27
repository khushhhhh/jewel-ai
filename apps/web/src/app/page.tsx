'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api, setAuthContext, pollJobStatus } from '@/lib/api';
import type { StatusResponse, ImageItem } from '@/lib/api';
import {
  BACKGROUND_PRESETS,
  ASPECT_RATIOS,
  RESOLUTION_TIERS,
  STATUS_CONFIG,
  PIPELINE_STAGES,
  ACCEPTED_FILE_TYPES,
  MAX_FILE_SIZE,
} from '@/lib/constants';

type Page = 'dashboard' | 'upload' | 'gallery' | 'jobs' | 'settings';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info';
}

export default function Home() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [workspaceId, setWorkspaceId] = useState('');
  const [userId, setUserId] = useState('');
  const [creditBalance, setCreditBalance] = useState(0);
  const [workspaceName, setWorkspaceName] = useState('');
  const [images, setImages] = useState<ImageItem[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('pure_white_ecommerce');
  const [selectedAspectRatios, setSelectedAspectRatios] = useState<string[]>(['1:1']);
  const [selectedResolution, setSelectedResolution] = useState('standard');
  const [isDragging, setIsDragging] = useState(false);

  // Job tracking state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobStatus, setActiveJobStatus] = useState<StatusResponse | null>(null);
  const cancelPollRef = useRef<(() => void) | null>(null);

  const addToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  // Initialize workspace
  useEffect(() => {
    const init = async () => {
      try {
        // Try to get demo workspace
        const ws = await api.getWorkspace('demo-studio');
        setWorkspaceId(ws.id);
        setWorkspaceName(ws.name);
        setCreditBalance(ws.credit_balance);

        // Get first user (demo)
        setAuthContext(ws.id, ws.user_id || ws.id); // Temporary — will be replaced

        // Try to fetch user ID from workspace
        setUserId(ws.user_id || ws.id);
        setAuthContext(ws.id, ws.user_id || ws.id);

        // Load images
        const result = await api.listImages();
        setImages(result.items);
      } catch {
        // Workspace doesn't exist yet — create it
        try {
          const created = await api.createWorkspace({
            name: 'Demo Jewelry Studio',
            slug: 'demo-studio',
            owner_email: 'demo@jewel-ai.dev',
          });
          setWorkspaceId(created.workspace_id);
          setUserId(created.user_id);
          setWorkspaceName(created.name);
          setCreditBalance(created.credit_balance);
          setAuthContext(created.workspace_id, created.user_id);
        } catch {
          // API not running — use mock data for UI development
          setWorkspaceId('mock-workspace');
          setUserId('mock-user');
          setWorkspaceName('Demo Studio');
          setCreditBalance(500);
        }
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (cancelPollRef.current) cancelPollRef.current();
    };
  }, []);

  const refreshImages = async () => {
    try {
      const result = await api.listImages();
      setImages(result.items);
    } catch {
      // Silent fail
    }
  };

  // ── Upload Flow ─────────────────────────────────────────────
  const handleFileSelect = (file: File) => {
    if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
      addToast('Invalid file type. Accepted: JPEG, PNG, HEIC, WebP', 'error');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      addToast('File too large. Maximum size: 50MB', 'error');
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleUploadAndProcess = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadProgress(0);

    try {
      // Step 1: Upload file through API proxy to MinIO
      setUploadProgress(10);
      const upload = await api.uploadDirect(selectedFile);
      setUploadProgress(50);

      // Step 2: Submit for processing
      const job = await api.processImage({
        asset_id: upload.asset_id,
        background_preset: selectedPreset,
        output_aspect_ratios: selectedAspectRatios,
        output_resolution_tier: selectedResolution,
      });
      setUploadProgress(70);
      setCreditBalance(prev => prev - job.credits_charged);

      addToast(`Processing started! ${job.credits_charged} credits charged.`, 'success');

      // Step 4: Start polling for status
      setActiveJobId(job.job_id);
      setCurrentPage('jobs');

      if (cancelPollRef.current) cancelPollRef.current();
      cancelPollRef.current = pollJobStatus(job.job_id, (status) => {
        setActiveJobStatus(status);
        if (status.status === 'COMPLETED') {
          addToast('Image processing complete! ✨', 'success');
          refreshImages();
        } else if (status.status === 'FAILED') {
          addToast(`Processing failed: ${status.failure_reason || 'Unknown error'}`, 'error');
        }
      });

      setUploadProgress(100);
      setSelectedFile(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      addToast(message, 'error');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const toggleAspectRatio = (ratio: string) => {
    setSelectedAspectRatios(prev =>
      prev.includes(ratio) ? prev.filter(r => r !== ratio) : [...prev, ratio]
    );
  };

  // ── Credit cost preview ─────────────────────────────────────
  const resMultiplier = { standard: 1, hd: 1.5, '4k': 2.5 }[selectedResolution] || 1;
  const bgMultiplier = { pure_white_ecommerce: 1, marble_luxury: 1.3, velvet_dark: 1.3, outdoor_editorial: 1.5 }[selectedPreset] || 1;
  const estimatedCredits = Math.ceil(resMultiplier * bgMultiplier * selectedAspectRatios.length);

  // ── Render ──────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>💎</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Loading Jewel AI...</div>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ── Sidebar ──────────────────────────────────────────── */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">💎</div>
          <span className="sidebar-logo-text">Jewel AI</span>
        </div>

        <nav className="sidebar-nav">
          {([
            { page: 'dashboard' as Page, icon: '📊', label: 'Dashboard' },
            { page: 'upload' as Page, icon: '📤', label: 'Upload' },
            { page: 'gallery' as Page, icon: '🖼️', label: 'Gallery' },
            { page: 'jobs' as Page, icon: '⚡', label: 'Jobs' },
            { page: 'settings' as Page, icon: '⚙️', label: 'Settings' },
          ]).map(({ page, icon, label }) => (
            <button
              key={page}
              className={`sidebar-link ${currentPage === page ? 'active' : ''}`}
              onClick={() => { setCurrentPage(page); setSidebarOpen(false); }}
            >
              <span className="sidebar-link-icon">{icon}</span>
              {label}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: 'auto', paddingTop: 'var(--space-lg)', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>Workspace</div>
          <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>{workspaceName || 'Demo Studio'}</div>
        </div>
      </aside>

      {/* ── Header ───────────────────────────────────────────── */}
      <header className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{ display: 'none' }}
            id="mobile-menu-toggle"
          >
            ☰
          </button>
          <h1 className="header-title">
            {currentPage === 'dashboard' && 'Dashboard'}
            {currentPage === 'upload' && 'Upload & Process'}
            {currentPage === 'gallery' && 'Gallery'}
            {currentPage === 'jobs' && 'Job Status'}
            {currentPage === 'settings' && 'Settings'}
          </h1>
        </div>

        <div className="header-actions">
          <div className="credit-badge">
            <span className="credit-badge-icon">💰</span>
            <span>{creditBalance} credits</span>
          </div>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => setCurrentPage('upload')}
          >
            + New Upload
          </button>
        </div>
      </header>

      {/* ── Main Content ─────────────────────────────────────── */}
      <main className="main-content">
        {/* ── DASHBOARD ────────────────────────────────────── */}
        {currentPage === 'dashboard' && (
          <div className="animate-fade-in">
            <div className="stats-grid stagger-children">
              <div className="stat-card">
                <div className="stat-label">Total Images</div>
                <div className="stat-value">{images.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Processing</div>
                <div className="stat-value">
                  {images.filter(i => !['COMPLETED', 'FAILED', 'UPLOADED'].includes(i.status)).length}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Completed</div>
                <div className="stat-value">
                  {images.filter(i => i.status === 'COMPLETED').length}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Credits Remaining</div>
                <div className="stat-value" style={{ color: 'var(--accent-gold)' }}>
                  {creditBalance}
                </div>
              </div>
            </div>

            <div className="section-header">
              <div>
                <h2 className="section-title">Recent Jobs</h2>
                <p className="section-subtitle">Your latest image processing jobs</p>
              </div>
              <button className="btn btn-primary" onClick={() => setCurrentPage('upload')}>
                + Upload New
              </button>
            </div>

            {images.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: 'var(--space-3xl)' }}>
                <div className="empty-state">
                  <div className="empty-state-icon">💎</div>
                  <div className="empty-state-title">No images yet</div>
                  <div className="empty-state-desc">
                    Upload your first jewelry photo to see AI-powered enhancement in action.
                  </div>
                  <button className="btn btn-primary btn-lg" onClick={() => setCurrentPage('upload')}>
                    Upload Your First Image
                  </button>
                </div>
              </div>
            ) : (
              <div className="job-list">
                {images.slice(0, 10).map(image => {
                  const config = STATUS_CONFIG[image.status] || STATUS_CONFIG.UPLOADED;
                  return (
                    <div key={image.id} className="job-row" onClick={() => {
                      setActiveJobId(image.id);
                      setCurrentPage('jobs');
                    }}>
                      <div className="job-thumb" style={{ overflow: 'hidden', borderRadius: '4px', position: 'relative' }}>
                        {image.status === 'COMPLETED' && image.cdn_url ? (
                          <img src={image.cdn_url} alt="thumbnail" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                          <div style={{ width: '100%', height: '100%', background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                            {config.icon}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="job-name">{image.raw_s3_key?.split('/').pop() || 'Untitled'}</div>
                      </div>
                      <div className="job-preset" style={{ textTransform: 'capitalize' }}>
                        {image.background_preset?.replace(/_/g, ' ') || '—'}
                      </div>
                      <span className={`badge ${config.badgeClass}`}>
                        {config.label}
                      </span>
                      <div className="job-date">
                        {image.created_at ? new Date(image.created_at).toLocaleDateString() : '—'}
                      </div>
                      <div className="job-credits">
                        {image.credits_charged ? `${image.credits_charged} cr` : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── UPLOAD ───────────────────────────────────────── */}
        {currentPage === 'upload' && (
          <div className="animate-fade-in">
            <div style={{ maxWidth: '800px', margin: '0 auto' }}>
              {/* Upload Zone */}
              <div
                className={`upload-zone ${isDragging ? 'dragging' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById('file-input')?.click()}
              >
                <input
                  id="file-input"
                  type="file"
                  accept={ACCEPTED_FILE_TYPES.join(',')}
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
                {selectedFile ? (
                  <div style={{ position: 'relative', zIndex: 1 }}>
                    <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>✅</div>
                    <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                      {selectedFile.name}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB · {selectedFile.type}
                    </div>
                  </div>
                ) : (
                  <div style={{ position: 'relative', zIndex: 1 }}>
                    <div className="upload-icon">💎</div>
                    <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                      Drop your jewelry photo here
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-tertiary)' }}>
                      or click to browse · JPEG, PNG, HEIC, WebP · Max 50MB
                    </div>
                  </div>
                )}
              </div>

              {/* Upload Progress */}
              {isUploading && (
                <div style={{ marginTop: 'var(--space-lg)' }}>
                  <div className="progress-bar">
                    <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                  </div>
                  <div style={{ textAlign: 'center', marginTop: 'var(--space-sm)', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                    {uploadProgress < 50 ? 'Uploading to S3...' : uploadProgress < 70 ? 'Submitting for processing...' : 'Processing started!'}
                  </div>
                </div>
              )}

              {selectedFile && !isUploading && (
                <>
                  {/* Background Preset Selector */}
                  <div style={{ marginTop: 'var(--space-xl)' }}>
                    <h3 style={{ marginBottom: 'var(--space-md)' }}>Background Style</h3>
                    <div className="preset-grid">
                      {BACKGROUND_PRESETS.map(preset => (
                        <div
                          key={preset.id}
                          className={`preset-card ${selectedPreset === preset.id ? 'selected' : ''}`}
                          onClick={() => setSelectedPreset(preset.id)}
                        >
                          <div style={{ position: 'absolute', inset: 0, background: preset.gradient }} />
                          <div className="preset-card-overlay">
                            <div>
                              <div className="preset-card-label">{preset.name}</div>
                              <div style={{ fontSize: '0.6875rem', color: 'rgba(255,255,255,0.7)', marginTop: '2px' }}>
                                {preset.description}
                              </div>
                            </div>
                          </div>
                          {selectedPreset === preset.id && (
                            <div style={{ position: 'absolute', top: '8px', right: '8px', width: '20px', height: '20px', borderRadius: '50%', background: 'var(--accent-gold)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', color: 'var(--text-inverse)' }}>
                              ✓
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Aspect Ratio Selector */}
                  <div style={{ marginTop: 'var(--space-xl)' }}>
                    <h3 style={{ marginBottom: 'var(--space-md)' }}>Output Aspect Ratios</h3>
                    <div className="aspect-ratio-grid">
                      {ASPECT_RATIOS.map(ratio => (
                        <div
                          key={ratio.id}
                          className={`aspect-card ${selectedAspectRatios.includes(ratio.id) ? 'selected' : ''}`}
                          onClick={() => toggleAspectRatio(ratio.id)}
                        >
                          <div className={`aspect-preview ${ratio.cssClass}`} />
                          <div className="aspect-label">{ratio.label}</div>
                          <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>{ratio.description}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Resolution Tier */}
                  <div style={{ marginTop: 'var(--space-xl)' }}>
                    <h3 style={{ marginBottom: 'var(--space-md)' }}>Resolution</h3>
                    <div className="chip-group">
                      {RESOLUTION_TIERS.map(tier => (
                        <button
                          key={tier.id}
                          className={`chip ${selectedResolution === tier.id ? 'selected' : ''}`}
                          onClick={() => setSelectedResolution(tier.id)}
                        >
                          {tier.name} ({tier.description}) · {tier.multiplier}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Credit Cost Preview & Submit */}
                  <div className="card" style={{ marginTop: 'var(--space-xl)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
                        Estimated Cost
                      </div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-gold)', fontFamily: 'var(--font-heading)' }}>
                        {estimatedCredits} credit{estimatedCredits !== 1 ? 's' : ''}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                        {selectedAspectRatios.length} ratio{selectedAspectRatios.length !== 1 ? 's' : ''} × {selectedResolution} resolution
                      </div>
                    </div>
                    <button
                      className="btn btn-primary btn-lg"
                      onClick={handleUploadAndProcess}
                      disabled={estimatedCredits > creditBalance || selectedAspectRatios.length === 0}
                      style={{
                        opacity: (estimatedCredits > creditBalance || selectedAspectRatios.length === 0) ? 0.5 : 1,
                        cursor: (estimatedCredits > creditBalance || selectedAspectRatios.length === 0) ? 'not-allowed' : 'pointer',
                      }}
                    >
                      ✨ Enhance Image
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── GALLERY ──────────────────────────────────────── */}
        {currentPage === 'gallery' && (
          <div className="animate-fade-in">
            <div className="section-header">
              <div>
                <h2 className="section-title">Gallery</h2>
                <p className="section-subtitle">Your processed jewelry images</p>
              </div>
              <button className="btn btn-secondary" onClick={refreshImages}>
                ↻ Refresh
              </button>
            </div>

            {images.filter(i => i.status === 'COMPLETED').length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: 'var(--space-3xl)' }}>
                <div className="empty-state">
                  <div className="empty-state-icon">🖼️</div>
                  <div className="empty-state-title">No completed images</div>
                  <div className="empty-state-desc">
                    Your processed images will appear here once they are complete.
                  </div>
                  <button className="btn btn-primary" onClick={() => setCurrentPage('upload')}>
                    Upload an Image
                  </button>
                </div>
              </div>
            ) : (
              <div className="gallery-grid">
                {images.filter(i => i.status === 'COMPLETED').map(image => (
                  <div key={image.id} className="gallery-item" onClick={() => {
                    setActiveJobId(image.id);
                    setCurrentPage('jobs');
                  }}>
                    <div className="gallery-item-image" style={{ overflow: 'hidden', position: 'relative' }}>
                      {image.cdn_url ? (
                        <img src={image.cdn_url} alt={image.raw_s3_key?.split('/').pop() || 'Enhanced jewelry'} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <div style={{ width: '100%', height: '100%', background: 'var(--gradient-card)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '3rem' }}>
                          ✨
                        </div>
                      )}
                    </div>
                    <div className="gallery-item-info">
                      <div className="gallery-item-title">
                        {image.raw_s3_key?.split('/').pop() || 'Untitled'}
                      </div>
                      <div className="gallery-item-meta">
                        <span style={{ textTransform: 'capitalize' }}>
                          {image.background_preset?.replace(/_/g, ' ') || '—'}
                        </span>
                        <span className="badge badge-completed">Complete</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── JOBS ─────────────────────────────────────────── */}
        {currentPage === 'jobs' && (
          <div className="animate-fade-in">
            {activeJobId && activeJobStatus ? (
              <div>
                <button className="btn btn-ghost" onClick={() => { setActiveJobId(null); setActiveJobStatus(null); }} style={{ marginBottom: 'var(--space-lg)' }}>
                  ← Back to all jobs
                </button>

                <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-lg)' }}>
                    <div>
                      <h2 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>Job Status</h2>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                        {activeJobId}
                      </div>
                    </div>
                    <span className={`badge ${(STATUS_CONFIG[activeJobStatus.status] || STATUS_CONFIG.PROCESSING).badgeClass}`}>
                      {(STATUS_CONFIG[activeJobStatus.status] || STATUS_CONFIG.PROCESSING).label}
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div style={{ marginBottom: 'var(--space-xl)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Progress</span>
                      <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent-gold)' }}>{activeJobStatus.progress_pct}%</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${activeJobStatus.progress_pct}%` }} />
                    </div>
                  </div>

                  {/* Pipeline Visualization */}
                  <div className="pipeline">
                    {PIPELINE_STAGES.map((stage, idx) => {
                      const stageStatus = activeJobStatus.stages.find(s => s.stage === stage.key);
                      const isActive = activeJobStatus.status === stage.key;
                      const isCompleted = stageStatus?.completed || false;
                      const isFailed = activeJobStatus.status === 'FAILED' && activeJobStatus.failed_step === stage.key.toLowerCase();

                      return (
                        <div key={stage.key} style={{ display: 'contents' }}>
                          <div className={`pipeline-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${isFailed ? 'failed' : ''}`}>
                            <div className="pipeline-node">
                              {isCompleted ? '✓' : isFailed ? '✗' : stage.icon}
                            </div>
                            <div className="pipeline-label">
                              {stage.label}
                              <div style={{ fontSize: '0.625rem', opacity: 0.7, marginTop: '2px' }}>{stage.description}</div>
                            </div>
                          </div>
                          {idx < PIPELINE_STAGES.length - 1 && (
                            <div className={`pipeline-connector ${isCompleted ? 'completed' : ''} ${isActive ? 'active' : ''}`} />
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Failure Info */}
                  {activeJobStatus.status === 'FAILED' && (
                    <div style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-md)', background: 'rgba(239, 68, 68, 0.1)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-failed)', marginBottom: '4px' }}>
                        Failed at: {activeJobStatus.failed_step || 'Unknown'}
                      </div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        {activeJobStatus.failure_reason || 'No details available'}
                      </div>
                    </div>
                  )}

                  {/* Final result */}
                  {(() => {
                    const currentImageItem = images.find(img => img.id === activeJobId);
                    const rawUrl = currentImageItem?.raw_s3_key ? `http://localhost:9000/jewel-raw-uploads/${currentImageItem.raw_s3_key}` : null;
                    return (
                      <>
                        {activeJobStatus.status === 'COMPLETED' && activeJobStatus.final_cdn_url && (
                          <div style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-md)', background: 'rgba(52, 211, 153, 0.1)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(52, 211, 153, 0.2)' }}>
                            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-completed)', marginBottom: '4px' }}>
                              ✨ Enhancement Complete
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                              CDN URL: <a href={activeJobStatus.final_cdn_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-gold)', textDecoration: 'underline' }}>{activeJobStatus.final_cdn_url}</a>
                            </div>
                          </div>
                        )}

                        {(rawUrl || activeJobStatus.final_cdn_url) && (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-lg)', marginTop: 'var(--space-xl)' }}>
                            {rawUrl && (
                              <div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.05em' }}>ORIGINAL IMAGE</div>
                                <div style={{ height: '300px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <img src={rawUrl} alt="Original raw upload" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                                </div>
                              </div>
                            )}
                            {activeJobStatus.status === 'COMPLETED' && activeJobStatus.final_cdn_url && (
                              <div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent-gold)', marginBottom: '8px', fontWeight: 600, letterSpacing: '0.05em' }}>ENHANCED BY JEWEL AI</div>
                                <div style={{ height: '300px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', border: '1px solid var(--accent-gold)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                  <img src={activeJobStatus.final_cdn_url} alt="Enhanced output" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              </div>
            ) : (
              <>
                <div className="section-header">
                  <div>
                    <h2 className="section-title">All Jobs</h2>
                    <p className="section-subtitle">Track your image processing pipeline</p>
                  </div>
                  <button className="btn btn-secondary" onClick={refreshImages}>
                    ↻ Refresh
                  </button>
                </div>

                {images.length === 0 ? (
                  <div className="card" style={{ textAlign: 'center', padding: 'var(--space-3xl)' }}>
                    <div className="empty-state">
                      <div className="empty-state-icon">⚡</div>
                      <div className="empty-state-title">No jobs yet</div>
                      <div className="empty-state-desc">
                        Upload and process an image to see real-time pipeline tracking.
                      </div>
                      <button className="btn btn-primary" onClick={() => setCurrentPage('upload')}>
                        Get Started
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="job-list">
                    {images.map(image => {
                      const config = STATUS_CONFIG[image.status] || STATUS_CONFIG.UPLOADED;
                      return (
                        <div key={image.id} className="job-row" onClick={async () => {
                          setActiveJobId(image.id);
                          try {
                            const status = await api.getStatus(image.id);
                            setActiveJobStatus(status);
                          } catch {
                            // Use basic status from list
                            setActiveJobStatus({
                              job_id: image.id,
                              status: image.status,
                              progress_pct: image.status === 'COMPLETED' ? 100 : 0,
                              stages: PIPELINE_STAGES.map(s => ({
                                stage: s.key,
                                completed: false,
                                s3_url: null,
                              })),
                              final_cdn_url: image.cdn_url,
                              failure_reason: null,
                              failed_step: null,
                            });
                          }
                        }}>
                          <div className="job-thumb">
                            <div style={{ width: '100%', height: '100%', background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem' }}>
                              {config.icon}
                            </div>
                          </div>
                          <div>
                            <div className="job-name">{image.raw_s3_key?.split('/').pop() || 'Untitled'}</div>
                          </div>
                          <div className="job-preset" style={{ textTransform: 'capitalize' }}>
                            {image.background_preset?.replace(/_/g, ' ') || '—'}
                          </div>
                          <span className={`badge ${config.badgeClass}`}>
                            {config.label}
                          </span>
                          <div className="job-date">
                            {image.created_at ? new Date(image.created_at).toLocaleDateString() : '—'}
                          </div>
                          <div className="job-credits">
                            {image.credits_charged ? `${image.credits_charged} cr` : '—'}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── SETTINGS ─────────────────────────────────────── */}
        {currentPage === 'settings' && (
          <div className="animate-fade-in" style={{ maxWidth: '640px' }}>
            <h2 className="section-title" style={{ marginBottom: 'var(--space-xl)' }}>Workspace Settings</h2>

            <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
              <h3 style={{ marginBottom: 'var(--space-lg)' }}>Workspace Info</h3>
              <div style={{ display: 'grid', gap: 'var(--space-md)' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</div>
                  <div style={{ fontSize: '0.875rem' }}>{workspaceName || 'Demo Studio'}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Plan</div>
                  <span className="badge badge-completed" style={{ textTransform: 'capitalize' }}>Pro</span>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Workspace ID</div>
                  <div style={{ fontSize: '0.8125rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{workspaceId}</div>
                </div>
              </div>
            </div>

            <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
              <h3 style={{ marginBottom: 'var(--space-lg)' }}>Credits</h3>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-gold)', fontFamily: 'var(--font-heading)' }}>
                    {creditBalance}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>credits remaining</div>
                </div>
                <button className="btn btn-primary">
                  Purchase Credits
                </button>
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 'var(--space-lg)' }}>API Access</h3>
              <p style={{ marginBottom: 'var(--space-md)', fontSize: '0.875rem' }}>
                Use these headers for API requests during development:
              </p>
              <div style={{ background: 'var(--bg-tertiary)', padding: 'var(--space-md)', borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', lineHeight: 1.8 }}>
                <div><span style={{ color: 'var(--text-tertiary)' }}>X-Workspace-Id:</span> <span style={{ color: 'var(--accent-gold)' }}>{workspaceId}</span></div>
                <div><span style={{ color: 'var(--text-tertiary)' }}>X-User-Id:</span> <span style={{ color: 'var(--accent-gold)' }}>{userId}</span></div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Toasts ───────────────────────────────────────────── */}
      <div style={{ position: 'fixed', bottom: 'var(--space-xl)', right: 'var(--space-xl)', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', zIndex: 1000 }}>
        {toasts.map(toast => (
          <div key={toast.id} className="toast" style={{
            position: 'relative',
            borderLeft: `3px solid ${toast.type === 'success' ? 'var(--status-completed)' : toast.type === 'error' ? 'var(--status-failed)' : 'var(--accent-gold)'}`,
          }}>
            {toast.message}
          </div>
        ))}
      </div>
    </>
  );
}
