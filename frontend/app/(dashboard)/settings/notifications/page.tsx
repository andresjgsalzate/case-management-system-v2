"use client";

import { useState } from "react";
import { Bell, Mail, Monitor, Save } from "lucide-react";

interface NotifSetting {
  id: string;
  label: string;
  description: string;
  email: boolean;
  inApp: boolean;
}

const DEFAULT_SETTINGS: NotifSetting[] = [
  { id: "case_assigned",      label: "Caso asignado",         description: "Cuando te asignan un caso",                  email: true,  inApp: true  },
  { id: "case_commented",     label: "Nuevo comentario",       description: "Cuando alguien comenta en tus casos",        email: false, inApp: true  },
  { id: "sla_breached",       label: "SLA incumplido",         description: "Cuando un caso supera el plazo de SLA",     email: true,  inApp: true  },
  { id: "case_status_change", label: "Cambio de estado",       description: "Cuando cambia el estado de un caso tuyo",   email: false, inApp: true  },
  { id: "mention",            label: "Mención",                description: "Cuando alguien te menciona en una nota",    email: true,  inApp: true  },
  { id: "kb_review",          label: "Revisión de artículo KB", description: "Cuando tu artículo entra en revisión",     email: false, inApp: true  },
];

export default function NotificationsSettingsPage() {
  const [settings, setSettings] = useState<NotifSetting[]>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  function toggle(id: string, channel: "email" | "inApp") {
    setSettings((prev) =>
      prev.map((s) => (s.id === id ? { ...s, [channel]: !s[channel] } : s))
    );
    setSaved(false);
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Notificaciones</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Configura qué eventos generan notificaciones y por qué canal
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="grid grid-cols-[1fr_auto_auto] items-center px-4 py-2 border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground uppercase tracking-wider gap-6">
          <span>Evento</span>
          <span className="flex items-center gap-1 w-16 justify-center"><Mail className="h-3.5 w-3.5" /> Email</span>
          <span className="flex items-center gap-1 w-16 justify-center"><Monitor className="h-3.5 w-3.5" /> App</span>
        </div>

        {settings.map((setting, idx) => (
          <div
            key={setting.id}
            className={`grid grid-cols-[1fr_auto_auto] items-center px-4 py-3.5 gap-6 ${idx !== settings.length - 1 ? "border-b border-border" : ""}`}
          >
            <div>
              <p className="text-sm font-medium text-foreground">{setting.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{setting.description}</p>
            </div>

            {(["email", "inApp"] as const).map((channel) => (
              <div key={channel} className="flex justify-center w-16">
                <button
                  type="button"
                  onClick={() => toggle(setting.id, channel)}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-150 focus:outline-none ${
                    setting[channel]
                      ? "bg-primary"
                      : "bg-muted-foreground/30"
                  }`}
                  role="switch"
                  aria-checked={setting[channel]}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-150 ${
                      setting[channel] ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Save className="h-4 w-4" />
          Guardar preferencias
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-green-600 dark:text-green-400">
            <Bell className="h-4 w-4" />
            Preferencias guardadas
          </span>
        )}
      </div>
    </div>
  );
}
