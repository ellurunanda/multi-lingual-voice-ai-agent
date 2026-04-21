/**
 * Voice recording button component with animated states.
 * Shows different visual states: idle, recording, processing, playing.
 */
import { Mic, Loader2, Volume2, Square } from "lucide-react";

export const VoiceButton = ({
  recordingState,
  isConnected,
  onStartRecording,
  onStopRecording,
  disabled = false,
}) => {
  const handleClick = () => {
    if (!isConnected || disabled) return;
    if (recordingState === "recording") {
      onStopRecording();
    } else if (recordingState === "idle") {
      onStartRecording();
    }
  };

  const getButtonConfig = () => {
    switch (recordingState) {
      case "recording":
        return {
          icon: <Square className="w-8 h-8" />,
          label: "Stop Recording",
          className: "bg-red-500 hover:bg-red-600 shadow-red-300",
          pulse: true,
          ringColor: "ring-red-400",
        };
      case "processing":
        return {
          icon: <Loader2 className="w-8 h-8 animate-spin" />,
          label: "Processing...",
          className: "bg-yellow-500 cursor-not-allowed shadow-yellow-300",
          pulse: false,
          ringColor: "ring-yellow-400",
        };
      case "playing":
        return {
          icon: <Volume2 className="w-8 h-8" />,
          label: "Playing Response",
          className: "bg-green-500 cursor-not-allowed shadow-green-300",
          pulse: true,
          ringColor: "ring-green-400",
        };
      default:
        return {
          icon: <Mic className="w-8 h-8" />,
          label: isConnected ? "Start Recording" : "Not Connected",
          className: isConnected
            ? "bg-blue-600 hover:bg-blue-700 shadow-blue-300"
            : "bg-gray-400 cursor-not-allowed shadow-gray-300",
          pulse: false,
          ringColor: "ring-blue-400",
        };
    }
  };

  const config = getButtonConfig();
  const isClickable = isConnected && (recordingState === "idle" || recordingState === "recording");

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative">
        {config.pulse && (
          <>
            <div
              className={`absolute inset-0 rounded-full ${
                recordingState === "recording" ? "bg-red-400" : "bg-green-400"
              } animate-ping opacity-30 scale-150`}
            />
            <div
              className={`absolute inset-0 rounded-full ${
                recordingState === "recording" ? "bg-red-400" : "bg-green-400"
              } animate-ping opacity-20 scale-125`}
              style={{ animationDelay: "0.3s" }}
            />
          </>
        )}
        <button
          onClick={handleClick}
          disabled={!isClickable || disabled}
          className={`
            relative w-24 h-24 rounded-full text-white font-medium
            transition-all duration-200 ease-in-out
            shadow-lg ${config.className}
            ${isClickable ? "hover:scale-105 active:scale-95" : ""}
            focus:outline-none focus:ring-4 ${config.ringColor} focus:ring-opacity-50
            flex items-center justify-center
          `}
          aria-label={config.label}
          title={config.label}
        >
          {config.icon}
        </button>
      </div>

      <span
        className={`text-sm font-medium ${
          recordingState === "recording"
            ? "text-red-600"
            : recordingState === "processing"
              ? "text-yellow-600"
              : recordingState === "playing"
                ? "text-green-600"
                : isConnected
                  ? "text-blue-600"
                  : "text-gray-500"
        }`}
      >
        {config.label}
      </span>

      {recordingState === "recording" && (
        <div className="flex items-center gap-1 h-8">
          {[1, 2, 3, 4, 5, 4, 3, 2, 1].map((height, i) => (
            <div
              key={i}
              className="w-1 bg-red-500 rounded-full"
              style={{
                height: `${height * 6}px`,
                animation: "wave 1s ease-in-out infinite",
                animationDelay: `${i * 0.1}s`,
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
};