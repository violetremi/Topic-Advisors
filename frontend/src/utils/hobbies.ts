/** 兴趣爱好标签：统一解析 / 序列化（兼容旧的自由文本） */

/** 人员自带企业标签名，不可作为兴趣录入 */
export const COMPANY_HOBBY_TAB = '企业';

export function parseHobbyTags(hobbies: string | string[] | null | undefined): string[] {
  if (!hobbies) return [];
  if (Array.isArray(hobbies)) {
    return dedupe(hobbies.map((t) => String(t).trim()).filter(Boolean));
  }
  const raw = hobbies.trim();
  if (!raw) return [];
  if (raw.startsWith('[')) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return dedupe(parsed.map((t) => String(t).trim()).filter(Boolean));
      }
    } catch {
      /* fall through */
    }
  }
  // 新格式用逗号连接；旧数据兼容空格 / 中英文标点分隔
  return dedupe(raw.split(/[,，;；、|\s]+/).map((t) => t.trim()).filter(Boolean));
}

export function serializeHobbyTags(tags: string[] | string | null | undefined): string {
  return parseHobbyTags(tags as any).join(',');
}

function dedupe(tags: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of tags) {
    if (t === COMPANY_HOBBY_TAB) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}
