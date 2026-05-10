import type { KBArticle } from "@/lib/types";

export interface Filter {
  term: string;
  exact: boolean;
}

export type MatchedField = "T" | "C" | "E" | "CA";

export interface ScoredArticle {
  article: KBArticle;
  score: number | null;
  matched: MatchedField[];
}

const normalize = (s: string): string =>
  // NFD decomposes letters; strip combining diacritical marks (U+0300–U+036F)
  s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

const SCORE_THRESHOLD = 30;

export function searchArticles(
  articles: KBArticle[],
  filters: Filter[],
): ScoredArticle[] {
  if (filters.length === 0) {
    return articles.map((a) => ({ article: a, score: null, matched: [] }));
  }

  const scored: ScoredArticle[] = [];
  for (const a of articles) {
    const caseRefs = a.case_refs ?? [];
    const fieldsRaw = {
      T: a.title,
      C: a.content_text,
      E: (a.tags ?? []).map((t) => t.name).join(" "),
      CA: caseRefs.map((c) => `${c.case_number} ${c.case_title}`).join(" "),
    };
    const fieldsNorm = {
      T: normalize(fieldsRaw.T),
      C: normalize(fieldsRaw.C),
      E: normalize(fieldsRaw.E),
      CA: normalize(fieldsRaw.CA),
    };
    const haystackNorm = Object.values(fieldsNorm).join(" ");
    const haystackRaw = Object.values(fieldsRaw).join(" ");

    let passes = true;
    for (const f of filters) {
      if (f.exact) {
        if (!haystackRaw.includes(f.term)) {
          passes = false;
          break;
        }
      } else {
        const words = normalize(f.term).split(/\s+/).filter(Boolean);
        if (!words.every((w) => haystackNorm.includes(w))) {
          passes = false;
          break;
        }
      }
    }
    if (!passes) continue;

    const virtualQuery = filters.map((f) => f.term).join(" ");
    const queryWords = normalize(virtualQuery).split(/\s+/).filter(Boolean);
    if (queryWords.length === 0) {
      scored.push({ article: a, score: 100, matched: [] });
      continue;
    }

    const matchedCount = queryWords.filter((w) => haystackNorm.includes(w)).length;
    const base = (matchedCount / queryWords.length) * 70;
    const bonusExactPhrase = haystackNorm.includes(normalize(virtualQuery)) ? 20 : 0;
    const bonusTitleMatch = queryWords.some((w) => fieldsNorm.T.includes(w)) ? 10 : 0;
    const score = Math.min(100, base + bonusExactPhrase + bonusTitleMatch);

    if (score < SCORE_THRESHOLD) continue;

    const matched: MatchedField[] = [];
    if (queryWords.some((w) => fieldsNorm.T.includes(w))) matched.push("T");
    if (queryWords.some((w) => fieldsNorm.C.includes(w))) matched.push("C");
    if (queryWords.some((w) => fieldsNorm.E.includes(w))) matched.push("E");
    if (queryWords.some((w) => fieldsNorm.CA.includes(w))) matched.push("CA");

    scored.push({ article: a, score, matched });
  }

  scored.sort((x, y) => (y.score ?? 0) - (x.score ?? 0));
  return scored;
}

export function scoreBand(
  score: number,
): "excelente" | "muy-bueno" | "bueno" | "parcial" {
  if (score >= 90) return "excelente";
  if (score >= 70) return "muy-bueno";
  if (score >= 50) return "bueno";
  return "parcial";
}
