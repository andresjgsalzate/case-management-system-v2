// Ruta /archive/[id] — muestra el mismo detalle de caso que /cases/[id].
// Al vivir bajo /archive, el sidebar resalta "Archivo" y usePathname()
// retorna "/archive/..." haciendo que fromArchive = true automáticamente.
export { default } from "@/app/(dashboard)/cases/[id]/page";
