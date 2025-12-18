"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react"
import type { LucideIcon } from "lucide-react"
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Camera,
  Flame,
  LifeBuoy,
  Loader2,
  MessageSquare,
  Phone,
  Shield,
  ShieldAlert,
  Sparkles,
  Video,
} from "lucide-react"
import { toast } from "@/hooks/use-toast"
import {
  REALTIME_API_BASE_URL,
  uploadEmergencyVideo,
  type RealtimeVideoInfo,
  type RealtimeVideoReport,
  type RealtimeTimelineEntry,
  type RealtimeEmergencyResponse,
} from "@/lib/api"

interface EmergencyMetrics {
  frame_number: number
  timestamp: string
  urgency_level: string
  detected_hazards?: string[]
  scene_description?: string
}

interface AgentToolCall {
  tool?: string
  input?: Record<string, unknown>
  output?: string
  action_summary?: string
}

interface AgentCallEventPayload {
  emergency_responses?: RealtimeEmergencyResponse[]
  agent_response?: string | null
  actions_taken?: AgentToolCall[]
  tool_calls?: AgentToolCall[]
}

interface XAIHeatmapPayload {
  frame_number: number
  timestamp: string
  grid_size: number
  heatmap_image_base64: string
  cells: {
    row: number
    col: number
    score: number
    summary: string
  }[]
  explanation?: string
  max_score?: number
}

const hazardLabels: Record<string, { label: string; color: string }> = {
  fire: { label: "Feu", color: "bg-red-100 text-red-700" },
  smoke: { label: "Fumée", color: "bg-slate-200 text-slate-700" },
  medical_emergency: { label: "Blessés", color: "bg-rose-100 text-rose-700" },
  structural_damage: { label: "Structure", color: "bg-orange-100 text-orange-700" },
}

const urgencyStyles: Record<string, { label: string; badge: string }> = {
  low: { label: "Faible", badge: "bg-emerald-100 text-emerald-700" },
  normal: { label: "Normal", badge: "bg-slate-100 text-slate-700" },
  medium: { label: "Modéré", badge: "bg-amber-100 text-amber-700" },
  high: { label: "Élevé", badge: "bg-rose-100 text-rose-700" },
}

interface ServiceVisualStyle {
  label: string
  icon: LucideIcon
  border: string
  iconBg: string
  iconColor: string
  badge: string
}

const SERVICE_VISUALS: Record<string, ServiceVisualStyle> = {
  FIRE: {
    label: "Pompiers",
    icon: Flame,
    border: "border-rose-200/80",
    iconBg: "bg-rose-50",
    iconColor: "text-rose-600",
    badge: "bg-rose-100 text-rose-700",
  },
  SAMU: {
    label: "SAMU / EMS",
    icon: LifeBuoy,
    border: "border-emerald-200/80",
    iconBg: "bg-emerald-50",
    iconColor: "text-emerald-600",
    badge: "bg-emerald-100 text-emerald-700",
  },
  POLICE: {
    label: "Police",
    icon: ShieldAlert,
    border: "border-indigo-200/80",
    iconBg: "bg-indigo-50",
    iconColor: "text-indigo-600",
    badge: "bg-indigo-100 text-indigo-700",
  },
  SMS: {
    label: "Notification",
    icon: MessageSquare,
    border: "border-cyan-200/80",
    iconBg: "bg-cyan-50",
    iconColor: "text-cyan-600",
    badge: "bg-cyan-100 text-cyan-700",
  },
  DEFAULT: {
    label: "Intervention",
    icon: Shield,
    border: "border-slate-200/80",
    iconBg: "bg-slate-50",
    iconColor: "text-slate-600",
    badge: "bg-slate-100 text-slate-600",
  },
}

const DEFAULT_TIMELINE_DESCRIPTION = "Observation fournie par SmolVLM"
const MAX_TIMELINE_ENTRIES = 160

function normalizeTimelineEntry(entry: RealtimeTimelineEntry): EmergencyMetrics {
  return {
    frame_number: entry.frame_number,
    timestamp: entry.timestamp,
    urgency_level: entry.urgency_level ?? "normal",
    detected_hazards: entry.detected_hazards ?? [],
    scene_description: entry.scene_description ?? DEFAULT_TIMELINE_DESCRIPTION,
  }
}

function formatDuration(seconds?: number): string {
  if (typeof seconds !== "number" || Number.isNaN(seconds) || seconds <= 0) {
    return "—"
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`
}

function formatResolution(info?: RealtimeVideoInfo | null): string {
  if (!info?.width || !info?.height) return "—"
  return `${info.width}×${info.height}`
}

function formatClock(timestamp?: string | null): string {
  if (!timestamp) return ""
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return timestamp
  return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

function formatChannelLabel(channel?: string | null): string {
  if (!channel) return "Agent IA"
  return channel === "frontend_queue" ? "Agent IA" : channel
}

const PARTICLE_DATA = [
  { w: 3.5, h: 4.2, bg: 0.08, x: 15, y: 25, tx: 85, ty: 60, dur: 14, del: 1 },
  { w: 2.8, h: 3.1, bg: 0.12, x: 45, y: 10, tx: 20, ty: 80, dur: 16, del: 2 },
  { w: 4.1, h: 2.9, bg: 0.06, x: 80, y: 55, tx: 35, ty: 15, dur: 13, del: 0.5 },
  { w: 3.2, h: 4.5, bg: 0.1, x: 25, y: 70, tx: 70, ty: 30, dur: 18, del: 3 },
  { w: 2.5, h: 3.8, bg: 0.07, x: 60, y: 40, tx: 10, ty: 90, dur: 15, del: 1.5 },
  { w: 4, h: 3.3, bg: 0.09, x: 90, y: 20, tx: 50, ty: 75, dur: 17, del: 4 },
  { w: 3, h: 4, bg: 0.11, x: 35, y: 85, tx: 65, ty: 45, dur: 14, del: 2.5 },
  { w: 3.7, h: 2.6, bg: 0.05, x: 70, y: 5, tx: 25, ty: 55, dur: 19, del: 0 },
  { w: 2.3, h: 3.5, bg: 0.08, x: 5, y: 50, tx: 95, ty: 35, dur: 16, del: 3.5 },
  { w: 4.3, h: 4.1, bg: 0.13, x: 55, y: 95, tx: 40, ty: 20, dur: 12, del: 1.2 },
  { w: 3.4, h: 2.8, bg: 0.06, x: 20, y: 15, tx: 75, ty: 85, dur: 15, del: 4.5 },
  { w: 2.9, h: 3.9, bg: 0.1, x: 85, y: 65, tx: 30, ty: 10, dur: 18, del: 2.2 },
  { w: 3.8, h: 3.2, bg: 0.07, x: 40, y: 30, tx: 60, ty: 70, dur: 13, del: 0.8 },
  { w: 2.6, h: 4.4, bg: 0.09, x: 65, y: 80, tx: 15, ty: 40, dur: 17, del: 3.8 },
  { w: 4.2, h: 3.6, bg: 0.11, x: 10, y: 45, tx: 90, ty: 25, dur: 14, del: 1.8 },
]

function FloatingParticles() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {PARTICLE_DATA.map((p, index) => (
        <motion.div
          key={index}
          className="absolute rounded-full"
          style={{
            width: p.w,
            height: p.h,
            background: `rgba(8, 145, 178, ${p.bg})`,
          }}
          initial={{ x: `${p.x}%`, y: `${p.y}%` }}
          animate={{ y: [null, `${p.ty}%`], x: [null, `${p.tx}%`], opacity: [0, 0.5, 0] }}
          transition={{ duration: p.dur, repeat: Infinity, delay: p.del, ease: "easeInOut" }}
        />
      ))}
    </div>
  )
}

export default function RealtimeAnalysisPage() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [timeline, setTimeline] = useState<EmergencyMetrics[]>([])
  const [latestMetrics, setLatestMetrics] = useState<EmergencyMetrics | null>(null)
  const [videoInfo, setVideoInfo] = useState<RealtimeVideoInfo | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)
  const [lastAnalysisAt, setLastAnalysisAt] = useState<string | null>(null)
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null)
  const [emergencyResponses, setEmergencyResponses] = useState<RealtimeEmergencyResponse[]>([])
  const [agentFallbackResponse, setAgentFallbackResponse] = useState<string | null>(null)
  const [agentFallbackActions, setAgentFallbackActions] = useState<string[]>([])
  const [xaiHeatmap, setXaiHeatmap] = useState<XAIHeatmapPayload | null>(null)
  const [xaiError, setXaiError] = useState<string | null>(null)
  const [videoPanelHeight, setVideoPanelHeight] = useState<number | null>(null)
  const [syncTimelineHeight, setSyncTimelineHeight] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const autoCallNoticesRef = useRef<Set<string>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const videoPanelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof window === "undefined" || !videoPanelRef.current) {
      return
    }
    const panel = videoPanelRef.current
    const updateHeight = () => {
      const rect = panel.getBoundingClientRect()
      if (rect.height > 0) {
        setVideoPanelHeight(rect.height)
      }
    }
    updateHeight()
    const observer = new ResizeObserver(() => updateHeight())
    observer.observe(panel)
    return () => {
      observer.disconnect()
    }
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    const query = window.matchMedia("(min-width: 1024px)")
    const handleChange = (event: MediaQueryListEvent | MediaQueryList) => {
      setSyncTimelineHeight(event.matches)
    }
    handleChange(query)
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", handleChange)
      return () => query.removeEventListener("change", handleChange)
    }
    query.addListener(handleChange)
    return () => query.removeListener(handleChange)
  }, [])

  const teardownSession = useCallback(() => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
    autoCallNoticesRef.current.clear()
    setSessionId(null)
    setTimeline([])
    setLatestMetrics(null)
    setVideoInfo(null)
    setLastAnalysisAt(null)
  setEmergencyResponses([])
  setXaiHeatmap(null)
  setXaiError(null)
  setAgentFallbackResponse(null)
  setAgentFallbackActions([])
    setUploadedFileName(null)
    setUploadError(null)
    setVideoPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setIsAnalyzing(false)
  }, [])

  const handleCameraClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleFrameEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as RealtimeTimelineEntry
      const metrics = normalizeTimelineEntry(payload)
      setLatestMetrics(metrics)
      setTimeline((prev) => [...prev.slice(-(MAX_TIMELINE_ENTRIES - 1)), metrics])
    } catch (error) {
      console.error("Frame event parse error", error)
    }
  }, [])

  const handleCompleteEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as RealtimeVideoReport
      if (payload.video_info) {
        setVideoInfo(payload.video_info)
      }
      const normalized = (payload.urgency_timeline ?? []).map(normalizeTimelineEntry)
      if (normalized.length) {
        const limited = normalized.slice(-MAX_TIMELINE_ENTRIES)
        setTimeline(limited)
        setLatestMetrics(limited[limited.length - 1] ?? null)
      }
      if (payload.emergency_responses) {
        setEmergencyResponses(payload.emergency_responses)
      }
      const payloadWithXai = payload as unknown as Record<string, unknown>
      const maybeXai = payloadWithXai.xai_analysis as XAIHeatmapPayload | undefined
      if (!xaiHeatmap && maybeXai?.heatmap_image_base64) {
        setXaiHeatmap(maybeXai)
      }
      const incidentWithAgentDecision = payload.critical_incidents?.find(
        (incident) => incident.agent_response || (incident.actions_taken?.length ?? 0) > 0,
      )
      if (incidentWithAgentDecision?.agent_response) {
        setAgentFallbackResponse(incidentWithAgentDecision.agent_response)
      }
      if (incidentWithAgentDecision?.actions_taken?.length) {
        const summarized = incidentWithAgentDecision.actions_taken
          .map((action) => action.tool_output || action.tool_name)
          .filter((value): value is string => Boolean(value))
        setAgentFallbackActions(summarized)
      }
      setLastAnalysisAt(new Date().toISOString())
      setIsAnalyzing(false)
      toast({
        title: "Analyse terminée",
        description: "Le rapport vidéo a été généré.",
      })
    } catch (error) {
      console.error("Complete event parse error", error)
    }
  }, [xaiHeatmap])

  const handleAgentEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as AgentCallEventPayload
      if (payload.emergency_responses?.length) {
        setEmergencyResponses(payload.emergency_responses)
      }
      if (payload.agent_response && payload.agent_response.trim().length > 0) {
        setAgentFallbackResponse(payload.agent_response)
      }
      if (payload.actions_taken?.length) {
        const summarized = payload.actions_taken
          .map((action) => action.output || action.action_summary || action.tool)
          .filter((value): value is string => Boolean(value))
        if (summarized.length) {
          setAgentFallbackActions(summarized)
        }
      }
    } catch (error) {
      console.error("Agent event parse error", error)
    }
  }, [])

  const handleToolCallEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as RealtimeEmergencyResponse
      if (!payload) {
        return
      }
      setEmergencyResponses((prev) => {
        const key = payload.call_id || `${payload.tool ?? "tool"}-${payload.service ?? "service"}-${payload.timestamp ?? Date.now()}`
        const next = prev.map((item) => {
          const existingKey = item.call_id || `${item.tool ?? "tool"}-${item.service ?? "service"}-${item.timestamp ?? ""}`
          if (existingKey === key) {
            return { ...item, ...payload }
          }
          return item
        })
        const matched = next.some((item) => (item.call_id || `${item.tool ?? "tool"}-${item.service ?? "service"}-${item.timestamp ?? ""}`) === key)
        if (matched) {
          return next
        }
        return [...next, payload]
      })
      if (!payload.requires_manual_dispatch) {
        const noticeKey = payload.call_id || `${payload.tool ?? "tool"}-${payload.timestamp ?? Date.now()}`
        if (!autoCallNoticesRef.current.has(noticeKey)) {
          autoCallNoticesRef.current.add(noticeKey)
          toast({
            title: payload.service ? `${payload.service} contacté` : "Appel automatique enregistré",
            description:
              payload.message ||
              payload.situation ||
              payload.situation_summary ||
              "L'agent IA a confirmé l'appel aux autorités.",
          })
        }
      }
    } catch (error) {
      console.error("Tool call event parse error", error)
    }
  }, [])

  const handleXaiHeatmapEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as XAIHeatmapPayload
      if (!payload?.heatmap_image_base64) {
        return
      }
      setXaiHeatmap(payload)
      setXaiError(null)
      toast({
        title: "Analyse XAI disponible",
        description: `Carte thermique générée pour la frame #${payload.frame_number}`,
      })
    } catch (error) {
      console.error("XAI event parse error", error)
    }
  }, [])

  const handleXaiErrorEvent = useCallback((event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as { detail?: string; frame_number?: number }
      const detail = payload?.detail || "Erreur XAI";
      setXaiError(detail)
      toast({
        title: "Erreur XAI",
        description: detail,
        variant: "destructive",
      })
    } catch (error) {
      console.error("XAI error event parse error", error)
    }
  }, [])

  const handleEndEvent = useCallback(() => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
    setSessionId(null)
    setIsAnalyzing(false)
  }, [])

  const handleVideoUpload = useCallback(async (file: File) => {
    setIsUploading(true)
    setUploadError(null)
    try {
      autoCallNoticesRef.current.clear()
      const session = await uploadEmergencyVideo(file)
  setSessionId(session.session_id)
  setIsAnalyzing(true)
  setTimeline([])
  setLatestMetrics(null)
  setVideoInfo(null)
  setLastAnalysisAt(null)
  setEmergencyResponses([])
  setXaiHeatmap(null)
  setXaiError(null)
  setAgentFallbackResponse(null)
  setAgentFallbackActions([])
      toast({
        title: "Analyse démarrée",
        description: "SSE connecté, attente des frames...",
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : "Impossible d'analyser la vidéo"
      setUploadError(message)
      toast({
        title: "Erreur d'analyse",
        description: message,
        variant: "destructive",
      })
    } finally {
      setIsUploading(false)
    }
  }, [])

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (file) {
        teardownSession()
        setUploadedFileName(file.name)
        setUploadError(null)
        setVideoPreviewUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev)
          return URL.createObjectURL(file)
        })
        void handleVideoUpload(file)
      }
      event.target.value = ""
    },
    [handleVideoUpload, teardownSession],
  )

  const hazards = useMemo(() => {
    const unique = new Set<string>()
    timeline.forEach((entry) => {
      entry.detected_hazards?.forEach((hazard) => unique.add(hazard))
    })
    return Array.from(unique)
  }, [timeline])
  const xaiTopCells = useMemo(() => {
    if (!xaiHeatmap?.cells?.length) return []
    return [...xaiHeatmap.cells].sort((a, b) => b.score - a.score).slice(0, 4)
  }, [xaiHeatmap])
  const xaiHeatmapSrc = useMemo(() => {
    if (!xaiHeatmap?.heatmap_image_base64) return null
    const src = xaiHeatmap.heatmap_image_base64
    return src.startsWith("data:") ? src : `data:image/jpeg;base64,${src}`
  }, [xaiHeatmap])
  const isBusy = isUploading || isAnalyzing
  const latestUrgencyStyle = urgencyStyles[latestMetrics?.urgency_level ?? "normal"]
  const hasTimeline = timeline.length > 0
  const statusLabel = isAnalyzing
    ? "Analyse en cours"
    : sessionId
      ? "Flux connecté"
      : "En attente d'une vidéo"
  const statusTone = isAnalyzing
    ? "bg-emerald-100 text-emerald-700"
    : sessionId
      ? "bg-cyan-100 text-cyan-700"
      : "bg-slate-100 text-slate-600"
  const agentCallSummary = useMemo(() => {
    const summary = {
      total: emergencyResponses.length,
      manualPending: 0,
      automated: 0,
      resolved: 0,
    }
    emergencyResponses.forEach((response) => {
      const isManual = response.requires_manual_dispatch
      if (isManual && response.dispatch_status !== "completed") {
        summary.manualPending += 1
      }
      if (!isManual) {
        summary.automated += 1
      }
      if ((response.dispatch_status ?? "") === "completed" || (response.status ?? "") === "completed") {
        summary.resolved += 1
      }
    })
    return summary
  }, [emergencyResponses])

  useEffect(() => () => teardownSession(), [teardownSession])

  useEffect(() => {
    if (!sessionId) {
      return
    }

    const baseUrl = REALTIME_API_BASE_URL.replace(/\/$/, "")
    const streamUrl = `${baseUrl}/stream/video/${sessionId}`
    const source = new EventSource(streamUrl)
    eventSourceRef.current = source

  source.addEventListener("frame", handleFrameEvent as EventListener)
  source.addEventListener("complete", handleCompleteEvent as EventListener)
  source.addEventListener("end", handleEndEvent as EventListener)
  source.addEventListener("agent_call", handleAgentEvent as EventListener)
  source.addEventListener("tool_call", handleToolCallEvent as EventListener)
  source.addEventListener("xai_heatmap", handleXaiHeatmapEvent as EventListener)
  source.addEventListener("xai_error", handleXaiErrorEvent as EventListener)

    source.onerror = () => {
      setIsAnalyzing(false)
      setUploadError("Flux SSE interrompu")
      toast({
        title: "Flux interrompu",
        description: "Connexion SSE perdue.",
        variant: "destructive",
      })
      source.close()
      if (eventSourceRef.current === source) {
        eventSourceRef.current = null
      }
      setSessionId(null)
    }

    return () => {
      source.close()
      if (eventSourceRef.current === source) {
        eventSourceRef.current = null
      }
    }
  }, [
    sessionId,
    handleFrameEvent,
    handleCompleteEvent,
    handleEndEvent,
    handleAgentEvent,
    handleToolCallEvent,
    handleXaiHeatmapEvent,
    handleXaiErrorEvent,
  ])

  useEffect(() => {
    if (!videoPreviewUrl || !videoRef.current) {
      return
    }
    const videoElement = videoRef.current
    videoElement.load()
    videoElement.play().catch(() => undefined)

    return () => {
      URL.revokeObjectURL(videoPreviewUrl)
    }
  }, [videoPreviewUrl])

  return (
    <div className="relative flex min-h-[100dvh] flex-col bg-gradient-to-b from-slate-50 via-cyan-50/30 to-white">
      <FloatingParticles />

      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky top-0 z-40 border-b border-white/60 bg-white/80 backdrop-blur-2xl shadow-sm shadow-cyan-100/60"
      >
        <div className="mx-auto flex w-full max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-2xl border border-slate-200/80 p-2.5 text-slate-500 transition hover:border-cyan-300 hover:bg-white hover:text-cyan-700"
            aria-label="Retour"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="min-w-0 flex-1 space-y-1">
            <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-cyan-600">
              <Sparkles className="h-3.5 w-3.5" />
              Moniteur vidéo IA
            </p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-base font-bold text-slate-900 sm:text-xl">Analyse vidéo en temps réel</h1>
              <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusTone}`}>{statusLabel}</span>
            </div>
            <p className="text-sm text-slate-500">
              Realtime video analysis
            </p>
          </div>

          <div className="hidden items-center gap-2 sm:flex">
            <Link
              href="/chat"
              className="rounded-2xl border border-slate-200/80 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-cyan-300 hover:text-cyan-700"
            >
              Mode chat
            </Link>
            <Link
              href="/voice-call"
              className="rounded-2xl bg-gradient-to-r from-[#0891B2] via-cyan-600 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-cyan-500/25 transition hover:shadow-cyan-500/40"
            >
              Appel vocal
            </Link>
          </div>
        </div>
      </motion.header>

      <main className="relative z-10 mx-auto w-full max-w-6xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid gap-6 items-start lg:grid-cols-[minmax(0,1fr)_360px]">
          <motion.div
            ref={videoPanelRef}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="rounded-3xl border border-slate-200/80 bg-white/90 p-5 shadow-xl shadow-cyan-100/50 backdrop-blur-xl sm:p-6"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/mp4,video/quicktime,video/x-matroska"
              className="hidden"
              onChange={handleFileChange}
            />
            <div
              ref={videoPanelRef}
              className="relative aspect-video overflow-hidden rounded-2xl border border-dashed border-slate-200 bg-slate-900/90"
            >
              {videoPreviewUrl ? (
                <video
                  ref={videoRef}
                  src={videoPreviewUrl}
                  controls
                  autoPlay
                  muted
                  loop
                  playsInline
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-4 text-white/70">
                  <Video className="h-10 w-10 text-white/50" />
                  <div className="text-center">
                    <p className="text-base font-semibold">Aucune vidéo en cours</p>
                    <p className="text-sm">Importez un fichier pour lancer l&apos;analyse temps réel.</p>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 grid gap-3 sm:flex sm:items-center sm:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Dernière analyse</div>
                <div className="text-sm font-semibold text-slate-800">
                  {lastAnalysisAt ? formatClock(lastAnalysisAt) : "En attente..."}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleCameraClick}
                  disabled={isBusy}
                  className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-[#0891B2] via-cyan-600 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-cyan-500/30 transition hover:shadow-cyan-500/40 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isBusy ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Attente des frames…
                    </>
                  ) : (
                    <>
                      <Camera className="h-4 w-4" />
                      Téléverser une vidéo
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={teardownSession}
                  disabled={!sessionId && !uploadedFileName}
                  className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-cyan-300 hover:text-cyan-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Réinitialiser
                </button>
              </div>
            </div>

            {uploadError && (
              <p className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{uploadError}</p>
            )}

            {uploadedFileName && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <div>
                  <div className="text-xs uppercase text-slate-400">Vidéo chargée</div>
                  <p className="font-semibold text-slate-800">{uploadedFileName}</p>
                </div>
                {isAnalyzing ? (
                  <span className="flex items-center gap-1 text-emerald-600">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Analyse…
                  </span>
                ) : lastAnalysisAt ? (
                  <span className="text-emerald-600">Analyse terminée</span>
                ) : null}
              </div>
            )}

            {videoInfo && (
              <dl className="mt-4 grid grid-cols-1 gap-4 text-sm text-slate-600 sm:grid-cols-3">
                <div>
                  <dt className="text-xs uppercase text-slate-400">Résolution</dt>
                  <dd className="text-lg font-semibold text-slate-900">{formatResolution(videoInfo)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-400">Durée</dt>
                  <dd className="text-lg font-semibold text-slate-900">{formatDuration(videoInfo.duration_seconds)}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase text-slate-400">Images par seconde</dt>
                  <dd className="text-lg font-semibold text-slate-900">{videoInfo.fps ?? "—"}</dd>
                </div>
              </dl>
            )}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05 }}
            className="flex h-full flex-col rounded-3xl border border-slate-200/80 bg-white/90 p-5 shadow-lg shadow-cyan-100/40 backdrop-blur-xl sm:p-6"
            style={syncTimelineHeight && videoPanelHeight ? { height: videoPanelHeight } : undefined}
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <Activity className="h-4 w-4 text-cyan-500" />
                  Chronologie en direct
                </p>
                <p className="text-sm text-slate-500">Chaque point correspond à une frame analysée.</p>
              </div>
            </div>
            <div className="relative mt-6 flex-1 overflow-hidden">
              <div
                className="absolute inset-y-0 left-5 w-px bg-gradient-to-b from-cyan-200 via-slate-200 to-transparent"
                aria-hidden
              />
              <div className="relative h-full space-y-4 overflow-y-auto pr-4">
                {hasTimeline
                  ? timeline.map((entry) => {
                      const style = urgencyStyles[entry.urgency_level] ?? urgencyStyles.normal
                      return (
                        <div
                          key={`${entry.frame_number}-${entry.timestamp}`}
                          className="relative flex gap-4 rounded-2xl border border-slate-100 bg-white/80 p-4 pl-12 shadow-sm"
                        >
                          <div className="absolute left-4 top-5 h-3 w-3 rounded-full bg-gradient-to-br from-cyan-400 to-teal-400 shadow-[0_0_0_4px_rgba(6,182,212,0.1)]" />
                          <div className="space-y-2 text-slate-700">
                            <div className="flex flex-wrap items-center justify-between text-xs uppercase text-slate-400">
                              <span>Frame #{entry.frame_number}</span>
                              <span>{formatClock(entry.timestamp)}</span>
                            </div>
                            <span className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold ${style.badge}`}>
                              {style.label}
                            </span>
                            <p className="text-sm text-slate-700">
                              {entry.scene_description || DEFAULT_TIMELINE_DESCRIPTION}
                            </p>
                            {entry.detected_hazards?.length ? (
                              <div className="flex flex-wrap gap-2 pt-1">
                                {entry.detected_hazards.map((hazard) => {
                                  const hazardInfo = hazardLabels[hazard] ?? {
                                    label: hazard,
                                    color: "bg-slate-100 text-slate-600",
                                  }
                                  return (
                                    <span
                                      key={`${entry.timestamp}-${hazard}`}
                                      className={`rounded-full px-3 py-1 text-[11px] font-semibold ${hazardInfo.color}`}
                                    >
                                      {hazardInfo.label}
                                    </span>
                                  )
                                })}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      )
                    })
                  : null}
              </div>
            </div>
          </motion.div>

        </section>

        {hazards.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.05 }}
            className="rounded-3xl border border-slate-200/80 bg-white/90 p-5 shadow-lg shadow-cyan-100/40 backdrop-blur-xl sm:p-6"
          >
            <div className="flex flex-wrap items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <div>
                <h2 className="text-base font-semibold text-slate-900">Risques relevés</h2>
                <p className="text-sm text-slate-500">Synthèse des risques identifiés pendant l&apos;analyse en direct.</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {hazards.map((hazard) => {
                const hazardInfo = hazardLabels[hazard] ?? { label: hazard, color: "bg-slate-100 text-slate-600" }
                return (
                  <span key={hazard} className={`rounded-full px-3 py-1 text-xs font-semibold ${hazardInfo.color}`}>
                    {hazardInfo.label}
                  </span>
                )
              })}
            </div>
          </motion.section>
        )}

        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="rounded-3xl border border-cyan-200/70 bg-white/95 p-5 shadow-xl shadow-cyan-100/50 backdrop-blur-xl sm:p-6"
        >
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-100 to-teal-50 text-cyan-700">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-cyan-600">Actions de l&apos;agent</p>
              <h2 className="text-base font-semibold text-slate-900">Appels et outils déclenchés</h2>
              <p className="text-sm text-slate-500">
                Visualisez instantanément quelles unités ont été contactées et le statut de chaque intervention.
              </p>
            </div>
          </div>

          {emergencyResponses.length > 0 ? (
            <>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {[
                  { label: "Actions totales", value: agentCallSummary.total, Icon: Activity },
                  { label: "Manuel à traiter", value: agentCallSummary.manualPending, Icon: Phone },
                  { label: "Automatisées", value: agentCallSummary.automated, Icon: Sparkles },
                ].map(({ label, value, Icon: StatIcon }) => (
                  <div
                    key={label}
                    className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm shadow-cyan-100/40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-cyan-600">
                        <StatIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
                        <p className="text-2xl font-semibold text-slate-900">{value}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                {emergencyResponses.map((response, index) => {
                  const serviceKey = (response.service_type || response.service || "default").toUpperCase()
                  const visual = SERVICE_VISUALS[serviceKey] ?? SERVICE_VISUALS.DEFAULT
                  const Icon = visual.icon
                  const toolBadge = response.tool?.replace(/_/g, " ") ?? visual.label
                  const requiresManual = response.requires_manual_dispatch
                  const isCompleted = (response.dispatch_status ?? "") === "completed"
                  const statusChip = requiresManual
                    ? isCompleted
                      ? {
                          label: "Manuel confirmé",
                          className: "bg-emerald-100 text-emerald-700",
                        }
                      : {
                          label: "Action opérateur",
                          className: "bg-amber-100 text-amber-800",
                        }
                    : {
                        label: "Appel automatique",
                        className: "bg-emerald-50 text-emerald-700",
                      }

                  return (
                    <div
                      key={response.call_id ?? `${response.service ?? "decision"}-${index}`}
                      className={`rounded-2xl border ${visual.border} bg-white/95 p-4 shadow-lg shadow-slate-100/60`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase text-slate-400">{formatChannelLabel(response.channel)}</p>
                          <h3 className="text-lg font-semibold text-slate-900">{response.service ?? visual.label}</h3>
                        </div>
                        <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${visual.iconBg}`}>
                          <Icon className={`h-5 w-5 ${visual.iconColor}`} />
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${visual.badge}`}>
                          {toolBadge}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${statusChip.className}`}>
                          {statusChip.label}
                        </span>
                        {response.hazard_type && (
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">
                            {response.hazard_type}
                          </span>
                        )}
                      </div>
                      {response.message && <p className="mt-3 text-sm text-slate-700">{response.message}</p>}
                      {response.situation && response.situation !== response.message && (
                        <p className="mt-2 text-xs text-slate-500">{response.situation}</p>
                      )}
                      {response.actions_taken?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {response.actions_taken.map((action) => (
                            <span
                              key={`${action}-${response.call_id ?? index}`}
                              className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600"
                            >
                              {action}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                        {response.timestamp && <span>{formatClock(response.timestamp)}</span>}
                        {response.call_id && (
                          <span className="font-mono text-[11px] text-slate-400">#{response.call_id}</span>
                        )}
                        {response.urgency && (
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">
                            Urgence: {response.urgency}
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          ) : agentFallbackResponse ? (
            <div className="mt-4 rounded-2xl border border-dashed border-cyan-200 bg-cyan-50/70 p-5 text-slate-700">
              <div className="flex items-center gap-2 text-xs uppercase text-cyan-600">
                <Phone className="h-4 w-4" />
                <span>Recommandation enregistrée</span>
              </div>
              <p className="mt-2 text-sm font-medium">{agentFallbackResponse}</p>
              {agentFallbackActions.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {agentFallbackActions.map((action, idx) => (
                    <span
                      key={`${action}-${idx}`}
                      className="rounded-full bg-white/80 px-3 py-1 text-[11px] font-semibold text-cyan-700"
                    >
                      {action}
                    </span>
                  ))}
                </div>
              )}
              <p className="mt-3 text-xs text-slate-500">
                Aucun appel automatique n&apos;a été validé, mais l&apos;instruction reste disponible pour l&apos;équipe terrain.
              </p>
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white/70 p-5 text-sm text-slate-500">
              En attente d&apos;une décision de l&apos;agent IA… Dès qu&apos;un outil sera déclenché, il apparaîtra ici.
            </div>
          )}
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="rounded-3xl border border-emerald-200/70 bg-white/95 p-5 shadow-xl shadow-emerald-100/40 backdrop-blur-xl sm:p-6"
        >
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-100 to-lime-50 text-emerald-700">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-600">Explainable-IA</p>
              <h2 className="text-base font-semibold text-slate-900">Heatmap des zones critiques</h2>
              <p className="text-sm text-slate-500">
                Visualisez la zone exacte qui a déclenché l&apos;alerte haute urgence.
              </p>
            </div>
          </div>

          {xaiHeatmapSrc ? (
            <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
              <div className="space-y-4">
                <div className="overflow-hidden rounded-2xl border border-emerald-100 bg-slate-900/90">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={xaiHeatmapSrc} alt="Carte thermique XAI" className="h-full w-full object-cover" />
                </div>
                <div className="rounded-2xl border border-slate-100 bg-white/90 p-4 text-sm text-slate-700">
                  <div className="text-xs uppercase text-slate-400">Explication</div>
                  <p className="mt-1 font-medium text-slate-900">
                    {xaiHeatmap?.explanation || "Zone à risque identifiée par l&apos;IA"}
                  </p>
                  <div className="mt-3 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
                    <div>
                      <div className="uppercase text-slate-400">Frame</div>
                      <div className="text-base font-semibold text-slate-900">#{xaiHeatmap?.frame_number}</div>
                    </div>
                    <div>
                      <div className="uppercase text-slate-400">Horodatage</div>
                      <div className="text-base font-semibold text-slate-900">
                        {formatClock(xaiHeatmap?.timestamp)}
                      </div>
                    </div>
                    <div>
                      <div className="uppercase text-slate-400">Score max</div>
                      <div className="text-base font-semibold text-slate-900">
                        {xaiHeatmap?.max_score?.toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="text-xs uppercase text-slate-400">Patches les plus critiques</div>
                {xaiTopCells.length ? (
                  xaiTopCells.map((cell) => (
                    <div
                      key={`${cell.row}-${cell.col}`}
                      className="rounded-2xl border border-slate-100 bg-white/90 p-4 shadow-sm"
                    >
                      <div className="flex items-center justify-between text-xs uppercase text-slate-400">
                        <span>
                          Ligne {cell.row + 1} / Colonne {cell.col + 1}
                        </span>
                        <span className="font-mono text-sm text-emerald-600">{cell.score.toFixed(2)}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{cell.summary || "Observation critique"}</p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-4 text-sm text-slate-500">
                    En attente des détails de patch…
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white/70 p-5 text-sm text-slate-500">
              {xaiError
                ? `Échec de la génération de la carte thermique : ${xaiError}`
                : "La carte XAI apparaît automatiquement dès qu'une frame d'urgence élevée est détectée."}
            </div>
          )}
        </motion.section>

      </main>
    </div>
  )
}
