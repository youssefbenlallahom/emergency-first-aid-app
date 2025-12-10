"use client"

import { motion, AnimatePresence } from "framer-motion"
import {
  Camera,
  CameraOff,
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Volume2,
  Heart,
  Shield,
  Zap,
  Activity,
  Info,
  Phone,
  MessageCircle,
} from "lucide-react"
import Link from "next/link"
import { useState, useRef, useEffect, useCallback } from "react"

type CPRState = "idle" | "ready" | "active" | "paused"
type FeedbackType = "correct" | "incorrect" | "neutral"

interface CompressionFeedback {
  depth: FeedbackType
  rate: FeedbackType
  position: FeedbackType
}

function HeartbeatPulse({ isActive }: { isActive: boolean }) {
  return (
    <motion.div
      className="absolute top-4 right-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm rounded-full px-3 py-1.5"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <motion.div
        animate={isActive ? { scale: [1, 1.3, 1] } : { scale: 1 }}
        transition={{ duration: 0.5, repeat: isActive ? Infinity : 0 }}
      >
        <Heart className={`w-4 h-4 ${isActive ? "text-red-500 fill-red-500" : "text-white/60"}`} />
      </motion.div>
      <span className="text-xs font-medium text-white/80">
        {isActive ? "En cours" : "Prêt"}
      </span>
    </motion.div>
  )
}

function CompressionCounter({
  count,
  isActive,
}: {
  count: number
  isActive: boolean
}) {
  const cycleCount = Math.floor(count / 30)
  const currentInCycle = count % 30

  return (
    <motion.div
      className="absolute top-20 left-1/2 -translate-x-1/2 bg-black/70 backdrop-blur-md rounded-2xl px-6 py-4 border border-white/10"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="text-center">
        <motion.span
          key={count}
          initial={{ scale: 1.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-5xl font-bold text-white block"
        >
          {currentInCycle || 30}
        </motion.span>
        <p className="text-xs text-white/60 mt-1">sur 30 compressions</p>
        <div className="flex items-center justify-center gap-2 mt-2">
          <div className="px-2 py-0.5 rounded-full bg-cyan-500/20 border border-cyan-500/30">
            <span className="text-xs font-medium text-cyan-400">Cycle {cycleCount + 1}</span>
          </div>
          <div className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/30">
            <span className="text-xs font-medium text-emerald-400">Total: {count}</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function RhythmGuide({ isActive }: { isActive: boolean }) {
  return (
    <motion.div
      className="absolute bottom-36 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <div className="flex items-center gap-1.5">
        {Array.from({ length: 7 }).map((_, i) => (
          <motion.div
            key={i}
            className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-gradient-to-r from-cyan-400 to-teal-400"
            animate={
              isActive
                ? {
                    scale: [1, 1.6, 1],
                    opacity: [0.3, 1, 0.3],
                  }
                : { scale: 1, opacity: 0.3 }
            }
            transition={{
              duration: 0.5,
              repeat: isActive ? Infinity : 0,
              delay: i * 0.08,
            }}
          />
        ))}
      </div>
      <motion.div
        className="bg-black/60 backdrop-blur-sm rounded-full px-4 py-1.5"
        animate={{ scale: isActive ? [1, 1.03, 1] : 1 }}
        transition={{ duration: 1, repeat: isActive ? Infinity : 0 }}
      >
        <span className="text-white/90 text-sm font-medium">🎵 100-120 bpm</span>
      </motion.div>
    </motion.div>
  )
}

function FeedbackDisplay({ feedback }: { feedback: CompressionFeedback }) {
  const items = [
    { label: "Profondeur", status: feedback.depth, icon: Activity },
    { label: "Rythme", status: feedback.rate, icon: Zap },
    { label: "Position", status: feedback.position, icon: Shield },
  ]

  return (
    <motion.div
      className="absolute top-20 right-3 space-y-2"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
    >
      {items.map((item, index) => (
        <motion.div 
          key={item.label} 
          className={`flex items-center gap-2 backdrop-blur-md rounded-xl px-3 py-2.5 border ${
            item.status === "correct" 
              ? "bg-emerald-500/20 border-emerald-500/30" 
              : item.status === "incorrect" 
                ? "bg-red-500/20 border-red-500/30" 
                : "bg-black/50 border-white/10"
          }`}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.1 }}
        >
          {item.status === "correct" ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : item.status === "incorrect" ? (
            <AlertCircle className="w-4 h-4 text-red-400" />
          ) : (
            <item.icon className="w-4 h-4 text-white/50" />
          )}
          <span className={`text-xs font-medium ${
            item.status === "correct" 
              ? "text-emerald-300" 
              : item.status === "incorrect" 
                ? "text-red-300" 
                : "text-white/70"
          }`}>{item.label}</span>
        </motion.div>
      ))}
    </motion.div>
  )
}

function HandPositionOverlay() {
  return (
    <motion.div
      className="absolute inset-0 flex items-center justify-center pointer-events-none"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {/* Outer glow */}
      <motion.div
        className="absolute w-44 h-44 rounded-full bg-emerald-500/10"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{ duration: 2, repeat: Infinity }}
      />
      
      {/* Target zone */}
      <motion.div
        className="relative w-36 h-36 border-4 border-dashed rounded-full"
        animate={{
          scale: [1, 1.05, 1],
          borderColor: ["#34d399", "#10b981", "#34d399"],
        }}
        transition={{ duration: 1.5, repeat: Infinity }}
        style={{ borderColor: "#34d399" }}
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
          >
            <Heart className="w-10 h-10 text-emerald-400 fill-emerald-400/30" />
          </motion.div>
        </div>

        {/* Corner markers */}
        {[0, 90, 180, 270].map((angle) => (
          <motion.div
            key={angle}
            className="absolute w-3 h-3 bg-emerald-400 rounded-full"
            style={{
              top: "50%",
              left: "50%",
              transform: `rotate(${angle}deg) translateY(-72px) translateX(-50%)`,
            }}
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1, repeat: Infinity, delay: angle / 360 }}
          />
        ))}

        {/* Guide text */}
        <motion.div
          className="absolute -bottom-14 left-1/2 -translate-x-1/2 whitespace-nowrap"
          animate={{ opacity: [0.7, 1, 0.7], y: [0, -2, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <span className="text-sm text-white font-medium bg-gradient-to-r from-emerald-500/80 to-teal-500/80 px-4 py-2 rounded-full shadow-lg">
            👐 Placez vos mains ici
          </span>
        </motion.div>
      </motion.div>
    </motion.div>
  )
}

export default function CPRCameraPage() {
  const [cprState, setCprState] = useState<CPRState>("idle")
  const [compressionCount, setCompressionCount] = useState(0)
  const [feedback, setFeedback] = useState<CompressionFeedback>({
    depth: "neutral",
    rate: "neutral",
    position: "neutral",
  })
  const [cameraPermission, setCameraPermission] = useState<boolean | null>(null)
  const [audioEnabled, setAudioEnabled] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)
  const countIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        setCameraPermission(true)
        setCprState("ready")
      }
    } catch {
      setCameraPermission(false)
    }
  }, [])

  const stopCamera = useCallback(() => {
    if (videoRef.current?.srcObject) {
      const tracks = (videoRef.current.srcObject as MediaStream).getTracks()
      tracks.forEach((track) => track.stop())
      videoRef.current.srcObject = null
    }
    setCprState("idle")
    setCameraPermission(null)
  }, [])

  const startCPR = useCallback(() => {
    setCprState("active")
    setCompressionCount(0)

    // Simulate compression counting
    countIntervalRef.current = setInterval(() => {
      setCompressionCount((prev) => prev + 1)

      // Simulate random feedback with higher chance of correct
      const getStatus = (): FeedbackType => {
        const rand = Math.random()
        if (rand < 0.6) return "correct"
        if (rand < 0.8) return "neutral"
        return "incorrect"
      }
      
      setFeedback({
        depth: getStatus(),
        rate: getStatus(),
        position: getStatus(),
      })
    }, 550)
  }, [])

  const pauseCPR = useCallback(() => {
    setCprState("paused")
    if (countIntervalRef.current) {
      clearInterval(countIntervalRef.current)
    }
  }, [])

  const resetCPR = useCallback(() => {
    setCprState("ready")
    setCompressionCount(0)
    setFeedback({
      depth: "neutral",
      rate: "neutral",
      position: "neutral",
    })
    if (countIntervalRef.current) {
      clearInterval(countIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    return () => {
      stopCamera()
      if (countIntervalRef.current) {
        clearInterval(countIntervalRef.current)
      }
    }
  }, [stopCamera])

  return (
    <div className="min-h-[100dvh] bg-slate-900 flex flex-col">
      {/* Header - Enhanced */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-50 bg-black/70 backdrop-blur-xl border-b border-white/5 safe-area-top"
      >
        <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white/80 hover:text-white active:text-white/60 transition-colors px-2 py-1.5 rounded-lg hover:bg-white/10">
            <motion.div whileHover={{ x: -3 }} whileTap={{ scale: 0.95 }}>
              <ArrowLeft className="w-5 h-5" />
            </motion.div>
            <span className="font-medium text-sm sm:text-base">Retour</span>
          </Link>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-cyan-500/20 to-teal-500/20 border border-cyan-500/30">
              <Heart className="w-4 h-4 text-red-500" />
              <span className="font-semibold text-white text-sm">Guide CPR</span>
            </div>
          </div>
          <motion.button
            onClick={() => setAudioEnabled(!audioEnabled)}
            className={`p-2.5 rounded-xl transition-all ${
              audioEnabled 
                ? "text-white bg-white/10 hover:bg-white/20" 
                : "text-white/40 bg-white/5"
            }`}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
          >
            <Volume2 className="w-5 h-5" />
          </motion.button>
        </div>
      </motion.header>

      {/* Camera View */}
      <div className="flex-1 relative bg-black">
        {cprState === "idle" ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 flex flex-col items-center justify-center p-4 sm:p-6 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900"
          >
            {/* Animated background */}
            <div className="absolute inset-0 overflow-hidden">
              {Array.from({ length: 20 }).map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute w-2 h-2 rounded-full bg-cyan-500/10"
                  initial={{
                    x: `${Math.random() * 100}%`,
                    y: `${Math.random() * 100}%`,
                  }}
                  animate={{
                    y: [null, `${Math.random() * 100}%`],
                    opacity: [0, 0.5, 0],
                  }}
                  transition={{
                    duration: 8 + Math.random() * 4,
                    repeat: Infinity,
                    delay: Math.random() * 3,
                  }}
                />
              ))}
            </div>

            <motion.div 
              className="relative z-10 w-24 h-24 sm:w-28 sm:h-28 rounded-3xl bg-gradient-to-br from-cyan-500/20 to-teal-500/20 border-2 border-cyan-500/30 flex items-center justify-center mb-6"
              animate={{ 
                boxShadow: [
                  "0 0 20px rgba(8, 145, 178, 0.2)",
                  "0 0 40px rgba(8, 145, 178, 0.4)",
                  "0 0 20px rgba(8, 145, 178, 0.2)",
                ]
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Camera className="w-12 h-12 sm:w-14 sm:h-14 text-cyan-400" />
            </motion.div>
            
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2 text-center relative z-10">
              Guide CPR avec Vision IA
            </h2>
            <p className="text-white/60 text-center text-sm sm:text-base mb-8 max-w-sm relative z-10 leading-relaxed">
              Activez la caméra pour recevoir des <span className="text-cyan-400 font-medium">instructions visuelles en temps réel</span> sur les gestes de réanimation cardio-pulmonaire.
            </p>

            <motion.button
              onClick={startCamera}
              className="px-7 sm:px-8 py-3.5 sm:py-4 bg-gradient-to-r from-[#0891B2] via-cyan-500 to-teal-500 text-white rounded-2xl font-semibold text-base sm:text-lg shadow-2xl shadow-cyan-500/30 active:scale-95 transition-transform relative z-10"
              whileHover={{ scale: 1.05, boxShadow: "0 20px 40px -10px rgba(8, 145, 178, 0.5)" }}
              whileTap={{ scale: 0.95 }}
            >
              <span className="flex items-center gap-2">
                <Camera className="w-5 h-5" />
                Activer la caméra
              </span>
            </motion.button>

            {cameraPermission === false && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }} 
                animate={{ opacity: 1, y: 0 }} 
                className="mt-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl max-w-sm relative z-10"
              >
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="text-red-300 font-medium text-sm">Accès caméra refusé</p>
                    <p className="text-red-300/70 text-xs mt-1">Veuillez autoriser l'accès dans les paramètres de votre navigateur.</p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Features grid */}
            <div className="grid grid-cols-3 gap-3 mt-8 w-full max-w-sm relative z-10">
              {[
                { icon: Activity, label: "Temps réel", color: "text-cyan-400" },
                { icon: Shield, label: "Guide précis", color: "text-emerald-400" },
                { icon: Heart, label: "Rythme CPR", color: "text-red-400" },
              ].map((item, index) => (
                <motion.div
                  key={item.label}
                  className="bg-white/5 backdrop-blur-sm rounded-xl p-3 text-center border border-white/10"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 + index * 0.1 }}
                  whileHover={{ scale: 1.05, backgroundColor: "rgba(255,255,255,0.1)" }}
                >
                  <item.icon className={`w-5 h-5 mx-auto mb-1.5 ${item.color}`} />
                  <span className="text-[10px] sm:text-xs text-white/70 font-medium">{item.label}</span>
                </motion.div>
              ))}
            </div>

            {/* Emergency call option */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="mt-8 relative z-10"
            >
              <a href="tel:190">
                <motion.button
                  className="flex items-center gap-2 px-4 py-2 text-red-400 hover:text-red-300 text-sm font-medium"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Phone className="w-4 h-4" />
                  Urgence ? Appelez le 190
                </motion.button>
              </a>
            </motion.div>
          </motion.div>
        ) : (
          <>
            {/* Video Feed */}
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />

            {/* Heartbeat indicator */}
            <HeartbeatPulse isActive={cprState === "active"} />

            {/* Overlays */}
            <AnimatePresence>
              {(cprState === "ready" || cprState === "active") && <HandPositionOverlay />}
              {cprState === "active" && (
                <>
                  <CompressionCounter count={compressionCount} isActive={cprState === "active"} />
                  <FeedbackDisplay feedback={feedback} />
                  <RhythmGuide isActive={cprState === "active"} />
                </>
              )}
            </AnimatePresence>

            {/* Controls - Enhanced */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute bottom-8 sm:bottom-10 left-0 right-0 flex items-center justify-center gap-4 sm:gap-5 px-4"
            >
              {cprState === "ready" && (
                <motion.button
                  onClick={startCPR}
                  className="flex items-center gap-2.5 px-6 sm:px-8 py-3.5 sm:py-4 bg-gradient-to-r from-emerald-500 to-green-600 text-white rounded-2xl font-semibold text-base sm:text-lg shadow-2xl shadow-emerald-500/40 active:scale-95"
                  whileHover={{ scale: 1.05, boxShadow: "0 20px 40px -10px rgba(34, 197, 94, 0.5)" }}
                  whileTap={{ scale: 0.95 }}
                >
                  <Play className="w-5 h-5 sm:w-6 sm:h-6" />
                  Démarrer CPR
                </motion.button>
              )}

              {cprState === "active" && (
                <>
                  <motion.button
                    onClick={pauseCPR}
                    className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 text-white flex items-center justify-center active:scale-90 shadow-xl shadow-amber-500/30"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Pause className="w-6 h-6 sm:w-7 sm:h-7" />
                  </motion.button>
                  <motion.button
                    onClick={resetCPR}
                    className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-white/20 backdrop-blur-sm text-white flex items-center justify-center active:scale-90 border border-white/20"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <RotateCcw className="w-6 h-6 sm:w-7 sm:h-7" />
                  </motion.button>
                </>
              )}

              {cprState === "paused" && (
                <>
                  <motion.button
                    onClick={startCPR}
                    className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-500 text-white flex items-center justify-center active:scale-90 shadow-xl shadow-emerald-500/30"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <Play className="w-6 h-6 sm:w-7 sm:h-7" />
                  </motion.button>
                  <motion.button
                    onClick={resetCPR}
                    className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-white/20 backdrop-blur-sm text-white flex items-center justify-center active:scale-90 border border-white/20"
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <RotateCcw className="w-6 h-6 sm:w-7 sm:h-7" />
                  </motion.button>
                </>
              )}

              <motion.button
                onClick={stopCamera}
                className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 text-white flex items-center justify-center active:scale-90 shadow-xl shadow-red-500/30"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
              >
                <CameraOff className="w-6 h-6 sm:w-7 sm:h-7" />
              </motion.button>
            </motion.div>
          </>
        )}
      </div>

      {/* Instructions Panel - Enhanced */}
      <AnimatePresence>
        {cprState !== "idle" && (
          <motion.div
            initial={{ opacity: 0, y: 100 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 100 }}
            className="bg-white rounded-t-3xl p-5 sm:p-6 safe-area-bottom shadow-2xl"
          >
            <div className="w-12 h-1.5 bg-slate-200 rounded-full mx-auto mb-4" />
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-500 flex items-center justify-center">
                <Info className="w-4 h-4 text-white" />
              </div>
              <h3 className="font-bold text-slate-800 text-base sm:text-lg">Instructions CPR</h3>
            </div>
            <ol className="text-sm text-slate-600 space-y-3">
              {[
                { step: 1, text: "Placez le talon de votre main au centre de la poitrine (sternum)" },
                { step: 2, text: "Entrelacez vos doigts et gardez les bras tendus" },
                { step: 3, text: "Comprimez à 5-6 cm de profondeur, 100-120 fois/minute" },
              ].map((item) => (
                <motion.li 
                  key={item.step}
                  className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 border border-slate-100"
                  whileHover={{ scale: 1.01, backgroundColor: "rgb(241 245 249)" }}
                >
                  <span className="w-6 h-6 rounded-lg bg-gradient-to-br from-[#0891B2] to-cyan-600 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                    {item.step}
                  </span>
                  <span className="leading-relaxed">{item.text}</span>
                </motion.li>
              ))}
            </ol>
            
            {/* Quick actions */}
            <div className="flex gap-3 mt-4">
              <Link href="/voice-call" className="flex-1">
                <motion.button
                  className="w-full py-2.5 bg-gradient-to-r from-cyan-50 to-teal-50 text-[#0891B2] rounded-xl font-medium text-sm border border-cyan-100 flex items-center justify-center gap-2"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Volume2 className="w-4 h-4" />
                  Aide vocale
                </motion.button>
              </Link>
              <Link href="/chat" className="flex-1">
                <motion.button
                  className="w-full py-2.5 bg-slate-100 text-slate-700 rounded-xl font-medium text-sm flex items-center justify-center gap-2"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <MessageCircle className="w-4 h-4" />
                  Chat IA
                </motion.button>
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
