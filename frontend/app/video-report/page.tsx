"use client"

import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowLeft,
  Video,
  Download,
  Share2,
  Trash2,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle,
  Upload,
  Loader2,
  RefreshCw,
  Mail,
  X,
  Plus,
} from "lucide-react"
import Link from "next/link"
import { useState, useEffect, useRef, useCallback } from "react"
import {
  listVideoReports,
  getVideoReport,
  analyzeVideo,
  deleteVideoReport,
  emailVideoReport,
  getVideoAnalysisStatus,
  type VideoReportItem,
  type VideoReportDetail,
} from "@/lib/api"

function pseudoRandom01(seed: number) {
  let t = seed + 0x6d2b79f5
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}

const FLOATING_PARTICLES = Array.from({ length: 15 }, (_, i) => {
  const size = 2 + pseudoRandom01(i * 17 + 1) * 4
  const alpha = 0.05 + pseudoRandom01(i * 17 + 2) * 0.15
  return {
    size,
    alpha,
    x0: pseudoRandom01(i * 17 + 3) * 100,
    y0: pseudoRandom01(i * 17 + 4) * 100,
    x1: pseudoRandom01(i * 17 + 5) * 100,
    y1: pseudoRandom01(i * 17 + 6) * 100,
    duration: 15 + pseudoRandom01(i * 17 + 7) * 10,
    delay: pseudoRandom01(i * 17 + 8) * 5,
  }
})

function FloatingParticles() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {FLOATING_PARTICLES.map((p, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: p.size,
            height: p.size,
            background: `rgba(8, 145, 178, ${p.alpha})`,
          }}
          initial={{ x: `${p.x0}%`, y: `${p.y0}%` }}
          animate={{
            y: [null, `${p.y1}%`],
            x: [null, `${p.x1}%`],
            opacity: [0, 0.6, 0],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, {
    bg: string
    border: string
    icon: typeof CheckCircle
    text: string
    label: string
  }> = {
    completed: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      icon: CheckCircle,
      text: "text-emerald-700",
      label: "Terminé",
    },
    success: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      icon: CheckCircle,
      text: "text-emerald-700",
      label: "Succès",
    },
    processing: {
      bg: "bg-cyan-50",
      border: "border-cyan-200",
      icon: Loader2,
      text: "text-cyan-700",
      label: "En cours",
    },
    analyzing_frames: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      icon: Loader2,
      text: "text-blue-700",
      label: "Analyse images",
    },
    analyzing_audio: {
      bg: "bg-indigo-50",
      border: "border-indigo-200",
      icon: Loader2,
      text: "text-indigo-700",
      label: "Analyse audio",
    },
    generating_report: {
      bg: "bg-purple-50",
      border: "border-purple-200",
      icon: FileText,
      text: "text-purple-700",
      label: "Génération",
    },
    queued: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      icon: Clock,
      text: "text-amber-700",
      label: "En attente",
    },
    warning: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      icon: AlertTriangle,
      text: "text-amber-700",
      label: "À vérifier",
    },
    error: {
      bg: "bg-red-50",
      border: "border-red-200",
      icon: AlertTriangle,
      text: "text-red-700",
      label: "Erreur",
    },
  }

  const config = statusConfig[status] || statusConfig.processing
  const Icon = config.icon
  const isAnimated = ["processing", "analyzing_frames", "analyzing_audio", "generating_report", "queued"].includes(status)

  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border shadow-sm ${config.bg} ${config.border} backdrop-blur-sm`}>
      <Icon className={`w-3.5 h-3.5 ${config.text} ${isAnimated ? "animate-spin" : ""}`} />
      <span className={`text-[10px] sm:text-xs font-bold uppercase tracking-wider ${config.text}`}>{config.label}</span>
    </div>
  )
}

export default function VideoReportPage() {
  const [reports, setReports] = useState<VideoReportItem[]>([])
  const [selectedReport, setSelectedReport] = useState<VideoReportDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [showEmailModal, setShowEmailModal] = useState(false)
  const [emailAddress, setEmailAddress] = useState("")
  const [isSendingEmail, setIsSendingEmail] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load reports on mount
  const loadReports = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)
      const response = await listVideoReports()
      setReports(response.reports)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors du chargement des rapports")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadReports()
  }, [loadReports])

  // Poll for in-progress reports
  useEffect(() => {
    const inProgressReports = reports.filter(r =>
      ["queued", "processing", "analyzing_frames", "analyzing_audio", "generating_report"].includes(r.status)
    )

    if (inProgressReports.length === 0) return

    const interval = setInterval(async () => {
      for (const report of inProgressReports) {
        try {
          const status = await getVideoAnalysisStatus(report.id)
          if (status.status === "completed" || status.status === "error") {
            loadReports()
          } else {
            // Update status in place
            setReports(prev => prev.map(r =>
              r.id === report.id ? { ...r, status: status.status } : r
            ))
          }
        } catch {
          // Ignore polling errors
        }
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [reports, loadReports])

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // Validate file type
    const allowedTypes = ["video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/webm"]
    if (!allowedTypes.includes(file.type)) {
      setError("Type de fichier non supporté. Utilisez MP4, MPEG, MOV, AVI ou WebM.")
      return
    }

    try {
      setIsUploading(true)
      setError(null)
      setUploadProgress("Téléchargement de la vidéo...")

      const response = await analyzeVideo(file, { language: "fr" })

      setUploadProgress(`Analyse démarrée - ${response.report_id}`)

      // Add to reports list
      setReports(prev => [{
        id: response.report_id,
        title: `Analyse en cours - ${file.name}`,
        date: new Date().toISOString(),
        status: "queued",
        summary: file.name
      }, ...prev])

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'upload")
    } finally {
      setIsUploading(false)
      setUploadProgress("")
    }
  }

  const handleDelete = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()

    if (!confirm("Êtes-vous sûr de vouloir supprimer ce rapport ?")) return

    try {
      await deleteVideoReport(id)
      setReports(prev => prev.filter(r => r.id !== id))
      if (selectedReport?.id === id) {
        setSelectedReport(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de la suppression")
    }
  }

  const handleViewReport = async (report: VideoReportItem) => {
    try {
      setIsLoading(true)
      const detail = await getVideoReport(report.id)
      setSelectedReport(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors du chargement du rapport")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSendEmail = async () => {
    if (!selectedReport || !emailAddress) return

    try {
      setIsSendingEmail(true)
      await emailVideoReport(selectedReport.id, emailAddress)
      setShowEmailModal(false)
      setEmailAddress("")
      alert("Email envoyé avec succès!")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'envoi de l'email")
    } finally {
      setIsSendingEmail(false)
    }
  }

  const handleDownload = () => {
    if (!selectedReport) return

    // Create blob from HTML content
    const blob = new Blob([selectedReport.content_html], { type: "text/html" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `rapport_${selectedReport.id}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="min-h-[100dvh] bg-gradient-to-b from-slate-50 via-white to-cyan-50/30 pb-24 sm:pb-28 relative overflow-hidden">
      <FloatingParticles />

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/mp4,video/mpeg,video/quicktime,video/x-msvideo,video/webm"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Email Modal */}
      <AnimatePresence>
        {showEmailModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowEmailModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl border border-slate-100"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-slate-900">Partager le rapport</h3>
                <button onClick={() => setShowEmailModal(false)} className="p-2 hover:bg-slate-100 rounded-xl transition-colors">
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>
              <div className="relative mb-6">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="email"
                  value={emailAddress}
                  onChange={e => setEmailAddress(e.target.value)}
                  placeholder="Adresse email"
                  className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 transition-all font-medium"
                />
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSendEmail}
                disabled={!emailAddress || isSendingEmail}
                className="w-full py-4 bg-gradient-to-r from-cyan-600 to-teal-600 text-white font-bold rounded-2xl shadow-lg shadow-cyan-500/20 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
              >
                {isSendingEmail ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Envoi...
                  </>
                ) : (
                  <>
                    <Mail className="w-5 h-5" />
                    Envoyer le rapport
                  </>
                )}
              </motion.button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-50 backdrop-blur-2xl bg-white/70 border-b border-slate-100/50 safe-area-top"
      >
        <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                className="p-2 hover:bg-slate-100 rounded-xl transition-colors"
              >
                <ArrowLeft className="w-6 h-6 text-slate-600" />
              </motion.button>
            </Link>
            <div>
              <h1 className="text-xl sm:text-2xl font-black bg-gradient-to-r from-[#0891B2] to-teal-600 bg-clip-text text-transparent">
                Focus Vidéo
              </h1>
              <p className="text-[10px] sm:text-xs text-slate-500 font-bold uppercase tracking-widest flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                Dossiers Médicaux
              </p>
            </div>
          </div>
          <motion.button
            whileHover={{ rotate: 180 }}
            transition={{ duration: 0.5 }}
            onClick={loadReports}
            className="p-2.5 hover:bg-slate-100 rounded-xl transition-all"
            title="Actualiser"
          >
            <RefreshCw className={`w-5 h-5 text-slate-500 ${isLoading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </motion.header>

      {/* Error Banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: -10 }}
            className="w-full flex justify-center px-4 sm:px-6 pt-4 relative z-50"
          >
            <div className="w-full max-w-3xl">
              <div className="bg-rose-50/90 backdrop-blur-sm border border-rose-200/50 rounded-2xl p-4 flex items-center justify-between shadow-lg shadow-rose-500/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center shadow-sm">
                    <AlertTriangle className="w-5 h-5 text-rose-500" />
                  </div>
                  <p className="text-sm font-bold text-rose-700">{error}</p>
                </div>
                <button onClick={() => setError(null)} className="p-2 hover:bg-rose-100 rounded-xl transition-colors">
                  <X className="w-4 h-4 text-rose-600" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="w-full flex justify-center px-4 sm:px-6 py-8 sm:py-12 relative z-10">
        <div className="w-full max-w-3xl">
          <AnimatePresence mode="wait">
            {selectedReport ? (
              <motion.div
                key="detail"
                initial={{ opacity: 0, y: 30, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 30, scale: 0.95 }}
                className="space-y-8"
              >
                {/* Detail Header Action */}
                <motion.button
                  onClick={() => setSelectedReport(null)}
                  className="flex items-center gap-2 text-[#0891B2] hover:text-teal-700 font-bold transition-all"
                  whileHover={{ x: -4 }}
                >
                  <ArrowLeft className="w-5 h-5" />
                  <span className="text-sm uppercase tracking-widest leading-none pt-0.5">Retour aux dossiers</span>
                </motion.button>

                {/* Report Header Card */}
                <motion.div
                  className="bg-white rounded-[2.5rem] p-8 sm:p-10 shadow-2xl shadow-slate-200/50 border border-slate-100/50 relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-50/50 rounded-bl-[5rem] -mr-10 -mt-10 blur-2xl" />

                  <div className="relative space-y-8">
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6">
                      <div className="space-y-4">
                        <div className="flex items-center gap-3">
                          <span className="px-3 py-1 bg-slate-900/5 text-[10px] font-black text-slate-600 rounded-lg uppercase tracking-widest border border-slate-200/50">
                            Expertise IA
                          </span>
                          <span className="text-xs font-bold text-slate-400">#{selectedReport.id.slice(0, 8)}</span>
                        </div>
                        <h2 className="text-3xl sm:text-4xl font-black text-slate-900 leading-tight tracking-tight">
                          {selectedReport.title}
                        </h2>
                      </div>
                      <StatusBadge status={selectedReport.status} />
                    </div>

                    <div className="flex flex-wrap items-center gap-6 p-6 bg-slate-50/50 rounded-3xl border border-slate-100">
                      <div className="flex items-center gap-2.5">
                        <div className="w-10 h-10 rounded-xl bg-white shadow-sm flex items-center justify-center">
                          <Clock className="w-5 h-5 text-cyan-500" />
                        </div>
                        <div>
                          <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Date</p>
                          <p className="text-sm font-bold text-slate-700">{formatDate(selectedReport.date)}</p>
                        </div>
                      </div>

                      {selectedReport.video_info && (
                        <>
                          <div className="w-px h-10 bg-slate-200 hidden sm:block" />
                          <div className="flex items-center gap-2.5">
                            <div className="w-10 h-10 rounded-xl bg-white shadow-sm flex items-center justify-center">
                              <Video className="w-5 h-5 text-cyan-500" />
                            </div>
                            <div>
                              <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Durée</p>
                              <p className="text-sm font-bold text-slate-700">
                                {(selectedReport.video_info as any).duration
                                  ? `${Math.round((selectedReport.video_info as any).duration)}s`
                                  : "N/A"}
                              </p>
                            </div>
                          </div>
                        </>
                      )}
                    </div>

                    <div className="flex flex-col sm:flex-row gap-4">
                      <motion.button
                        whileHover={{ scale: 1.02, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleDownload}
                        className="flex-1 flex items-center justify-center gap-3 bg-slate-900 text-white font-black py-4.5 rounded-2xl shadow-xl shadow-slate-900/20 active:bg-slate-800 transition-all uppercase tracking-widest text-sm"
                      >
                        <Download className="w-5 h-5" />
                        Télécharger
                      </motion.button>
                      <motion.button
                        whileHover={{ scale: 1.02, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => setShowEmailModal(true)}
                        className="flex-1 flex items-center justify-center gap-3 bg-white text-slate-900 font-black py-4.5 rounded-2xl border border-slate-200 shadow-sm hover:shadow-xl transition-all uppercase tracking-widest text-sm"
                      >
                        <Share2 className="w-5 h-5 text-cyan-500" />
                        Partager
                      </motion.button>
                    </div>
                  </div>
                </motion.div>

                {/* Synthesis Content */}
                {selectedReport.status === "completed" && selectedReport.content_html && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="bg-white rounded-[2.5rem] shadow-2xl shadow-slate-200/50 border border-slate-100/50 overflow-hidden"
                  >
                    <div className="p-8 sm:p-10 border-b border-slate-50 flex items-center gap-4 bg-slate-50/30">
                      <div className="w-12 h-12 bg-white rounded-2xl flex items-center justify-center shadow-sm border border-slate-100">
                        <FileText className="w-6 h-6 text-cyan-600" />
                      </div>
                      <div>
                        <h3 className="font-black text-slate-900 text-xl tracking-tight">Synthèse Médicale</h3>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Compte-rendu d'incident</p>
                      </div>
                    </div>
                    <div className="p-8 sm:p-12">
                      <div
                        className="report-content-wrapper prose prose-slate max-w-none 
                        prose-headings:text-slate-900 prose-headings:font-black prose-headings:tracking-tight 
                        prose-h1:hidden
                        prose-h2:text-2xl prose-h2:pb-3 prose-h2:border-b-2 prose-h2:border-cyan-100 prose-h2:mt-12 prose-h2:mb-6
                        prose-h3:text-lg prose-h3:text-cyan-700 prose-h3:mt-8 prose-h3:mb-4
                        prose-p:text-slate-600 prose-p:leading-relaxed prose-p:text-base
                        prose-strong:text-slate-900 prose-strong:font-bold
                        prose-ul:list-none prose-ul:pl-0
                        prose-li:relative prose-li:pl-7 prose-li:mb-3 prose-li:text-slate-600
                        prose-li:before:content-[''] prose-li:before:absolute prose-li:before:left-0 prose-li:before:top-[0.6em] prose-li:before:w-2 prose-li:before:h-2 prose-li:before:bg-cyan-500 prose-li:before:rounded-full
                        prose-hr:border-slate-100 prose-hr:my-10
                        [&_.alert]:p-6 [&_.alert]:rounded-3xl [&_.alert]:my-8 [&_.alert]:border-l-8 [&_.alert]:shadow-sm
                        [&_.alert-danger]:bg-rose-50/50 [&_.alert-danger]:border-rose-500 [&_.alert-danger]:text-rose-900
                        [&_.alert-warning]:bg-amber-50/50 [&_.alert-warning]:border-amber-500 [&_.alert-warning]:text-amber-900
                        [&_.alert-info]:bg-cyan-50/50 [&_.alert-info]:border-cyan-500 [&_.alert-info]:text-cyan-900
                        [&_.alert-success]:bg-emerald-50/50 [&_.alert-success]:border-emerald-500 [&_.alert-success]:text-emerald-900
                        "
                        dangerouslySetInnerHTML={{ __html: selectedReport.content_html }}
                      />
                    </div>
                  </motion.div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="list"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-12"
              >
                {/* Upload Section (Home Action Style) */}
                <motion.section
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <motion.div
                    className="relative overflow-hidden rounded-[2.5rem] p-8 sm:p-10 bg-gradient-to-br from-cyan-50 via-teal-50 to-emerald-50 border border-white/50 shadow-2xl shadow-cyan-500/10 cursor-pointer"
                    whileHover={{
                      scale: 1.02,
                      y: -4,
                      boxShadow: "0 40px 80px -20px rgba(8, 145, 178, 0.2)"
                    }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => !isUploading && fileInputRef.current?.click()}
                  >
                    <div className="flex items-center gap-6 sm:gap-8">
                      <motion.div
                        className="w-16 h-16 sm:w-20 sm:h-20 rounded-[1.5rem] bg-gradient-to-br from-cyan-500 to-teal-500 shadow-lg shadow-cyan-500/30 flex items-center justify-center shrink-0"
                        animate={{ y: [0, -6, 0] }}
                        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                      >
                        <Upload className="w-8 h-8 sm:w-10 sm:h-10 text-white" />
                      </motion.div>

                      <div className="flex-1 min-w-0">
                        <h3 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                          Nouvelle Expertise
                        </h3>
                        <p className="text-sm sm:text-base text-slate-600 font-medium mt-1">
                          {uploadProgress || "Importez une vidéo d'incident pour analyse IA"}
                        </p>
                      </div>

                      <div className="hidden sm:flex w-10 h-10 rounded-full bg-white/80 shadow-sm items-center justify-center shrink-0">
                        <Plus className="w-5 h-5 text-cyan-500" />
                      </div>
                    </div>

                    <div className={`mt-8 px-6 py-3.5 bg-slate-900 text-white font-black rounded-2xl text-center shadow-xl transition-all uppercase tracking-widest text-sm ${isUploading ? "opacity-50" : "hover:bg-slate-800"}`}>
                      {isUploading ? (
                        <span className="flex items-center justify-center gap-3">
                          <Loader2 className="w-5 h-5 animate-spin" />
                          Traitement en cours...
                        </span>
                      ) : (
                        "Glisser ou cliquer pour importer"
                      )}
                    </div>

                    {/* Decorative accent */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-cyan-500 to-teal-500 opacity-5 rounded-full blur-3xl -mr-10 -mt-10" />
                  </motion.div>
                </motion.section>

                {/* Reports List */}
                <div className="space-y-6">
                  <div className="flex items-center justify-between px-2">
                    <h2 className="text-lg font-black text-slate-900 flex items-center gap-2">
                      <Clock className="w-5 h-5 text-cyan-500" />
                      Dossiers Récents
                    </h2>
                    <span className="px-3 py-1 bg-white border border-slate-100 rounded-full text-[10px] font-black text-slate-400 uppercase tracking-widest shadow-sm">
                      {reports.length} Analyses
                    </span>
                  </div>

                  {isLoading && reports.length === 0 ? (
                    <div className="py-20 flex flex-col items-center gap-4">
                      <div className="relative">
                        <div className="absolute inset-0 bg-cyan-100 blur-xl animate-pulse rounded-full" />
                        <Loader2 className="w-10 h-10 animate-spin text-cyan-600 relative" />
                      </div>
                      <p className="text-sm font-bold text-slate-400 uppercase tracking-widest animate-pulse">Récupération...</p>
                    </div>
                  ) : reports.length > 0 ? (
                    <div className="grid gap-4">
                      {reports.map((report, index) => (
                        <motion.div
                          key={report.id}
                          initial={{ opacity: 0, y: 20, scale: 0.98 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          transition={{ delay: index * 0.05 }}
                          onClick={() => handleViewReport(report)}
                          className="group relative bg-white rounded-3xl p-5 shadow-sm border border-slate-100 hover:shadow-xl hover:shadow-slate-200/50 hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden"
                        >
                          <div className="flex items-center gap-5">
                            <div className="w-14 h-14 rounded-2xl bg-slate-50 flex items-center justify-center shrink-0 border border-slate-100 group-hover:bg-cyan-50 group-hover:border-cyan-100 transition-colors relative">
                              <Video className="w-6 h-6 text-slate-400 group-hover:text-cyan-500 transition-colors" />
                              {report.status !== "completed" && report.status !== "error" && (
                                <motion.div
                                  className="absolute -top-1 -right-1 w-4 h-4 bg-cyan-500 border-2 border-white rounded-full"
                                  animate={{ scale: [1, 1.2, 1] }}
                                  transition={{ duration: 1.5, repeat: Infinity }}
                                />
                              )}
                            </div>

                            <div className="flex-1 min-w-0 pr-8">
                              <div className="flex items-center gap-2 mb-1">
                                <h3 className="font-black text-slate-900 truncate tracking-tight text-base group-hover:text-[#0891B2] transition-colors">
                                  {report.title}
                                </h3>
                              </div>
                              <div className="flex items-center gap-3">
                                <span className="text-xs font-bold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                                  <Clock className="w-3.5 h-3.5" />
                                  {formatDate(report.date)}
                                </span>
                                {report.summary && (
                                  <span className="text-xs font-medium text-slate-400 truncate italic">
                                    • {report.summary}
                                  </span>
                                )}
                              </div>
                            </div>

                            <StatusBadge status={report.status} />
                          </div>

                          {/* Delete Action (Desktop overlay) */}
                          <div className="absolute top-1/2 -translate-y-1/2 right-4 opacity-0 group-hover:opacity-100 transition-all translate-x-4 group-hover:translate-x-0 hidden sm:block">
                            <motion.button
                              whileHover={{ scale: 1.1 }}
                              whileTap={{ scale: 0.9 }}
                              onClick={(e) => handleDelete(report.id, e)}
                              className="p-3 bg-rose-50 text-rose-500 rounded-xl hover:bg-rose-100 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </motion.button>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="py-12 px-6 rounded-[2.5rem] bg-white border border-dashed border-slate-200 text-center"
                    >
                      <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-slate-100 shadow-sm">
                        <Video className="w-8 h-8 text-slate-300" />
                      </div>
                      <h3 className="text-lg font-black text-slate-900 tracking-tight">Aucun Rapport</h3>
                      <p className="text-sm text-slate-500 font-medium max-w-[200px] mx-auto mt-1">
                        Commencez par importer une vidéo pour voir vos expertises ici.
                      </p>
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
