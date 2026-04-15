import Link from "next/link";
import {
  Users, Shield, Clock, Zap, Bell, Tag,
  AlertTriangle, Flag, Layers, Globe, Hash, LayoutGrid, Building2, Mail,
} from "lucide-react";

const SETTINGS_SECTIONS = [
  {
    group: "Usuarios y acceso",
    items: [
      { href: "/settings/users",   icon: Users,     color: "text-indigo-500", bg: "bg-indigo-50 dark:bg-indigo-950/40",  title: "Usuarios",         description: "Gestiona cuentas y accesos al sistema" },
      { href: "/settings/roles",   icon: Shield,    color: "text-violet-500", bg: "bg-violet-50 dark:bg-violet-950/40",  title: "Roles y permisos", description: "Configura roles y sus permisos por módulo" },
      { href: "/settings/teams",   icon: Users,     color: "text-blue-500",   bg: "bg-blue-50 dark:bg-blue-950/40",      title: "Equipos",          description: "Crea equipos y gestiona sus miembros" },
      { href: "/settings/tenants", icon: Building2, color: "text-slate-500",  bg: "bg-slate-100 dark:bg-slate-800/40",   title: "Tenants",          description: "Organizaciones con datos aislados dentro del sistema" },
    ],
  },
  {
    group: "Casos",
    items: [
      { href: "/settings/statuses",       icon: Flag,          color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950/40",  title: "Estados",                  description: "Flujo de estados y transiciones permitidas" },
      { href: "/settings/priorities",     icon: AlertTriangle, color: "text-amber-500",   bg: "bg-amber-50 dark:bg-amber-950/40",      title: "Prioridades",              description: "Niveles de urgencia para los casos" },
      { href: "/settings/applications",   icon: Layers,        color: "text-teal-500",    bg: "bg-teal-50 dark:bg-teal-950/40",        title: "Aplicaciones",             description: "Sistemas o productos origen de los casos" },
      { href: "/settings/origins",        icon: Globe,         color: "text-cyan-500",    bg: "bg-cyan-50 dark:bg-cyan-950/40",        title: "Orígenes",                 description: "Canales de entrada: email, chat, teléfono…" },
      { href: "/settings/classification", icon: LayoutGrid,    color: "text-purple-500",  bg: "bg-purple-50 dark:bg-purple-950/40",    title: "Rúbrica de clasificación", description: "Criterios y puntajes para clasificar complejidad de casos" },
      { href: "/settings/case-numbers",   icon: Hash,          color: "text-slate-500",   bg: "bg-slate-100 dark:bg-slate-800/40",     title: "Numeración de casos",      description: "Prefijo y formato de los números de caso" },
    ],
  },
  {
    group: "Operaciones",
    items: [
      { href: "/settings/sla",           icon: Clock, color: "text-red-500",    bg: "bg-red-50 dark:bg-red-950/40",       title: "Políticas SLA",  description: "Define plazos de respuesta y resolución" },
      { href: "/settings/notifications", icon: Bell,  color: "text-orange-500", bg: "bg-orange-50 dark:bg-orange-950/40", title: "Notificaciones", description: "Configuración de alertas y emails" },
      { href: "/settings/email",         icon: Mail,  color: "text-sky-500",    bg: "bg-sky-50 dark:bg-sky-950/40",       title: "Email",          description: "Configuración SMTP y plantillas de correo" },
      { href: "/settings/automation",    icon: Zap,   color: "text-yellow-500", bg: "bg-yellow-50 dark:bg-yellow-950/40", title: "Automatización", description: "Reglas de automatización y acciones" },
      { href: "/dispositions",           icon: Tag,   color: "text-cyan-500",   bg: "bg-cyan-50 dark:bg-cyan-950/40",     title: "Disposiciones",  description: "Respuestas y plantillas predefinidas" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-7">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Configuración</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Administra usuarios, roles, estados, prioridades, SLA y más.
        </p>
      </div>

      {SETTINGS_SECTIONS.map((section) => (
        <div key={section.group}>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">
            {section.group}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 hover:border-primary/40 hover:shadow-sm transition-all duration-150 group"
                >
                  <div className={`h-9 w-9 rounded-md flex items-center justify-center shrink-0 transition-colors ${item.bg}`}>
                    <Icon className={`h-[18px] w-[18px] ${item.color}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
