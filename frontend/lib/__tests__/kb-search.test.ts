import { describe, it, expect } from "vitest";
import { searchArticles, scoreBand, type Filter } from "@/lib/kb-search";
import type { KBArticle } from "@/lib/types";

function makeArticle(overrides: Partial<KBArticle> = {}): KBArticle {
  return {
    id: "id-" + Math.random().toString(36).slice(2),
    title: "",
    content_json: { blocks: [] },
    content_text: "",
    status: "published",
    version: 1,
    created_by_id: "u1",
    created_by_name: "User",
    view_count: 0,
    helpful_count: 0,
    not_helpful_count: 0,
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
    document_type_id: null,
    visibility: "public",
    pending_visibility: null,
    document_type: null,
    tags: [],
    case_refs: [],
    ...overrides,
  };
}

describe("searchArticles", () => {
  it("returns all articles with score=null when filters are empty", () => {
    const articles = [
      makeArticle({ title: "Migración" }),
      makeArticle({ title: "Otro" }),
    ];
    const result = searchArticles(articles, []);
    expect(result).toHaveLength(2);
    expect(result.every((r) => r.score === null)).toBe(true);
    expect(result.every((r) => r.matched.length === 0)).toBe(true);
  });

  it("matches title with bonuses → 90-100% band", () => {
    const a = makeArticle({ title: "Migración del servidor" });
    const filters: Filter[] = [{ term: "migración", exact: false }];
    const result = searchArticles([a], filters);
    expect(result).toHaveLength(1);
    expect(result[0].score).toBeGreaterThanOrEqual(90);
    expect(result[0].matched).toContain("T");
  });

  it("ignores accents in non-exact mode", () => {
    const a = makeArticle({ title: "Migración" });
    const result = searchArticles([a], [{ term: "migracion", exact: false }]);
    expect(result).toHaveLength(1);
    expect(result[0].score).not.toBeNull();
  });

  it("ANDs chained filters — both must match", () => {
    const a = makeArticle({ title: "Configuración del servidor nginx" });
    const filters: Filter[] = [
      { term: "configuracion", exact: false },
      { term: "nginx", exact: false },
    ];
    const result = searchArticles([a, makeArticle({ title: "Solo nginx" })], filters);
    expect(result).toHaveLength(1);
    expect(result[0].article.id).toBe(a.id);
  });

  it("respects case + accents in exact mode", () => {
    const a = makeArticle({ title: "Pruebas1 manual" });
    expect(
      searchArticles([a], [{ term: "Pruebas1", exact: true }]),
    ).toHaveLength(1);
    expect(
      searchArticles([a], [{ term: "pruebas1", exact: true }]),
    ).toHaveLength(0);
    expect(
      searchArticles([a], [{ term: "Migracion", exact: true }]),
    ).toHaveLength(0);
  });

  it("mixes exact + normal filters in a single chain", () => {
    const a = makeArticle({
      title: "Pruebas1 servidor",
      content_text: "configuracion avanzada",
    });
    const filters: Filter[] = [
      { term: "Pruebas1", exact: true },
      { term: "configuración", exact: false },
    ];
    const result = searchArticles([a], filters);
    expect(result).toHaveLength(1);
    expect(result[0].score).not.toBeNull();
  });

  it("matches tag → indicator E only", () => {
    const a = makeArticle({
      title: "Doc cualquiera",
      content_text: "lorem ipsum",
      tags: [{ id: "t1", name: "redes", slug: "redes" }],
    });
    const result = searchArticles([a], [{ term: "redes", exact: false }]);
    expect(result).toHaveLength(1);
    expect(result[0].matched).toEqual(["E"]);
  });

  it("matches case_refs → indicator CA", () => {
    const a = makeArticle({
      title: "Doc",
      case_refs: [{ case_number: "CASE-001", case_title: "Bug crítico" }],
    });
    const result = searchArticles([a], [{ term: "CASE-001", exact: false }]);
    expect(result).toHaveLength(1);
    expect(result[0].matched).toContain("CA");
  });

  it("drops articles below score threshold of 30", () => {
    const a = makeArticle({
      title: "Sin relación",
      content_text: "una palabra suelta xyz",
    });
    const result = searchArticles(
      [a],
      [{ term: "una palabra inexistente", exact: false }],
    );
    expect(result).toHaveLength(0);
  });

  it("scoreBand maps numbers to band names", () => {
    expect(scoreBand(95)).toBe("excelente");
    expect(scoreBand(80)).toBe("muy-bueno");
    expect(scoreBand(60)).toBe("bueno");
    expect(scoreBand(35)).toBe("parcial");
  });
});
