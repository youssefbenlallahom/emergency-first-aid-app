/**
 * API client utilities for the Emergency First Aid Assistant
 * Handles communication with the backend CrewAI-powered assistant
 */

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================
// Types
// ============================================

export interface ChatRequest {
  message: string;
  channel_id?: string;
  user_id?: string;
  username?: string;
}

export interface ChatResponse {
  response: string;
  channel_id: string;
  timestamp: string;
}

export interface ConversationPair {
  user_query: string;
  bot_response: string;
  username: string;
  timestamp: string;
  user_id: string;
}

export interface ConversationHistoryResponse {
  channel_id: string;
  conversations: ConversationPair[];
  total_count: number;
}

export interface HealthResponse {
  status: string;
  redis_connected: boolean;
  timestamp: string;
}

export interface ClearHistoryResponse {
  success: boolean;
  message: string;
}

// Video Report Types
export interface VideoAnalysisResponse {
  report_id: string;
  status: string;
  message: string;
  video_info?: {
    filename?: string;
    size?: number;
  };
}

export interface VideoReportItem {
  id: string;
  title: string;
  date: string;
  status: string;
  thumbnail?: string;
  summary?: string;
}

export interface VideoReportListResponse {
  reports: VideoReportItem[];
  total_count: number;
}

export interface VideoReportDetail {
  id: string;
  title: string;
  date: string;
  status: string;
  content_html: string;
  content_markdown: string;
  video_info?: Record<string, unknown>;
  frame_analyses?: Array<Record<string, unknown>>;
  audio_analysis?: Record<string, unknown>;
}

export interface VideoAnalysisStatus {
  report_id: string;
  status: string;
  created_at?: string;
  error?: string;
}

export interface ApiError {
  error: string;
  detail: string;
  timestamp: string;
}

// ============================================
// Helper Functions
// ============================================

/**
 * Generate a unique channel ID for the session
 */
export function generateChannelId(): string {
  const timestamp = Date.now().toString(36);
  const randomPart = Math.random().toString(36).substring(2, 10);
  return `web_${timestamp}_${randomPart}`;
}

/**
 * Generate a unique user ID
 */
export function generateUserId(): string {
  return `user_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 10)}`;
}

/**
 * Get or create session IDs from localStorage
 */
export function getSessionIds(): { channelId: string; userId: string } {
  if (typeof window === 'undefined') {
    return { channelId: generateChannelId(), userId: generateUserId() };
  }
  
  let channelId = localStorage.getItem('chat_channel_id');
  let userId = localStorage.getItem('chat_user_id');
  
  if (!channelId) {
    channelId = generateChannelId();
    localStorage.setItem('chat_channel_id', channelId);
  }
  
  if (!userId) {
    userId = generateUserId();
    localStorage.setItem('chat_user_id', userId);
  }
  
  return { channelId, userId };
}

/**
 * Clear session IDs from localStorage
 */
export function clearSessionIds(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('chat_channel_id');
    localStorage.removeItem('chat_user_id');
  }
}

// ============================================
// API Functions
// ============================================

/**
 * Send a message to the AI assistant
 */
export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: 'Network error',
      detail: 'Failed to communicate with the server',
      timestamp: new Date().toISOString(),
    }));
    throw new Error(error.detail || 'Failed to send message');
  }
  
  return response.json();
}

/**
 * Get conversation history for a channel
 */
export async function getConversationHistory(
  channelId: string,
  limit: number = 10
): Promise<ConversationHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/history/${encodeURIComponent(channelId)}?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: 'Network error',
      detail: 'Failed to fetch conversation history',
      timestamp: new Date().toISOString(),
    }));
    throw new Error(error.detail || 'Failed to fetch history');
  }
  
  return response.json();
}

/**
 * Clear conversation history for a channel
 */
export async function clearConversationHistory(
  channelId: string
): Promise<ClearHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/history/${encodeURIComponent(channelId)}`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );
  
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: 'Network error',
      detail: 'Failed to clear conversation history',
      timestamp: new Date().toISOString(),
    }));
    throw new Error(error.detail || 'Failed to clear history');
  }
  
  return response.json();
}

/**
 * Check API health status
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error('API is not healthy');
  }
  
  return response.json();
}

/**
 * Check if the API is available
 */
export async function isApiAvailable(): Promise<boolean> {
  try {
    const health = await checkHealth();
    return health.status === 'healthy' || health.status === 'degraded';
  } catch {
    return false;
  }
}


// ============================================
// Video Report API
// ============================================

/**
 * Upload and analyze a video for emergency report generation
 */
export async function analyzeVideo(
  file: File,
  options?: {
    language?: string;
    sendEmail?: boolean;
    email?: string;
  }
): Promise<VideoAnalysisResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', options?.language || 'fr');
  formData.append('send_email', String(options?.sendEmail || false));
  if (options?.email) {
    formData.append('email', options.email);
  }

  const response = await fetch(`${API_BASE_URL}/api/video/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Échec de l\'analyse de la vidéo',
    }));
    throw new Error(error.detail || 'Failed to analyze video');
  }

  return response.json();
}

/**
 * Get the status of a video analysis task
 */
export async function getVideoAnalysisStatus(reportId: string): Promise<VideoAnalysisStatus> {
  const response = await fetch(`${API_BASE_URL}/api/video/status/${encodeURIComponent(reportId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Échec de la récupération du statut',
    }));
    throw new Error(error.detail || 'Failed to get status');
  }

  return response.json();
}

/**
 * List all video reports
 */
export async function listVideoReports(): Promise<VideoReportListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/video/reports`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Échec de la récupération des rapports',
    }));
    throw new Error(error.detail || 'Failed to list reports');
  }

  return response.json();
}

/**
 * Get a specific video report by ID
 */
export async function getVideoReport(reportId: string): Promise<VideoReportDetail> {
  const response = await fetch(`${API_BASE_URL}/api/video/reports/${encodeURIComponent(reportId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Rapport non trouvé',
    }));
    throw new Error(error.detail || 'Failed to get report');
  }

  return response.json();
}

/**
 * Delete a video report
 */
export async function deleteVideoReport(reportId: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/video/reports/${encodeURIComponent(reportId)}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Échec de la suppression du rapport',
    }));
    throw new Error(error.detail || 'Failed to delete report');
  }

  return response.json();
}

/**
 * Send a video report via email
 */
export async function emailVideoReport(
  reportId: string,
  email: string,
  subject?: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/video/reports/${encodeURIComponent(reportId)}/email`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, subject }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'Échec de l\'envoi de l\'email',
    }));
    throw new Error(error.detail || 'Failed to send email');
  }

  return response.json();
}

/**
 * Get frame image URL for a video report
 */
export function getVideoFrameUrl(reportId: string, filename: string): string {
  return `${API_BASE_URL}/api/video/frames/${encodeURIComponent(reportId)}/${encodeURIComponent(filename)}`;
}

/**
 * Poll for video analysis completion
 */
export async function pollVideoAnalysis(
  reportId: string,
  onStatusChange?: (status: string) => void,
  maxAttempts: number = 60,
  intervalMs: number = 2000
): Promise<VideoReportDetail> {
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    const status = await getVideoAnalysisStatus(reportId);
    
    if (onStatusChange) {
      onStatusChange(status.status);
    }
    
    if (status.status === 'completed') {
      return getVideoReport(reportId);
    }
    
    if (status.status === 'error') {
      throw new Error(status.error || 'L\'analyse de la vidéo a échoué');
    }
    
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }
  
  throw new Error('Délai d\'attente dépassé pour l\'analyse de la vidéo');
}


// ============================================
// Voice WebSocket API
// ============================================

// WebSocket URL (convert http to ws)
const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');

export interface VoiceMessage {
  type: 'audio' | 'text' | 'end';
  data?: string;  // base64 audio data
  message?: string;  // text message
}

export interface VoiceServerMessage {
  type: 'transcript' | 'response' | 'status' | 'error' | 'info';
  text?: string;
  audio?: string | null;
  state?: 'connected' | 'listening' | 'processing' | 'speaking' | 'ended';
  message?: string;
}

export type VoiceMessageHandler = (message: VoiceServerMessage) => void;

/**
 * Voice WebSocket connection manager
 */
export class VoiceConnection {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private messageHandler: VoiceMessageHandler | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  
  constructor(sessionId?: string) {
    this.sessionId = sessionId || generateUserId();
  }
  
  /**
   * Connect to the voice WebSocket
   */
  connect(onMessage: VoiceMessageHandler): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const url = `${WS_BASE_URL}/api/voice/${this.sessionId}`;
        this.ws = new WebSocket(url);
        this.messageHandler = onMessage;
        
        this.ws.onopen = () => {
          console.log('🎤 Voice WebSocket connected');
          this.reconnectAttempts = 0;
          resolve();
        };
        
        this.ws.onmessage = (event) => {
          try {
            const message: VoiceServerMessage = JSON.parse(event.data);
            if (this.messageHandler) {
              this.messageHandler(message);
            }
          } catch (e) {
            console.error('Failed to parse voice message:', e);
          }
        };
        
        this.ws.onerror = (error) => {
          console.error('Voice WebSocket error:', error);
          reject(new Error('WebSocket connection failed'));
        };
        
        this.ws.onclose = (event) => {
          console.log('Voice WebSocket closed:', event.code, event.reason);
          if (this.messageHandler) {
            this.messageHandler({
              type: 'status',
              state: 'ended',
              message: 'Connection closed'
            });
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }
  
  /**
   * Send a text message through the voice channel
   */
  sendText(message: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'text',
        message: message
      }));
    } else {
      console.warn('Voice WebSocket not connected');
    }
  }
  
  /**
   * Send audio data (base64 encoded)
   */
  sendAudio(base64Audio: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'audio',
        data: base64Audio
      }));
    } else {
      console.warn('Voice WebSocket not connected');
    }
  }
  
  /**
   * End the voice session
   */
  endSession(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'end' }));
    }
  }
  
  /**
   * Disconnect from the voice WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.messageHandler = null;
  }
  
  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
  
  /**
   * Get the session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }
}
