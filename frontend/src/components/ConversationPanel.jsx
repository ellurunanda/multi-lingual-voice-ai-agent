import { useEffect, useRef } from "react";
import { User, Bot, Clock, CheckCircle, AlertCircle, Loader2, Zap } from "lucide-react";
import { SUPPORTED_LANGUAGES } from "../types/index.js";

const LatencyBadge = ({ metrics }) => (
  <div className={`flex items-center gap-1 text-xs mt-1 ${metrics.met_target ? "text-green-600" : "text-orange-500"}`}>
    {metrics.met_target
      ? <CheckCircle className="w-3 h-3" />
      : <AlertCircle className="w-3 h-3" />}
    <Zap className="w-3 h-3" />
    <span className="font-medium">{metrics.total_ms}ms</span>
    <span className="text-slate-400 text-xs">
      STT:{metrics.stt_ms} · LLM:{metrics.llm_ms} · TTS:{metrics.tts_ms}
    </span>
  </div>
);

const ProcessingIndicator = ({ stage }) => {
  if (!stage) return null;
  const labels = { stt: "Transcribing speech…", llm: "AI is thinking…", tts: "Generating voice…" };
  const stages = ["stt", "llm", "tts"];
  const idx = stages.indexOf(stage);
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="bg-white rounded-2xl rounded-tl-none px-4 py-3 shadow-sm border border-slate-100 max-w-xs">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
          <span>{labels[stage]}</span>
        </div>
        <div className="flex gap-1 mt-2">
          {stages.map((s, i) => (
            <div key={s} className={`h-1 flex-1 rounded-full transition-all duration-500 ${
              i < idx ? "bg-green-400" : i === idx ? "bg-blue-500" : "bg-slate-200"
            }`} />
          ))}
        </div>
      </div>
    </div>
  );
};

export const ConversationPanel = ({ messages, processingStage, isConnected }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, processingStage]);

  const getLang = (code) => SUPPORTED_LANGUAGES.find((l) => l.code === code);

  if (!isConnected && messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: "linear-gradient(135deg, #eff6ff, #e0e7ff)" }}>
            <Bot className="w-10 h-10 text-blue-400" />
          </div>
          <h3 className="text-base font-semibold text-slate-700 mb-1">Ready to assist</h3>
          <p className="text-sm text-slate-400">Click <strong>Connect</strong> to begin your voice session</p>
          <div className="flex items-center justify-center gap-2 mt-4">
            {["EN", "HI", "TA", "TE"].map((l) => (
              <span key={l} className="px-2 py-1 rounded-lg text-xs font-semibold bg-slate-100 text-slate-500">{l}</span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3" style={{ background: "#f8fafc" }}>
      {messages.length === 0 && isConnected && (
        <div className="text-center py-8">
          <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
            style={{ background: "linear-gradient(135deg, #dcfce7, #d1fae5)" }}>
            <CheckCircle className="w-6 h-6 text-green-500" />
          </div>
          <p className="text-sm font-medium text-slate-600">Session started</p>
          <p className="text-xs text-slate-400 mt-1">Speak or tap the microphone to begin</p>
        </div>
      )}

      {messages.map((message) => (
        <div key={message.id}
          className={`flex items-end gap-2.5 ${message.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
          {/* Avatar */}
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${
            message.role === "user" ? "" : ""
          }`}
            style={message.role === "user"
              ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)" }
              : { background: "linear-gradient(135deg, #f1f5f9, #e2e8f0)" }
            }>
            {message.role === "user"
              ? <User className="w-4 h-4 text-white" />
              : <Bot className="w-4 h-4 text-slate-600" />}
          </div>

          {/* Bubble */}
          <div className={`max-w-[72%] flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
            {/* Language tag */}
            <div className={`flex items-center gap-1 text-xs mb-1 ${message.role === "user" ? "flex-row-reverse" : ""}`}>
              <span>{getLang(message.language)?.flag || "🌐"}</span>
              <span className="text-slate-400">{getLang(message.language)?.nativeName || message.language}</span>
            </div>

            <div className={`px-4 py-3 rounded-2xl shadow-sm text-sm leading-relaxed ${
              message.role === "user"
                ? "rounded-br-sm text-white"
                : "rounded-bl-sm text-slate-800 bg-white border border-slate-100"
            }`}
              style={message.role === "user"
                ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)" }
                : {}
              }>
              {message.isLoading ? (
                <div className="flex items-center gap-1.5 py-0.5">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-2 h-2 rounded-full bg-slate-300 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{message.text}</p>
              )}
            </div>

            {/* Timestamp + latency */}
            <div className={`flex items-center gap-2 mt-1 ${message.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className="flex items-center gap-1 text-xs text-slate-400">
                <Clock className="w-3 h-3" />
                <span>{message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
              {message.latency && message.role === "assistant" && (
                <LatencyBadge metrics={message.latency} />
              )}
            </div>
          </div>
        </div>
      ))}

      <ProcessingIndicator stage={processingStage} />
      <div ref={bottomRef} />
    </div>
  );
};