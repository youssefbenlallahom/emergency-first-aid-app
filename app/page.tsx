"use client"

import { motion, AnimatePresence } from "framer-motion"
import { 
  Phone, 
  MessageCircle, 
  Camera, 
  Heart, 
  Activity, 
  Shield, 
  Clock, 
  ChevronRight, 
  Mic, 
  AlertTriangle,
  Zap,
  Users,
  MapPin
} from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect } from "react"

// Animated background particles
function FloatingParticles() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {Array.from({ length: 20 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: Math.random() * 4 + 2,
            height: Math.random() * 4 + 2,
            background: `rgba(8, 145, 178, ${Math.random() * 0.15 + 0.05})`,
          }}
          initial={{
            x: `${Math.random() * 100}%`,
            y: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [null, `${Math.random() * 100}%`],
            x: [null, `${Math.random() * 100}%`],
            opacity: [0, 0.6, 0],
          }}
          transition={{
            duration: 15 + Math.random() * 10,
            repeat: Infinity,
            delay: Math.random() * 5,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

// Pulse animation for emergency button
function EmergencyPulse() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      {[1, 2, 3].map((ring) => (
        <motion.div
          key={ring}
          className="absolute rounded-full border-2 border-white/30"
          style={{
            width: 80 + ring * 50,
            height: 80 + ring * 50,
          }}
          animate={{
            scale: [1, 1.4],
            opacity: [0.6, 0],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            delay: ring * 0.4,
            ease: "easeOut",
          }}
        />
      ))}
    </div>
  )
}

// Stats counter animation
function AnimatedCounter({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [count, setCount] = useState(0)
  
  useEffect(() => {
    const duration = 2000
    const steps = 60
    const increment = value / steps
    let current = 0
    
    const timer = setInterval(() => {
      current += increment
      if (current >= value) {
        setCount(value)
        clearInterval(timer)
      } else {
        setCount(Math.floor(current))
      }
    }, duration / steps)
    
    return () => clearInterval(timer)
  }, [value])
  
  return <span>{count.toLocaleString()}{suffix}</span>
}

// Animated gradient border
function GradientBorder({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <motion.div
        className="absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-cyan-500 via-teal-500 to-emerald-500 opacity-75 blur-sm"
        animate={{
          backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
        }}
        transition={{
          duration: 5,
          repeat: Infinity,
          ease: "linear",
        }}
        style={{ backgroundSize: "200% 200%" }}
      />
      <div className="relative bg-white rounded-2xl">{children}</div>
    </div>
  )
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { 
      duration: 0.5, 
      ease: [0.25, 0.46, 0.45, 0.94] 
    },
  },
}

const quickActions = [
  {
    icon: MessageCircle,
    label: "Chatbot IA",
    description: "Assistance textuelle instantanée",
    href: "/chat",
    gradient: "from-cyan-500 to-teal-500",
    bgColor: "bg-gradient-to-br from-cyan-50 to-teal-50",
    iconBg: "bg-gradient-to-br from-cyan-500 to-teal-500",
    avatar: "/images/logo-llama.png",
  },
  {
    icon: Mic,
    label: "Appel Vocal IA",
    description: "Parlez directement à l'assistant",
    href: "/voice-call",
    gradient: "from-emerald-500 to-green-500",
    bgColor: "bg-gradient-to-br from-emerald-50 to-green-50",
    iconBg: "bg-gradient-to-br from-emerald-500 to-green-500",
    featured: true,
    avatar: "/images/logo-llama.png",
  },
  {
    icon: Camera,
    label: "Guide CPR Visuel",
    description: "Instructions en temps réel",
    href: "/cpr-camera",
    gradient: "from-blue-500 to-indigo-500",
    bgColor: "bg-gradient-to-br from-blue-50 to-indigo-50",
    iconBg: "bg-gradient-to-br from-blue-500 to-indigo-500",
  },
]

const emergencyProcedures = [
  { 
    icon: Heart, 
    label: "Arrêt cardiaque", 
    description: "Massage cardiaque & défibrillation",
    color: "text-red-500",
    bgColor: "bg-red-50",
    borderColor: "border-red-100"
  },
  { 
    icon: AlertTriangle, 
    label: "Étouffement", 
    description: "Manœuvre de Heimlich",
    color: "text-amber-500",
    bgColor: "bg-amber-50",
    borderColor: "border-amber-100"
  },
  { 
    icon: Activity, 
    label: "Hémorragie", 
    description: "Compression & garrot",
    color: "text-rose-500",
    bgColor: "bg-rose-50",
    borderColor: "border-rose-100"
  },
]

const stats = [
  { icon: Users, value: 15000, suffix: "+", label: "Utilisateurs" },
  { icon: Zap, value: 190, suffix: "", label: "N° Urgence" },
  { icon: MapPin, value: 24, suffix: "/7", label: "Disponible" },
]

export default function HomePage() {
  const [currentTime, setCurrentTime] = useState("")
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    setIsLoaded(true)
    const updateTime = () => {
      setCurrentTime(
        new Date().toLocaleTimeString("fr-FR", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      )
    }
    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-[100dvh] bg-gradient-to-b from-slate-50 via-white to-cyan-50/30 pb-24 sm:pb-28 relative overflow-hidden">
      <FloatingParticles />
      
      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="sticky top-0 z-50 backdrop-blur-2xl bg-white/70 border-b border-slate-100/50 safe-area-top"
      >
        <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
          <motion.div 
            className="flex items-center gap-3 sm:gap-4"
            whileHover={{ scale: 1.02 }}
            transition={{ type: "spring", stiffness: 400 }}
          >
            <motion.div
              initial={{ rotate: -10, scale: 0.8 }}
              animate={{ rotate: 0, scale: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="overflow-hidden rounded-2xl"
            >
              {/* Container avec clip pour masquer le watermark en haut */}
              <div className="relative w-16 h-16 sm:w-20 sm:h-20 md:w-24 md:h-24 overflow-hidden">
                <img
                  src="/animations/logo_monkedh.gif"
                  alt="Monkedh Logo"
                  className="absolute top-[-10%] left-0 w-full h-[120%] object-cover drop-shadow-lg"
                />
              </div>
            </motion.div>
            <div>
              <motion.h1 
                className="font-extrabold text-xl sm:text-2xl bg-gradient-to-r from-[#0891B2] to-teal-600 bg-clip-text text-transparent"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
              >
                Monkedh
              </motion.h1>
              <motion.p 
                className="text-[10px] sm:text-xs text-slate-500 font-medium"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
              >
                🇹🇳 Secourisme d'urgence Tunisie
              </motion.p>
            </div>
          </motion.div>
          
          <motion.div 
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100/80 text-slate-600"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5 }}
          >
            <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="text-xs sm:text-sm font-medium tabular-nums">{currentTime}</span>
          </motion.div>
        </div>
      </motion.header>

      <main className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-5 sm:py-8 space-y-6 sm:space-y-8 relative z-10">
        
        {/* Emergency SOS Button */}
        <motion.section
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <Link href="tel:190">
            <motion.div
              className="relative flex flex-col items-center justify-center p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-red-500 via-rose-500 to-red-600 text-white shadow-2xl shadow-red-500/40 overflow-hidden cursor-pointer"
              whileHover={{ scale: 1.02, boxShadow: "0 25px 50px -12px rgba(239, 68, 68, 0.5)" }}
              whileTap={{ scale: 0.98 }}
            >
              {/* Animated background pattern */}
              <div className="absolute inset-0 opacity-10">
                <div className="absolute inset-0" style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                }} />
              </div>
              
              <EmergencyPulse />

              <motion.div
                className="relative z-10 w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center mb-4 border-4 border-white/30"
                animate={{
                  boxShadow: [
                    "0 0 0 0 rgba(255,255,255,0.4)",
                    "0 0 0 30px rgba(255,255,255,0)",
                  ],
                }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <Phone className="w-10 h-10 sm:w-12 sm:h-12" />
              </motion.div>
              
              <motion.span 
                className="relative z-10 text-3xl sm:text-4xl font-black tracking-wider"
                animate={{ scale: [1, 1.02, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                APPEL 190
              </motion.span>
              <span className="relative z-10 text-sm sm:text-base opacity-90 mt-2 font-medium">
                SAMU Tunisie - Urgence médicale
              </span>
              
              <motion.div 
                className="mt-4 px-4 py-1.5 rounded-full bg-white/20 backdrop-blur-sm text-xs sm:text-sm font-medium"
                animate={{ opacity: [0.7, 1, 0.7] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                Appuyez pour appeler immédiatement
              </motion.div>
            </motion.div>
          </Link>
        </motion.section>

        {/* Stats Section */}
        <motion.section
          variants={containerVariants}
          initial="hidden"
          animate={isLoaded ? "visible" : "hidden"}
          className="grid grid-cols-3 gap-3 sm:gap-4"
        >
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              variants={itemVariants}
              className="bg-white rounded-2xl p-3 sm:p-4 shadow-sm border border-slate-100 text-center"
              whileHover={{ y: -4, boxShadow: "0 10px 40px -10px rgba(0,0,0,0.1)" }}
            >
              <div className="w-10 h-10 sm:w-12 sm:h-12 mx-auto mb-2 rounded-xl bg-gradient-to-br from-cyan-50 to-teal-50 flex items-center justify-center">
                <stat.icon className="w-5 h-5 sm:w-6 sm:h-6 text-[#0891B2]" />
              </div>
              <div className="text-xl sm:text-2xl font-bold text-slate-800">
                <AnimatedCounter value={stat.value} suffix={stat.suffix} />
              </div>
              <div className="text-[10px] sm:text-xs text-slate-500 font-medium">{stat.label}</div>
            </motion.div>
          ))}
        </motion.section>

        {/* Quick Actions */}
        <motion.section 
          variants={containerVariants} 
          initial="hidden" 
          animate={isLoaded ? "visible" : "hidden"}
          className="space-y-3 sm:space-y-4"
        >
          <motion.div variants={itemVariants} className="flex items-center gap-2 px-1">
            <Zap className="w-4 h-4 text-amber-500" />
            <h2 className="text-sm sm:text-base font-bold text-slate-800">
              Assistance IA immédiate
            </h2>
          </motion.div>

          <div className="grid gap-3 sm:gap-4">
            {quickActions.map((action, index) => (
              <motion.div key={action.label} variants={itemVariants}>
                <Link href={action.href}>
                  <motion.div
                    className={`relative overflow-hidden rounded-2xl p-4 sm:p-5 ${action.bgColor} border border-white/50 shadow-lg shadow-slate-200/50 active:scale-[0.98] transition-all ${
                      action.featured ? "ring-2 ring-emerald-400/50 ring-offset-2" : ""
                    }`}
                    whileHover={{ 
                      scale: 1.02, 
                      y: -4,
                      boxShadow: "0 20px 40px -15px rgba(0,0,0,0.15)" 
                    }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <div className="flex items-center gap-4">
                      {action.avatar ? (
                        <motion.div
                          className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-white shadow-lg flex items-center justify-center overflow-hidden border-2 border-white"
                          whileHover={{ rotate: [0, -5, 5, 0] }}
                          transition={{ duration: 0.5 }}
                        >
                          <Image
                            src={action.avatar}
                            alt={action.label}
                            width={56}
                            height={56}
                            className="object-cover scale-110"
                          />
                        </motion.div>
                      ) : (
                        <div className={`w-14 h-14 sm:w-16 sm:h-16 rounded-2xl ${action.iconBg} shadow-lg flex items-center justify-center`}>
                          <action.icon className="w-7 h-7 sm:w-8 sm:h-8 text-white" />
                        </div>
                      )}
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-bold text-slate-800 text-base sm:text-lg">{action.label}</h3>
                          {action.featured && (
                            <motion.span
                              className="px-2.5 py-1 text-[10px] sm:text-xs font-bold bg-gradient-to-r from-emerald-500 to-green-500 text-white rounded-full shadow-sm"
                              animate={{ scale: [1, 1.05, 1] }}
                              transition={{ duration: 2, repeat: Infinity }}
                            >
                              ⭐ Recommandé
                            </motion.span>
                          )}
                        </div>
                        <p className="text-xs sm:text-sm text-slate-600 mt-0.5">{action.description}</p>
                      </div>
                      
                      <motion.div
                        className="w-10 h-10 rounded-full bg-white/80 shadow-sm flex items-center justify-center"
                        whileHover={{ x: 5 }}
                      >
                        <ChevronRight className="w-5 h-5 text-slate-400" />
                      </motion.div>
                    </div>

                    {/* Decorative gradient */}
                    <motion.div
                      className={`absolute -top-10 -right-10 w-32 h-32 bg-gradient-to-br ${action.gradient} opacity-10 rounded-full blur-2xl`}
                      animate={{ scale: [1, 1.2, 1], opacity: [0.1, 0.15, 0.1] }}
                      transition={{ duration: 4, repeat: Infinity }}
                    />
                  </motion.div>
                </Link>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Emergency Procedures */}
        <motion.section 
          variants={containerVariants} 
          initial="hidden" 
          animate={isLoaded ? "visible" : "hidden"}
          className="space-y-3 sm:space-y-4"
        >
          <motion.div variants={itemVariants} className="flex items-center gap-2 px-1">
            <Heart className="w-4 h-4 text-red-500" />
            <h2 className="text-sm sm:text-base font-bold text-slate-800">
              Gestes qui sauvent
            </h2>
          </motion.div>

          <motion.div
            variants={itemVariants}
            className="bg-white rounded-2xl border border-slate-100 shadow-lg shadow-slate-100/50 overflow-hidden"
          >
            {emergencyProcedures.map((procedure, index) => (
              <motion.button
                key={procedure.label}
                className={`w-full flex items-center gap-4 p-4 sm:p-5 hover:bg-slate-50/80 active:bg-slate-100 transition-all ${
                  index !== emergencyProcedures.length - 1 ? "border-b border-slate-100" : ""
                }`}
                whileHover={{ x: 8, backgroundColor: "rgba(248, 250, 252, 0.8)" }}
                whileTap={{ scale: 0.99 }}
              >
                <motion.div 
                  className={`w-12 h-12 sm:w-14 sm:h-14 rounded-xl ${procedure.bgColor} ${procedure.borderColor} border-2 flex items-center justify-center shadow-sm`}
                  whileHover={{ rotate: [0, -10, 10, 0], scale: 1.1 }}
                  transition={{ duration: 0.4 }}
                >
                  <procedure.icon className={`w-6 h-6 sm:w-7 sm:h-7 ${procedure.color}`} />
                </motion.div>
                <div className="flex-1 text-left">
                  <span className="font-bold text-slate-800 text-sm sm:text-base block">{procedure.label}</span>
                  <span className="text-xs sm:text-sm text-slate-500">{procedure.description}</span>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-300" />
              </motion.button>
            ))}
          </motion.div>
        </motion.section>

        {/* Info Card with Gradient Border */}
        <motion.section
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.6 }}
        >
          <GradientBorder>
            <div className="p-5 sm:p-6">
              <div className="flex items-start gap-4">
                <motion.div 
                  className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-teal-500 flex items-center justify-center flex-shrink-0 shadow-lg shadow-cyan-500/30"
                  animate={{ rotate: [0, 5, -5, 0] }}
                  transition={{ duration: 4, repeat: Infinity }}
                >
                  <Shield className="w-6 h-6 sm:w-7 sm:h-7 text-white" />
                </motion.div>
                <div>
                  <h3 className="font-bold text-slate-800 text-base sm:text-lg mb-1">
                    Restez calme, nous sommes là
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    En situation d'urgence, notre assistant IA vous guide étape par étape avec des instructions claires et précises. 
                    <span className="font-semibold text-[#0891B2]"> Chaque seconde compte.</span>
                  </p>
                </div>
              </div>
            </div>
          </GradientBorder>
        </motion.section>
      </main>

      {/* Bottom Navigation - Enhanced */}
      <motion.nav
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.5 }}
        className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-2xl border-t border-slate-100/50 safe-area-bottom z-50"
      >
        <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-2 sm:py-3">
          <div className="flex items-center justify-around">
            {[
              { icon: Activity, label: "Accueil", href: "/", active: true },
              { icon: MessageCircle, label: "Chat", href: "/chat" },
              { icon: Mic, label: "Appel", href: "/voice-call" },
              { icon: Camera, label: "CPR", href: "/cpr-camera" },
            ].map((item) => (
              <Link
                key={item.label}
                href={item.href}
              >
                <motion.div
                  className={`flex flex-col items-center gap-1 px-4 sm:px-6 py-2.5 rounded-2xl transition-all ${
                    item.active 
                      ? "text-[#0891B2] bg-gradient-to-br from-cyan-50 to-teal-50 shadow-sm" 
                      : "text-slate-400 hover:text-slate-600"
                  }`}
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <item.icon className={`w-5 h-5 sm:w-6 sm:h-6 ${item.active ? "stroke-[2.5]" : ""}`} />
                  <span className={`text-[10px] sm:text-xs font-semibold ${item.active ? "font-bold" : ""}`}>
                    {item.label}
                  </span>
                </motion.div>
              </Link>
            ))}
          </div>
        </div>
      </motion.nav>
    </div>
  )
}
