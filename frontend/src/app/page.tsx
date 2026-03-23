"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { getApiBaseUrl, requestJson } from "@/lib/api";

type UploadState = {
  pending: boolean;
  error: string | null;
  message: string | null;
  datasetId: string | null;
};

type AnalysisState = {
  pending: boolean;
  error: string | null;
};

type DatasetOption = {
  dataset_id: string;
  source_label: string | null;
  filename: string | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const initialUploadState: UploadState = {
  pending: false,
  error: null,
  message: null,
  datasetId: null
};

const initialAnalysisState: AnalysisState = {
  pending: false,
  error: null
};

export default function HomePage() {
  const [openStep, setOpenStep] = useState<1 | 2>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLabel, setSourceLabel] = useState("");
  const [datasetSelector, setDatasetSelector] = useState("");
  const [datasetSearch, setDatasetSearch] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [uploadState, setUploadState] = useState<UploadState>(initialUploadState);
  const [analysisState, setAnalysisState] = useState<AnalysisState>(initialAnalysisState);
  const [datasetOptions, setDatasetOptions] = useState<DatasetOption[]>([]);
  const [conversation, setConversation] = useState<ChatMessage[]>([]);
  const [conversationTokens, setConversationTokens] = useState(0);

  const filteredDatasetOptions = useMemo(() => {
    const query = datasetSearch.trim().toLowerCase();
    if (!query) {
      return datasetOptions;
    }

    return datasetOptions.filter((item) => {
      const idMatch = item.dataset_id.toLowerCase().includes(query);
      const labelMatch = item.source_label?.toLowerCase().includes(query) ?? false;
      return idMatch || labelMatch;
    });
  }, [datasetOptions, datasetSearch]);

  useEffect(() => {
    void refreshDatasets();
  }, []);

  async function refreshDatasets() {
    try {
      const data = await requestJson("/api/v1/datasets", { method: "GET" });
      const items = extractDatasetItems(data);
      setDatasetOptions(items);
    } catch {
      setDatasetOptions([]);
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadState({
        pending: false,
        error: "Select a csv or xlsx file before uploading.",
        message: null,
        datasetId: null
      });
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("file_name", selectedFile.name);

    if (sourceLabel.trim()) {
      formData.append("source_label", sourceLabel.trim());
    }

    setUploadState({ pending: true, error: null, message: null, datasetId: null });

    try {
      const data = await requestJson("/api/v1/datasets/upload", {
        method: "POST",
        body: formData
      });

      const inferredDatasetId = getValueIfString(data, "dataset_id");
      const statusText = getValueIfString(data, "status") || "uploaded";

      if (inferredDatasetId) {
        setDatasetSelector(inferredDatasetId);
        setDatasetSearch(inferredDatasetId);
        setConversation([]);
        setConversationTokens(0);
      }

      setUploadState({
        pending: false,
        error: null,
        message: `File ${statusText}.`,
        datasetId: inferredDatasetId
      });
      setOpenStep(2);
      await refreshDatasets();
    } catch (error) {
      setUploadState({
        pending: false,
        error: error instanceof Error ? error.message : "Upload failed.",
        message: null,
        datasetId: null
      });
    }
  }

  async function handleAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const selector = datasetSelector.trim();
    const prompt = userPrompt.trim();

    if (!selector || !prompt) {
      setAnalysisState({
        pending: false,
        error: "Dataset selector and analysis question are required."
      });
      return;
    }

    setAnalysisState({ pending: true, error: null });

    try {
      const data = await requestJson("/api/v1/analysis/jobs", {
        method: "POST",
        body: JSON.stringify({
          dataset_selector: selector,
          user_prompt: prompt,
          memory: conversation.map((message) => ({
            role: message.role,
            content: message.content
          }))
        }),
        headers: {
          "Content-Type": "application/json"
        }
      });

      const responseText = getValueIfString(data, "result") || "";
      const tokens = getNestedNumber(data, "usage", "total_tokens");

      if (responseText) {
        setConversation((prev) => [...prev, { role: "user", content: prompt }, { role: "assistant", content: responseText }]);
      }

      if (tokens > 0) {
        setConversationTokens((prev) => prev + tokens);
      }

      setUserPrompt("");
      setAnalysisState({ pending: false, error: null });
    } catch (error) {
      setAnalysisState({
        pending: false,
        error: error instanceof Error ? error.message : "Analysis request failed."
      });
    }
  }

  function handleDatasetSelect(nextValue: string) {
    setDatasetSelector(nextValue);
    setDatasetSearch(nextValue);
    setConversation([]);
    setConversationTokens(0);
    setAnalysisState(initialAnalysisState);
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

      <section className="accordion-stack">
        <article className={`accordion-panel ${openStep === 1 ? "open" : ""}`}>
          <button type="button" className="accordion-trigger" onClick={() => setOpenStep(openStep === 1 ? 2 : 1)}>
            <span>
              <span className="panel-kicker">Step 1</span>
              <h2>Upload a dataset</h2>
            </span>
            <span className="accordion-icon">{openStep === 1 ? "-" : "+"}</span>
          </button>

          <div className="accordion-content">
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
                {uploadState.pending ? "Uploading..." : "Upload dataset"}
              </button>
            </form>

            <section className="status-inline">
              <h3>Upload status</h3>
              {uploadState.error ? <p className="error-text">{uploadState.error}</p> : null}
              {uploadState.message ? <p className="ok-text">{uploadState.message}</p> : <p className="muted-text">No upload request sent yet.</p>}
              {uploadState.datasetId ? (
                <p className="dataset-pill">Dataset ID: {uploadState.datasetId}</p>
              ) : null}
            </section>
          </div>
        </article>

        <article className={`accordion-panel ${openStep === 2 ? "open" : ""}`}>
          <button type="button" className="accordion-trigger" onClick={() => setOpenStep(openStep === 2 ? 1 : 2)}>
            <span>
              <span className="panel-kicker">Step 2</span>
              <h2>Ask for analysis</h2>
            </span>
            <span className="accordion-icon">{openStep === 2 ? "-" : "+"}</span>
          </button>

          <div className="accordion-content">
            <div className="selector-block">
              <label className="field">
                <span>Search dataset by dataset ID or source label</span>
                <input
                  type="text"
                  value={datasetSearch}
                  onChange={(event) => setDatasetSearch(event.target.value)}
                  placeholder="Search datasets..."
                />
              </label>

              <label className="field">
                <span>Dataset selector (dataset ID or source label)</span>
                <input
                  type="text"
                  value={datasetSelector}
                  onChange={(event) => handleDatasetSelect(event.target.value)}
                  placeholder="Enter dataset ID or source label"
                />
              </label>

              <div className="dataset-match-list" role="list">
                {filteredDatasetOptions.slice(0, 8).map((item) => (
                  <button
                    key={item.dataset_id}
                    type="button"
                    className="dataset-match-item"
                    onClick={() => handleDatasetSelect(item.dataset_id)}
                  >
                    <strong>{item.dataset_id}</strong>
                    <span>{item.source_label || item.filename || "No label"}</span>
                  </button>
                ))}
              </div>
            </div>

            <form className="chat-composer" onSubmit={handleAnalysis}>
              <textarea
                rows={3}
                value={userPrompt}
                onChange={(event) => setUserPrompt(event.target.value)}
                placeholder="Ask a question about the selected dataset."
              />
              <button className="primary-button" type="submit" disabled={analysisState.pending}>
                {analysisState.pending ? "Thinking..." : "Send"}
              </button>
            </form>

            {analysisState.error ? <p className="error-text">{analysisState.error}</p> : null}

            <section className="chat-cell">
              {conversation.length === 0 ? <p className="muted-text">Start a conversation to see analysis results here.</p> : null}
              {conversation.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`chat-row ${message.role}`}>
                  <div className="chat-bubble">{message.content}</div>
                </div>
              ))}
              {analysisState.pending ? (
                <div className="chat-row assistant">
                  <div className="chat-bubble">Working on your analysis...</div>
                </div>
              ) : null}
              <p className="token-counter">Conversation tokens: {conversationTokens}</p>
            </section>
          </div>
        </article>
      </section>
    </main>
  );
}

function extractDatasetItems(data: unknown): DatasetOption[] {
  if (!data || typeof data !== "object") {
    return [];
  }

  const items = (data as Record<string, unknown>).items;
  if (!Array.isArray(items)) {
    return [];
  }

  const mapped = items
    .map((raw) => {
      if (!raw || typeof raw !== "object") {
        return null;
      }

      const row = raw as Record<string, unknown>;
      const dataset_id = typeof row.dataset_id === "string" ? row.dataset_id : "";
      if (!dataset_id) {
        return null;
      }

      return {
        dataset_id,
        source_label: typeof row.source_label === "string" ? row.source_label : null,
        filename: typeof row.filename === "string" ? row.filename : null
      } satisfies DatasetOption;
    })
    .filter((item): item is DatasetOption => item !== null);

  return mapped;
}

function getValueIfString(data: unknown, key: string) {
  if (!data || typeof data !== "object" || !(key in data)) {
    return null;
  }

  const value = (data as Record<string, unknown>)[key];
  return typeof value === "string" ? value : null;
}

function getNestedNumber(data: unknown, parentKey: string, key: string) {
  if (!data || typeof data !== "object") {
    return 0;
  }

  const parent = (data as Record<string, unknown>)[parentKey];
  if (!parent || typeof parent !== "object") {
    return 0;
  }

  const value = (parent as Record<string, unknown>)[key];
  return typeof value === "number" ? value : 0;
}
