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
  RefreshCw,
  WifiOff,
} from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { useState, useRef, useEffect, useCallback } from "react"
import { sendMessage, getSessionIds, isApiAvailable, clearSessionIds, getConversationHistory } from "@/lib/api"

interface Message {
  id: string
  type: "user" | "ai"
  content: string
  timestamp: Date
  isTyping?: boolean
  isError?: boolean
}

const quickSuggestions = [
  { icon: Heart, text: "Massage cardiaque", color: "text-red-500", bg: "bg-gradient-to-br from-red-50 to-rose-50", border: "border-red-100", gradient: "from-red-500 to-rose-500" },
  { icon: Activity, text: "Étouffement adulte", color: "text-amber-500", bg: "bg-gradient-to-br from-amber-50 to-orange-50", border: "border-amber-100", gradient: "from-amber-500 to-orange-500" },
  { icon: AlertTriangle, text: "Hémorragie", color: "text-rose-500", bg: "bg-gradient-to-br from-rose-50 to-pink-50", border: "border-rose-100", gradient: "from-rose-500 to-pink-500" },
  { icon: Shield, text: "Position PLS", color: "text-blue-500", bg: "bg-gradient-to-br from-blue-50 to-indigo-50", border: "border-blue-100", gradient: "from-blue-500 to-indigo-500" },
]

// API base URL for images
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Parse message content and extract visual guides
function parseMessageContent(content: string): { text: string; images: { path: string; description: string }[] } {
  const images: { path: string; description: string }[] = [];
  
  // Pattern: 📷 GUIDE VISUEL : path\nCette image montre : description
  const guidePattern = /📷\s*GUIDE VISUEL\s*:\s*([^\n]+)\n(?:Cette image montre\s*:\s*)?([^\n📷]*)/g;
  
  let match;
  while ((match = guidePattern.exec(content)) !== null) {
    const imagePath = match[1].trim();
    const description = match[2]?.trim() || '';
    images.push({ path: imagePath, description });
  }
  
  // Remove the guide visual sections from text
  const cleanText = content
    .replace(/📷\s*GUIDE VISUEL\s*:\s*[^\n]+\n(?:Cette image montre\s*:\s*)?[^\n📷]*/g, '')
    .trim();
  
  return { text: cleanText, images };
}

// Simple markdown renderer for chat messages
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  
  lines.forEach((line, lineIndex) => {
    // Process inline formatting
    const processInline = (str: string): React.ReactNode[] => {
      const parts: React.ReactNode[] = [];
      let remaining = str;
      let keyIndex = 0;
      
      // Bold text: **text**
      while (remaining.length > 0) {
        const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
        if (boldMatch && boldMatch.index !== undefined) {
          // Text before bold
          if (boldMatch.index > 0) {
            parts.push(remaining.slice(0, boldMatch.index));
          }
          // Bold text
          parts.push(<strong key={`bold-${keyIndex++}`} className="font-semibold">{boldMatch[1]}</strong>);
          remaining = remaining.slice(boldMatch.index + boldMatch[0].length);
        } else {
          parts.push(remaining);
          break;
        }
      }
      return parts;
    };
    
    // Headers
    if (line.startsWith('### ')) {
      elements.push(
        <h3 key={lineIndex} className="font-bold text-base mt-3 mb-1 text-slate-800">
          {processInline(line.slice(4))}
        </h3>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={lineIndex} className="font-bold text-lg mt-3 mb-1 text-slate-800">
          {processInline(line.slice(3))}
        </h2>
      );
    }
    // Bullet points
    else if (line.match(/^[-•]\s/)) {
      elements.push(
        <div key={lineIndex} className="flex items-start gap-2 ml-2">
          <span className="text-cyan-500 mt-0.5">•</span>
          <span>{processInline(line.slice(2))}</span>
        </div>
      );
    }
    // Numbered lists
    else if (line.match(/^\d+\.\s/)) {
      const num = line.match(/^(\d+)\./)?.[1];
      elements.push(
        <div key={lineIndex} className="flex items-start gap-2 ml-2">
          <span className="text-cyan-600 font-semibold min-w-[1.2rem]">{num}.</span>
          <span>{processInline(line.slice(line.indexOf('.') + 2))}</span>
        </div>
      );
    }
    // Sub-items with dash
    else if (line.match(/^\s+-\s/)) {
      elements.push(
        <div key={lineIndex} className="flex items-start gap-2 ml-6 text-slate-600">
          <span className="text-slate-400">–</span>
          <span>{processInline(line.trim().slice(2))}</span>
        </div>
      );
    }
    // Empty lines
    else if (line.trim() === '') {
      elements.push(<div key={lineIndex} className="h-2" />);
    }
    // Regular text
    else {
      elements.push(
        <p key={lineIndex} className="leading-relaxed">
          {processInline(line)}
        </p>
      );
    }
  });
  
  return elements;
}

// Component to render message content with images
function MessageContent({ content }: { content: string }) {
  const { text, images } = parseMessageContent(content);
  
  return (
    <div className="space-y-1">
      {/* Text content with markdown rendering */}
      {text && (
        <div className="text-[13px] sm:text-sm relative z-10">
          {renderMarkdown(text)}
        </div>
      )}
      
      {/* Visual guides */}
      {images.map((img, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 + index * 0.1 }}
          className="mt-3 rounded-xl overflow-hidden border border-slate-200 bg-slate-50"
        >
          {/* Image */}
          <div className="relative w-full bg-white">
            <img
              src={`${API_BASE_URL}/images/${encodeURIComponent(img.path.replace('emergency_image_db/', ''))}`}
              alt={img.description || "Guide visuel"}
              className="w-full h-auto max-h-64 object-contain"
              onError={(e) => {
                // Try alternative path format
                const target = e.target as HTMLImageElement;
                const altPath = img.path.replace('emergency_image_db/', '').replace(/ – /g, ' - ');
                target.src = `${API_BASE_URL}/images/${encodeURIComponent(altPath)}`;
              }}
            />
          </div>
          
          {/* Description */}
          {img.description && (
            <div className="px-3 py-2 bg-gradient-to-r from-cyan-50 to-teal-50 border-t border-slate-200">
              <div className="flex items-start gap-2">
                <ImageIcon className="w-4 h-4 text-cyan-600 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-slate-600 leading-relaxed">{img.description}</p>
              </div>
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
}

// Animated background with floating medical symbols
// Pre-generated particle data to avoid hydration mismatch
const PARTICLE_DATA = [
  { w: 3.5, h: 4.2, bg: 0.08, x: 15, y: 25, tx: 85, ty: 60, dur: 14, del: 1 },
  { w: 2.8, h: 3.1, bg: 0.12, x: 45, y: 10, tx: 20, ty: 80, dur: 16, del: 2 },
  { w: 4.1, h: 2.9, bg: 0.06, x: 80, y: 55, tx: 35, ty: 15, dur: 13, del: 0.5 },
  { w: 3.2, h: 4.5, bg: 0.10, x: 25, y: 70, tx: 70, ty: 30, dur: 18, del: 3 },
  { w: 2.5, h: 3.8, bg: 0.07, x: 60, y: 40, tx: 10, ty: 90, dur: 15, del: 1.5 },
  { w: 4.0, h: 3.3, bg: 0.09, x: 90, y: 20, tx: 50, ty: 75, dur: 17, del: 4 },
  { w: 3.0, h: 4.0, bg: 0.11, x: 35, y: 85, tx: 65, ty: 45, dur: 14, del: 2.5 },
  { w: 3.7, h: 2.6, bg: 0.05, x: 70, y: 5, tx: 25, ty: 55, dur: 19, del: 0 },
  { w: 2.3, h: 3.5, bg: 0.08, x: 5, y: 50, tx: 95, ty: 35, dur: 16, del: 3.5 },
  { w: 4.3, h: 4.1, bg: 0.13, x: 55, y: 95, tx: 40, ty: 20, dur: 12, del: 1.2 },
  { w: 3.4, h: 2.8, bg: 0.06, x: 20, y: 15, tx: 75, ty: 85, dur: 15, del: 4.5 },
  { w: 2.9, h: 3.9, bg: 0.10, x: 85, y: 65, tx: 30, ty: 10, dur: 18, del: 2.2 },
  { w: 3.8, h: 3.2, bg: 0.07, x: 40, y: 30, tx: 60, ty: 70, dur: 13, del: 0.8 },
  { w: 2.6, h: 4.4, bg: 0.09, x: 65, y: 80, tx: 15, ty: 40, dur: 17, del: 3.8 },
  { w: 4.2, h: 3.6, bg: 0.11, x: 10, y: 45, tx: 90, ty: 25, dur: 14, del: 1.8 },
];

function FloatingParticles() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {PARTICLE_DATA.map((p, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: p.w,
            height: p.h,
            background: `rgba(8, 145, 178, ${p.bg})`,
          }}
          initial={{
            x: `${p.x}%`,
            y: `${p.y}%`,
          }}
          animate={{
            y: [null, `${p.ty}%`],
            x: [null, `${p.tx}%`],
            opacity: [0, 0.5, 0],
          }}
          transition={{
            duration: p.dur,
            repeat: Infinity,
            delay: p.del,
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

function MessageBubble({ message, isLast, onRetry }: { message: Message; isLast: boolean; onRetry?: () => void }) {
  const isUser = message.type === "user"
  const isError = message.isError

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
            : isError
              ? "bg-red-50 text-red-800 rounded-2xl rounded-bl-sm shadow-lg shadow-red-200/60 border border-red-200"
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
        {!isUser && !message.isTyping && !isError && (
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-50/50 via-transparent to-teal-50/30 rounded-2xl rounded-bl-sm pointer-events-none" />
        )}

        {message.isTyping ? (
          <TypingIndicator />
        ) : (
          <>
            {isUser ? (
              <p className="text-[13px] sm:text-sm leading-relaxed relative z-10 whitespace-pre-wrap">{message.content}</p>
            ) : (
              <MessageContent content={message.content} />
            )}
            {isError && onRetry && (
              <motion.button
                onClick={onRetry}
                className="mt-2 flex items-center gap-1.5 text-xs text-red-600 hover:text-red-700 font-medium"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <RefreshCw className="w-3 h-3" />
                Réessayer
              </motion.button>
            )}
            <div className={`flex items-center gap-2 mt-2 relative z-10 ${isUser ? "justify-end" : "justify-start"}`}>
              <p className={`text-[10px] sm:text-xs ${isUser ? "text-white/60" : isError ? "text-red-400" : "text-slate-400"}`}>
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
  const [isApiConnected, setIsApiConnected] = useState(true)
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const sessionRef = useRef<{ channelId: string; userId: string } | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Initialize session and check API availability
  useEffect(() => {
    const initSession = async () => {
      sessionRef.current = getSessionIds()
      const apiAvailable = await isApiAvailable()
      setIsApiConnected(apiAvailable)
      
      if (!apiAvailable) {
        setMessages((prev) => [
          ...prev,
          {
            id: "api-warning",
            type: "ai",
            content: "⚠️ Le serveur n'est pas disponible actuellement. Veuillez vérifier votre connexion ou réessayer plus tard.",
            timestamp: new Date(),
            isError: true,
          },
        ])
      }
    }
    initSession()
  }, [])

  const handleSendMessage = useCallback(async (text: string) => {
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
    setLastFailedMessage(null)

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

    try {
      const session = sessionRef.current || getSessionIds()
      const response = await sendMessage({
        message: text,
        channel_id: session.channelId,
        user_id: session.userId,
        username: "Utilisateur",
      })

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== typingId),
        {
          id: Date.now().toString(),
          type: "ai",
          content: response.response,
          timestamp: new Date(response.timestamp),
        },
      ])
      setIsApiConnected(true)
    } catch (error) {
      console.error("Error sending message:", error)
      setLastFailedMessage(text)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== typingId),
        {
          id: Date.now().toString(),
          type: "ai",
          content: "Désolé, une erreur s'est produite lors de la communication avec le serveur. Veuillez réessayer.",
          timestamp: new Date(),
          isError: true,
        },
      ])
      setIsApiConnected(false)
    } finally {
      setIsLoading(false)
    }
  }, [isLoading])

  const handleRetry = useCallback(() => {
    if (lastFailedMessage) {
      // Remove the last error message
      setMessages((prev) => prev.filter((m) => !m.isError || m.id === "welcome"))
      handleSendMessage(lastFailedMessage)
    }
  }, [lastFailedMessage, handleSendMessage])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleSendMessage(inputValue)
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
                  className={`w-2 h-2 rounded-full ${isApiConnected ? "bg-gradient-to-r from-emerald-400 to-green-500" : "bg-gradient-to-r from-amber-400 to-orange-500"}`}
                  animate={{ 
                    opacity: [1, 0.5, 1],
                    scale: [1, 0.9, 1]
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <p className={`text-[11px] sm:text-xs font-medium ${isApiConnected ? "text-emerald-600" : "text-amber-600"}`}>
                  {isApiConnected ? "Prêt à vous aider" : "Connexion en cours..."}
                </p>
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
              <a href="tel:190">
                <motion.button
                  className="px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-full text-xs font-bold transition-colors"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  Appeler
                </motion.button>
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages Area - Enhanced */}
      <div className="flex-1 overflow-y-auto relative z-10 scrollbar-hide">
        <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 space-y-4 sm:space-y-5">
          {/* API Connection Status Banner */}
          {!isApiConnected && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm"
            >
              <WifiOff className="w-4 h-4" />
              <span>Mode hors connexion - Vérifiez votre connexion au serveur</span>
            </motion.div>
          )}
          <AnimatePresence mode="popLayout">
            {messages.map((message, index) => (
              <MessageBubble 
                key={message.id} 
                message={message} 
                isLast={index === messages.length - 1 && message.type === "ai"}
                onRetry={message.isError ? handleRetry : undefined}
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
            {/* Grid layout for mobile, horizontal scroll for larger screens */}
            <div className="grid grid-cols-2 gap-2 sm:flex sm:gap-2.5 sm:overflow-x-auto sm:pb-2 sm:scrollbar-hide">
              {quickSuggestions.map((suggestion, index) => (
                <motion.button
                  key={suggestion.text}
                  onClick={() => handleSendMessage(suggestion.text)}
                  className={`flex items-center gap-2 px-3 py-2.5 sm:px-4 sm:py-3 ${suggestion.bg} rounded-xl sm:rounded-2xl border ${suggestion.border} shadow-sm sm:whitespace-nowrap active:scale-95 transition-all group`}
                  initial={{ opacity: 0, y: 10, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: index * 0.08, duration: 0.3 }}
                  whileHover={{ scale: 1.03, y: -2, boxShadow: "0 8px 20px -8px rgba(0,0,0,0.15)" }}
                  whileTap={{ scale: 0.97 }}
                >
                  <motion.div
                    className={`w-6 h-6 sm:w-8 sm:h-8 rounded-lg sm:rounded-xl bg-gradient-to-br ${suggestion.gradient} flex items-center justify-center shadow-sm flex-shrink-0`}
                    whileHover={{ rotate: [0, -10, 10, 0] }}
                    transition={{ duration: 0.4 }}
                  >
                    <suggestion.icon className="w-3 h-3 sm:w-4 sm:h-4 text-white" />
                  </motion.div>
                  <span className="text-[11px] sm:text-sm font-semibold text-slate-700 truncate">{suggestion.text}</span>
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
