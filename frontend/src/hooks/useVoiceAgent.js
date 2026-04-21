/**
 * Custom React hook for managing the Voice AI Agent state and WebSocket connection.
 * Handles audio recording, WebSocket communication, and conversation state.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { VoiceWebSocketService, AudioRecorder, AudioPlayer } from "../services/websocket";

const generateId = () => Math.random().toString(36).substr(2, 9);

export function useVoiceAgent(options = {}) {
  const { patientId, initialLanguage = "en", autoConnect = false } = options;

  const [state, setState] = useState({
    sessionId: uuidv4(),
    patientId,
    language: initialLanguage,
    recordingState: "idle",
    isConnected: false,
    isConnecting: false,
    messages: [],
    currentLatency: undefined,
    processingStage: undefined,
    error: undefined,
  });

  const wsRef = useRef(null);
  const recorderRef = useRef(null);
  const playerRef = useRef(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Initialize audio player
  useEffect(() => {
    playerRef.current = new AudioPlayer();
    playerRef.current.onEnd(() => {
      setState((prev) => ({ ...prev, recordingState: "idle" }));
    });
    return () => {
      playerRef.current?.stop();
    };
  }, []);

  const connect = useCallback(async () => {
    if (stateRef.current.isConnected || stateRef.current.isConnecting) return;
    setState((prev) => ({ ...prev, isConnecting: true, error: undefined }));

    const sessionId = stateRef.current.sessionId;
    const ws = new VoiceWebSocketService(sessionId);
    wsRef.current = ws;

    ws.on("session_started", (msg) => {
      setState((prev) => ({
        ...prev,
        isConnected: true,
        isConnecting: false,
        language: msg.language || prev.language,
      }));
    });

    ws.on("transcript", (msg) => {
      const userMessage = {
        id: generateId(),
        role: "user",
        text: msg.text,
        language: msg.language,
        timestamp: new Date(),
      };
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        processingStage: "llm",
      }));
    });

    ws.on("response_text", (msg) => {
      const assistantMessage = {
        id: generateId(),
        role: "assistant",
        text: msg.text,
        language: msg.language,
        timestamp: new Date(),
        isLoading: true,
      };
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
        processingStage: "tts",
      }));
    });

    ws.on("audio_response", async (msg) => {
      try {
        setState((prev) => ({ ...prev, recordingState: "playing" }));
        setState((prev) => ({
          ...prev,
          messages: prev.messages.map((item, idx) =>
            idx === prev.messages.length - 1 && item.role === "assistant"
              ? { ...item, isLoading: false }
              : item,
          ),
          processingStage: undefined,
        }));
        await playerRef.current?.play(msg.data, msg.format || "mp3");
      } catch (error) {
        console.error("Failed to play audio:", error);
        setState((prev) => ({ ...prev, recordingState: "idle" }));
      }
    });

    ws.on("latency", (msg) => {
      setState((prev) => ({
        ...prev,
        currentLatency: msg.metrics,
        messages: prev.messages.map((item, idx) =>
          idx === prev.messages.length - 1 && item.role === "assistant"
            ? { ...item, latency: msg.metrics }
            : item,
        ),
      }));
    });

    ws.on("processing", (msg) => {
      setState((prev) => ({ ...prev, processingStage: msg.stage }));
    });

    ws.on("error", (msg) => {
      setState((prev) => ({
        ...prev,
        error: msg.message,
        recordingState: "idle",
        processingStage: undefined,
      }));
    });

    ws.on("session_ended", () => {
      setState((prev) => ({ ...prev, isConnected: false }));
    });

    ws.onConnect(() => {
      setState((prev) => ({ ...prev, isConnected: true, isConnecting: false }));
    });

    ws.onDisconnect(() => {
      setState((prev) => ({ ...prev, isConnected: false, isConnecting: false }));
    });

    ws.onError(() => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        isConnecting: false,
        error: "Connection failed. Please try again.",
      }));
    });

    try {
      await ws.connect(patientId, stateRef.current.language);
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isConnecting: false,
        error: "Failed to connect to voice agent.",
      }));
    }
  }, [patientId]);

  const disconnect = useCallback(() => {
    wsRef.current?.disconnect();
    wsRef.current = null;
    recorderRef.current = null;
    setState((prev) => ({
      ...prev,
      isConnected: false,
      isConnecting: false,
      recordingState: "idle",
    }));
  }, []);

  // Auto-connect if requested — placed after connect/disconnect declarations
  useEffect(() => {
    if (autoConnect) connect();
    return () => { disconnect(); };
  }, [autoConnect, connect, disconnect]);

  const startRecording = useCallback(async () => {
    if (!stateRef.current.isConnected) {
      setState((prev) => ({ ...prev, error: "Not connected. Please connect first." }));
      return;
    }
    if (stateRef.current.recordingState !== "idle") return;
    try {
      playerRef.current?.stop();
      const recorder = new AudioRecorder();
      recorderRef.current = recorder;
      await recorder.start();
      setState((prev) => ({ ...prev, recordingState: "recording", error: undefined }));
    } catch (error) {
      console.error("Failed to start recording:", error);
      setState((prev) => ({
        ...prev,
        error: "Microphone access denied. Please allow microphone access.",
        recordingState: "idle",
      }));
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (stateRef.current.recordingState !== "recording") return;
    if (!recorderRef.current) return;
    setState((prev) => ({ ...prev, recordingState: "processing", processingStage: "stt" }));
    try {
      const audioBlob = await recorderRef.current.stop();
      const format = recorderRef.current.getFormat();
      if (audioBlob.size > 0 && wsRef.current) {
        wsRef.current.sendAudio(audioBlob, format, stateRef.current.language);
      }
      recorderRef.current = null;
    } catch (error) {
      console.error("Failed to stop recording:", error);
      setState((prev) => ({ ...prev, recordingState: "idle", processingStage: undefined }));
    }
  }, []);

  const sendTextMessage = useCallback((text) => {
    if (!stateRef.current.isConnected || !text.trim()) return;
    wsRef.current?.sendText(text, stateRef.current.language);
    setState((prev) => ({ ...prev, processingStage: "llm" }));
  }, []);

  const setLanguage = useCallback((language) => {
    setState((prev) => ({ ...prev, language }));
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: undefined }));
  }, []);

  const clearMessages = useCallback(() => {
    setState((prev) => ({ ...prev, messages: [] }));
  }, []);

  return {
    state,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    sendTextMessage,
    setLanguage,
    clearError,
    clearMessages,
  };
}