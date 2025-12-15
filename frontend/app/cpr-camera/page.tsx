"use client"

import { motion, AnimatePresence } from "framer-motion"
import {
  Camera,
  CameraOff,
  ArrowLeft,
  Play,
  AlertCircle,
  Heart,
  Info,
  Volume2,
} from "lucide-react"
import Link from "next/link"
import { useState, useRef, useEffect, useCallback } from "react"
import { io, Socket } from "socket.io-client"

type CPRState = "idle" | "ready" | "active"
type FeedbackType = "correct" | "incorrect" | "neutral"

interface CompressionFeedback {
  depth: FeedbackType
  rate: FeedbackType
  position: FeedbackType
}

interface CPRScores {
  overall: number
  depth_score: number
  depth_cm: number
  rate_score: number
  rate_cpm: number
  hand_position_score: number
  compression_count: number
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

export default function CPRCameraPage() {
  const [cprState, setCprState] = useState<CPRState>("idle")
  const [compressionCount, setCompressionCount] = useState(0)
  const [feedback, setFeedback] = useState<CompressionFeedback>({
    depth: "neutral",
    rate: "neutral",
    position: "neutral",
  })
  const [scores, setScores] = useState<CPRScores | null>(null)
  const [cameraPermission, setCameraPermission] = useState<boolean | null>(null)
  const [videoReady, setVideoReady] = useState(false)
  const [vlmFeedback, setVlmFeedback] = useState<string | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected")
  const [debugLog, setDebugLog] = useState<string[]>([])
  const [ttsEnabled, setTtsEnabled] = useState(true)
  
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const socketRef = useRef<Socket | null>(null)
  const frameIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  // FIX: addLog must be defined BEFORE speak because speak relies on it 
  // in its dependency array and its function body.
  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    const logMessage = `[${timestamp}] ${message}`
    console.log(logMessage)
    setDebugLog(prev => [...prev.slice(-20), logMessage])
  }, [])

  // Text-to-Speech function
  const speak = useCallback((text: string) => {
    if (!ttsEnabled || !text) return
    
    try {
      // Cancel any ongoing speech
      window.speechSynthesis.cancel()
      
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'fr-FR'
      utterance.rate = 0.9
      utterance.pitch = 1.0
      utterance.volume = 1.0
      
      // Try to find a French voice
      const voices = window.speechSynthesis.getVoices()
      const frenchVoice = voices.find(voice => voice.lang.startsWith('fr'))
      if (frenchVoice) {
        utterance.voice = frenchVoice
      }
      
      window.speechSynthesis.speak(utterance)
      addLog('🔊 Speaking: ' + text)
    } catch (error: any) {
      addLog('⚠️ TTS error: ' + error.message)
    }
  }, [ttsEnabled, addLog]) // addLog is now defined

  // Initialize WebSocket
  useEffect(() => {
    addLog('🔌 Initializing Socket.IO connection to: ' + BACKEND_URL)
    setConnectionStatus('connecting')
    
    const socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    })

    socketRef.current = socket

    socket.on('connect', () => {
      addLog('✅ Socket.IO connected!')
      setConnectionStatus('connected')
    })

    socket.on('disconnect', () => {
      addLog('❌ Socket.IO disconnected')
      setConnectionStatus('disconnected')
    })

    socket.on('cpr_analysis', (data) => {
      if (data.detection && data.scores) {
        setScores(data.scores)
        setCompressionCount(data.scores.compression_count)
        setFeedback(data.feedback)
        addLog(`📊 Analysis: ${data.scores.compression_count} compressions, ${data.scores.overall}% score`)
      } else {
        addLog('⚠️ No CPR detected in frame')
      }
    })

    socket.on('vlm_feedback', (data) => {
      addLog('💡 VLM: ' + data.advice)
      setVlmFeedback(data.advice)
      speak(data.advice)  // Speak the advice!
      setTimeout(() => setVlmFeedback(null), 8000)
    })

    socket.on('error', (data) => {
      addLog('❌ Backend error: ' + data.message)
    })

    return () => {
      addLog('🔌 Cleaning up socket')
      socket.disconnect()
    }
  }, [addLog, speak]) // Added 'speak' to dependencies for completeness

  const startCamera = useCallback(async () => {
    try {
      addLog('📷 Requesting camera access...')
      
      // Check video ref BEFORE requesting camera
      if (!videoRef.current) {
        addLog('❌ Video ref is null before camera request!')
        await new Promise(resolve => setTimeout(resolve, 100))
        if (!videoRef.current) {
          addLog('❌ Video ref still null after delay!')
          throw new Error('Video element not ready')
        }
      }
      
      addLog('✅ Video ref confirmed present')
      
      // Request camera with specific constraints
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { 
          facingMode: "user",
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false,
      })
      
      addLog(`✅ Camera stream obtained - ${stream.getTracks().length} track(s)`)
      stream.getTracks().forEach(track => {
        addLog(`   Track: ${track.kind} - ${track.label} - ${track.readyState}`)
      })
      
      streamRef.current = stream
      
      // Double-check video ref again
      if (!videoRef.current) {
        addLog('❌ Video ref is null after stream obtained!')
        throw new Error('Video element disappeared')
      }
      
      // Attach stream to video element
      videoRef.current.srcObject = stream
      addLog('✅ Stream attached to video element')
      
      // Set video attributes explicitly
      videoRef.current.setAttribute('playsinline', 'true')
      videoRef.current.setAttribute('autoplay', 'true')
      videoRef.current.muted = true
      
      // Wait for video to be ready
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          addLog('❌ Video load timeout after 5 seconds')
          reject(new Error('Video load timeout'))
        }, 5000)
        
        if (!videoRef.current) {
          clearTimeout(timeout)
          reject(new Error('Video ref is null'))
          return
        }
        
        videoRef.current.onloadedmetadata = async () => {
          if (!videoRef.current) return
          
          addLog(`✅ Video metadata loaded: ${videoRef.current.videoWidth}x${videoRef.current.videoHeight}`)
          addLog(`   readyState: ${videoRef.current.readyState}`)
          
          try {
            // Explicitly play the video
            await videoRef.current.play()
            addLog('✅ Video.play() successful')
            addLog(`   paused: ${videoRef.current.paused}`)
            addLog(`   currentTime: ${videoRef.current.currentTime}`)
            
            clearTimeout(timeout)
            setVideoReady(true)
            resolve()
          } catch (playError: any) {
            addLog('❌ Video.play() failed: ' + playError.message)
            clearTimeout(timeout)
            reject(playError)
          }
        }
        
        videoRef.current.onerror = (e) => {
          addLog('❌ Video element error: ' + e)
          clearTimeout(timeout)
          reject(e)
        }
      })
      
      setCameraPermission(true)
      setCprState("ready")
      addLog('✅ Camera ready - State updated to "ready"')
      
      // Initialize backend
      addLog('🔄 Initializing backend session...')
      try {
        const response = await fetch(`${BACKEND_URL}/api/cpr/initialize`, { 
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          const data = await response.json()
          addLog('✅ Backend initialized: ' + JSON.stringify(data))
        } else {
          addLog('⚠️ Backend init failed: ' + response.status)
        }
      } catch (err: any) {
        addLog('⚠️ Backend init error: ' + err.message)
      }
    } catch (error: any) {
      addLog('❌ Camera error: ' + error.message)
      console.error('Full camera error:', error)
      setCameraPermission(false)
      setVideoReady(false)
      
      // Clean up stream if it was created
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => {
          track.stop()
          addLog('🛑 Stopped track: ' + track.label)
        })
        streamRef.current = null
      }
    }
  }, [addLog])

  const stopCamera = useCallback(() => {
    addLog('🛑 Stopping camera...')
    
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current)
      frameIntervalRef.current = null
      addLog('⏹️ Stopped frame capture')
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop()
        addLog(`🛑 Stopped track: ${track.label}`)
      })
      streamRef.current = null
    }
    
    if (videoRef.current) {
      videoRef.current.srcObject = null
      videoRef.current.pause()
    }
    
    setCprState("idle")
    setCameraPermission(null)
    setVideoReady(false)
    setScores(null)
    setCompressionCount(0)
    
    fetch(`${BACKEND_URL}/api/cpr/stop`, { method: 'POST' })
      .then(() => addLog('✅ Backend stopped'))
      .catch((err) => addLog('⚠️ Backend stop error: ' + err.message))
  }, [addLog])

  const captureAndSendFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !socketRef.current) {
      return
    }

    const video = videoRef.current
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')

    if (!ctx || video.readyState !== video.HAVE_ENOUGH_DATA) {
      return
    }

    try {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      const frameData = canvas.toDataURL('image/jpeg', 0.8)
      socketRef.current.emit('video_frame', {
        frame: frameData,
        timestamp: Date.now()
      })
    } catch (err: any) {
      addLog('❌ Frame capture error: ' + err.message)
    }
  }, [addLog])

  const startCPR = useCallback(async () => {
    addLog('▶️ Starting CPR monitoring...')
    setCprState("active")
    setCompressionCount(0)
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/cpr/start`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (response.ok) {
        addLog('✅ Backend CPR started')
      } else {
        addLog('⚠️ Backend start failed: ' + response.status)
      }
    } catch (error: any) {
      addLog('❌ Backend start error: ' + error.message)
    }

    // Start frame capture at 10 FPS
    frameIntervalRef.current = setInterval(() => {
      captureAndSendFrame()
    }, 100)
    
    addLog('✅ Frame capture started (10 FPS)')
  }, [captureAndSendFrame, addLog])

  // Load voices when available
  useEffect(() => {
    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      if (voices.length > 0) {
        const frVoices = voices.filter(v => v.lang.startsWith('fr'))
        addLog(`🔊 TTS: ${voices.length} voices available, ${frVoices.length} French`)
      }
    }
    
    loadVoices()
    window.speechSynthesis.onvoiceschanged = loadVoices
  }, [addLog])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
      if (frameIntervalRef.current) {
        clearInterval(frameIntervalRef.current)
      }
      window.speechSynthesis.cancel()
    }
  }, [])

  return (
    <div className="min-h-[100dvh] bg-slate-900 flex flex-col">
      <canvas ref={canvasRef} className="hidden" />

      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-50 bg-black/70 backdrop-blur-xl border-b border-white/5"
      >
        <div className="w-full max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white/80 hover:text-white">
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium">Retour</span>
          </Link>
          <div className="flex items-center gap-2">
            <Heart className="w-4 h-4 text-red-500" />
            <span className="font-semibold text-white text-sm">CPR Debug Mode</span>
            <div 
              className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected' ? 'bg-green-500' : 
                connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
              }`} 
              title={connectionStatus}
            />
            <button
              onClick={() => setTtsEnabled(!ttsEnabled)}
              className={`ml-2 p-1.5 rounded-lg transition-colors ${
                ttsEnabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
              }`}
              title={ttsEnabled ? 'Audio ON' : 'Audio OFF'}
            >
              <Volume2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <div className="flex-1 flex flex-col lg:flex-row gap-4 p-4 max-w-7xl mx-auto w-full">
        {/* Camera View */}
        <div className="flex-1 relative bg-black rounded-2xl overflow-hidden min-h-[500px] border-2 border-white/10">
          {cprState === "idle" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6">
              <Camera className="w-16 h-16 text-cyan-400 mb-4" />
              <h2 className="text-2xl font-bold text-white mb-2">CPR Camera Debug</h2>
              <p className="text-white/60 text-center mb-6 max-w-md">
                This diagnostic version will help identify camera issues
              </p>

              <button
                onClick={startCamera}
                disabled={connectionStatus !== 'connected'}
                className="px-8 py-4 bg-gradient-to-r from-cyan-500 to-teal-500 text-white rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 transition-transform"
              >
                {connectionStatus === 'connected' ? 'Test Camera' : 
                  connectionStatus === 'connecting' ? 'Connecting...' : 'Server Offline'}
              </button>

              {cameraPermission === false && (
                <div className="mt-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl max-w-md">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
                    <div>
                      <p className="text-red-300 font-medium text-sm">Camera Access Denied</p>
                      <p className="text-red-300/70 text-xs mt-1">Check browser permissions</p>
                    </div>
                  </div>
                </div>
              )}

              {connectionStatus === 'disconnected' && (
                <div className="mt-6 p-4 bg-amber-500/20 border border-amber-500/30 rounded-xl max-w-md">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5" />
                    <div>
                      <p className="text-amber-300 font-medium text-sm">Backend Disconnected</p>
                      <p className="text-amber-300/70 text-xs mt-1">
                        Make sure api_server.py is running on port 5000
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : null}
          
          {/* Video element - ALWAYS rendered, just hidden when idle */}
          <div className={`relative w-full h-full ${cprState === "idle" ? "hidden" : ""}`}>
            {/* Video element with explicit styling */}
            <video 
              ref={videoRef} 
              autoPlay 
              playsInline 
              muted
              className="w-full h-full object-cover"
              style={{
                display: 'block',
                backgroundColor: '#000',
                minHeight: '500px',
                minWidth: '100%'
              }}
            />
            
            {/* Debug overlay to verify video is rendering */}
            {videoReady && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                <div className="bg-cyan-500/20 border-2 border-cyan-500 rounded-lg p-4 text-center">
                  <p className="text-cyan-300 text-sm font-mono">
                    Video Element Active
                    <br />
                    {videoRef.current?.videoWidth}x{videoRef.current?.videoHeight}
                  </p>
                </div>
              </div>
            )}
            
            {/* Loading indicator */}
            {!videoReady && cprState !== "idle" && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80 z-10">
                <div className="text-center">
                  <div className="w-16 h-16 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-white text-sm">Loading video...</p>
                </div>
              </div>
            )}
            
            {/* Video ready indicator */}
            {videoReady && cprState !== "idle" && (
              <div className="absolute top-4 left-4 bg-green-500/90 backdrop-blur-sm rounded-lg px-3 py-1.5 z-20 shadow-lg">
                <span className="text-white text-xs font-semibold">🎥 Camera Active</span>
              </div>
            )}
            
            {/* Test pattern overlay - helps verify rendering */}
            {videoReady && (
              <div className="absolute bottom-4 left-4 bg-purple-500/80 rounded-lg px-3 py-2 text-white text-xs font-mono z-20">
                Stream: {streamRef.current?.active ? '✓ Active' : '✗ Inactive'}
                <br />
                Tracks: {streamRef.current?.getTracks().length || 0}
              </div>
            )}
            
            {cprState === "ready" && videoReady && (
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
                <button
                  onClick={startCPR}
                  className="px-6 py-3 bg-gradient-to-r from-emerald-500 to-green-600 text-white rounded-xl font-semibold flex items-center gap-2 hover:scale-105 transition-transform shadow-lg"
                >
                  <Play className="w-5 h-5" />
                  Start CPR Analysis
                </button>
              </div>
            )}

            {cprState === "active" && scores && (
              <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-md rounded-xl p-4 text-white">
                <div className="text-3xl font-bold mb-2">{scores.compression_count}</div>
                <div className="text-xs text-white/60 mb-3">Compressions</div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between gap-4">
                    <span className="text-white/60">Rate:</span>
                    <span className="font-semibold">{scores.rate_cpm}/min</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-white/60">Depth:</span>
                    <span className="font-semibold">{scores.depth_cm}cm</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="text-white/60">Score:</span>
                    <span className="font-semibold">{scores.overall}%</span>
                  </div>
                </div>
              </div>
            )}

            {cprState !== "idle" && (
              <button
                onClick={stopCamera}
                className="absolute top-4 right-4 w-12 h-12 rounded-xl bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors shadow-lg"
              >
                <CameraOff className="w-6 h-6" />
              </button>
            )}
          </div>
        </div>

        {/* Debug Panel */}
        <div className="lg:w-96 bg-slate-800 rounded-2xl p-4 flex flex-col border-2 border-white/10">
          <div className="flex items-center gap-2 mb-4">
            <Info className="w-5 h-5 text-cyan-400" />
            <h3 className="font-bold text-white">Debug Console</h3>
          </div>
          
          <div className="flex-1 bg-black/50 rounded-xl p-3 overflow-y-auto font-mono text-xs space-y-1 max-h-[400px] min-h-[300px]">
            {debugLog.length === 0 ? (
              <div className="text-white/40">Waiting for events...</div>
            ) : (
              debugLog.map((log, i) => (
                <div 
                  key={i} 
                  className={`whitespace-pre-wrap break-all ${
                    log.includes('❌') ? 'text-red-400' : 
                    log.includes('✅') ? 'text-green-400' : 
                    log.includes('⚠️') ? 'text-yellow-400' : 
                    log.includes('💡') ? 'text-purple-400' :
                    log.includes('🔍') ? 'text-blue-400' :
                    'text-green-300'
                  }`}
                >
                  {log}
                </div>
              ))
            )}
          </div>

          <div className="mt-4 space-y-2 text-xs">
            <div className="flex justify-between p-2 bg-black/30 rounded">
              <span className="text-white/60">Backend:</span>
              <span className={connectionStatus === 'connected' ? 'text-green-400 font-semibold' : 'text-red-400 font-semibold'}>
                {connectionStatus}
              </span>
            </div>
            <div className="flex justify-between p-2 bg-black/30 rounded">
              <span className="text-white/60">Camera:</span>
              <span className={cameraPermission ? 'text-green-400 font-semibold' : 'text-white/40'}>
                {cameraPermission === null ? 'Not requested' : cameraPermission ? 'Active' : 'Denied'}
              </span>
            </div>
            <div className="flex justify-between p-2 bg-black/30 rounded">
              <span className="text-white/60">Video Ready:</span>
              <span className={videoReady ? 'text-green-400 font-semibold' : 'text-white/40'}>
                {videoReady ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex justify-between p-2 bg-black/30 rounded">
              <span className="text-white/60">State:</span>
              <span className="text-cyan-400 font-semibold">{cprState}</span>
            </div>
            {scores && (
              <div className="flex justify-between p-2 bg-black/30 rounded">
                <span className="text-white/60">Compressions:</span>
                <span className="text-cyan-400 font-semibold">{compressionCount}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}