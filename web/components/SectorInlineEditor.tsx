"use client";

import { useState, useCallback } from "react";
import {
  createToolItem,
  updateToolItem,
  deleteToolItem,
} from "@/lib/sector-admin";

// ─── Types ───────────────────────────────────────────────────────────────────

interface InlineEditorProps {
  sectorId: string;
  toolPath: string;
  dataKey: string;
  idField: string;
  /** The full data response from the API (e.g., { threats: [...], ok: true }) */
  responseData: Record<string, unknown>;
  /** The primary data array (e.g., responseData["threats"] or responseData) */
  records: Record<string, unknown>[];
  /** Columns to show in the editor (auto-detected) */
  columns: string[];
  /** Called when data has changed, to trigger a refresh */
  onDataChanged: () => void;
  /** Sector color for styling */
  accentColor: string;
}

interface EditorModalProps {
  sectorId: string;
  toolPath: string;
  idField: string;
  /** The item being edited, or null for create mode */
  item: Record<string, unknown> | null;
  /** All detected columns for form rendering */
  columns: string[];
  accentColor: string;
  onClose: () => void;
  onSaved: () => void;
}

// ─── Field type detection ────────────────────────────────────────────────────

function detectFieldType(value: unknown): "text" | "number" | "boolean" | "json" {
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "object" && value !== null) return "json";
  return "text";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return String(value);
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function parseValue(value: string, type: "text" | "number" | "boolean" | "json"): unknown {
  if (type === "number") {
    const n = parseFloat(value);
    return isNaN(n) ? value : n;
  }
  if (type === "boolean") return value === "true";
  if (type === "json") {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  return value;
}

function formatFieldLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/([a-z])([A-Z])/g, "$1 $2");
}

// ─── Skip keys that aren't user-editable ─────────────────────────────────────

const SKIP_KEYS = new Set(["ok", "source", "total", "scan_summary"]);

// ─── Item Editor Modal ───────────────────────────────────────────────────────

function ItemEditorModal({
  sectorId,
  toolPath,
  idField,
  item,
  columns,
  accentColor,
  onClose,
  onSaved,
}: EditorModalProps) {
  const isCreate = item === null;
  const [formData, setFormData] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const col of columns) {
      if (SKIP_KEYS.has(col)) continue;
      init[col] = isCreate ? "" : formatValue(item![col]);
    }
    return init;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = useCallback((key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);

    // Build the item from form data
    const builtItem: Record<string, unknown> = {};
    for (const col of columns) {
      if (SKIP_KEYS.has(col)) continue;
      const raw = formData[col];
      const example = isCreate
        ? typeof raw === "string" && raw.length > 0
          ? raw
          : ""
        : item?.[col];
      const type = detectFieldType(example);
      builtItem[col] = parseValue(raw, type);
    }

    let result;
    if (isCreate) {
      result = await createToolItem(sectorId, toolPath, builtItem);
    } else {
      const idValue = formData[idField] || builtItem[idField];
      result = await updateToolItem(sectorId, toolPath, idField, String(idValue), builtItem);
    }

    if (result.ok) {
      onSaved();
      onClose();
    } else {
      setError(result.error || "Failed to save");
    }
    setSaving(false);
  }, [sectorId, toolPath, idField, item, isCreate, formData, columns, onClose, onSaved]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSave();
      }
    },
    [onClose, handleSave],
  );

  return (
    <div className="sector-editor-overlay" onClick={onClose}>
      <div
        className="sector-editor-modal"
        style={{ borderTop: `3px solid ${accentColor}` }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="sector-editor-header">
          <h2>{isCreate ? "➕ Add New Item" : "✏️ Edit Item"}</h2>
          <div className="sector-editor-badge" style={{ background: `${accentColor}20`, color: accentColor }}>
            {sectorId}/{toolPath}
          </div>
          <button className="sector-editor-close" onClick={onClose}>×</button>
        </div>

        <div className="sector-editor-body">
          {columns
            .filter((col) => !SKIP_KEYS.has(col))
            .map((col) => {
              const example = isCreate ? "" : item?.[col];
              const type = detectFieldType(example);

              return (
                <div key={col} className="sector-editor-field">
                  <label className="sector-editor-label">
                    {formatFieldLabel(col)}
                    {col === idField && <span className="sector-editor-id-badge">ID</span>}
                  </label>
                  {type === "boolean" ? (
                    <select
                      className="sector-editor-select"
                      value={formData[col] || "false"}
                      onChange={(e) => handleChange(col, e.target.value)}
                    >
                      <option value="true">True</option>
                      <option value="false">False</option>
                    </select>
                  ) : type === "json" ? (
                    <textarea
                      className="sector-editor-textarea"
                      value={formData[col] || "{}"}
                      onChange={(e) => handleChange(col, e.target.value)}
                      rows={4}
                      placeholder="{ }"
                    />
                  ) : type === "number" ? (
                    <input
                      type="number"
                      className="sector-editor-input"
                      value={formData[col]}
                      onChange={(e) => handleChange(col, e.target.value)}
                      placeholder="0"
                      step="any"
                    />
                  ) : (
                    <input
                      type="text"
                      className="sector-editor-input"
                      value={formData[col]}
                      onChange={(e) => handleChange(col, e.target.value)}
                      placeholder={`Enter ${formatFieldLabel(col).toLowerCase()}`}
                    />
                  )}
                </div>
              );
            })}
        </div>

        {error && <div className="sector-editor-error">⚠ {error}</div>}

        <div className="sector-editor-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className="btn"
            onClick={handleSave}
            disabled={saving}
            style={{ background: accentColor, borderColor: accentColor, color: "#fff" }}
          >
            {saving ? "⏳ Saving..." : isCreate ? "➕ Create" : "💾 Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Confirm Delete Modal ────────────────────────────────────────────────────

function ConfirmDeleteModal({
  sectorId,
  toolPath,
  idField,
  item,
  accentColor,
  onClose,
  onDeleted,
}: {
  sectorId: string;
  toolPath: string;
  idField: string;
  item: Record<string, unknown>;
  accentColor: string;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const idValue = String(item[idField] ?? "");

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    setError(null);
    const result = await deleteToolItem(sectorId, toolPath, idField, idValue);
    if (result.ok) {
      onDeleted();
      onClose();
    } else {
      setError(result.error || "Failed to delete");
    }
    setDeleting(false);
  }, [sectorId, toolPath, idField, idValue, onClose, onDeleted]);

  return (
    <div className="sector-editor-overlay" onClick={onClose}>
      <div
        className="sector-editor-modal sector-editor-modal-sm"
        style={{ borderTop: `3px solid #ef4444` }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sector-editor-header">
          <h2>🗑️ Confirm Delete</h2>
          <button className="sector-editor-close" onClick={onClose}>×</button>
        </div>
        <div className="sector-editor-body" style={{ textAlign: "center", padding: "24px" }}>
          <p style={{ fontSize: "1.1rem", marginBottom: 8, color: "var(--aeon-fg)" }}>
            Are you sure you want to delete this item?
          </p>
          <p style={{ color: "var(--aeon-fg-mute)", fontSize: "0.9rem", marginBottom: 8 }}>
            <strong>{formatFieldLabel(idField)}:</strong> {idValue}
          </p>
          <p style={{ color: "var(--aeon-fg-mute)", fontSize: "0.85rem" }}>
            Sector: <strong>{sectorId}</strong> / Tool: <strong>{toolPath}</strong>
          </p>
        </div>
        {error && <div className="sector-editor-error">⚠ {error}</div>}
        <div className="sector-editor-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={deleting}>
            Cancel
          </button>
          <button
            className="btn"
            onClick={handleDelete}
            disabled={deleting}
            style={{
              background: "#ef4444",
              borderColor: "#ef4444",
              color: "#fff",
            }}
          >
            {deleting ? "⏳ Deleting..." : "🗑️ Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Inline Editor ──────────────────────────────────────────────────────

export default function SectorInlineEditor({
  sectorId,
  toolPath,
  idField,
  responseData,
  records,
  columns,
  onDataChanged,
  accentColor,
}: InlineEditorProps) {
  const [editingItem, setEditingItem] = useState<Record<string, unknown> | null>(null);
  const [createMode, setCreateMode] = useState(false);
  const [deletingItem, setDeletingItem] = useState<Record<string, unknown> | null>(null);

  // Don't show inline editor for object-based tools (no id_field)
  if (!idField) {
    return (
      <div className="sector-editor-actions">
        <button
          className="btn btn-xs"
          onClick={() => setCreateMode(true)}
          title="Edit this object"
          style={{ borderColor: accentColor, color: accentColor }}
        >
          ✏️ Edit
        </button>
        {createMode && (
          <ItemEditorModal
            sectorId={sectorId}
            toolPath={toolPath}
            idField={idField}
            item={responseData}
            columns={columns}
            accentColor={accentColor}
            onClose={() => setCreateMode(false)}
            onSaved={onDataChanged}
          />
        )}
      </div>
    );
  }

  return (
    <div className="sector-editor-wrapper">
      {/* Action bar */}
      <div className="sector-editor-actions">
        <span className="sector-editor-count">
          {records.length} {records.length === 1 ? "item" : "items"}
        </span>
        <button
          className="btn btn-xs"
          onClick={() => setCreateMode(true)}
          style={{ borderColor: accentColor, color: accentColor }}
        >
          ➕ Add
        </button>
      </div>

      {/* Items list with inline edit/delete */}
      <div className="sector-editor-items">
        {records.map((record, idx) => {
          const idValue = String(record[idField] ?? "");
          return (
            <div key={idValue || idx} className="sector-editor-item">
              <div className="sector-editor-item-info">
                <span className="sector-editor-item-id">
                  {formatFieldLabel(idField)}: <strong>{idValue}</strong>
                </span>
                <span className="sector-editor-item-preview">
                  {columns
                    .filter((c) => c !== idField && !SKIP_KEYS.has(c))
                    .slice(0, 2)
                    .map((c) => {
                      const v = record[c];
                      const s = typeof v === "object" ? "..." : String(v ?? "—");
                      return `${formatFieldLabel(c)}: ${s.length > 25 ? s.slice(0, 22) + "…" : s}`;
                    })
                    .join(" | ")}
                </span>
              </div>
              <div className="sector-editor-item-actions">
                <button
                  className="btn btn-xs btn-ghost"
                  onClick={() => setEditingItem(record)}
                  title="Edit"
                >
                  ✏️
                </button>
                <button
                  className="btn btn-xs btn-ghost"
                  onClick={() => setDeletingItem(record)}
                  title="Delete"
                  style={{ color: "#ef4444" }}
                >
                  🗑️
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* No items state */}
      {records.length === 0 && (
        <div className="sector-editor-empty">
          <p>No items yet. Click <strong>Add</strong> to create one.</p>
        </div>
      )}

      {/* Create modal */}
      {createMode && (
        <ItemEditorModal
          sectorId={sectorId}
          toolPath={toolPath}
          idField={idField}
          item={null}
          columns={columns}
          accentColor={accentColor}
          onClose={() => setCreateMode(false)}
          onSaved={onDataChanged}
        />
      )}

      {/* Edit modal */}
      {editingItem && (
        <ItemEditorModal
          sectorId={sectorId}
          toolPath={toolPath}
          idField={idField}
          item={editingItem}
          columns={columns}
          accentColor={accentColor}
          onClose={() => setEditingItem(null)}
          onSaved={onDataChanged}
        />
      )}

      {/* Delete confirm modal */}
      {deletingItem && (
        <ConfirmDeleteModal
          sectorId={sectorId}
          toolPath={toolPath}
          idField={idField}
          item={deletingItem}
          accentColor={accentColor}
          onClose={() => setDeletingItem(null)}
          onDeleted={onDataChanged}
        />
      )}
    </div>
  );
}
