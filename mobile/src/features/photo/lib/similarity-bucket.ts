/** Map raw CLIP similarity (0..1) to an honest bucket label + gauge tier.
 * Raw cosine reads deceptively low (S11 §2) so we never show the number.
 * Thresholds are tunable; calibrate against labelled pairs later. */
export type SimilarityLabel = "매우 닮음" | "닮음" | "비슷함";

export interface SimilarityBucket {
  label: SimilarityLabel;
  tier: number; // gauge fill fraction 0..1
}

export function bucketFor(similarity: number): SimilarityBucket {
  if (similarity >= 0.75) return { label: "매우 닮음", tier: 1 };
  if (similarity >= 0.65) return { label: "닮음", tier: 0.66 };
  return { label: "비슷함", tier: 0.33 };
}
