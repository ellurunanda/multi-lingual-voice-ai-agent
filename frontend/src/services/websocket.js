/**
 * WebSocket service for real-time voice communication with the AI agent.
 * Handles connection management, audio streaming, and message routing.
 */

export class VoiceWebSocketService {
  ws = null;
  sessionId;
  reconnectAttempts = 0;
  maxReconnectAttempts = 3;
  reconnectDelay = 1000;
  messageHandlers = new Map();
  onConnectHandlers = [];
  onDisconnectHandlers = [];
  onErrorHandlers = [];
  pingInterval = null;

  constructor(sessionId) {
    this.sessionId = sessionId;
  }

  connect(patientId, language) {
    return new Promise((resolve, reject) => {
      const wsUrl = this.buildWsUrl(patientId, language);
      try {
        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = "arraybuffer";

        this.ws.onopen = () => {
          console.log(`[WS] Connected: ${this.sessionId}`);
          this.reconnectAttempts = 0;
          this.startPingInterval();
          this.onConnectHandlers.forEach((h) => h());
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.ws.onclose = (event) => {
          console.log(`[WS] Disconnected: ${event.code} ${event.reason}`);
          this.stopPingInterval();
          this.onDisconnectHandlers.forEach((h) => h());
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect(patientId, language);
          }
        };

        this.ws.onerror = (error) => {
          console.error("[WS] Error:", error);
          this.onErrorHandlers.forEach((h) => h(error));
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect() {
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close(1000, "Client disconnected");
      this.ws = null;
    }
  }

  sendAudio(audioData, format = "webm", languageHint) {
    if (!this.isConnected()) return;
    const reader = new FileReader();
    const blob = audioData instanceof Blob ? audioData : new Blob([audioData]);
    reader.onloadend = () => {
      const base64 = reader.result.split(",")[1];
      this.sendJSON({ type: "audio", data: base64, format, language_hint: languageHint });
    };
    reader.readAsDataURL(blob);
  }

  sendText(text, language) {
    this.sendJSON({ type: "text", data: text, language });
  }

  sendJSON(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn("[WS] Cannot send - not connected");
    }
  }

  on(type, handler) {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type).push(handler);
  }

  off(type, handler) {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) handlers.splice(index, 1);
    }
  }

  onConnect(handler) { this.onConnectHandlers.push(handler); }
  onDisconnect(handler) { this.onDisconnectHandlers.push(handler); }
  onError(handler) { this.onErrorHandlers.push(handler); }

  isConnected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  getSessionId() { return this.sessionId; }

  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      const handlers = this.messageHandlers.get(message.type);
      if (handlers) handlers.forEach((h) => h(message));
    } catch (error) {
      console.error("[WS] Failed to parse message:", error);
    }
  }

  buildWsUrl(patientId, language) {
    const baseUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000`;
    let url = `${baseUrl}/ws/voice/${this.sessionId}`;
    const params = new URLSearchParams();
    if (patientId) params.append("patient_id", patientId);
    if (language) params.append("language", language);
    const queryString = params.toString();
    if (queryString) url += `?${queryString}`;
    return url;
  }

  startPingInterval() {
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) this.sendJSON({ type: "ping" });
    }, 30000);
  }

  stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  scheduleReconnect(patientId, language) {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => {
      this.connect(patientId, language).catch(console.error);
    }, delay);
  }
}

/**
 * Audio recorder utility for capturing microphone input.
 */
export class AudioRecorder {
  mediaRecorder = null;
  audioChunks = [];
  stream = null;
  onDataCallback = undefined;
  onStopCallback = undefined;

  async start(onData) {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      this.onDataCallback = onData;
      this.audioChunks = [];
      const mimeType = this.getSupportedMimeType();
      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
          if (this.onDataCallback) this.onDataCallback(event.data);
        }
      };
      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.audioChunks, { type: mimeType });
        if (this.onStopCallback) this.onStopCallback(blob);
      };
      this.mediaRecorder.start(250);
      console.log("[AudioRecorder] Started recording");
    } catch (error) {
      console.error("[AudioRecorder] Failed to start:", error);
      throw error;
    }
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder) { resolve(new Blob()); return; }
      this.onStopCallback = resolve;
      this.mediaRecorder.stop();
      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
        this.stream = null;
      }
      console.log("[AudioRecorder] Stopped recording");
    });
  }

  isRecording() { return this.mediaRecorder?.state === "recording"; }

  getSupportedMimeType() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return "audio/webm";
  }

  getFormat() {
    const mimeType = this.getSupportedMimeType();
    if (mimeType.includes("webm")) return "webm";
    if (mimeType.includes("ogg")) return "ogg";
    if (mimeType.includes("mp4")) return "mp4";
    return "webm";
  }
}

/**
 * Audio player utility for playing TTS responses.
 */
export class AudioPlayer {
  audioContext = null;
  currentSource = null;
  onEndCallback = undefined;

  async play(base64Audio, _format = "mp3") {
    try {
      this.stop();
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      if (!this.audioContext) this.audioContext = new AudioContext();
      if (this.audioContext.state === "suspended") await this.audioContext.resume();
      const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);
      this.currentSource = this.audioContext.createBufferSource();
      this.currentSource.buffer = audioBuffer;
      this.currentSource.connect(this.audioContext.destination);
      this.currentSource.onended = () => {
        this.currentSource = null;
        if (this.onEndCallback) this.onEndCallback();
      };
      this.currentSource.start(0);
      console.log("[AudioPlayer] Playing audio");
    } catch (error) {
      console.error("[AudioPlayer] Failed to play:", error);
      throw error;
    }
  }

  stop() {
    if (this.currentSource) {
      try { this.currentSource.stop(); } catch (e) { /* ignore */ }
      this.currentSource = null;
    }
  }

  onEnd(callback) { this.onEndCallback = callback; }
  isPlaying() { return this.currentSource !== null; }
}