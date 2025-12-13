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
// Voice WebSocket API - GPT Realtime Integration
// ============================================

// WebSocket URL (convert http to ws)
const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');

export interface VoiceMessage {
  type: 'audio' | 'text' | 'end' | 'interrupt';
  data?: string;  // base64 audio data
  message?: string;  // text message
}

export interface VoiceServerMessage {
  type: 'transcript' | 'transcript_delta' | 'response' | 'status' | 'error' | 'info' | 'audio' | 'control';
  text?: string;
  data?: string;  // base64 audio for playback
  level?: number;  // audio level 0.0-1.0 for visualization
  sampleRate?: number;  // audio sample rate (24000 for GPT-Realtime)
  speaker?: 'user' | 'assistant';
  state?: 'connected' | 'listening' | 'user_speaking' | 'processing' | 'speaking' | 'ended';
  mode?: 'realtime' | 'text_only';
  message?: string;
  action?: 'stop_playback';
  responseId?: string;
}

export type VoiceMessageHandler = (message: VoiceServerMessage) => void;

/**
 * Audio Processor for real-time audio handling
 * Captures microphone audio and converts to PCM16 24kHz for GPT-Realtime
 */
export class AudioProcessor {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private onAudioChunk: ((chunk: string) => void) | null = null;
  private onAudioLevel: ((level: number) => void) | null = null;
  private isRecording = false;

  // Target: 24kHz mono PCM16 for GPT-Realtime
  private targetSampleRate = 24000;
  private chunkSize = 2400; // 100ms at 24kHz

  async start(
    onAudioChunk: (chunk: string) => void,
    onAudioLevel: (level: number) => void
  ): Promise<void> {
    this.onAudioChunk = onAudioChunk;
    this.onAudioLevel = onAudioLevel;

    try {
      // Get microphone access
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: this.targetSampleRate,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      // Create audio context with target sample rate
      this.audioContext = new AudioContext({ sampleRate: this.targetSampleRate });
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Create analyser for level visualization
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.sourceNode.connect(this.analyser);

      // Use ScriptProcessor for audio capture (worklet alternative)
      const bufferSize = 4096;
      const scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

      let audioBuffer: Float32Array[] = [];
      let samplesCollected = 0;

      const targetFps = 30;
      const minIntervalMs = 1000 / targetFps;
      let lastEmitMs = 0;
      let lastLevel = -1;

      scriptProcessor.onaudioprocess = (event) => {
        if (!this.isRecording) return;

        const inputData = event.inputBuffer.getChannelData(0);
        audioBuffer.push(new Float32Array(inputData));
        samplesCollected += inputData.length;

        // Send chunk when we have enough samples
        if (samplesCollected >= this.chunkSize) {
          const combinedBuffer = this.combineBuffers(audioBuffer, samplesCollected);
          const pcm16 = this.floatToPCM16(combinedBuffer.slice(0, this.chunkSize));
          const base64 = this.arrayBufferToBase64(pcm16.buffer);

          if (this.onAudioChunk) {
            this.onAudioChunk(base64);
          }

          // Keep remainder for next chunk
          const remainder = combinedBuffer.slice(this.chunkSize);
          audioBuffer = remainder.length > 0 ? [remainder] : [];
          samplesCollected = remainder.length;
        }

        // Calculate audio level for visualization (throttled)
        if (this.analyser && this.onAudioLevel) {
          const nowMs = performance.now();
          if (nowMs - lastEmitMs >= minIntervalMs) {
            const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            const level = average / 255;

            if (lastLevel < 0 || Math.abs(level - lastLevel) > 0.02) {
              this.onAudioLevel(level);
              lastLevel = level;
            } else if (level === 0 && lastLevel !== 0) {
              this.onAudioLevel(0);
              lastLevel = 0;
            }

            lastEmitMs = nowMs;
          }
        }
      };

      this.sourceNode.connect(scriptProcessor);
      scriptProcessor.connect(this.audioContext.destination);

      this.isRecording = true;
      console.log('🎤 Audio capture started at', this.audioContext.sampleRate, 'Hz');

    } catch (error) {
      console.error('Failed to start audio capture:', error);
      throw error;
    }
  }

  private combineBuffers(buffers: Float32Array[], totalLength: number): Float32Array {
    const result = new Float32Array(totalLength);
    let offset = 0;
    for (const buffer of buffers) {
      result.set(buffer, offset);
      offset += buffer.length;
    }
    return result;
  }

  private floatToPCM16(float32Array: Float32Array): Int16Array {
    const pcm16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16;
  }

  private arrayBufferToBase64(buffer: ArrayBuffer | ArrayBufferLike): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  stop(): void {
    this.isRecording = false;

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.sourceNode = null;
    this.analyser = null;
    this.onAudioChunk = null;
    this.onAudioLevel = null;

    console.log('🎤 Audio capture stopped');
  }

  pause(): void {
    this.isRecording = false;
  }

  resume(): void {
    this.isRecording = true;
  }

  isActive(): boolean {
    return this.isRecording;
  }
}

/**
 * Audio Player for streaming GPT-Realtime audio output
 * Plays PCM16 24kHz audio with level tracking for visualization
 */
export class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private audioQueue: AudioBuffer[] = [];
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private onAudioLevel: ((level: number) => void) | null = null;
  private onPlaybackEnd: (() => void) | null = null;
  private animationFrame: number | null = null;

  private sampleRate = 24000;

  async init(onAudioLevel: (level: number) => void, onPlaybackEnd?: () => void): Promise<void> {
    this.onAudioLevel = onAudioLevel;
    this.onPlaybackEnd = onPlaybackEnd || null;
    this.audioContext = new AudioContext({ sampleRate: this.sampleRate });

    // Create analyser for output level visualization
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.connect(this.audioContext.destination);

    // Start level monitoring
    this.startLevelMonitoring();
  }

  private startLevelMonitoring(): void {
    const targetFps = 30;
    const minIntervalMs = 1000 / targetFps;

    let lastEmitMs = 0;
    let lastLevel = -1;

    const updateLevel = (nowMs: number) => {
      if (!this.onAudioLevel) {
        this.animationFrame = requestAnimationFrame(updateLevel);
        return;
      }

      if (nowMs - lastEmitMs >= minIntervalMs) {
        let level = 0;

        if (this.analyser && this.isPlaying) {
          const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
          this.analyser.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          level = average / 255;
        }

        // Avoid spamming React state updates for tiny/no changes
        if (lastLevel < 0 || Math.abs(level - lastLevel) > 0.02) {
          this.onAudioLevel(level);
          lastLevel = level;
        } else if (level === 0 && lastLevel !== 0) {
          this.onAudioLevel(0);
          lastLevel = 0;
        }

        lastEmitMs = nowMs;
      }

      this.animationFrame = requestAnimationFrame(updateLevel);
    };

    this.animationFrame = requestAnimationFrame(updateLevel);
  }

  /**
   * Queue audio chunk for playback
   * @param base64Audio Base64 encoded PCM16 audio
   * @param level Pre-calculated audio level (0-1)
   */
  async queueAudio(base64Audio: string, level?: number): Promise<void> {
    if (!this.audioContext) {
      await this.init(this.onAudioLevel || (() => { }));
    }

    // If level is provided, use it immediately for visualization
    if (level !== undefined && this.onAudioLevel) {
      this.onAudioLevel(level);
    }

    // Decode base64 to PCM16
    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Convert PCM16 to Float32
    const pcm16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768;
    }

    // Create audio buffer
    const audioBuffer = this.audioContext!.createBuffer(1, float32.length, this.sampleRate);
    audioBuffer.getChannelData(0).set(float32);

    this.audioQueue.push(audioBuffer);

    if (!this.isPlaying) {
      this.playNext();
    }
  }

  private playNext(): void {
    if (this.audioQueue.length === 0 || !this.audioContext) {
      this.isPlaying = false;
      if (this.onPlaybackEnd) {
        this.onPlaybackEnd();
      }
      return;
    }

    this.isPlaying = true;
    const buffer = this.audioQueue.shift()!;

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyser!);

    source.onended = () => {
      this.playNext();
    };

    this.currentSource = source;
    source.start();
  }

  stop(): void {
    if (this.currentSource) {
      try {
        this.currentSource.stop();
      } catch { }
      this.currentSource = null;
    }
    this.audioQueue = [];
    this.isPlaying = false;

    if (this.onPlaybackEnd) {
      this.onPlaybackEnd();
    }

    if (this.onAudioLevel) {
      this.onAudioLevel(0);
    }
  }

  destroy(): void {
    this.stop();

    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    this.analyser = null;
  }

  isActive(): boolean {
    return this.isPlaying;
  }
}

/**
 * Voice WebSocket connection manager with GPT-Realtime support
 */
export class VoiceConnection {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private messageHandler: VoiceMessageHandler | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private audioProcessor: AudioProcessor | null = null;
  private audioPlayer: AudioPlayer | null = null;
  private isMuted = false;
  private pendingListening = false;

  // Barge-in (interrupt while assistant is speaking) gating
  private assistantSpeaking = false;
  private inputLevel = 0;
  private bargeInFrames = 0;
  private readonly bargeInThreshold = 0.4; // mic level threshold (0-1) - increased to reduce false positives
  private readonly bargeInMinFrames = 3; // ~100ms at 30fps
  private allowStreamingDuringAssistant = false;

  // Synchronization: track which response we are currently playing/expecting
  private activeResponseId: string | null = null;
  private ignoredResponseIds = new Set<string>();

  constructor(sessionId?: string) {
    this.sessionId = sessionId || generateUserId();
  }

  /**
   * Connect to the voice WebSocket with full audio support
   */
  async connect(
    onMessage: VoiceMessageHandler,
    onInputLevel?: (level: number) => void,
    onOutputLevel?: (level: number) => void
  ): Promise<void> {
    return new Promise(async (resolve, reject) => {
      try {
        const url = `${WS_BASE_URL}/api/voice/${this.sessionId}`;
        this.ws = new WebSocket(url);
        this.messageHandler = onMessage;

        // Initialize audio player
        this.audioPlayer = new AudioPlayer();
        await this.audioPlayer.init(
          onOutputLevel || (() => { }),
          () => {
            if (this.pendingListening && this.messageHandler) {
              this.pendingListening = false;
              this.assistantSpeaking = false;
              this.allowStreamingDuringAssistant = false;
              this.bargeInFrames = 0;
              this.messageHandler({ type: 'status', state: 'listening' });
            }
          }
        );

        // Initialize audio processor
        this.audioProcessor = new AudioProcessor();

        this.ws.onopen = async () => {
          console.log('🎤 Voice WebSocket connected');
          this.reconnectAttempts = 0;

          // Start audio capture
          try {
            await this.audioProcessor!.start(
              (chunk) => {
                // While assistant is speaking, do not stream mic audio unless barge-in is active.
                // This prevents echo/self-interrupt loops while keeping the mic level visible.
                if (this.assistantSpeaking && !this.allowStreamingDuringAssistant) {
                  return;
                }
                this.sendAudio(chunk);
              },
              (level) => {
                this.inputLevel = level;
                if (onInputLevel) {
                  onInputLevel(level);
                }

                // Detect real user speech while assistant is speaking (barge-in)
                if (this.assistantSpeaking && !this.allowStreamingDuringAssistant) {
                  if (level >= this.bargeInThreshold) {
                    this.bargeInFrames += 1;
                    if (this.bargeInFrames >= this.bargeInMinFrames) {
                      console.log(`🔴 FRONTEND BARGE-IN triggered! level=${level.toFixed(3)}, frames=${this.bargeInFrames}`);
                      this.allowStreamingDuringAssistant = true;
                      this.interrupt();
                    }
                  } else {
                    this.bargeInFrames = 0;
                  }
                }
              }
            );
          } catch (e) {
            console.warn('Audio capture not available:', e);
          }

          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: VoiceServerMessage = JSON.parse(event.data);

            // Handle audio playback
            if (message.type === 'audio' && message.data) {
              // If this audio belongs to an ignored response (interrupted), drop it.
              if (message.responseId && this.ignoredResponseIds.has(message.responseId)) {
                return;
              }

              // If it's a new response ID we haven't seen, make it active
              if (message.responseId && message.responseId !== this.activeResponseId) {
                this.activeResponseId = message.responseId;
              }

              this.audioPlayer?.queueAudio(message.data, message.level);
              this.assistantSpeaking = true;
            }

            // If backend says "listening" while audio is still playing, delay it until playback drains.
            if (message.type === 'status' && message.state === 'listening') {
              if (this.audioPlayer?.isActive()) {
                this.pendingListening = true;
                return;
              }
              this.pendingListening = false;
              this.assistantSpeaking = false;
              this.allowStreamingDuringAssistant = false;
              this.bargeInFrames = 0;
            }

            if (message.type === 'status' && message.state === 'speaking') {
              this.assistantSpeaking = true;
            }

            // Allow server to force-stop playback (e.g., interrupt / cancel)
            if (message.type === 'control' && message.action === 'stop_playback') {
              // Only stop if the command targets the currently active response (or if no ID provided)
              // This prevents a late "stop" from a previous turn killing the NEW turn's audio.
              if (!message.responseId || message.responseId === this.activeResponseId) {
                this.audioPlayer?.stop();
                this.pendingListening = false;
                this.assistantSpeaking = false;
                this.allowStreamingDuringAssistant = false;
                this.bargeInFrames = 0;
              }
            }

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
          this.cleanup();
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
   * Send audio data (base64 encoded PCM16)
   */
  sendAudio(base64Audio: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && !this.isMuted) {
      this.ws.send(JSON.stringify({
        type: 'audio',
        data: base64Audio
      }));
    }
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
   * End the voice session
   */
  endSession(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'end' }));
    }
  }

  /**
   * Mute/unmute microphone
   */
  setMuted(muted: boolean): void {
    this.isMuted = muted;
    if (muted) {
      this.audioProcessor?.pause();
    } else {
      this.audioProcessor?.resume();
    }
  }

  /**
   * Stop audio playback (speaker off)
   */
  stopPlayback(): void {
    this.audioPlayer?.stop();
  }

  /**
   * Interrupt assistant speech immediately (cancel TTS + stop local playback)
   */
  interrupt(): void {
    // Mark current response as ignored so any in-flight audio packets are dropped
    if (this.activeResponseId) {
      this.ignoredResponseIds.add(this.activeResponseId);
      this.activeResponseId = null;
    }

    this.stopPlayback();
    this.assistantSpeaking = false;
    // After interrupt, allow streaming so the user's new request is captured immediately.
    this.allowStreamingDuringAssistant = true;
    this.bargeInFrames = 0;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'interrupt' }));
    }
  }

  private cleanup(): void {
    this.audioProcessor?.stop();
    this.audioPlayer?.destroy();
    this.audioProcessor = null;
    this.audioPlayer = null;
  }

  /**
   * Disconnect from the voice WebSocket
   */
  disconnect(): void {
    this.cleanup();
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
