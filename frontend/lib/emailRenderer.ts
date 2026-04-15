// frontend/lib/emailRenderer.ts
import type { Block } from "@/hooks/useEmailConfig";

export const SCOPE_OPTIONS = [
  { value: "global",              label: "Global (todos los eventos)" },
  { value: "case.assigned",       label: "Caso asignado" },
  { value: "case.status_changed", label: "Cambio de estado" },
  { value: "case.updated",        label: "Caso actualizado" },
  { value: "sla.breached",        label: "SLA vencido" },
  { value: "kb.review_requested", label: "Revisión KB" },
  { value: "mention",             label: "Mención" },
];

export const SCOPE_VARIABLES: Record<string, { name: string; description: string }[]> = {
  global:               [{ name: "full_name", description: "Nombre del destinatario" }, { name: "email", description: "Email del destinatario" }],
  "case.assigned":      [{ name: "case_number", description: "Número del caso" }, { name: "case_title", description: "Título" }, { name: "assigned_by", description: "Asignado por" }],
  "case.status_changed":[{ name: "case_number", description: "Número del caso" }, { name: "case_title", description: "Título" }, { name: "from_status", description: "Estado anterior" }, { name: "to_status", description: "Nuevo estado" }],
  "case.updated":       [{ name: "case_number", description: "Número del caso" }, { name: "case_title", description: "Título" }, { name: "updated_by", description: "Modificado por" }],
  "sla.breached":       [{ name: "case_number", description: "Número del caso" }, { name: "case_title", description: "Título del caso" }],
  "kb.review_requested":[{ name: "article_title", description: "Título del artículo" }, { name: "requested_by", description: "Solicitado por" }],
  mention:              [{ name: "full_name", description: "Nombre mencionado" }, { name: "case_number", description: "Número del caso" }],
};

export const BLOCK_TYPES: { type: Block["type"]; label: string; description: string }[] = [
  { type: "header",      label: "Encabezado",    description: "Logo + título sobre fondo de color" },
  { type: "hero",        label: "Hero",           description: "Título grande y subtítulo centrado" },
  { type: "body",        label: "Cuerpo",         description: "Texto con soporte de variables" },
  { type: "text",        label: "Texto libre",    description: "Bloque de texto multilínea" },
  { type: "button",      label: "Botón CTA",      description: "Enlace con estilo de botón" },
  { type: "divider",     label: "Separador",      description: "Línea horizontal" },
  { type: "footer",      label: "Pie de página",  description: "Texto legal y créditos" },
  { type: "data_table",  label: "Tabla de datos", description: "Filas etiqueta/valor" },
  { type: "alert",       label: "Alerta",         description: "Mensaje de info/warning/error/success" },
  { type: "image",       label: "Imagen",         description: "Imagen con URL" },
  { type: "two_columns", label: "Dos columnas",   description: "Layout de dos columnas" },
];

export function defaultProps(type: Block["type"]): Record<string, unknown> {
  switch (type) {
    case "header":      return { logo_url: "", bg_color: "#1e40af", title: "Encabezado" };
    case "hero":        return { title: "Título principal", subtitle: "", bg_color: "#eff6ff", text_color: "#1e40af" };
    case "body":        return { content: "Escribe el contenido aquí…" };
    case "text":        return { content: "" };
    case "button":      return { label: "Ver caso", url: "#", bg_color: "#1e40af", text_color: "#ffffff" };
    case "divider":     return { color: "#e5e7eb", thickness: 1 };
    case "footer":      return { content: "© 2026 CaseManager. Todos los derechos reservados.", bg_color: "#f9fafb", text_color: "#6b7280" };
    case "data_table":  return { rows: [{ label: "Caso", value: "{case_number}" }] };
    case "alert":       return { alert_type: "info", message: "Mensaje de alerta" };
    case "image":       return { url: "", alt: "", width: "100%" };
    case "two_columns": return { left: [], right: [] };
    default:            return {};
  }
}

function fmt(text: string, vars: Record<string, string>): string {
  return text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? `{${k}}`);
}

function renderBlock(block: Block, vars: Record<string, string>): string {
  const { type, props } = block;
  const p = props as Record<string, string>;

  switch (type) {
    case "header": {
      const bg = p.bg_color || "#1e40af";
      const title = fmt(p.title || "", vars);
      const logo = p.logo_url ? `<img src="${p.logo_url}" alt="Logo" style="max-height:40px;display:block;margin-bottom:8px;">` : "";
      const t = title ? `<h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;">${title}</h1>` : "";
      return `<tr><td style="background:${bg};padding:24px 32px;">${logo}${t}</td></tr>`;
    }
    case "hero": {
      const bg = p.bg_color || "#eff6ff", tc = p.text_color || "#1e40af";
      const title = fmt(p.title || "", vars), sub = fmt(p.subtitle || "", vars);
      return `<tr><td style="background:${bg};padding:32px;text-align:center;">${title ? `<h2 style="margin:0 0 8px;color:${tc};font-size:24px;font-weight:700;">${title}</h2>` : ""}${sub ? `<p style="margin:0;color:${tc};font-size:15px;opacity:.8;">${sub}</p>` : ""}</td></tr>`;
    }
    case "body":
    case "text": {
      const content = fmt(p.content || "", vars).replace(/\n/g, "<br>");
      return `<tr><td style="padding:24px 32px;color:#374151;font-size:15px;line-height:1.6;">${content}</td></tr>`;
    }
    case "button": {
      const bg = p.bg_color || "#1e40af", tc = p.text_color || "#fff";
      return `<tr><td style="padding:16px 32px;text-align:center;"><a href="${fmt(p.url||"#",vars)}" style="display:inline-block;background:${bg};color:${tc};padding:12px 28px;border-radius:6px;text-decoration:none;font-size:15px;font-weight:600;">${fmt(p.label||"Ver",vars)}</a></td></tr>`;
    }
    case "divider":
      return `<tr><td style="padding:0 32px;"><hr style="border:none;border-top:${p.thickness||1}px solid ${p.color||"#e5e7eb"};margin:8px 0;"></td></tr>`;
    case "footer": {
      const bg = p.bg_color || "#f9fafb", tc = p.text_color || "#6b7280";
      return `<tr><td style="background:${bg};padding:16px 32px;text-align:center;color:${tc};font-size:12px;">${fmt(p.content||"",vars)}</td></tr>`;
    }
    case "data_table": {
      const rows = (props.rows as { label: string; value: string }[]) || [];
      const rowsHtml = rows.map(r => `<tr style="border-bottom:1px solid #e5e7eb;"><td style="color:#6b7280;font-size:13px;padding:8px 4px;width:40%;">${r.label}</td><td style="color:#111827;font-size:13px;font-weight:500;padding:8px 4px;">${fmt(String(r.value),vars)}</td></tr>`).join("");
      return `<tr><td style="padding:16px 32px;"><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">${rowsHtml}</table></td></tr>`;
    }
    case "alert": {
      const colorMap: Record<string, [string,string,string]> = {
        info: ["#eff6ff","#1e40af","#bfdbfe"], warning: ["#fffbeb","#92400e","#fde68a"],
        error: ["#fef2f2","#991b1b","#fecaca"], success: ["#f0fdf4","#166534","#bbf7d0"],
      };
      const [bg, tc, border] = colorMap[p.alert_type || "info"] || colorMap.info;
      return `<tr><td style="padding:16px 32px;"><div style="background:${bg};border:1px solid ${border};border-radius:6px;padding:12px 16px;color:${tc};font-size:14px;">${fmt(p.message||"",vars)}</div></td></tr>`;
    }
    case "image":
      return p.url ? `<tr><td style="padding:16px 32px;text-align:center;"><img src="${p.url}" alt="${p.alt||""}" width="${p.width||"100%"}" style="max-width:100%;display:block;margin:0 auto;"></td></tr>` : "";
    case "two_columns": {
      const left = ((props.left as Block[]) || []).map(b => renderBlock(b, vars)).join("");
      const right = ((props.right as Block[]) || []).map(b => renderBlock(b, vars)).join("");
      return `<tr><td style="padding:16px 32px;"><table width="100%" cellpadding="0" cellspacing="0"><tr><td width="48%" valign="top"><table width="100%">${left}</table></td><td width="4%"></td><td width="48%" valign="top"><table width="100%">${right}</table></td></tr></table></td></tr>`;
    }
    default: return "";
  }
}

export function renderEmailPreview(blocks: Block[], variables: Record<string, string> = {}): string {
  const inner = blocks.map(b => renderBlock(b, variables)).join("");
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 0;"><table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);">${inner}</table></td></tr></table></body></html>`;
}
