const positionNames: Record<string, string> = {
  B: "バリ",
  C: "キャッシャー",
  F: "フロア",
  S: "サブ",
  M: "入金"
};

export function positionDisplayName(code: string, fallbackName?: string | null) {
  return positionNames[code] ?? fallbackName ?? code;
}

export function positionDisplayLabel(code: string, fallbackName?: string | null) {
  return `${code} / ${positionDisplayName(code, fallbackName)}`;
}
