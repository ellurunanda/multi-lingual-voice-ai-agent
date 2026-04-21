import { useEffect, useState } from "react";
import { apiFetch } from "../services/api";
import { Calendar, Clock, User, Phone, CheckCircle, XCircle, AlertCircle, Loader2, Plus, Search, X, Globe } from "lucide-react";

const STATUS = {
  scheduled: { icon: Calendar, color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200", dot: "bg-blue-500", label: "Scheduled" },
  completed: { icon: CheckCircle, color: "text-green-700", bg: "bg-green-50", border: "border-green-200", dot: "bg-green-500", label: "Completed" },
  cancelled: { icon: XCircle, color: "text-red-700", bg: "bg-red-50", border: "border-red-200", dot: "bg-red-400", label: "Cancelled" },
  pending: { icon: AlertCircle, color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", dot: "bg-amber-400", label: "Pending" },
};

const AppointmentCard = ({ appointment }) => {
  const s = STATUS[appointment.status] || STATUS.pending;
  const StatusIcon = s.icon;
  const d = new Date(appointment.appointment_time);

  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-5 shadow-sm hover:shadow-md transition-all duration-200 hover:-translate-y-0.5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: "linear-gradient(135deg, #eff6ff, #e0e7ff)" }}>
              <User className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="font-bold text-slate-900 text-sm">{appointment.patient_name}</p>
              {appointment.doctor_name && (
                <p className="text-xs text-slate-400">Dr. {appointment.doctor_name}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              <span>{d.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            {appointment.phone && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                <span>{appointment.phone}</span>
              </div>
            )}
          </div>

          {appointment.reason && (
            <div className="mt-3 px-3 py-2 rounded-xl text-xs text-slate-600 bg-slate-50 border border-slate-100">
              {appointment.reason}
            </div>
          )}
        </div>

        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold flex-shrink-0 border ${s.bg} ${s.color} ${s.border}`}>
          <div className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
          {s.label}
        </div>
      </div>
    </div>
  );
};

const TABS = [
  { key: "all", label: "All" },
  { key: "scheduled", label: "Upcoming" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
];

const RegisterPatientModal = ({ onClose, onSuccess }) => {
  const [form, setForm] = useState({ name: "", phone: "", preferred_language: "en", preferred_hospital: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lookupPhone, setLookupPhone] = useState("");
  const [lookupResult, setLookupResult] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [tab, setTab] = useState("register"); // "register" | "lookup"

  const handleLookup = async () => {
    if (!lookupPhone.trim()) return;
    setLookupLoading(true);
    setLookupResult(null);
    try {
      const res = await apiFetch(`/api/patients/phone/${encodeURIComponent(lookupPhone.trim())}`);
      if (res.ok) {
        const data = await res.json();
        setLookupResult({ found: true, data });
      } else {
        setLookupResult({ found: false });
      }
    } catch {
      setLookupResult({ found: false, error: true });
    } finally {
      setLookupLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      setError("Name and phone are required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/patients/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          phone: form.phone.trim(),
          preferred_language: form.preferred_language,
          preferred_hospital: form.preferred_hospital.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Registration failed.");
      } else {
        onSuccess(data);
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
              <User className="w-4 h-4 text-white" />
            </div>
            <h2 className="font-bold text-slate-900 text-sm">Patient Management</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-3 bg-slate-50 border-b border-slate-100">
          {[{ key: "register", label: "Register New" }, { key: "lookup", label: "Look Up Existing" }].map(t => (
            <button key={t.key} onClick={() => { setTab(t.key); setError(null); setLookupResult(null); }}
              className="flex-1 py-2 rounded-xl text-xs font-semibold transition-all"
              style={tab === t.key
                ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)", color: "white" }
                : { background: "transparent", color: "#64748b" }}>
              {t.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === "register" ? (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Full Name *</label>
                <input type="text" placeholder="e.g. Arjun Patel" value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Phone Number *</label>
                <input type="tel" placeholder="e.g. +91-9000000001" value={form.phone}
                  onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Preferred Language</label>
                <select value={form.preferred_language}
                  onChange={e => setForm(f => ({ ...f, preferred_language: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white">
                  {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Preferred Hospital <span className="text-slate-400 font-normal">(optional)</span></label>
                <input type="text" placeholder="e.g. Apollo Hospital" value={form.preferred_hospital}
                  onChange={e => setForm(f => ({ ...f, preferred_hospital: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-transparent" />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-3 py-2 text-xs text-red-600 flex items-center gap-2">
                  <XCircle className="w-3.5 h-3.5 flex-shrink-0" />{error}
                </div>
              )}

              <button type="submit" disabled={loading}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
                {loading ? <span className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Registering…</span> : "Register Patient"}
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Phone Number</label>
                <div className="flex gap-2">
                  <input type="tel" placeholder="e.g. +91-9000000001" value={lookupPhone}
                    onChange={e => setLookupPhone(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleLookup()}
                    className="flex-1 px-3 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
                  <button onClick={handleLookup} disabled={lookupLoading}
                    className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                    style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
                    {lookupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {lookupResult && (
                lookupResult.found ? (
                  <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-2">
                    <div className="flex items-center gap-2 text-green-700 font-semibold text-sm">
                      <CheckCircle className="w-4 h-4" /> Patient Found
                    </div>
                    <div className="text-xs text-slate-600 space-y-1">
                      <p><span className="font-semibold">Name:</span> {lookupResult.data.name}</p>
                      <p><span className="font-semibold">Patient ID:</span> <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs font-mono">{lookupResult.data.id}</code></p>
                      <p><span className="font-semibold">Language:</span> {lookupResult.data.preferred_language?.toUpperCase()}</p>
                    </div>
                    <p className="text-xs text-slate-500 mt-2">Use this Patient ID when booking via the voice agent.</p>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-700 flex items-center gap-2">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    No patient found with that phone number. Switch to &ldquo;Register New&rdquo; to create one.
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const SuccessModal = ({ patient, onClose }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 text-center">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
        style={{ background: "linear-gradient(135deg, #10b981, #059669)" }}>
        <CheckCircle className="w-7 h-7 text-white" />
      </div>
      <h3 className="font-bold text-slate-900 text-base mb-1">Patient Registered!</h3>
      <p className="text-sm text-slate-500 mb-4">Share this Patient ID with the voice agent to book appointments.</p>
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 mb-4">
        <p className="text-xs text-slate-500 mb-1">Patient ID</p>
        <p className="font-mono text-sm font-bold text-slate-900 break-all">{patient?.id}</p>
        <p className="text-xs text-slate-400 mt-1">{patient?.name} · {patient?.phone}</p>
      </div>
      <button onClick={onClose}
        className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
        style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
        Done
      </button>
    </div>
  </div>
);

export const AppointmentsPage = () => {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [registeredPatient, setRegisteredPatient] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const res = await apiFetch("/api/appointments");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setAppointments(data.appointments || data || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = appointments
    .filter((a) => filter === "all" || a.status === filter)
    .filter((a) => !search || a.patient_name?.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex flex-col h-full" style={{ background: "#f8fafc" }}>
      {showModal && (
        <RegisterPatientModal
          onClose={() => setShowModal(false)}
          onSuccess={(patient) => { setShowModal(false); setRegisteredPatient(patient); }}
        />
      )}
      {registeredPatient && (
        <SuccessModal patient={registeredPatient} onClose={() => setRegisteredPatient(null)} />
      )}

      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #10b981, #059669)" }}>
              <Calendar className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900">Appointments</h1>
              <p className="text-xs text-slate-500">Manage patient appointments</p>
            </div>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white shadow-sm transition-all hover:opacity-90"
            style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Register Patient</span>
          </button>
        </div>

        {/* Search + tabs */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search patients…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:bg-white transition-all"
            />
          </div>
          <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100">
            {TABS.map((tab) => (
              <button key={tab.key} onClick={() => setFilter(tab.key)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200"
                style={filter === tab.key
                  ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)", color: "white" }
                  : { background: "transparent", color: "#64748b" }
                }>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" style={{ color: "#3b82f6" }} />
              <p className="text-sm text-slate-500">Loading appointments…</p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-600 text-sm flex items-center gap-2">
            <XCircle className="w-4 h-4 flex-shrink-0" />
            Failed to load appointments: {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: "linear-gradient(135deg, #f1f5f9, #e2e8f0)" }}>
              <Calendar className="w-8 h-8 text-slate-400" />
            </div>
            <p className="font-semibold text-slate-600">No appointments found</p>
            <p className="text-sm text-slate-400 mt-1">
              {search ? "Try a different search term" : "Appointments booked via the voice agent will appear here"}
            </p>
            <button onClick={() => setShowModal(true)}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}>
              <Plus className="w-4 h-4" /> Register a Patient
            </button>
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="space-y-3">
            <p className="text-xs text-slate-400 font-medium mb-2">{filtered.length} appointment{filtered.length !== 1 ? "s" : ""}</p>
            {filtered.map((appt) => (
              <AppointmentCard key={appt.id} appointment={appt} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};