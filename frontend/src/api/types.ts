// API types mirroring backend/app/schemas/schemas.py
export interface Token {
  access_token: string;
  token_type: string;
  role: "admin" | "operator" | "viewer";
  username: string;
  full_name: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Camera {
  id: number;
  name: string;
  code: string;
  location_name: string;
  latitude: number | null;
  longitude: number | null;
  manufacturer: string;
  model: string;
  protocol: "rtsp" | "file" | "webcam";
  rtsp_url: string;
  description: string;
  enabled: boolean;
  detection_enabled: boolean;
  status: "online" | "offline" | "error" | "disabled";
  last_connected_at: string | null;
  last_health_check: string | null;
  last_error: string;
  stream_fps: number;
  created_at: string;
  is_demo: boolean;
}

export interface CameraInput {
  name: string;
  code: string;
  location_name?: string;
  latitude?: number | null;
  longitude?: number | null;
  manufacturer?: string;
  model?: string;
  protocol?: "rtsp" | "file" | "webcam";
  rtsp_url?: string;
  description?: string;
  enabled?: boolean;
  detection_enabled?: boolean;
  credential?: { username: string; secret: string; channel: string } | null;
}

export interface CameraTestResult {
  camera_id: number;
  ok: boolean;
  message: string;
  latency_ms: number | null;
}

export interface DetectionEvent {
  id: number;
  camera_id: number;
  timestamp: string;
  object_class: string;
  confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number | null;
  bbox_h: number;
  track_id: number | null;
  image_path: string;
  frame_path: string;
  is_demo: boolean;
}

export interface EventPage {
  items: DetectionEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface PlateRead {
  id: number;
  plate_text: string;
  raw_text: string;
  ocr_confidence: number;
  needs_review: boolean;
  corrected_text: string | null;
  crop_path: string;
  created_at: string;
  is_demo: boolean;
}

export interface Vehicle {
  id: number;
  registration_number: string;
  vehicle_class: string;
  first_seen_at: string;
  last_seen_at: string;
  total_sightings: number;
  is_demo: boolean;
}

export interface VehicleSighting {
  id: number;
  vehicle_id: number;
  event_id: number;
  camera_id: number;
  timestamp: string;
  camera_name: string | null;
  registration_number: string | null;
  object_class: string | null;
  confidence: number | null;
  image_path: string;
  frame_path: string;
  ocr_confidence: number | null;
}

export interface VehicleDetail {
  vehicle: Vehicle;
  sightings: VehicleSighting[];
}

export interface VehiclePage {
  items: Vehicle[];
  total: number;
  page: number;
  page_size: number;
}

export interface Alert {
  id: number;
  alert_type: string;
  severity: "info" | "warning" | "critical";
  camera_id: number | null;
  event_id: number | null;
  title: string;
  description: string;
  status: "open" | "acknowledged" | "resolved";
  acknowledged_by: number | null;
  acknowledged_at: string | null;
  assigned_to: number | null;
  created_at: string;
  is_demo: boolean;
}

export interface AlertPage {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
}

export interface OverviewStats {
  cameras_total: number;
  cameras_online: number;
  cameras_offline: number;
  streams_active: number;
  detections_today: number;
  anpr_today: number;
  alerts_open: number;
  events_total: number;
  demo_mode: boolean;
}

export interface TimeSeriesPoint {
  bucket: string;
  count: number;
}

export interface ClassBreakdown {
  object_class: string;
  count: number;
}

export interface CameraAvailability {
  camera_id: number;
  name: string;
  status: string;
  uptime_pct: number;
}

export interface AlertTypeBreakdown {
  alert_type: string;
  severity: string;
  count: number;
}

export interface GisCamera {
  id: number;
  name: string;
  code: string;
  status: string;
  location_name: string;
  latitude: number | null;
  longitude: number | null;
  last_connected_at: string | null;
  is_demo: boolean;
}

export interface GisSighting {
  event_id: number;
  camera_id: number;
  camera_name: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  registration_number: string | null;
  object_class: string | null;
  confidence: number | null;
  image_path: string;
}

export interface GisPathPoint {
  registration_number: string;
  points: GisSighting[];
}

export interface WorkerStatus {
  running: boolean;
  cameras: Record<string, string>;
  detector_ready: boolean;
  detector_device: string;
  ocr_ready: boolean;
  demo_mode: boolean;
}

export interface RecentDetection {
  id: number;
  camera_id: number;
  camera_name: string | null;
  timestamp: string;
  object_class: string;
  confidence: number;
  image_path: string;
  plate_text: string | null;
  ocr_confidence: number | null;
  is_demo: boolean;
}

export interface SettingItem {
  key: string;
  value: string;
  updated_at: string | null;
  updated_by: string;
}

export interface AuditLog {
  id: number;
  timestamp: string;
  username: string;
  action: string;
  resource: string;
  detail: string;
  ip_address: string;
}

// ---------- Optional AI modules (new, additive only) ----------

export interface VehicleAttribute {
  id: number;
  event_id: number;
  camera_id: number;
  timestamp: string;
  vehicle_type: string;
  color: string;
  color_confidence: number;
  body_style: string;
  model_name: string;
  is_demo: boolean;
}

export interface ReidMatch {
  id: number;
  event_id: number;
  camera_id: number;
  matched_event_id: number | null;
  matched_camera_id: number | null;
  similarity: number;
  matched_plate: string;
  status: "unconfirmed" | "confirmed" | "rejected";
  created_at: string;
  is_demo: boolean;
}

export interface QualityMetric {
  id: number;
  camera_id: number;
  timestamp: string;
  composite: number;
  blur_score: number;
  brightness_score: number;
  visibility_score: number;
  verdict: "good" | "degraded" | "poor";
  is_demo: boolean;
}

export interface PersonDetection {
  id: number;
  camera_id: number;
  timestamp: string;
  confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  is_demo: boolean;
}

export interface AnomalyReview {
  id: number;
  camera_id: number;
  event_id: number | null;
  timestamp: string;
  anomaly_type: "speed" | "loitering" | "direction" | string;
  score: number;
  detail: string;
  review_status: "pending" | "reviewed";
  is_demo: boolean;
}

export interface AiModulesStatus {
  reid: { enabled: boolean; available: boolean; gallery_size?: number; mode?: string };
  attributes: { enabled: boolean; available: boolean; mode?: string };
  person: { enabled: boolean; available: boolean; device?: string; error?: string };
  quality: { enabled: boolean; available: boolean; sample_every_n?: number };
  anomaly: { enabled: boolean; available: boolean; cameras_tracked?: number; direction_calibrated?: number };
}

export interface VehicleSightingWithAttrs extends VehicleSighting {
  attributes?: {
    color: string;
    vehicle_type: string;
    body_style: string;
    color_confidence: number;
  } | null;
}

// ---------- Watchlist (new, additive only) ----------

export type WatchlistCategory = "stolen_vehicle" | "wanted_person" | "missing_person" | "blacklist" | "custom";

export interface WatchlistEntry {
  id: number;
  category: WatchlistCategory;
  identifier_type: "plate" | "custom";
  identifier_value: string;
  display_value: string;
  title: string;
  notes: string;
  severity: "info" | "warning" | "critical";
  active: boolean;
  expires_at: string | null;
  created_at: string;
  updated_at: string | null;
  is_demo: boolean;
  hit_count: number;
}

export interface WatchlistEntryInput {
  category?: WatchlistCategory;
  identifier_value?: string;
  title?: string;
  notes?: string;
  severity?: "info" | "warning" | "critical";
  active?: boolean;
  expires_at?: string | null;
}

export interface WatchlistHit {
  id: number;
  entry_id: number;
  plate_read_id: number | null;
  event_id: number | null;
  camera_id: number | null;
  timestamp: string;
  plate_text: string;
  ocr_confidence: number;
  match_type: string;
  evidence_path: string;
  alert_id: number | null;
  acknowledged: boolean;
  is_demo: boolean;
}

export interface WatchlistCheck {
  plate: string;
  on_watchlist: boolean;
  entries: { id: number; category: string; title: string; severity: string; display_value: string }[];
}
