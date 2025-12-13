"use client"

import { motion, AnimatePresence } from "framer-motion"
import { Phone, PhoneOff, Mic, MicOff, Volume2, VolumeX, ArrowLeft, Heart, Shield, MessageCircle, Zap, Activity, WifiOff, Send, Radio, Waves } from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { isApiAvailable } from "@/lib/api"
import { useWebRTCVoice, VoiceState } from "@/hooks/useWebRTCVoice"

type CallState = "idle" | "disconnected" | "connecting" | "connected" | "listening" | "user_speaking" | "processing" | "speaking" | "ended" | "error"

// ===========================================
// Audio-Synchronized Waveform Component
// ===========================================
function AudioWaveform({
  audioLevel,
  isActive,
  isSpeaking,
  barCount = 48,
}: {
  audioLevel: number
  isActive: boolean
  isSpeaking: boolean
  barCount?: number
}) {
  const bars = useMemo(() => Array.from({ length: barCount }), [barCount])

  return (
    <div className="flex items-center justify-center gap-[2px] sm:gap-1 h-32 sm:h-40 px-4">
      {bars.map((_, i) => {
        const center = barCount / 2
        const distanceFromCenter = Math.abs(i - center) / center

        // Base height influenced by position (higher in center)
        const positionFactor = 1 - distanceFromCenter * 0.6

        // Audio level influence (stable)
        const audioFactor = audioLevel

        // Calculate final height
        const minHeight = 4
        const maxHeight = isSpeaking ? 120 : 80
        const targetHeight = minHeight + (maxHeight - minHeight) * positionFactor * audioFactor

        // Color based on speaking state
        const gradient = isSpeaking
          ? "from-emerald-400 via-green-400 to-teal-300"
          : "from-cyan-400 via-teal-400 to-cyan-300"

        const glowColor = isSpeaking
          ? "rgba(52, 211, 153, 0.6)"
          : "rgba(34, 211, 238, 0.6)"

        return (
          <div
            key={i}
            className={`w-1 sm:w-1.5 rounded-full bg-gradient-to-t ${gradient}`}
            style={{
              height: isActive ? Math.max(minHeight, targetHeight) : minHeight,
              opacity: isActive ? 0.7 + audioLevel * 0.3 : 0.3,
              boxShadow: isActive && audioLevel > 0.1
                ? `0 0 ${8 + audioLevel * 15}px ${glowColor}`
                : "none",
              transition: "height 70ms ease-out, opacity 120ms ease-out",
              willChange: isActive ? "height, opacity" : undefined,
            }}
          />
        )
      })}
    </div>
  )
}

// ===========================================
// Pulse Rings with Audio Response
// ===========================================
function AudioPulseRings({
  audioLevel,
  isActive,
  isSpeaking,
}: {
  audioLevel: number
  isActive: boolean
  isSpeaking: boolean
}) {
  const baseColor = isSpeaking ? "border-emerald-500" : "border-cyan-500"

  return (
    <div className="absolute inset-0 flex items-center justify-center">
      {[1, 2, 3, 4, 5].map((ring) => {
        const ringScale = 1 + audioLevel * 0.3 * ring
        const ringOpacity = Math.max(0, 0.4 - ring * 0.08) * (0.5 + audioLevel * 0.5)

        return (
          <motion.div
            key={ring}
            className={`absolute rounded-full border-2 ${baseColor}`}
            style={{
              width: 120 + ring * 40,
              height: 120 + ring * 40,
            }}
            animate={
              isActive
                ? {
                  scale: [ringScale * 0.9, ringScale * 1.1, ringScale * 0.9],
                  opacity: [ringOpacity * 0.8, ringOpacity, ringOpacity * 0.8],
                }
                : { scale: 0.8, opacity: 0 }
            }
            transition={{
              duration: 0.8 + ring * 0.2,
              repeat: Infinity,
              delay: ring * 0.1,
              ease: "easeInOut",
            }}
          />
        )
      })}
    </div>
  )
}


// ===========================================
// Animated Background
// ===========================================
function AnimatedBackground({ audioLevel }: { audioLevel: number }) {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <motion.div
        className="absolute inset-0"
        animate={{
          background: [
            `radial-gradient(ellipse at center, rgba(6, 182, 212, ${0.15 + audioLevel * 0.1}) 0%, rgba(15, 23, 42, 1) 70%)`,
            `radial-gradient(ellipse at center, rgba(20, 184, 166, ${0.15 + audioLevel * 0.1}) 0%, rgba(15, 23, 42, 1) 70%)`,
            `radial-gradient(ellipse at center, rgba(6, 182, 212, ${0.15 + audioLevel * 0.1}) 0%, rgba(15, 23, 42, 1) 70%)`,
          ],
        }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  )
}


// ===========================================
// Status Indicator
// ===========================================
function StatusIndicator({ state }: { state: CallState }) {
  const config: Record<CallState, { icon: typeof Mic; color: string; text: string }> = {
    listening: { icon: Mic, color: "from-cyan-400 to-teal-500", text: "Écoute..." },
    user_speaking: { icon: Radio, color: "from-blue-400 to-cyan-500", text: "Parole détectée" },
    processing: { icon: Activity, color: "from-amber-400 to-orange-500", text: "Traitement..." },
    speaking: { icon: Volume2, color: "from-emerald-400 to-green-500", text: "Réponse..." },
    connecting: { icon: Waves, color: "from-purple-400 to-pink-500", text: "Connexion..." },
    connected: { icon: Waves, color: "from-green-400 to-emerald-500", text: "Connecté" },
    idle: { icon: Phone, color: "from-slate-400 to-slate-500", text: "Prêt" },
    disconnected: { icon: Phone, color: "from-slate-400 to-slate-500", text: "Déconnecté" },
    ended: { icon: Heart, color: "from-rose-400 to-red-500", text: "Terminé" },
    error: { icon: WifiOff, color: "from-red-400 to-rose-500", text: "Erreur" },
  }

  const current = config[state]
  const Icon = current.icon

  return (
    <motion.div
      key={state}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r ${current.color} shadow-lg`}
    >
      <Icon className="w-4 h-4 text-white" />
      <span className="text-sm font-medium text-white">{current.text}</span>
    </motion.div>
  )
}

// ===========================================
// Main Voice Call Page
// ===========================================
export default function VoiceCallPage() {
  // WebRTC Voice Hook
  const {
    state: webrtcState,
    inputLevel: inputAudioLevel,
    outputLevel: outputAudioLevel,
    transcripts,
    connect,
    disconnect,
    interrupt,
    toggleMic,
    isMuted
  } = useWebRTCVoice({
    voice: 'cedar',
    onStateChange: (newState) => {
      console.log('WebRTC state:', newState);
    },
    onError: (error) => {
      console.error('WebRTC error:', error);
      setIsApiConnected(false);
    },
    onDebug: (msg) => addLog(msg)
  });

  // Map WebRTC state to CallState
  const [callEnded, setCallEnded] = useState(false);
  const callState: CallState = callEnded ? 'ended' : (webrtcState === 'disconnected' ? 'idle' : webrtcState);

  // UI State
  // Removed local isMuted state in favor of hook state
  const [isSpeakerOn, setIsSpeakerOn] = useState(true)
  const [isApiConnected, setIsApiConnected] = useState(true)
  const [textInput, setTextInput] = useState("")
  // ... (rest of component) ...

  // Mute toggle handler
  const handleMuteToggle = useCallback(() => {
    if (toggleMic) {
      toggleMic();
    }
  }, [toggleMic]);

  // Combined audio level for visualization
  const audioLevel = callState === "speaking" || callState === "processing"
    ? outputAudioLevel
    : inputAudioLevel

  // Check API availability
  useEffect(() => {
    const checkApi = async () => {
      const available = await isApiAvailable()
      setIsApiConnected(available)
    }
    checkApi()
    const interval = setInterval(checkApi, 30000)
    return () => clearInterval(interval)
  }, [])

  // Start call using WebRTC
  const startCall = useCallback(async () => {
    try {
      await connect();
    } catch (error) {
      console.error("Failed to start call:", error);
      setIsApiConnected(false);
    }
  }, [connect]);

  // End call
  const endCall = useCallback(() => {
    disconnect();
    setCallEnded(true);
    setTimeout(() => setCallEnded(false), 2000);
  }, [disconnect]);

  // Send text message (placeholder - WebRTC uses data channel)
  const sendTextMessage = useCallback(() => {
    // TODO: Implement text message via data channel if needed
    setTextInput("");
  }, []);

  const isCallActive = ["listening", "user_speaking", "processing", "speaking", "connecting", "connected"].includes(callState)

  // Debug logs state
  const [logs, setLogs] = useState<string[]>([])
  const addLog = useCallback((msg: string) => {
    setLogs(prev => [...prev, `${new Date().toISOString().split('T')[1].split('.')[0]} - ${msg}`].slice(-10))
  }, [])

  // Expose WebRTC logs to UI
  useEffect(() => {
    if (webrtcState) addLog(`WebRTC State: ${webrtcState}`)
  }, [webrtcState, addLog])

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={callState === "idle" || callState === "ended" ? "idle" : "active"}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className={`min-h-[100dvh] relative overflow-hidden ${isCallActive
          ? "bg-slate-900"
          : "bg-gradient-to-b from-slate-50 via-cyan-50/30 to-slate-50"
          }`}
      >
        {/* Background Effects removed for performance */}

        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`sticky top-0 z-50 safe-area-top ${isCallActive ? "bg-transparent" : "backdrop-blur-2xl bg-white/85 border-b border-slate-100/50 shadow-sm"
            }`}
        >
          <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex items-center justify-between">
            <Link
              href="/"
              className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all active:scale-95 ${isCallActive
                ? "text-white/80 hover:text-white hover:bg-white/10"
                : "text-slate-600 hover:text-slate-800 hover:bg-slate-100"
                }`}
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="font-medium text-sm sm:text-base">Retour</span>
            </Link>

            {isCallActive && (
              <div className="flex items-center gap-3">
                <StatusIndicator state={callState} />
              </div>
            )}

            {!isCallActive && (
              <Link
                href="/chat"
                className="flex items-center gap-2 px-3 py-2 text-slate-600 hover:text-[#0891B2] hover:bg-cyan-50 rounded-xl transition-all"
              >
                <MessageCircle className="w-5 h-5" />
                <span className="hidden sm:inline text-sm font-medium">Chat</span>
              </Link>
            )}
          </div>
        </motion.header>

        <main className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-4 sm:py-8 relative z-10">
          {/* DEBUG LOGS OVERLAY */}
          <div className="fixed bottom-4 left-4 z-50 w-64 max-h-48 overflow-y-auto bg-black/80 text-green-400 text-[10px] font-mono p-2 rounded pointer-events-none opacity-70">
            <div>DEBUG LOGS:</div>
            {logs.map((L, i) => <div key={i}>{L}</div>)}
          </div>

          {/* Idle State */}
          {callState === "idle" && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-5 sm:space-y-8">
              {/* API Connection Warning */}
              {!isApiConnected && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl"
                >
                  <WifiOff className="w-5 h-5 text-amber-500" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-amber-800">Mode hors ligne</p>
                    <p className="text-xs text-amber-600">L&apos;assistant vocal n&apos;est pas disponible</p>
                  </div>
                </motion.div>
              )}

              {/* Hero Card */}
              <motion.div
                className="bg-white rounded-3xl p-5 sm:p-7 shadow-xl shadow-slate-200/50 border border-slate-100"
                whileHover={{ y: -2, boxShadow: "0 25px 50px -12px rgba(0,0,0,0.12)" }}
              >
                <div className="flex items-center gap-4 sm:gap-5 mb-4 sm:mb-5">
                  <motion.div className="relative" whileHover={{ scale: 1.05, rotate: 3 }}>
                    <div className="w-18 h-18 sm:w-24 sm:h-24 rounded-2xl bg-gradient-to-br from-cyan-100 via-teal-50 to-emerald-100 border-3 border-white shadow-xl overflow-hidden">
                      <Image
                        src="/images/logo-llama.png"
                        alt="Assistant IA Monkedh"
                        width={96}
                        height={96}
                        className="object-cover scale-110 w-full h-full"
                        unoptimized
                      />
                    </div>
                    <motion.div
                      className="absolute -bottom-1.5 -right-1.5 w-7 h-7 sm:w-8 sm:h-8 bg-gradient-to-r from-emerald-400 to-green-500 rounded-full border-3 border-white flex items-center justify-center shadow-lg"
                      animate={{ scale: [1, 1.15, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    >
                      <Mic className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                    </motion.div>
                  </motion.div>
                  <div className="flex-1">
                    <h1 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">
                      Assistant Vocal IA
                    </h1>
                    <p className="text-sm sm:text-base text-slate-500 mt-1">
                      🇹🇳 Secourisme d&apos;urgence Tunisie
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">
                        GPT-Realtime
                      </span>
                      <span className="px-2 py-0.5 bg-cyan-100 text-cyan-700 text-xs font-medium rounded-full">
                        Audio bidirectionnel
                      </span>
                    </div>
                  </div>
                </div>
                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  Communication vocale en <span className="font-semibold text-[#0891B2]">temps réel</span> avec notre IA médicale.
                  Parlez naturellement - l&apos;assistant vous répond instantanément avec une voix naturelle.
                </p>
              </motion.div>

              {/* Call Button */}
              <div className="flex flex-col items-center gap-5 sm:gap-7 py-4">
                <motion.button
                  onClick={() => { addLog('Start Call Clicked'); startCall(); }}
                  disabled={!isApiConnected}
                  className={`relative w-32 h-32 sm:w-40 sm:h-40 rounded-full text-white shadow-2xl active:scale-95 ${isApiConnected
                    ? "bg-gradient-to-br from-[#22C55E] via-emerald-500 to-green-600 shadow-emerald-500/50"
                    : "bg-gradient-to-br from-slate-400 via-slate-500 to-slate-600 shadow-slate-500/50 cursor-not-allowed"
                    }`}
                  whileHover={isApiConnected ? { scale: 1.08 } : {}}
                  whileTap={isApiConnected ? { scale: 0.95 } : {}}
                >
                  {[1, 2, 3].map((ring) => (
                    <motion.div
                      key={ring}
                      className="absolute inset-0 rounded-full border-4 border-emerald-400"
                      animate={{
                        scale: [1, 1.35 + ring * 0.12],
                        opacity: [0.5 - ring * 0.12, 0],
                      }}
                      transition={{
                        duration: 2.2,
                        repeat: Infinity,
                        delay: ring * 0.35,
                      }}
                    />
                  ))}
                  <div className="relative z-10 flex items-center justify-center">
                    <Phone className="w-12 h-12 sm:w-16 sm:h-16" />
                  </div>
                </motion.button>

                <div className="text-center">
                  <motion.p
                    className="text-xl sm:text-2xl font-bold text-slate-800"
                    animate={{ scale: [1, 1.02, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    Démarrer l&apos;appel vocal
                  </motion.p>
                  <p className="text-sm sm:text-base text-slate-500 mt-1.5">
                    Conversation naturelle avec l&apos;IA
                  </p>
                </div>
              </div>

              {/* Features aligned with grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                {[
                  { icon: Waves, label: "Voix naturelle", color: "text-cyan-600", bg: "bg-gradient-to-br from-cyan-50 to-teal-50", border: "border-cyan-100" },
                  { icon: Heart, label: "Guide CPR", color: "text-red-500", bg: "bg-gradient-to-br from-red-50 to-rose-50", border: "border-red-100" },
                  { icon: Zap, label: "Temps réel", color: "text-amber-500", bg: "bg-gradient-to-br from-amber-50 to-orange-50", border: "border-amber-100" },
                  { icon: Shield, label: "24/7", color: "text-emerald-600", bg: "bg-gradient-to-br from-emerald-50 to-green-50", border: "border-emerald-100" },
                ].map((feature, index) => (
                  <motion.div
                    key={feature.label}
                    className={`${feature.bg} rounded-2xl p-4 sm:p-5 text-center border ${feature.border} shadow-sm`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    whileHover={{ scale: 1.05, y: -4 }}
                  >
                    <feature.icon className={`w-6 h-6 sm:w-7 sm:h-7 mx-auto mb-2 ${feature.color}`} />
                    <span className="text-xs sm:text-sm font-semibold text-slate-700">{feature.label}</span>
                  </motion.div>
                ))}
              </div>

              {/* Emergency Info */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="bg-gradient-to-br from-red-50 to-rose-50 rounded-2xl p-4 sm:p-5 border border-red-100"
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br from-red-500 to-rose-500 flex items-center justify-center shadow-lg shadow-red-500/30">
                    <Phone className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-slate-800 mb-1">Urgence vitale ?</h3>
                    <p className="text-sm text-slate-600">
                      En cas de danger immédiat, appelez le <span className="font-bold text-red-600">190 (SAMU)</span>
                    </p>
                  </div>
                  <a href="tel:190">
                    <motion.button
                      className="px-4 py-2 bg-gradient-to-r from-red-500 to-rose-500 text-white rounded-xl font-semibold text-sm shadow-lg shadow-red-500/30"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      190
                    </motion.button>
                  </a>
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* Active Call State - Same as before but wrapped */}
          {isCallActive && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center min-h-[65vh] sm:min-h-[70vh] space-y-4 sm:space-y-6"
            >
              {/* Avatar with Visualizers */}
              <div className="relative w-72 h-72 sm:w-80 sm:h-80">
                <AudioPulseRings
                  audioLevel={audioLevel}
                  isActive={isCallActive}
                  isSpeaking={callState === "speaking"}
                />

                {/* Central Avatar */}
                <motion.div
                  className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10"
                  animate={callState === "speaking" ? { scale: [1, 1.05, 1] } : { scale: 1 }}
                  transition={{ duration: 0.5, repeat: callState === "speaking" ? Infinity : 0 }}
                >
                  <div className="w-28 h-28 sm:w-32 sm:h-32 rounded-full bg-black border-4 border-white/20 shadow-2xl overflow-hidden">
                    <Image
                      src="/animations/logo_llama.gif"
                      alt="Assistant IA"
                      width={128}
                      height={128}
                      className="w-full h-full object-contain"
                      unoptimized
                    />
                  </div>

                  {/* Status Badge */}
                  <motion.div
                    className={`absolute -bottom-2 -right-2 w-10 h-10 rounded-full flex items-center justify-center shadow-xl ${callState === "speaking"
                      ? "bg-gradient-to-r from-emerald-400 to-green-500"
                      : callState === "user_speaking"
                        ? "bg-gradient-to-r from-blue-400 to-cyan-500"
                        : callState === "processing"
                          ? "bg-gradient-to-r from-amber-400 to-orange-500"
                          : "bg-gradient-to-r from-cyan-400 to-teal-500"
                      }`}
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  >
                    {callState === "speaking" ? (
                      <Volume2 className="w-5 h-5 text-white" />
                    ) : callState === "processing" ? (
                      <Activity className="w-5 h-5 text-white" />
                    ) : (
                      <Mic className="w-5 h-5 text-white" />
                    )}
                  </motion.div>
                </motion.div>
              </div>

              {/* Waveform Visualization */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="w-full max-w-md"
              >
                <AudioWaveform
                  audioLevel={audioLevel}
                  isActive={isCallActive}
                  isSpeaking={callState === "speaking"}
                  barCount={28}
                />
              </motion.div>

              {/* Call Controls */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="flex items-center gap-5 sm:gap-6 pt-4"
              >
                {/* Mute */}
                <motion.button
                  onClick={handleMuteToggle}
                  className={`w-14 h-14 sm:w-16 sm:h-16 rounded-full flex items-center justify-center transition-all ${isMuted
                    ? "bg-red-500/30 text-red-400 border-2 border-red-500/50"
                    : "bg-white/15 text-white border-2 border-white/20 hover:bg-white/25"
                    }`}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
                </motion.button>

                {/* End Call */}
                <motion.button
                  onClick={endCall}
                  className="w-18 h-18 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-red-500 to-rose-600 text-white flex items-center justify-center shadow-2xl shadow-red-500/50"
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <PhoneOff className="w-8 h-8" />
                </motion.button>

                {/* Speaker */}
                <motion.button
                  onClick={() => setIsSpeakerOn(!isSpeakerOn)}
                  className={`w-14 h-14 sm:w-16 sm:h-16 rounded-full flex items-center justify-center transition-all border-2 ${!isSpeakerOn
                    ? "bg-white/10 text-white/50 border-white/10"
                    : "bg-white/15 text-white border-white/20 hover:bg-white/25"
                    }`}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {isSpeakerOn ? <Volume2 className="w-6 h-6" /> : <VolumeX className="w-6 h-6" />}
                </motion.button>
              </motion.div>

              {/* Text Input Fallback */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="w-full max-w-md px-4"
              >
                <div className="flex items-center gap-2 bg-white/10 rounded-xl p-2 border border-white/20">
                  <input
                    type="text"
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendTextMessage()}
                    placeholder="Ou tapez votre message..."
                    className="flex-1 bg-transparent text-white placeholder-white/40 text-sm px-3 py-2 focus:outline-none"
                  />
                  <motion.button
                    onClick={sendTextMessage}
                    disabled={!textInput.trim()}
                    className="p-2 rounded-lg bg-cyan-500/30 text-cyan-300 hover:bg-cyan-500/50 disabled:opacity-50 transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Send className="w-4 h-4" />
                  </motion.button>
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* Ended State */}
          {callState === "ended" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center min-h-[65vh] space-y-6"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", bounce: 0.5 }}
                className="w-28 h-28 rounded-full bg-gradient-to-br from-emerald-500/20 to-green-500/20 flex items-center justify-center border-2 border-emerald-500/30"
              >
                <Heart className="w-14 h-14 text-emerald-500" />
              </motion.div>
              <div className="text-center space-y-2">
                <h2 className="text-2xl sm:text-3xl font-bold text-slate-800">Appel terminé</h2>
                <p className="text-sm sm:text-base text-slate-500 max-w-xs mx-auto">
                  Restez vigilant. Appelez le <span className="font-bold text-red-600">190</span> si besoin.
                </p>
              </div>
              <div className="flex gap-3">
                <Link href="/">
                  <motion.button
                    className="px-6 py-3 bg-slate-100 text-slate-700 rounded-xl font-semibold text-sm hover:bg-slate-200"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    Accueil
                  </motion.button>
                </Link>
                <Link href="/chat">
                  <motion.button
                    className="px-6 py-3 bg-gradient-to-r from-[#0891B2] to-cyan-600 text-white rounded-xl font-semibold text-sm shadow-lg shadow-cyan-500/30"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    Continuer par chat
                  </motion.button>
                </Link>
              </div>
            </motion.div>
          )}
        </main>
      </motion.div>
    </AnimatePresence>
  )
}
