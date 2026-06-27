/**
 * Jewel AI — Constants
 */

export const BACKGROUND_PRESETS = [
  {
    id: 'pure_white_ecommerce',
    name: 'Pure White',
    description: 'Clean e-commerce catalog style',
    color: '#ffffff',
    gradient: 'linear-gradient(135deg, #f5f5f5, #ffffff, #f0f0f0)',
  },
  {
    id: 'marble_luxury',
    name: 'Marble Luxury',
    description: 'Elegant marble surface',
    color: '#e8e0d4',
    gradient: 'linear-gradient(135deg, #d4c5b0, #e8e0d4, #c9baa6)',
  },
  {
    id: 'velvet_dark',
    name: 'Velvet Dark',
    description: 'Rich dark velvet fabric',
    color: '#1a1020',
    gradient: 'linear-gradient(135deg, #1a1020, #2d1f3d, #1a1020)',
  },
  {
    id: 'outdoor_editorial',
    name: 'Outdoor Editorial',
    description: 'Natural golden hour setting',
    color: '#c4a265',
    gradient: 'linear-gradient(135deg, #b8956a, #d4b078, #a8834f)',
  },
] as const;

export const ASPECT_RATIOS = [
  { id: '1:1', label: '1:1', description: 'Square', cssClass: 'aspect-1-1' },
  { id: '4:5', label: '4:5', description: 'Portrait', cssClass: 'aspect-4-5' },
  { id: '16:9', label: '16:9', description: 'Banner', cssClass: 'aspect-16-9' },
] as const;

export const RESOLUTION_TIERS = [
  { id: 'standard', name: 'Standard', description: '1024px', multiplier: '1x' },
  { id: 'hd', name: 'HD', description: '2048px', multiplier: '1.5x' },
  { id: '4k', name: '4K', description: '4096px', multiplier: '2.5x' },
] as const;

export const STATUS_CONFIG: Record<string, { label: string; badgeClass: string; icon: string }> = {
  UPLOADED: { label: 'Uploaded', badgeClass: 'badge-queued', icon: '📤' },
  QUEUED: { label: 'Queued', badgeClass: 'badge-queued', icon: '⏳' },
  ANALYZING: { label: 'Analyzing', badgeClass: 'badge-masking', icon: '🧠' },
  GENERATING_BG: { label: 'Generating', badgeClass: 'badge-generating', icon: '🎨' },
  PROCESSING: { label: 'Processing', badgeClass: 'badge-processing', icon: '⚙️' },
  COMPLETED: { label: 'Completed', badgeClass: 'badge-completed', icon: '✨' },
  FAILED: { label: 'Failed', badgeClass: 'badge-failed', icon: '❌' },
};

export const PIPELINE_STAGES = [
  { key: 'ANALYZING', label: 'Analysis', icon: '🧠', description: 'Claude Vision' },
  { key: 'GENERATING_BG', label: 'Background', icon: '🎨', description: 'Gemini Flash' },
] as const;

export const ACCEPTED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/heic', 'image/webp'];
export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
