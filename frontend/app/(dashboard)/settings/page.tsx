import Link from "next/link";
import { Users, Shield, Clock, Zap, Bell, Tag } from "lucide-react";

const SETTINGS_SECTIONS = [
  {
    href: "/settings/users",
    icon: Users,
    title: "Usuarios",
    description: "Gestiona cuentas y accesos al sistema",
  },
  {
    href: "/settings/roles",
    icon: Shield,
    title: "Roles y permisos",
    description: "Configura roles y sus permisos por módulo",
  },
  {
    href: "/settings/sla",
    icon: Clock,
    title: "Políticas SLA",
    description: "Define plazos de respuesta y resolución",
  },
  {
    href: "/settings/automation",
    icon: Zap,
    title: "Automatización",
    description: "Reglas de automatización y acciones",
  },
  {
    href: "/dispositions",
    icon: Tag,
    title: "Disposiciones",
    description: "Respuestas y plantillas predefinidas",
  },
  {
    href: "/settings/notifications",
    icon: Bell,
    title: "Notificaciones",
    description: "Configuración de alertas y emails",
  },
];

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Configuración</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Administra usuarios, roles, SLA y más.
        </p>
      </div>

      <div className="grid gap-3">
        {SETTINGS_SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <Link
              key={section.href}
              href={section.href}
              className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all duration-150"
            >
              <div className="h-10 w-10 rounded-md bg-muted flex items-center justify-center shrink-0">
                <Icon className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{section.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{section.description}</p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
