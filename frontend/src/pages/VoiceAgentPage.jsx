import { useState } from "react";
import { Wifi, WifiOff, Loader2, Activity, Mic, MicOff, Zap, Globe } from "lucide-react";
import { LanguageSelector } from "../components/LanguageSelector.jsx";
import { ConversationPanel } from "../components/ConversationPanel.jsx";
import { useVoiceAgent } from "../hooks/useVoiceAgent.js";

const ConnectionBadge = ({ status, latency }) => {
  const cfg = {
    disconnected: { dot: "bg-slate-400", text: "text-slate-500", bg: "bg-slate-100", label: "Disconnected" },
    connecting:   { dot: "bg-yellow-400 animate-pulse", text: "text-yellow-700", bg: "bg-yellow-50", label: "Connecting…" },
    connected:    { dot: "bg-green-400", text: "text-green-700", bg: "bg-green-50", label: "Connected" },
    error:        { dot: "bg-red-400", text: "text-red-700", bg: "bg-red-50", label: "Error" },
  }[status] || { dot: "bg-slate-400", text: "text-slate-500", bg: "bg-slate-100", label: "Disconnected" };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
      {status === "connected" && latency != null && (
        <span className="flex items-center gap-1 opacity-70">
          <Zap className="w-3 h-3" />{latency}ms
        </span>
      )}
    </div>
  );
};

const MicButton = ({ isRecording, isProcessing, isConnected, onToggle }) => {
  const disabled = !isConnected || isProcessing;
  return (
    <button
      onClick={onToggle}
      disabled={disabled}
      className="relative flex items-center justify-center rounded-full transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-40 disabled:cursor-not-allowed"
      style={{
        width: 80, height: 80,
        background: isRecording
          ? "linear-gradient(135deg, #ef4444, #dc2626)"
          : isConnected
            ? "linear-gradient(135deg, #3b82f6, #6366f1)"
            : "#e2e8f0",
        boxShadow: isRecording
          ? "0 0 0 12px rgba(239,68,68,0.15), 0 8px 32px rgba(239,68,68,0.4)"
          : isConnected
            ? "0 0 0 12px rgba(59,130,246,0.12), 0 8px 32px rgba(59,130,246,0.35)"
            : "none",
      }}
    >
      {isProcessing ? (
        <Loader2 className="w-8 h-8 text-white animate-spin" />
      ) : isRecording ? (
        <MicOff className="w-8 h-8 text-white" />
      ) : (
        <Mic className="w-8 h-8 text-white" />
      )}
      {isRecording && (
        <>
          <span className="absolute inset-0 rounded-full animate-ping opacity-30"
            style={{ background: "rgba(239,68,68,0.5)" }} />
        </>
      )}
    </button>
  );
};

export const VoiceAgentPage = () => {
  const [selectedLanguage, setSelectedLanguage] = useState("en");

  const { state, connect, disconnect, startRecording, stopRecording, setLanguage, clearMessages } =
    useVoiceAgent({ initialLanguage: selectedLanguage });

  const handleLanguageChange = (lang) => {
    setSelectedLanguage(lang);
    setLanguage(lang);
  };

  const { isConnected, isConnecting, messages, processingStage, error, currentLatency, recordingState } = state;
  const isRecording = recordingState === "recording";
  const lastLatency = currentLatency?.total_ms ?? null;
  const connectionStatus = isConnecting ? "connecting" : isConnected ? "connected" : error ? "error" : "disconnected";

  return (
    <div className="flex flex-col h-full" style={{ background: "#f8fafc" }}>

      {/* Top header bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
              <Mic className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900">Voice AI Agent</h1>
              <p className="text-xs text-slate-500">Multilingual clinical appointment assistant</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ConnectionBadge status={connectionStatus} latency={lastLatency} />
            <button
              onClick={isConnected ? disconnect : connect}
              disabled={isConnecting}
              className="px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              style={isConnected
                ? { background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }
                : { background: "linear-gradient(135deg, #3b82f6, #6366f1)", color: "white", border: "none" }
              }
            >
              {isConnecting ? "Connecting…" : isConnected ? "Disconnect" : "Connect"}
            </button>
          </div>
        </div>

        {/* Language + clear row */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-slate-400" />
            <span className="text-xs text-slate-500 font-medium">Language:</span>
            <LanguageSelector
              selectedLanguage={selectedLanguage}
              onLanguageChange={handleLanguageChange}
              disabled={isConnected}
            />
          </div>
          {messages.length > 0 && (
            <button onClick={clearMessages}
              className="text-xs text-slate-400 hover:text-slate-600 transition-colors px-2 py-1 rounded-lg hover:bg-slate-100">
              Clear history
            </button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mt-3 px-4 py-3 rounded-xl text-sm font-medium"
          style={{ background: "#fef2f2", color: "#dc2626", border: "1px solid #fecaca" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Conversation */}
      <ConversationPanel messages={messages} processingStage={processingStage} isConnected={isConnected} />

      {/* Footer mic control */}
      <div className="bg-white border-t border-slate-200 px-6 py-5">
        <div className="flex flex-col items-center gap-3">
          <MicButton
            isRecording={isRecording}
            isProcessing={!!processingStage}
            isConnected={isConnected}
            onToggle={isRecording ? stopRecording : startRecording}
          />
          <div className="text-center">
            <p className="text-sm font-medium text-slate-700">
              {!isConnected ? "Connect to start" : isRecording ? "Recording… tap to stop" : processingStage ? "Processing…" : "Tap to speak"}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {isConnected ? "Voice AI is ready" : "Click Connect above"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};