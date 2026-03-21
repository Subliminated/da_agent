"use client";

import { FormEvent, useState } from "react";
import { getApiBaseUrl, requestJson } from "@/lib/api";

type SubmissionState = {
  pending: boolean;
  error: string | null;
  response: unknown;
};

const initialSubmissionState: SubmissionState = {
  pending: false,
  error: null,
  response: null
};

export default function HomePage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLabel, setSourceLabel] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [uploadState, setUploadState] = useState<SubmissionState>(initialSubmissionState);
  const [analysisState, setAnalysisState] = useState<SubmissionState>(initialSubmissionState);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadState({
        pending: false,
        error: "Select a csv or xlsx file before uploading.",
        response: null
      });
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("file_name", selectedFile.name);

    if (sourceLabel.trim()) {
      formData.append("source_label", sourceLabel.trim());
    }

    setUploadState({ pending: true, error: null, response: null });

    try {
      const data = await requestJson("/api/v1/datasets/upload", {
        method: "POST",
        body: formData
      });

      const inferredDatasetId = getValueIfString(data, "dataset_id");

      if (inferredDatasetId) {
        setDatasetId(inferredDatasetId);
      }

      setUploadState({ pending: false, error: null, response: data });
    } catch (error) {
      setUploadState({
        pending: false,
        error: error instanceof Error ? error.message : "Upload failed.",
        response: null
      });
    }
  }

  async function handleAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!datasetId.trim() || !userPrompt.trim()) {
      setAnalysisState({
        pending: false,
        error: "Dataset ID and analysis question are required.",
        response: null
      });
      return;
    }

    setAnalysisState({ pending: true, error: null, response: null });

    try {
      const data = await requestJson("/api/v1/analysis/jobs", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: datasetId.trim(),
          user_prompt: userPrompt.trim()
        }),
        headers: {
          "Content-Type": "application/json"
        }
      });

      setAnalysisState({ pending: false, error: null, response: data });
    } catch (error) {
      setAnalysisState({
        pending: false,
        error: error instanceof Error ? error.message : "Analysis request failed.",
        response: null
      });
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Upload first. Analyze second.</p>
        <h1>Data Analyst Agent</h1>
        <p className="hero-copy">
          This frontend sends dataset ingestion and analysis-job requests to the backend API. It does not
          implement any backend behavior itself.
        </p>
        <div className="api-banner">
          <span>Backend target</span>
          <code>{getApiBaseUrl()}</code>
        </div>
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-header">
            <p className="panel-kicker">Step 1</p>
            <h2>Upload a dataset</h2>
          </div>

          <form className="form-stack" onSubmit={handleUpload}>
            <label className="field">
              <span>Source label</span>
              <input
                type="text"
                value={sourceLabel}
                onChange={(event) => setSourceLabel(event.target.value)}
                placeholder="Quarterly sales workbook"
              />
            </label>

            <label className="field">
              <span>File</span>
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>

            <button className="primary-button" type="submit" disabled={uploadState.pending}>
              {uploadState.pending ? "Uploading..." : "POST /api/v1/datasets/upload"}
            </button>
          </form>

          <StatusBlock
            title="Upload response"
            error={uploadState.error}
            response={uploadState.response}
            emptyMessage="No upload request sent yet."
          />
        </article>

        <article className="panel">
          <div className="panel-header">
            <p className="panel-kicker">Step 2</p>
            <h2>Ask for analysis</h2>
          </div>

          <form className="form-stack" onSubmit={handleAnalysis}>
            <label className="field">
              <span>Dataset ID</span>
              <input
                type="text"
                value={datasetId}
                onChange={(event) => setDatasetId(event.target.value)}
                placeholder="ds_123"
              />
            </label>

            <label className="field">
              <span>Analysis question</span>
              <textarea
                rows={5}
                value={userPrompt}
                onChange={(event) => setUserPrompt(event.target.value)}
                placeholder="Summarize total revenue by region and return the top 5 regions."
              />
            </label>

            <button className="primary-button" type="submit" disabled={analysisState.pending}>
              {analysisState.pending ? "Submitting..." : "POST /api/v1/analysis/jobs"}
            </button>
          </form>

          <StatusBlock
            title="Analysis response"
            error={analysisState.error}
            response={analysisState.response}
            emptyMessage="No analysis request sent yet."
          />
        </article>
      </section>
    </main>
  );
}

function StatusBlock({
  title,
  error,
  response,
  emptyMessage
}: {
  title: string;
  error: string | null;
  response: unknown;
  emptyMessage: string;
}) {
  return (
    <section className="status-block">
      <div className="status-header">
        <h3>{title}</h3>
      </div>

      {error ? <p className="error-text">{error}</p> : null}
      {response ? <pre>{JSON.stringify(response, null, 2)}</pre> : null}
      {!error && !response ? <p className="muted-text">{emptyMessage}</p> : null}
    </section>
  );
}

function getValueIfString(data: unknown, key: string) {
  if (!data || typeof data !== "object" || !(key in data)) {
    return null;
  }

  const value = (data as Record<string, unknown>)[key];
  return typeof value === "string" ? value : null;
}
