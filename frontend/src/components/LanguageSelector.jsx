import { SUPPORTED_LANGUAGES } from "../types/index.js";

export const LanguageSelector = ({ selectedLanguage, onLanguageChange, disabled }) => (
  <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100">
    {SUPPORTED_LANGUAGES.map((lang) => {
      const active = selectedLanguage === lang.code;
      return (
        <button
          key={lang.code}
          onClick={() => !disabled && onLanguageChange(lang.code)}
          disabled={disabled}
          title={lang.name}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
            disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
          }`}
          style={active
            ? { background: "linear-gradient(135deg, #3b82f6, #6366f1)", color: "white", boxShadow: "0 2px 8px rgba(59,130,246,0.35)" }
            : { background: "transparent", color: "#64748b" }
          }
        >
          <span className="text-sm leading-none">{lang.flag}</span>
          <span className="hidden sm:inline">{lang.code.toUpperCase()}</span>
        </button>
      );
    })}
  </div>
);