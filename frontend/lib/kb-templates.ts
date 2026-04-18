/**
 * Plantilla BlockNote con la estructura de documentación recomendada.
 * Estructura inspirada en el sistema v1: 4 secciones estándar.
 */
export const DOCUMENTATION_TEMPLATE: Array<Record<string, unknown>> = [
  {
    type: "heading",
    props: { level: 2 },
    content: [{ type: "text", text: "Descripción del problema", styles: {} }],
    children: [],
  },
  {
    type: "paragraph",
    props: {},
    content: [
      {
        type: "text",
        text: "Describe brevemente el problema o situación que este artículo aborda.",
        styles: {},
      },
    ],
    children: [],
  },
  {
    type: "heading",
    props: { level: 2 },
    content: [{ type: "text", text: "Diagnóstico", styles: {} }],
    children: [],
  },
  {
    type: "paragraph",
    props: {},
    content: [
      {
        type: "text",
        text: "Pasos de análisis o investigación realizados.",
        styles: {},
      },
    ],
    children: [],
  },
  {
    type: "heading",
    props: { level: 2 },
    content: [{ type: "text", text: "Solución aplicada", styles: {} }],
    children: [],
  },
  {
    type: "paragraph",
    props: {},
    content: [
      {
        type: "text",
        text: "Acciones específicas ejecutadas para resolver el problema.",
        styles: {},
      },
    ],
    children: [],
  },
  {
    type: "heading",
    props: { level: 2 },
    content: [{ type: "text", text: "Notas adicionales", styles: {} }],
    children: [],
  },
  {
    type: "paragraph",
    props: {},
    content: [
      {
        type: "text",
        text: "Referencias, advertencias o información complementaria.",
        styles: {},
      },
    ],
    children: [],
  },
];

export function templateToPlainText(): string {
  return [
    "Descripción del problema",
    "Describe brevemente el problema o situación que este artículo aborda.",
    "Diagnóstico",
    "Pasos de análisis o investigación realizados.",
    "Solución aplicada",
    "Acciones específicas ejecutadas para resolver el problema.",
    "Notas adicionales",
    "Referencias, advertencias o información complementaria.",
  ].join("\n\n");
}
