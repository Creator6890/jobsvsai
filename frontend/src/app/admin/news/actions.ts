"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { adminNewsMutate, type AdminNewsArticle } from "@/lib/api";

// Server actions only. Admin credentials live in the server environment and are attached by
// api.ts; nothing here reaches the browser.

function textField(form: FormData, name: string): string {
  return String(form.get(name) ?? "").trim();
}

function listField(form: FormData, name: string): string[] {
  return textField(form, name).split(",").map((item) => item.trim()).filter(Boolean);
}

function draftPayload(form: FormData) {
  return {
    headline: textField(form, "headline"),
    whatHappened: textField(form, "whatHappened"),
    whyItMattersForJobs: textField(form, "whyItMattersForJobs"),
    tags: listField(form, "tags"),
    jobAreas: listField(form, "jobAreas"),
  };
}

function refresh(articleId: number | string) {
  revalidatePath("/admin/news");
  revalidatePath(`/admin/news/${articleId}`);
  revalidatePath("/news");
}

export async function createArticle(form: FormData) {
  const created = await adminNewsMutate<AdminNewsArticle>("", draftPayload(form));
  revalidatePath("/admin/news");
  redirect(`/admin/news/${created.id}`);
}

export async function saveArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}`, draftPayload(form));
  refresh(id);
}

export async function addSource(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}/source`, {
    sourceName: textField(form, "sourceName"),
    siteUrl: textField(form, "siteUrl"),
    externalUrl: textField(form, "externalUrl"),
    originalTitle: textField(form, "originalTitle"),
    sourcePublishedAt: textField(form, "sourcePublishedAt") || null,
    isPrimary: true,
  });
  refresh(id);
}

export async function assessImpact(form: FormData) {
  const id = textField(form, "articleId");
  // The five factors go to the server; news-impact-v1 computes score and level there. The
  // UI never calculates or submits a level.
  await adminNewsMutate<AdminNewsArticle>(`/${id}/impact`, {
    capabilityAdvancement: Number(form.get("capabilityAdvancement")),
    commercialDeployability: Number(form.get("commercialDeployability")),
    breadthOfAffectedWork: Number(form.get("breadthOfAffectedWork")),
    adoptionSpeed: Number(form.get("adoptionSpeed")),
    humanWorkReductionPotential: Number(form.get("humanWorkReductionPotential")),
    impactConfidence: Number(form.get("impactConfidence")),
    impactReasoning: textField(form, "impactReasoning"),
  });
  refresh(id);
}

export async function overrideImpact(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}/impact/override`, {
    impactLevel: textField(form, "impactLevel"),
    reason: textField(form, "reason") || null,
  });
  refresh(id);
}

export async function publishArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}/publish`);
  refresh(id);
}

export async function rejectArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}/reject`);
  refresh(id);
}

export async function unpublishArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate<AdminNewsArticle>(`/${id}/unpublish`);
  refresh(id);
}


// ------------------------------------------------------------------ Phase 2 ingestion

function refreshIncoming() {
  revalidatePath("/admin/news/incoming");
  revalidatePath("/admin/news");
}

export async function setIncomingStatus(form: FormData) {
  const id = textField(form, "itemId");
  await adminNewsMutate(`/incoming/${id}/status`, { status: textField(form, "status") });
  refreshIncoming();
}

export async function draftFromIncoming(form: FormData) {
  const id = textField(form, "itemId");
  // Creates an empty draft carrying the candidate's source. Phase 2 writes no prose and no
  // impact assessment: both are the editor's job in the article editor.
  const created = await adminNewsMutate<{ id: number }>(`/incoming/${id}/draft`);
  refreshIncoming();
  redirect(`/admin/news/${created.id}`);
}

export async function runIngestion() {
  await adminNewsMutate("/ingest/run");
  refreshIncoming();
}

export async function generateFromIncoming(form: FormData) {
  const id = textField(form, "itemId");
  // Never raises on a provider failure: a failed generation is a normal retryable state,
  // and the outcome is shown on the candidate rather than thrown at the admin.
  await adminNewsMutate(`/incoming/${id}/generate`);
  refreshIncoming();
}

export async function runGenerationBatch() {
  await adminNewsMutate("/generation/batch");
  refreshIncoming();
}

export async function archiveArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate(`/${id}/archive`, { reason: textField(form, "reason") || null });
  refresh(id);
}

export async function restoreArticle(form: FormData) {
  const id = textField(form, "articleId");
  await adminNewsMutate(`/${id}/restore`);
  refresh(id);
}

export async function regenerateArticle(form: FormData) {
  const id = textField(form, "articleId");
  // Never raises on a provider failure or a refusal: both are normal states, reported on
  // the article rather than thrown at the editor.
  await adminNewsMutate(`/${id}/regenerate`);
  refresh(id);
}
