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
      bg: "bg-blue-50",
      border: "border-blue-200",
      icon: Loader2,
      text: "text-blue-700",
      label: "En cours",
    },
    analyzing_frames: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      icon: Loader2,
      text: "text-blue-700",
      label: "Analyse des images",
    },
    analyzing_audio: {
      bg: "bg-blue-50",
      border: "border-blue-200",
      icon: Loader2,
      text: "text-blue-700",
      label: "Analyse audio",
    },
    generating_report: {
      bg: "bg-purple-50",
      border: "border-purple-200",
      icon: FileText,
      text: "text-purple-700",
      label: "Génération du rapport",
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
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${config.bg} ${config.border}`}>
      <Icon className={`w-4 h-4 ${config.text} ${isAnimated ? "animate-spin" : ""}`} />
      <span className={`text-xs font-semibold ${config.text}`}>{config.label}</span>
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
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 pb-32 sm:pb-40">
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
            className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
            onClick={() => setShowEmailModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-white rounded-2xl p-6 max-w-md w-full shadow-xl"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-slate-900">Envoyer par email</h3>
                <button onClick={() => setShowEmailModal(false)} className="p-1 hover:bg-slate-100 rounded-lg">
                  <X className="w-5 h-5 text-slate-500" />
                </button>
              </div>
              <input
                type="email"
                value={emailAddress}
                onChange={e => setEmailAddress(e.target.value)}
                placeholder="Adresse email"
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 mb-4"
              />
              <button
                onClick={handleSendEmail}
                disabled={!emailAddress || isSendingEmail}
                className="w-full py-3 bg-gradient-to-r from-cyan-500 to-teal-500 text-white font-semibold rounded-xl hover:shadow-lg disabled:opacity-50 transition-all flex items-center justify-center gap-2"
              >
                {isSendingEmail ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Envoi en cours...
                  </>
                ) : (
                  <>
                    <Mail className="w-5 h-5" />
                    Envoyer
                  </>
                )}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-40 w-full bg-white/80 backdrop-blur-xl border-b border-slate-100/50"
      >
        <div className="w-full flex justify-center px-4 sm:px-6">
          <div className="w-full max-w-3xl py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
            <Link href="/">
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-6 h-6 text-slate-600" />
              </motion.button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Rapports Vidéo</h1>
              <p className="text-sm text-slate-500">Analyse d&apos;urgence par vidéo</p>
            </div>
          </div>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadReports}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            title="Actualiser"
          >
            <RefreshCw className={`w-5 h-5 text-slate-600 ${isLoading ? "animate-spin" : ""}`} />
          </motion.button>
          </div>
        </div>
      </motion.header>

      {/* Error Banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="w-full flex justify-center px-4 sm:px-6 pt-4"
          >
            <div className="w-full max-w-3xl">
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                <p className="text-red-700">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="p-1 hover:bg-red-100 rounded-lg">
                <X className="w-4 h-4 text-red-600" />
              </button>
            </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <div className="w-full flex justify-center px-4 sm:px-6 py-6">
        <div className="w-full max-w-3xl">
          <AnimatePresence mode="wait">
          {selectedReport ? (
            <motion.div
              key="detail"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="space-y-6"
            >
              {/* Detail Header */}
              <motion.button
                onClick={() => setSelectedReport(null)}
                className="flex items-center gap-2 text-[#0891B2] hover:text-teal-700 font-medium transition-colors"
                whileHover={{ x: -4 }}
              >
                <ArrowLeft className="w-4 h-4" />
                Retour à la liste
              </motion.button>

              {/* Report Header */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-100"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-2xl font-bold text-slate-900">{selectedReport.title}</h2>
                    <p className="text-slate-500 text-sm mt-1">{formatDate(selectedReport.date)}</p>
                  </div>
                  <StatusBadge status={selectedReport.status} />
                </div>

                {/* Video Info */}
                {selectedReport.video_info && (
                  <div className="grid grid-cols-3 gap-4 py-4 border-y border-slate-100 mb-4">
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wide">Fichier</p>
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {(selectedReport.video_info as { filename?: string }).filename || "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wide">Durée</p>
                      <p className="text-sm font-medium text-slate-900">
                        {(selectedReport.video_info as { duration?: number }).duration 
                          ? `${Math.round((selectedReport.video_info as { duration: number }).duration)}s` 
                          : "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wide">Taille</p>
                      <p className="text-sm font-medium text-slate-900">
                        {(selectedReport.video_info as { size?: number }).size 
                          ? `${((selectedReport.video_info as { size: number }).size / (1024 * 1024)).toFixed(1)} MB` 
                          : "N/A"}
                      </p>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleDownload}
                    className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-500 to-teal-500 text-white font-semibold py-3 rounded-xl hover:shadow-lg transition-all"
                  >
                    <Download className="w-5 h-5" />
                    Télécharger
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setShowEmailModal(true)}
                    className="flex-1 flex items-center justify-center gap-2 bg-slate-100 text-slate-700 font-semibold py-3 rounded-xl hover:bg-slate-200 transition-all"
                  >
                    <Share2 className="w-5 h-5" />
                    Envoyer
                  </motion.button>
                </div>
              </motion.div>

              {/* Report Content */}
              {selectedReport.status === "completed" && selectedReport.content_html && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                  className="bg-white rounded-3xl p-5 sm:p-8 shadow-sm border border-slate-100 overflow-hidden"
                >
                  <h3 className="font-semibold text-slate-900 mb-5 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-cyan-600" />
                    Contenu du Rapport
                  </h3>
                  <div 
                    className="report-content-wrapper prose prose-slate max-w-none rounded-2xl overflow-hidden border border-slate-200 shadow-sm"
                    dangerouslySetInnerHTML={{ __html: selectedReport.content_html }}
                  />
                </motion.div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="list"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              {/* Upload Section */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                onClick={() => !isUploading && fileInputRef.current?.click()}
                className="bg-gradient-to-br from-cyan-50 via-teal-50 to-emerald-50 rounded-3xl p-6 sm:p-8 border-2 border-dashed border-cyan-200 cursor-pointer hover:border-cyan-300 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <motion.div
                    animate={{ y: [0, -4, 0] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <Upload className="w-10 h-10 text-cyan-500" />
                  </motion.div>
                  <div className="flex-1">
                    <h3 className="font-bold text-slate-900">Importer une vidéo</h3>
                    <p className="text-sm text-slate-600">
                      {uploadProgress || "Cliquez ou glissez une vidéo (MP4, MOV, AVI, WebM)"}
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className={`px-6 py-2 bg-cyan-500 text-white font-semibold rounded-lg hover:bg-cyan-600 transition-all flex items-center gap-2 ${isUploading ? "opacity-50" : ""}`}
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Chargement...
                      </>
                    ) : (
                      "Importer"
                    )}
                  </motion.div>
                </div>
              </motion.div>

              {/* Loading State */}
              {isLoading && reports.length === 0 && (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                </div>
              )}

              {/* Reports List */}
              {reports.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-lg font-bold text-slate-900 px-2">
                    Rapports ({reports.length})
                  </h2>
                  {reports.map((report, index) => (
                    <motion.div
                      key={report.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => handleViewReport(report)}
                      className="bg-white rounded-2xl p-4 sm:p-5 shadow-sm border border-slate-100 hover:shadow-md cursor-pointer transition-all group"
                    >
                      <div className="flex items-start gap-4">
                        <motion.div
                          whileHover={{ scale: 1.1 }}
                          className="relative w-12 h-12 bg-gradient-to-br from-cyan-100 to-teal-100 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:shadow-lg transition-shadow"
                        >
                          <Video className="w-6 h-6 text-cyan-600" />
                        </motion.div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 justify-between mb-1">
                            <h3 className="font-semibold text-slate-900 truncate">{report.title}</h3>
                            <StatusBadge status={report.status} />
                          </div>
                          <p className="text-sm text-slate-500 flex items-center gap-1.5">
                            <Clock className="w-4 h-4" />
                            {formatDate(report.date)}
                          </p>
                          {report.summary && (
                            <p className="text-sm text-slate-600 mt-2 line-clamp-2">{report.summary}</p>
                          )}
                        </div>
                      </div>

                      {/* Action Icons */}
                      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100 opacity-0 group-hover:opacity-100 transition-opacity">
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.95 }}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(report.id)
                          }}
                          className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </motion.button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Empty State */}
              {!isLoading && reports.length === 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center py-12"
                >
                  <Video className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                  <p className="text-slate-500 font-medium">Aucun rapport vidéo</p>
                  <p className="text-sm text-slate-400">Commencez par importer une vidéo</p>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
