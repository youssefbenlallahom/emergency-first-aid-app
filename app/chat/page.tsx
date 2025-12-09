"use client"

import type React from "react"

import { motion, AnimatePresence } from "framer-motion"
import {
  Send,
  ArrowLeft,
  Mic,
  ImageIcon,
  Paperclip,
  Heart,
  Activity,
  AlertTriangle,
  Loader2,
  Sparkles,
  Shield,
  Phone,
  MoreVertical,
  Volume2,
} from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { useState, useRef, useEffect } from "react"

interface Message {
  id: string
  type: "user" | "ai"
  content: string
  timestamp: Date
  isTyping?: boolean
}

const quickSuggestions = [
  { icon: Heart, text: "Massage cardiaque", color: "text-red-500", bg: "bg-gradient-to-br from-red-50 to-rose-50", border: "border-red-100", gradient: "from-red-500 to-rose-500" },
  { icon: Activity, text: "Étouffement adulte", color: "text-amber-500", bg: "bg-gradient-to-br from-amber-50 to-orange-50", border: "border-amber-100", gradient: "from-amber-500 to-orange-500" },
  { icon: AlertTriangle, text: "Hémorragie", color: "text-rose-500", bg: "bg-gradient-to-br from-rose-50 to-pink-50", border: "border-rose-100", gradient: "from-rose-500 to-pink-500" },
  { icon: Shield, text: "Position PLS", color: "text-blue-500", bg: "bg-gradient-to-br from-blue-50 to-indigo-50", border: "border-blue-100", gradient: "from-blue-500 to-indigo-500" },
]

const aiResponses = [
  "Je comprends l'urgence. Restez calme et suivez mes instructions. Avez-vous vérifié si la personne respire normalement ?",
  "Très bien. Placez vos mains au centre de la poitrine, bras tendus. Effectuez 30 compressions profondes à un rythme de 100-120 par minute. Comptez à voix haute.",
  "Parfait, vous faites du bon travail ! Continuez les compressions. Entre chaque série de 30 compressions, faites 2 insufflations si vous êtes formé. Sinon, continuez uniquement les compressions.",
  "Les secours sont prévenus ? Si non, demandez à quelqu'un d'appeler le 190 immédiatement. Continuez le massage cardiaque sans vous arrêter.",
]

// Animated background with floating medical symbols
function FloatingParticles() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {Array.from({ length: 15 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: Math.random() * 3 + 2,
            height: Math.random() * 3 + 2,
            background: `rgba(8, 145, 178, ${Math.random() * 0.12 + 0.03})`,
          }}
          initial={{
            x: `${Math.random() * 100}%`,
            y: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [null, `${Math.random() * 100}%`],
            x: [null, `${Math.random() * 100}%`],
            opacity: [0, 0.5, 0],
          }}
          transition={{
            duration: 12 + Math.random() * 8,
            repeat: Infinity,
            delay: Math.random() * 5,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

function AIAvatar({ isTyping, size = "default" }: { isTyping?: boolean; size?: "default" | "large" }) {
  const sizeClasses = size === "large" ? "w-12 h-12 sm:w-14 sm:h-14" : "w-9 h-9 sm:w-11 sm:h-11"
  const imgSize = size === "large" ? 56 : 44
  
  return (
    <motion.div
      className="relative flex-shrink-0"
      animate={isTyping ? { scale: [1, 1.03, 1] } : {}}
      transition={{ duration: 1.5, repeat: Infinity }}
    >
      <motion.div 
        className={`${sizeClasses} rounded-2xl bg-gradient-to-br from-cyan-100 via-teal-50 to-emerald-100 border-2 border-white shadow-lg shadow-cyan-500/20 overflow-hidden`}
        whileHover={{ scale: 1.05 }}
      >
        <Image
          src="/images/logo-llama.png"
          alt="Assistant IA Monkedh"
          width={imgSize}
          height={imgSize}
          className="object-cover scale-110"
        />
      </motion.div>
      <motion.div
        className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 sm:w-4 sm:h-4 bg-gradient-to-r from-emerald-400 to-green-500 rounded-full border-2 border-white flex items-center justify-center shadow-sm"
        animate={isTyping ? { scale: [1, 1.3, 1] } : { scale: 1 }}
        transition={{ duration: 0.8, repeat: isTyping ? Infinity : 0 }}
      >
        {isTyping && <Sparkles className="w-2 h-2 text-white" />}
      </motion.div>
    </motion.div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-2 px-2">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-gradient-to-r from-cyan-400 to-teal-400"
          animate={{
            y: [-3, 3, -3],
            opacity: [0.4, 1, 0.4],
            scale: [0.9, 1.1, 0.9],
          }}
          transition={{
            duration: 0.7,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
      <span className="text-xs text-slate-400 ml-2">en train d'écrire...</span>
    </div>
  )
}

function MessageBubble({ message, isLast }: { message: Message; isLast: boolean }) {
  const isUser = message.type === "user"

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`flex items-end gap-2.5 sm:gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {!isUser && <AIAvatar isTyping={message.isTyping} />}

      <motion.div
        className={`max-w-[82%] sm:max-w-[75%] md:max-w-[70%] relative ${
          isUser
            ? "bg-gradient-to-br from-[#0891B2] via-cyan-600 to-teal-600 text-white rounded-2xl rounded-br-sm shadow-lg shadow-cyan-500/25"
            : "bg-white text-slate-800 rounded-2xl rounded-bl-sm shadow-lg shadow-slate-200/60 border border-slate-100/80"
        } px-4 py-3 sm:px-5 sm:py-3.5`}
        whileHover={{ scale: 1.01 }}
        transition={{ duration: 0.15 }}
        layout
      >
        {/* Shine effect for user messages */}
        {isUser && (
          <motion.div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent rounded-2xl rounded-br-sm"
            initial={{ x: "-100%" }}
            animate={{ x: "100%" }}
            transition={{ duration: 1.5, delay: 0.2 }}
          />
        )}

        {/* Subtle gradient overlay for AI messages */}
        {!isUser && !message.isTyping && (
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-50/50 via-transparent to-teal-50/30 rounded-2xl rounded-bl-sm pointer-events-none" />
        )}

        {message.isTyping ? (
          <TypingIndicator />
        ) : (
          <>
            <p className="text-[13px] sm:text-sm leading-relaxed relative z-10 whitespace-pre-wrap">{message.content}</p>
            <div className={`flex items-center gap-2 mt-2 relative z-10 ${isUser ? "justify-end" : "justify-start"}`}>
              <p className={`text-[10px] sm:text-xs ${isUser ? "text-white/60" : "text-slate-400"}`}>
                {message.timestamp.toLocaleTimeString("fr-FR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
              {!isUser && isLast && (
                <motion.button
                  className="p-1 rounded-full hover:bg-slate-100 text-slate-400 hover:text-cyan-600 transition-colors"
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  title="Écouter"
                >
                  <Volume2 className="w-3 h-3" />
                </motion.button>
              )}
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      type: "ai",
      content:
        "Salam ! 👋 Je suis votre assistant de secourisme Monkedh. Décrivez-moi la situation d'urgence et je vous guiderai pas à pas avec des instructions précises.",
      timestamp: new Date(),
    },
  ])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [showEmergencyBanner, setShowEmergencyBanner] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: text,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsLoading(true)
    setShowEmergencyBanner(false)

    const typingId = `typing-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      {
        id: typingId,
        type: "ai",
        content: "",
        timestamp: new Date(),
        isTyping: true,
      },
    ])

    setTimeout(() => {
      const responseIndex = Math.floor(Math.random() * aiResponses.length)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== typingId),
        {
          id: Date.now().toString(),
          type: "ai",
          content: aiResponses[responseIndex],
          timestamp: new Date(),
        },
      ])
      setIsLoading(false)
    }, 1500 + Math.random() * 1000)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(inputValue)
  }

  return (
    <div className="min-h-[100dvh] bg-gradient-to-b from-slate-50 via-cyan-50/20 to-slate-50 flex flex-col relative">
      <FloatingParticles />

      {/* Header - Enhanced */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-50 backdrop-blur-2xl bg-white/85 border-b border-slate-100/50 shadow-sm shadow-slate-100/50 safe-area-top"
      >
        <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 sm:gap-3">
          <Link
            href="/"
            className="p-2.5 -ml-1 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-100 active:bg-slate-200 transition-all"
            aria-label="Retour"
          >
            <motion.div whileHover={{ x: -2 }} whileTap={{ scale: 0.95 }}>
              <ArrowLeft className="w-5 h-5" />
            </motion.div>
          </Link>
          
          <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
            <AIAvatar size="large" />
            <div className="min-w-0 flex-1">
              <h1 className="font-bold text-slate-800 text-base sm:text-lg truncate">Assistant IA Monkedh</h1>
              <div className="flex items-center gap-1.5">
                <motion.div
                  className="w-2 h-2 rounded-full bg-gradient-to-r from-emerald-400 to-green-500"
                  animate={{ 
                    opacity: [1, 0.5, 1],
                    scale: [1, 0.9, 1]
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <p className="text-[11px] sm:text-xs text-emerald-600 font-medium">Prêt à vous aider</p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-1">
            <Link
              href="/voice-call"
              className="p-2.5 sm:p-3 text-white bg-gradient-to-r from-[#0891B2] to-cyan-600 rounded-xl shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 active:scale-95 transition-all"
              aria-label="Appel vocal"
            >
              <motion.div whileHover={{ rotate: 15 }} whileTap={{ scale: 0.9 }}>
                <Mic className="w-4 h-4 sm:w-5 sm:h-5" />
              </motion.div>
            </Link>
            <motion.button
              className="p-2.5 text-slate-400 hover:text-slate-600 rounded-xl hover:bg-slate-100 transition-all hidden sm:flex"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <MoreVertical className="w-5 h-5" />
            </motion.button>
          </div>
        </div>
      </motion.header>

      {/* Emergency Call Banner */}
      <AnimatePresence>
        {showEmergencyBanner && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-gradient-to-r from-red-500 to-rose-500 text-white relative z-40"
          >
            <div className="w-full max-w-3xl mx-auto px-4 py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4" />
                <span className="text-xs sm:text-sm font-medium">Urgence vitale ? Appelez le 190</span>
              </div>
              <Link href="tel:190">
                <motion.button
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-full text-xs font-bold transition-colors"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  Appeler
                </motion.button>
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages Area - Enhanced */}
      <div className="flex-1 overflow-y-auto relative z-10 scrollbar-hide">
        <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 space-y-4 sm:space-y-5">
          <AnimatePresence mode="popLayout">
            {messages.map((message, index) => (
              <MessageBubble 
                key={message.id} 
                message={message} 
                isLast={index === messages.length - 1 && message.type === "ai"}
              />
            ))}
          </AnimatePresence>
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </div>

      {/* Quick Suggestions - Enhanced */}
      {messages.length < 3 && (
        <motion.div 
          initial={{ opacity: 0, y: 20 }} 
          animate={{ opacity: 1, y: 0 }} 
          className="relative z-10 border-t border-slate-100/50 bg-gradient-to-t from-white via-white/95 to-white/80 backdrop-blur-sm"
        >
          <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
            <p className="text-[11px] sm:text-xs text-slate-500 mb-2.5 sm:mb-3 font-semibold uppercase tracking-wide flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-amber-500" />
              Situations fréquentes
            </p>
            <div className="flex gap-2 sm:gap-2.5 overflow-x-auto pb-2 scrollbar-hide -mx-1 px-1">
              {quickSuggestions.map((suggestion, index) => (
                <motion.button
                  key={suggestion.text}
                  onClick={() => sendMessage(suggestion.text)}
                  className={`flex items-center gap-2 sm:gap-2.5 px-3.5 sm:px-4 py-2.5 sm:py-3 ${suggestion.bg} rounded-2xl border ${suggestion.border} shadow-sm whitespace-nowrap active:scale-95 transition-all group`}
                  initial={{ opacity: 0, x: -20, scale: 0.9 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  transition={{ delay: index * 0.08, duration: 0.3 }}
                  whileHover={{ scale: 1.03, y: -2, boxShadow: "0 8px 20px -8px rgba(0,0,0,0.15)" }}
                  whileTap={{ scale: 0.97 }}
                >
                  <motion.div
                    className={`w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-gradient-to-br ${suggestion.gradient} flex items-center justify-center shadow-sm`}
                    whileHover={{ rotate: [0, -10, 10, 0] }}
                    transition={{ duration: 0.4 }}
                  >
                    <suggestion.icon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                  </motion.div>
                  <span className="text-xs sm:text-sm font-semibold text-slate-700">{suggestion.text}</span>
                </motion.button>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {/* Input Area - Enhanced & User-Friendly */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky bottom-0 bg-white/98 backdrop-blur-2xl border-t border-slate-200/80 relative z-20 safe-area-bottom"
      >
        <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <form onSubmit={handleSubmit} className="flex items-center gap-2 sm:gap-3">
            {/* Action Buttons */}
            <div className="hidden sm:flex items-center gap-1">
              <motion.button
                type="button"
                className="p-2.5 text-slate-400 hover:text-[#0891B2] rounded-xl hover:bg-cyan-50 active:bg-cyan-100 transition-all"
                whileHover={{ scale: 1.1, rotate: -10 }}
                whileTap={{ scale: 0.95 }}
                aria-label="Joindre un fichier"
              >
                <Paperclip className="w-5 h-5" />
              </motion.button>
              <motion.button
                type="button"
                className="p-2.5 text-slate-400 hover:text-[#0891B2] rounded-xl hover:bg-cyan-50 active:bg-cyan-100 transition-all"
                whileHover={{ scale: 1.1, rotate: 10 }}
                whileTap={{ scale: 0.95 }}
                aria-label="Envoyer une image"
              >
                <ImageIcon className="w-5 h-5" />
              </motion.button>
            </div>

            {/* Input Field - Enhanced */}
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Décrivez votre situation d'urgence..."
                className="w-full px-4 sm:px-5 py-3 sm:py-3.5 bg-slate-100/80 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-[#0891B2]/40 focus:bg-white border-2 border-transparent focus:border-[#0891B2]/30 transition-all placeholder:text-slate-400 shadow-inner"
                autoComplete="off"
              />
              <AnimatePresence>
                {inputValue.length > 0 && (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-400 bg-slate-200/80 px-2 py-0.5 rounded-full"
                  >
                    {inputValue.length}
                  </motion.span>
                )}
              </AnimatePresence>
            </div>

            {/* Send Button - Enhanced */}
            <motion.button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="p-3 sm:p-3.5 bg-gradient-to-r from-[#0891B2] via-cyan-600 to-teal-600 text-white rounded-2xl disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-cyan-500/30 hover:shadow-cyan-500/50 transition-all"
              whileHover={{ scale: inputValue.trim() && !isLoading ? 1.05 : 1 }}
              whileTap={{ scale: inputValue.trim() && !isLoading ? 0.95 : 1 }}
              aria-label="Envoyer"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 sm:w-6 sm:h-6 animate-spin" />
              ) : (
                <motion.div
                  animate={inputValue.trim() ? { x: [0, 3, 0] } : {}}
                  transition={{ duration: 0.8, repeat: Infinity }}
                >
                  <Send className="w-5 h-5 sm:w-6 sm:h-6" />
                </motion.div>
              )}
            </motion.button>
          </form>
          
          {/* Voice Input Hint */}
          <motion.p 
            className="text-[10px] sm:text-xs text-slate-400 text-center mt-2 flex items-center justify-center gap-1"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            <Mic className="w-3 h-3" />
            Préférez parler ? <Link href="/voice-call" className="text-[#0891B2] font-medium hover:underline">Appel vocal IA</Link>
          </motion.p>
        </div>
      </motion.div>
    </div>
  )
}
