import { organizerRules } from './organizerRules';

const rules = [organizerRules];

export function detectIntent(text) {
  const normalized = String(text || '').trim();
  if (!normalized) return null;

  for (const rule of rules) {
    if (!rule.matches(normalized)) continue;
    const params = rule.extractParams(normalized);
    const mode = rule.detectMode(normalized);
    return {
      intent: rule.intent,
      mode,
      params,
      confidence: 0.7,
    };
  }

  return null;
}
