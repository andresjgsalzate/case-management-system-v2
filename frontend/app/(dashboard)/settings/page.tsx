import Link from "next/link";
import {
  Users, Shield, Clock, Zap, Bell, Tag,
  AlertTriangle, Flag, Layers, Globe, Hash,
} from "lucide-react";

const SETTINGS_SECTIONS = [
  {
    group: "Usuarios y acceso",
    items: [
      { href: "/settings/users",  icon: Users,  title: "Usuarios",        description: "Gestiona cuentas y accesos al sistema" },
      { href: "/settings/roles",  icon: Shield, title: "Roles y permisos", description: "Configura roles y sus permisos por módulo" },
    ],
  },
  {
    group: "Casos",
    items: [
      { href: "/settings/priorities",   icon: AlertTriangle, title: "Prioridades",         description: "Niveles de urgencia para los casos" },
      { href: "/settings/statuses",     icon: Flag,          title: "Estados",             description: "Flujo de estados y transiciones permitidas" },
      { href: "/settings/applications", icon: Layers,        title: "Aplicaciones",        description: "Sistemas o productos origen de los casos" },
      { href: "/settings/origins",      icon: Globe,         title: "Orígenes",            description: "Canales de entrada: email, chat, teléfono…" },
      { href: "/settings/case-numbers", icon: Hash,          title: "Numeración de casos", description: "Prefijo y formato de los números de caso" },
    ],
  },
  {
    group: "Operaciones",
    items: [
      { href: "/settings/sla",          icon: Clock, title: "Políticas SLA",   description: "Define plazos de respuesta y resolución" },
      { href: "/settings/automation",   icon: Zap,   title: "Automatización",  description: "Reglas de automatización y acciones" },
      { href: "/dispositions",          icon: Tag,   title: "Disposiciones",   description: "Respuestas y plantillas predefinidas" },
      { href: "/settings/notifications",icon: Bell,  title: "Notificaciones",  description: "Configuración de alertas y emails" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-7 max-w-2xl">
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
          <div className="grid gap-2">
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 hover:border-primary/40 hover:shadow-sm transition-all duration-150 group"
                >
                  <div className="h-9 w-9 rounded-md bg-muted flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                    <Icon className="h-4.5 w-4.5 text-muted-foreground group-hover:text-primary transition-colors" />
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
