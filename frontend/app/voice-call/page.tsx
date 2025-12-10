"use client"

import { motion, AnimatePresence } from "framer-motion"
import { Phone, PhoneOff, Mic, MicOff, Volume2, VolumeX, ArrowLeft, Heart, Sparkles, Shield, MessageCircle, Zap, Activity } from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect, useCallback } from "react"

type CallState = "idle" | "connecting" | "listening" | "speaking" | "ended"

function VoiceWaveform({
  isActive,
  isSpeaking,
}: {
  isActive: boolean
  isSpeaking: boolean
}) {
  const bars = 45

  return (
    <div className="flex items-center justify-center gap-0.5 sm:gap-1 h-36 sm:h-40 px-4">
      {Array.from({ length: bars }).map((_, i) => {
        const center = bars / 2
        const distanceFromCenter = Math.abs(i - center) / center
        const maxHeight = isSpeaking ? 110 : 70
        const baseHeight = (1 - distanceFromCenter * 0.7) * maxHeight

        return (
          <motion.div
            key={i}
            className={`w-1 sm:w-1.5 rounded-full ${
              isSpeaking
                ? "bg-gradient-to-t from-emerald-500 via-green-400 to-emerald-300"
                : "bg-gradient-to-t from-cyan-500 via-teal-400 to-cyan-300"
            }`}
            initial={{ height: 4 }}
            animate={
              isActive
                ? {
                    height: [
                      4,
                      baseHeight * (0.3 + Math.random() * 0.7),
                      baseHeight * (0.2 + Math.random() * 0.8),
                      baseHeight * (0.4 + Math.random() * 0.6),
                      4,
                    ],
                  }
                : { height: 4 }
            }
            transition={{
              duration: isSpeaking ? 0.25 : 0.45,
              repeat: isActive ? Infinity : 0,
              delay: i * 0.015,
              ease: "easeInOut",
            }}
            style={{
              boxShadow: isActive
                ? isSpeaking
                  ? "0 0 15px rgba(34, 197, 94, 0.5), 0 0 30px rgba(34, 197, 94, 0.2)"
                  : "0 0 15px rgba(8, 145, 178, 0.5), 0 0 30px rgba(8, 145, 178, 0.2)"
                : "none",
            }}
          />
        )
      })}
    </div>
  )
}

function PulseRings({ isActive, color }: { isActive: boolean; color: string }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      {[1, 2, 3, 4].map((ring) => (
        <motion.div
          key={ring}
          className={`absolute rounded-full border-2 ${color}`}
          style={{
            width: 130 + ring * 45,
            height: 130 + ring * 45,
          }}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={
            isActive
              ? {
                  scale: [0.8, 1.3, 0.8],
                  opacity: [0, 0.35, 0],
                }
              : { scale: 0.8, opacity: 0 }
          }
          transition={{
            duration: 2.5,
            repeat: Infinity,
            delay: ring * 0.35,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

function FloatingSparkles({ isActive }: { isActive: boolean }) {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 30 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute"
          initial={{
            x: `${50 + (Math.random() - 0.5) * 20}%`,
            y: "50%",
            scale: 0,
          }}
          animate={
            isActive
              ? {
                  x: `${50 + (Math.random() - 0.5) * 100}%`,
                  y: `${50 + (Math.random() - 0.5) * 100}%`,
                  scale: [0, 1, 0],
                  rotate: [0, 180, 360],
                }
              : {}
          }
          transition={{
            duration: 2.5 + Math.random() * 2,
            repeat: Infinity,
            delay: i * 0.12,
            ease: "easeOut",
          }}
        >
          <Sparkles className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-cyan-400/50" />
        </motion.div>
      ))}
    </div>
  )
}

// Animated background gradient
function AnimatedBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <motion.div
        className="absolute inset-0 bg-gradient-to-br from-slate-900 via-cyan-950/50 to-slate-900"
        animate={{
          background: [
            "linear-gradient(135deg, rgb(15, 23, 42) 0%, rgba(8, 51, 68, 0.5) 50%, rgb(15, 23, 42) 100%)",
            "linear-gradient(135deg, rgb(15, 23, 42) 0%, rgba(6, 78, 59, 0.3) 50%, rgb(15, 23, 42) 100%)",
            "linear-gradient(135deg, rgb(15, 23, 42) 0%, rgba(8, 51, 68, 0.5) 50%, rgb(15, 23, 42) 100%)",
          ],
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  )
}

// Call Timer Component
function CallTimer({ isActive }: { isActive: boolean }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (!isActive) {
      setSeconds(0)
      return
    }
    const interval = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(interval)
  }, [isActive])

  const formatTime = (s: number) => {
    const mins = Math.floor(s / 60)
    const secs = s % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full border border-white/20"
    >
      <motion.div 
        className="w-2 h-2 rounded-full bg-red-500"
        animate={{ opacity: [1, 0.3, 1] }}
        transition={{ duration: 1, repeat: Infinity }}
      />
      <span className="text-lg sm:text-xl font-mono text-white/90 tracking-wider font-medium">
        {formatTime(seconds)}
      </span>
    </motion.div>
  )
}

export default function VoiceCallPage() {
  const [callState, setCallState] = useState<CallState>("idle")
  const [isMuted, setIsMuted] = useState(false)
  const [isSpeakerOn, setIsSpeakerOn] = useState(true)

  const startCall = useCallback(() => {
    setCallState("connecting")
    setTimeout(() => {
      setCallState("listening")
      setTimeout(() => {
        setCallState("speaking")
        setTimeout(() => {
          setCallState("listening")
        }, 4000)
      }, 3000)
    }, 2000)
  }, [])

  const endCall = useCallback(() => {
    setCallState("ended")
    setTimeout(() => setCallState("idle"), 2000)
  }, [])

  const getStatusText = () => {
    switch (callState) {
      case "idle":
        return "Prêt à vous assister"
      case "connecting":
        return "Connexion en cours..."
      case "listening":
        return "Je vous écoute..."
      case "speaking":
        return "Je vous guide..."
      case "ended":
        return "Appel terminé"
      default:
        return ""
    }
  }

  const getStatusSubtext = () => {
    switch (callState) {
      case "connecting":
        return "Préparation de l'assistant vocal..."
      case "listening":
        return "Décrivez la situation d'urgence clairement"
      case "speaking":
        return "Suivez attentivement les instructions"
      default:
        return ""
    }
  }

  const isCallActive = ["listening", "speaking", "connecting"].includes(callState)

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={callState === "idle" ? "idle" : "active"}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className={`min-h-[100dvh] relative overflow-hidden ${
          isCallActive
            ? "bg-slate-900"
            : "bg-gradient-to-b from-slate-50 via-cyan-50/30 to-slate-50"
        }`}
      >
        {/* Background Effects for Active Call */}
        {isCallActive && (
          <>
            <AnimatedBackground />
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/40 via-transparent to-transparent" />
            <FloatingSparkles isActive={callState === "speaking"} />
          </>
        )}

        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`sticky top-0 z-50 safe-area-top ${
            isCallActive ? "bg-transparent" : "backdrop-blur-2xl bg-white/85 border-b border-slate-100/50 shadow-sm"
          }`}
        >
          <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex items-center justify-between">
            <Link
              href="/"
              className={`flex items-center gap-2 px-3 py-2 rounded-xl transition-all active:scale-95 ${
                isCallActive
                  ? "text-white/80 hover:text-white hover:bg-white/10 active:bg-white/20"
                  : "text-slate-600 hover:text-slate-800 hover:bg-slate-100 active:bg-slate-200"
              }`}
            >
              <motion.div whileHover={{ x: -3 }} whileTap={{ scale: 0.95 }}>
                <ArrowLeft className="w-5 h-5" />
              </motion.div>
              <span className="font-medium text-sm sm:text-base">Retour</span>
            </Link>
            {isCallActive && <CallTimer isActive={isCallActive} />}
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
          {/* Idle State - Enhanced */}
          {callState === "idle" && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-5 sm:space-y-8">
              {/* Hero Card */}
              <motion.div 
                className="bg-white rounded-3xl p-5 sm:p-7 shadow-xl shadow-slate-200/50 border border-slate-100"
                whileHover={{ y: -2, boxShadow: "0 25px 50px -12px rgba(0,0,0,0.12)" }}
                transition={{ duration: 0.3 }}
              >
                <div className="flex items-center gap-4 sm:gap-5 mb-4 sm:mb-5">
                  <motion.div 
                    className="relative" 
                    whileHover={{ scale: 1.05, rotate: 3 }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
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
                      🇹🇳 Secourisme d'urgence Tunisie
                    </p>
                  </div>
                </div>
                <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                  Notre assistant vocal intelligent vous guide en <span className="font-semibold text-[#0891B2]">temps réel</span> avec des instructions de premiers secours claires et précises. 
                  Décrivez simplement la situation d'urgence.
                </p>
              </motion.div>

              {/* Call Button - Enhanced */}
              <div className="flex flex-col items-center gap-5 sm:gap-7 py-4">
                <motion.button
                  onClick={startCall}
                  className="relative w-32 h-32 sm:w-40 sm:h-40 rounded-full bg-gradient-to-br from-[#22C55E] via-emerald-500 to-green-600 text-white shadow-2xl shadow-emerald-500/50 active:scale-95"
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {/* Pulse rings */}
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
                  
                  {/* Shine effect */}
                  <motion.div
                    className="absolute inset-0 rounded-full bg-gradient-to-tr from-transparent via-white/20 to-transparent"
                    initial={{ rotate: 0 }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                  />
                </motion.button>

                <div className="text-center">
                  <motion.p 
                    className="text-xl sm:text-2xl font-bold text-slate-800"
                    animate={{ scale: [1, 1.02, 1] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    Démarrer l'appel
                  </motion.p>
                  <p className="text-sm sm:text-base text-slate-500 mt-1.5">Appuyez pour parler à l'assistant IA</p>
                </div>
              </div>

              {/* Features - Enhanced */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                {[
                  { icon: Mic, label: "Voix naturelle", color: "text-cyan-600", bg: "bg-gradient-to-br from-cyan-50 to-teal-50", border: "border-cyan-100" },
                  { icon: Heart, label: "Guide CPR", color: "text-red-500", bg: "bg-gradient-to-br from-red-50 to-rose-50", border: "border-red-100" },
                  { icon: Zap, label: "Temps réel", color: "text-amber-500", bg: "bg-gradient-to-br from-amber-50 to-orange-50", border: "border-amber-100" },
                  { icon: Shield, label: "Fiable 24/7", color: "text-emerald-600", bg: "bg-gradient-to-br from-emerald-50 to-green-50", border: "border-emerald-100" },
                ].map((feature, index) => (
                  <motion.div
                    key={feature.label}
                    className={`${feature.bg} rounded-2xl p-4 sm:p-5 text-center border ${feature.border} shadow-sm`}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.1 }}
                    whileHover={{ scale: 1.05, y: -4, boxShadow: "0 10px 30px -10px rgba(0,0,0,0.1)" }}
                  >
                    <motion.div
                      whileHover={{ rotate: [0, -10, 10, 0] }}
                      transition={{ duration: 0.4 }}
                    >
                      <feature.icon className={`w-6 h-6 sm:w-7 sm:h-7 mx-auto mb-2 ${feature.color}`} />
                    </motion.div>
                    <span className="text-xs sm:text-sm font-semibold text-slate-700">{feature.label}</span>
                  </motion.div>
                ))}
              </div>

              {/* Emergency Info Card */}
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
                      En cas de danger immédiat, appelez directement le <span className="font-bold text-red-600">190 (SAMU)</span>
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

          {/* Active Call State - Enhanced */}
          {isCallActive && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="flex flex-col items-center justify-center min-h-[65vh] sm:min-h-[70vh] space-y-5 sm:space-y-7"
            >
              <div className="relative">
                <PulseRings
                  isActive={isCallActive}
                  color={callState === "speaking" ? "border-emerald-500/30" : "border-cyan-500/30"}
                />

                <motion.div
                  className="relative z-10"
                  animate={callState === "speaking" ? { scale: [1, 1.1, 1] } : { scale: 1 }}
                  transition={{ duration: 0.6, repeat: callState === "speaking" ? Infinity : 0 }}
                >
                  <div
                    className={`w-28 h-28 sm:w-36 sm:h-36 rounded-full bg-gradient-to-br from-cyan-100 via-teal-50 to-emerald-100 backdrop-blur-xl border-3 border-white/30 flex items-center justify-center shadow-2xl overflow-hidden`}
                  >
                    {/* Logo Llama animé - centré */}
                    <div className="relative w-full h-full overflow-hidden rounded-full bg-black flex items-center justify-center">
                      <img
                        src="/animations/logo_llama.gif"
                        alt="Assistant IA Monkedh"
                        className="w-[95%] h-[95%] object-contain"
                      />
                    </div>
                  </div>

                  {/* Status indicator */}
                  <motion.div
                    className={`absolute -bottom-2 -right-2 sm:-bottom-3 sm:-right-3 w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shadow-xl ${
                      callState === "speaking"
                        ? "bg-gradient-to-r from-emerald-400 to-green-500"
                        : callState === "listening"
                          ? "bg-gradient-to-r from-cyan-400 to-teal-500"
                          : "bg-gradient-to-r from-amber-400 to-orange-500"
                    }`}
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  >
                    {callState === "speaking" ? (
                      <Volume2 className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                    ) : callState === "listening" ? (
                      <Mic className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                    ) : (
                      <motion.div 
                        className="w-3 h-3 sm:w-4 sm:h-4 bg-white rounded-full"
                        animate={{ opacity: [1, 0.3, 1] }}
                        transition={{ duration: 0.6, repeat: Infinity }}
                      />
                    )}
                  </motion.div>
                </motion.div>
              </div>

              {/* Status Text - Enhanced */}
              <motion.div
                key={callState}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center px-4"
              >
                <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2">{getStatusText()}</h2>
                <p className="text-sm sm:text-base text-white/60 max-w-xs mx-auto">
                  {getStatusSubtext()}
                </p>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0, y: 20 }} 
                animate={{ opacity: 1, y: 0 }} 
                className="w-full max-w-sm sm:max-w-md"
              >
                <VoiceWaveform
                  isActive={callState === "listening" || callState === "speaking"}
                  isSpeaking={callState === "speaking"}
                />
              </motion.div>

              {/* Call Controls - Enhanced */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="flex items-center gap-5 sm:gap-6"
              >
                {/* Mute Button */}
                <motion.button
                  onClick={() => setIsMuted(!isMuted)}
                  className={`w-14 h-14 sm:w-18 sm:h-18 rounded-full flex items-center justify-center transition-all active:scale-90 ${
                    isMuted
                      ? "bg-red-500/30 text-red-400 border-2 border-red-500/50 shadow-lg shadow-red-500/20"
                      : "bg-white/15 text-white hover:bg-white/25 active:bg-white/30 border-2 border-white/20"
                  }`}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {isMuted ? <MicOff className="w-6 h-6 sm:w-7 sm:h-7" /> : <Mic className="w-6 h-6 sm:w-7 sm:h-7" />}
                </motion.button>

                {/* End Call Button */}
                <motion.button
                  onClick={endCall}
                  className="w-18 h-18 sm:w-22 sm:h-22 rounded-full bg-gradient-to-br from-red-500 to-rose-600 text-white flex items-center justify-center shadow-2xl shadow-red-500/50 active:scale-90"
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <PhoneOff className="w-8 h-8 sm:w-10 sm:h-10" />
                </motion.button>

                {/* Speaker Button */}
                <motion.button
                  onClick={() => setIsSpeakerOn(!isSpeakerOn)}
                  className={`w-14 h-14 sm:w-18 sm:h-18 rounded-full flex items-center justify-center transition-all border-2 active:scale-90 ${
                    !isSpeakerOn
                      ? "bg-white/10 text-white/50 border-white/10"
                      : "bg-white/15 text-white hover:bg-white/25 active:bg-white/30 border-white/20"
                  }`}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                >
                  {isSpeakerOn ? <Volume2 className="w-6 h-6 sm:w-7 sm:h-7" /> : <VolumeX className="w-6 h-6 sm:w-7 sm:h-7" />}
                </motion.button>
              </motion.div>

              {/* Tip text */}
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="text-xs sm:text-sm text-white/40 text-center"
              >
                Parlez clairement et décrivez les symptômes observés
              </motion.p>
            </motion.div>
          )}

          {/* Ended State - Enhanced */}
          {callState === "ended" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex flex-col items-center justify-center min-h-[65vh] sm:min-h-[70vh] space-y-5 sm:space-y-7 px-4"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", bounce: 0.5 }}
                className="w-28 h-28 sm:w-32 sm:h-32 rounded-full bg-gradient-to-br from-emerald-500/20 to-green-500/20 flex items-center justify-center border-2 border-emerald-500/30"
              >
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <Heart className="w-14 h-14 sm:w-16 sm:h-16 text-emerald-500" />
                </motion.div>
              </motion.div>
              <div className="text-center space-y-2">
                <h2 className="text-2xl sm:text-3xl font-bold text-slate-800">Appel terminé</h2>
                <p className="text-sm sm:text-base text-slate-500 max-w-xs mx-auto">
                  Restez vigilant et n'hésitez pas à appeler le <span className="font-bold text-red-600">190</span> si la situation s'aggrave
                </p>
              </div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="flex gap-3"
              >
                <Link href="/">
                  <motion.button
                    className="px-6 py-3 bg-slate-100 text-slate-700 rounded-xl font-semibold text-sm hover:bg-slate-200 transition-colors"
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
              </motion.div>
            </motion.div>
          )}
        </main>
      </motion.div>
    </AnimatePresence>
  )
}
