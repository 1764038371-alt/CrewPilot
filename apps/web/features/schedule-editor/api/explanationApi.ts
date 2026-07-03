import { apiGet } from "@/lib/api/client";
import type { ShiftSegmentExplanation, Uuid } from "../types";

export function getShiftSegmentExplanation(segmentId: Uuid): Promise<ShiftSegmentExplanation> {
  return apiGet<ShiftSegmentExplanation>(`/api/shift-segments/${segmentId}/explanation`);
}
