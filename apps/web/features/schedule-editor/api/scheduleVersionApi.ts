import { apiPost } from "@/lib/api/client";
import type { ScheduleVersion, Uuid } from "../types";

export type PublishValidationIssue = {
  code: string;
  message: string;
  severity: string;
};

export type PublishValidationResult = {
  schedule_version_id: Uuid;
  can_publish: boolean;
  issues: PublishValidationIssue[];
};

export type ScheduleVersionActionResult = {
  schedule_version: ScheduleVersion;
  validation: PublishValidationResult | null;
};

export function validatePublish(
  scheduleVersionId: Uuid,
  expectedRevision: number
): Promise<PublishValidationResult> {
  return apiPost<PublishValidationResult>(
    `/api/schedule-versions/${scheduleVersionId}/validate-publish`,
    { expected_revision: expectedRevision }
  );
}

export function approveScheduleVersion(
  scheduleVersionId: Uuid
): Promise<ScheduleVersionActionResult> {
  return apiPost<ScheduleVersionActionResult>(
    `/api/schedule-versions/${scheduleVersionId}/approve`,
    {}
  );
}

export function publishScheduleVersion(
  scheduleVersionId: Uuid,
  expectedRevision: number
): Promise<ScheduleVersionActionResult> {
  return apiPost<ScheduleVersionActionResult>(
    `/api/schedule-versions/${scheduleVersionId}/publish`,
    { expected_revision: expectedRevision }
  );
}

export function archiveScheduleVersion(
  scheduleVersionId: Uuid
): Promise<ScheduleVersionActionResult> {
  return apiPost<ScheduleVersionActionResult>(
    `/api/schedule-versions/${scheduleVersionId}/archive`,
    {}
  );
}

export function duplicateScheduleVersion(
  scheduleVersionId: Uuid
): Promise<ScheduleVersionActionResult> {
  return apiPost<ScheduleVersionActionResult>(
    `/api/schedule-versions/${scheduleVersionId}/duplicate`,
    {}
  );
}
