export function normalizeChallengeFeatures(challenge) {
  if (!challenge) return null;
  const normalized = {};
  for (const [key, value] of Object.entries(challenge)) {
    if (value !== undefined && value !== null) {
      normalized[key] = value;
    }
  }
  return Object.keys(normalized).length ? normalized : null;
}
