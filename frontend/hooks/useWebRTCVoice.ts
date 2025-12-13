/**
 * WebRTC Voice Hook for Azure OpenAI Realtime API
 * 
 * This hook establishes a direct WebRTC connection between the browser
 * and Azure OpenAI, providing the lowest possible latency for voice calls.
 * 
 * Features:
 * - Direct browser <-> Azure connection (no backend proxy for audio)
 * - Proper interruption handling with conversation.item.truncate
 * - Built-in VAD (Voice Activity Detection)
 * - Audio level visualization
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============================================
// Types
// ============================================

export type VoiceState =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'listening'
    | 'user_speaking'
    | 'processing'
    | 'speaking'
    | 'error';

export interface Transcript {
    speaker: 'user' | 'assistant';
    text: string;
    timestamp: Date;
}

export interface UseWebRTCVoiceOptions {
    voice?: string;
    onTranscript?: (transcript: Transcript) => void;
    onStateChange?: (state: VoiceState) => void;
    onError?: (error: string) => void;
    onDebug?: (message: string) => void;
}

export interface UseWebRTCVoiceReturn {
    state: VoiceState;
    inputLevel: number;
    outputLevel: number;
    transcripts: Transcript[];
    connect: () => Promise<void>;
    disconnect: () => void;
    interrupt: () => void;
    toggleMic: () => boolean;
    isMuted: boolean;
}

// ============================================
// Token Fetching
// ============================================

interface TokenResponse {
    token: string;
    expires_at: string;
    webrtc_url: string;
    ice_servers: RTCIceServer[];
}

async function getRealtimeToken(voice: string = 'cedar'): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE_URL}/api/realtime/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voice })
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get token' }));
        throw new Error(error.detail || 'Failed to get realtime token');
    }

    return response.json();
}

// ============================================
// Main Hook
// ============================================

export function useWebRTCVoice(options: UseWebRTCVoiceOptions = {}): UseWebRTCVoiceReturn {
    const { voice = 'cedar', onTranscript, onStateChange, onError, onDebug } = options;

    // Callback refs to prevent re-renders triggering effects
    const onTranscriptRef = useRef(onTranscript);
    const onStateChangeRef = useRef(onStateChange);
    const onErrorRef = useRef(onError);
    const onDebugRef = useRef(onDebug);

    useEffect(() => {
        onTranscriptRef.current = onTranscript;
        onStateChangeRef.current = onStateChange;
        onErrorRef.current = onError;
        onDebugRef.current = onDebug;
    }, [onTranscript, onStateChange, onError, onDebug]);

    // State
    const [state, setState] = useState<VoiceState>('disconnected');
    const [inputLevel, setInputLevel] = useState(0);
    const [outputLevel, setOutputLevel] = useState(0);
    const [transcripts, setTranscripts] = useState<Transcript[]>([]);

    // Refs
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const dcRef = useRef<RTCDataChannel | null>(null);
    const localStreamRef = useRef<MediaStream | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const animationFrameRef = useRef<number | null>(null);

    // Track current response for truncation
    const currentResponseIdRef = useRef<string | null>(null);
    const audioQueueRef = useRef<AudioBufferSourceNode[]>([]);

    // Update state and notify
    const updateState = useCallback((newState: VoiceState) => {
        setState(newState);
        onStateChangeRef.current?.(newState);
    }, []);

    // Add transcript
    const addTranscript = useCallback((speaker: 'user' | 'assistant', text: string) => {
        const transcript: Transcript = { speaker, text, timestamp: new Date() };
        setTranscripts(prev => [...prev, transcript]);
        onTranscriptRef.current?.(transcript);
    }, []);

    // Stop all audio playback (for interruption)
    const stopAllAudio = useCallback(() => {
        audioQueueRef.current.forEach(source => {
            try { source.stop(); } catch { }
        });
        audioQueueRef.current = [];
        setOutputLevel(0);
    }, []);

    // Helper to toggle microphone
    const setMicEnabled = useCallback((enabled: boolean) => {
        if (localStreamRef.current) {
            localStreamRef.current.getAudioTracks().forEach(track => {
                track.enabled = enabled;
            });
            console.log(`🎤 Microphone ${enabled ? 'enabled' : 'disabled'}`);
            onDebugRef.current?.(`Microphone ${enabled ? 'enabled' : 'disabled'}`);
        }
    }, []);

    // Handle data channel messages
    const handleDataChannelMessage = useCallback((event: MessageEvent) => {
        try {
            const msg = JSON.parse(event.data);

            switch (msg.type) {
                case 'session.created':
                case 'session.updated':
                    console.log('✅ WebRTC session established');
                    updateState('listening');
                    break;

                case 'input_audio_buffer.speech_started':
                    updateState('user_speaking');
                    break;

                case 'input_audio_buffer.speech_stopped':
                    updateState('processing');
                    break;

                case 'conversation.item.input_audio_transcription.completed':
                    if (msg.transcript) {
                        addTranscript('user', msg.transcript);
                    }
                    break;

                case 'response.created':
                    currentResponseIdRef.current = msg.response?.id || null;
                    updateState('speaking');
                    break;

                case 'response.audio_transcript.delta':
                    // Streaming text - could be used for live captions
                    break;

                case 'response.function_call_arguments.done':
                    const callId = msg.call_id;
                    const args = JSON.parse(msg.arguments);

                    if (msg.name === 'query_medical_assistant') {
                        console.log(`🧠 Calling CrewAI: ${args.query}`);
                        onDebugRef.current?.(`CrewAI thinking: ${args.query.slice(0, 30)}...`);
                        updateState('processing');
                        setMicEnabled(false); // 🔇 Mute mic during processing

                        // Call backend API
                        fetch(`${API_BASE_URL}/api/chat`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ message: args.query })
                        })
                            .then(res => res.json())
                            .then(data => {
                                const result = data.response;
                                console.log('🧠 CrewAI response received');
                                onDebugRef.current?.('CrewAI responded');

                                // Send result back to Realtime API
                                dcRef.current?.send(JSON.stringify({
                                    type: 'conversation.item.create',
                                    item: {
                                        type: 'function_call_output',
                                        call_id: callId,
                                        output: result
                                    }
                                }));

                                // Trigger response generation based on tool output
                                dcRef.current?.send(JSON.stringify({
                                    type: 'response.create'
                                }));
                            })
                            .catch(err => {
                                console.error('CrewAI API Error:', err);
                                onDebugRef.current?.('CrewAI Error');

                                // Send error so conversation continues
                                dcRef.current?.send(JSON.stringify({
                                    type: 'conversation.item.create',
                                    item: {
                                        type: 'function_call_output',
                                        call_id: callId,
                                        output: "Error retrieving medical advice. Please proceed with standard protocols."
                                    }
                                }));
                                dcRef.current?.send(JSON.stringify({
                                    type: 'response.create'
                                }));
                            })
                            .finally(() => {
                                setMicEnabled(true); // 🎤 Unmute mic after processing
                            });
                    }
                    break;

                case 'response.done':
                    updateState('listening');
                    currentResponseIdRef.current = null;
                    break;

                case 'conversation.item.truncated':
                    // ✅ KEY EVENT: Audio was truncated due to interruption
                    // Clear the audio queue immediately
                    console.log('🔴 conversation.item.truncated - clearing audio queue');
                    stopAllAudio();
                    updateState('listening');
                    break;

                case 'error':
                    console.error('WebRTC error:', msg.error);
                    onErrorRef.current?.(msg.error?.message || 'Unknown error');
                    break;
            }
        } catch (e) {
            console.error('Failed to parse data channel message:', e);
            onDebugRef.current?.(`Data Channel Parse Error: ${e}`);
        }
    }, [updateState, addTranscript, stopAllAudio]);

    // Setup audio level monitoring
    const setupAudioLevelMonitoring = useCallback((stream: MediaStream) => {
        audioContextRef.current = new AudioContext();
        const source = audioContextRef.current.createMediaStreamSource(stream);
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 256;
        source.connect(analyserRef.current);

        const updateLevel = () => {
            if (!analyserRef.current) return;

            const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
            analyserRef.current.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
            setInputLevel(average / 255);

            animationFrameRef.current = requestAnimationFrame(updateLevel);
        };

        updateLevel();
    }, []);

    // Connect to WebRTC
    const connect = useCallback(async () => {
        try {
            updateState('connecting');

            // Get ephemeral token from backend
            const { token, webrtc_url, ice_servers } = await getRealtimeToken(voice);
            onDebugRef.current?.(`Token OK. URL: ${webrtc_url.slice(0, 40)}...`);

            // Create RTCPeerConnection
            const pc = new RTCPeerConnection({
                iceServers: ice_servers.length > 0 ? ice_servers : [
                    { urls: 'stun:stun.l.google.com:19302' }
                ]
            });
            pcRef.current = pc;

            // Handle incoming audio track
            pc.ontrack = (event) => {
                console.log('🔊 Received remote audio track');
                onDebugRef.current?.('Received remote audio track');
                const audio = new Audio();
                audio.srcObject = event.streams[0];
                audio.play().catch(console.error);

                // Monitor output level
                if (audioContextRef.current) {
                    const source = audioContextRef.current.createMediaStreamSource(event.streams[0]);
                    const analyser = audioContextRef.current.createAnalyser();
                    analyser.fftSize = 256;
                    source.connect(analyser);

                    const updateOutputLevel = () => {
                        if (pcRef.current?.connectionState === 'closed') return;
                        const dataArray = new Uint8Array(analyser.frequencyBinCount);
                        analyser.getByteFrequencyData(dataArray);
                        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
                        setOutputLevel(average / 255);
                        requestAnimationFrame(updateOutputLevel);
                    };
                    updateOutputLevel();
                }
            };

            // Get microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 24000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            localStreamRef.current = stream;

            // Add local audio track - GUARDED against closed connection
            if (pc.signalingState !== 'closed') {
                stream.getTracks().forEach(track => pc.addTrack(track, stream));
            } else {
                console.warn('Connection closed before adding tracks');
                return;
            }

            // Setup audio level monitoring
            setupAudioLevelMonitoring(stream);

            // Create data channel for events
            const dc = pc.createDataChannel('oai-events');
            dcRef.current = dc;

            dc.onopen = () => {
                console.log('📡 Data channel opened');
                onDebugRef.current?.('Data channel opened');

                // Send session configuration
                // Simplified to avoid validation errors
                // input_audio_format is for buffer/rest, not needed for WebRTC usually
                dc.send(JSON.stringify({
                    type: 'session.update',
                    session: {
                        modalities: ['text', 'audio'],
                        voice: voice,
                        input_audio_transcription: { model: 'whisper-1' },
                        turn_detection: {
                            type: 'server_vad',
                            threshold: 0.6, // Increased to prevent echo triggering interruption
                            prefix_padding_ms: 300,
                            silence_duration_ms: 1000
                        }
                    }
                }));
            };

            dc.onmessage = handleDataChannelMessage;

            dc.onerror = (error) => {
                console.error('Data channel error:', error);
                onErrorRef.current?.('Data channel error');
            };

            // Create and set local description
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            // Wait for ICE gathering to complete (with timeout)
            await new Promise<void>((resolve) => {
                if (pc.iceGatheringState === 'complete') {
                    resolve();
                    return;
                }

                const timeout = setTimeout(() => {
                    console.warn('⚠️ ICE gathering timed out - proceeding with gathered candidates');
                    resolve();
                }, 2000);

                pc.onicegatheringstatechange = () => {
                    if (pc.iceGatheringState === 'complete') {
                        clearTimeout(timeout);
                        resolve();
                    }
                };
            });

            // Send offer to Azure WebRTC endpoint
            onDebugRef.current?.(`Sending SDP to ${webrtc_url.split('?')[0]}...`);
            const sdpResponse = await fetch(webrtc_url, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/sdp'
                },
                body: pc.localDescription?.sdp
            });

            if (!sdpResponse.ok) {
                const text = await sdpResponse.text();
                onDebugRef.current?.(`SDP Error ${sdpResponse.status}: ${text.slice(0, 100)}`);
                throw new Error(`WebRTC negotiation failed: ${sdpResponse.status}`);
            }

            const answerSdp = await sdpResponse.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });

            updateState('connected');
            console.log('✅ WebRTC connection established');
            onDebugRef.current?.('WebRTC connected');

        } catch (error) {
            console.error('WebRTC connection error:', error);
            updateState('error');

            // Detailed error message for users
            let errorMessage = error instanceof Error ? error.message : 'Connection failed';

            if (errorMessage.includes('404')) {
                errorMessage += ' (Invalid WebRTC URL - check resource/region)';
            } else if (errorMessage.includes('401') || errorMessage.includes('403')) {
                errorMessage += ' (Auth failed - check token)';
            } else if (errorMessage.includes('negotiation failed')) {
                errorMessage += ' (SDP Handshake failed)';
            } else if (errorMessage.includes('Connection closed')) {
                errorMessage += ' (Interrupted - retry)';
            }

            onErrorRef.current?.(errorMessage);
        }
    }, [voice, updateState, handleDataChannelMessage, setupAudioLevelMonitoring]);

    // Disconnect
    const disconnect = useCallback(() => {
        // Stop animation frame
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
        }

        // Close data channel
        if (dcRef.current) {
            dcRef.current.close();
            dcRef.current = null;
        }

        // Close peer connection
        if (pcRef.current) {
            pcRef.current.close();
            pcRef.current = null;
        }

        // Stop local stream
        if (localStreamRef.current) {
            localStreamRef.current.getTracks().forEach(track => track.stop());
            localStreamRef.current = null;
        }

        // Close audio context
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        stopAllAudio();
        updateState('disconnected');
        console.log('🔌 WebRTC disconnected');
    }, [stopAllAudio, updateState]);

    // Interrupt - cancel current response
    const interrupt = useCallback(() => {
        if (dcRef.current && dcRef.current.readyState === 'open' && currentResponseIdRef.current) {
            console.log('🔴 Sending response.cancel');
            dcRef.current.send(JSON.stringify({
                type: 'response.cancel'
            }));
            stopAllAudio();
        }
    }, [stopAllAudio]);

    // Toggle microphone manually
    const toggleMic = useCallback(() => {
        if (localStreamRef.current) {
            const enabled = !localStreamRef.current.getAudioTracks()[0].enabled;
            setMicEnabled(enabled);
            return enabled;
        }
        return false;
    }, [setMicEnabled]);

    // Track mic state
    const [isMuted, setIsMuted] = useState(false);

    // Update isMuted when setMicEnabled is called
    const setMicEnabledWithState = useCallback((enabled: boolean) => {
        setMicEnabled(enabled);
        setIsMuted(!enabled);
    }, [setMicEnabled]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    return {
        state,
        inputLevel,
        outputLevel,
        transcripts,
        connect,
        disconnect,
        interrupt,
        toggleMic,
        isMuted
    };
}
