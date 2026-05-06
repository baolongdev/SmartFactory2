/**
 * conveyor_cycle.js — Chu kỳ tự động bật/tắt băng tải (UART 0/1).
 *
 * Logic:
 *   Bật  → gửi UART 1  → chờ runMs  → Tắt
 *   Tắt  → gửi UART 0  → chờ stopMs → Bật  → lặp lại
 *
 * UI elements (IDs):
 *   cycle-run-ms       — input số ms chạy
 *   cycle-stop-ms      — input số ms dừng
 *   cycle-status-badge — badge ON/OFF trên header
 *   cycle-phase-label  — nhãn pha hiện tại (RUN / STOP)
 *   cycle-countdown    — đếm ngược giây còn lại
 *   cycle-progress-bar — thanh tiến trình
 *   cycle-info-row     — hàng hiển thị khi đang chạy
 *   btn-cycle-toggle   — nút bật/tắt
 *   btn-cycle-icon     — icon trong nút
 *   btn-cycle-label    — chữ trong nút
 */

import { sendUART, UART_CMD } from "./uart.js";
import { t } from "./i18n.js";

// ── State ──────────────────────────────────────────────────────────────────
let _enabled      = false;
let _phase        = "stopped";   // "running" | "stopped"
let _phaseTimer   = null;
let _displayTimer = null;
let _phaseStart   = 0;
let _phaseDuration = 0;

// ── Helpers ────────────────────────────────────────────────────────────────
function _runMs()  { return Math.max(500, parseInt(document.getElementById("cycle-run-ms")?.value  || 3000, 10)); }
function _stopMs() { return Math.max(500, parseInt(document.getElementById("cycle-stop-ms")?.value || 2000, 10)); }

// ── Cycle engine ───────────────────────────────────────────────────────────
async function _doRun() {
    if (!_enabled) return;
    _phase        = "running";
    _phaseStart   = Date.now();
    _phaseDuration = _runMs();
    await sendUART(UART_CMD.CONVEYOR_RUN);
    _phaseTimer = setTimeout(_doStop, _phaseDuration);
    _updateUI();
}

async function _doStop() {
    if (!_enabled) return;
    _phase        = "stopped";
    _phaseStart   = Date.now();
    _phaseDuration = _stopMs();
    await sendUART(UART_CMD.CONVEYOR_STOP);
    _phaseTimer = setTimeout(_doRun, _phaseDuration);
    _updateUI();
}

// ── Display update (100 ms tick) ───────────────────────────────────────────
function _startDisplay() {
    if (_displayTimer) clearInterval(_displayTimer);
    _displayTimer = setInterval(_updateUI, 100);
}

function _stopDisplay() {
    if (_displayTimer) { clearInterval(_displayTimer); _displayTimer = null; }
}

function _updateUI() {
    const elapsed   = Date.now() - _phaseStart;
    const remaining = Math.max(0, _phaseDuration - elapsed);
    const pct       = _phaseDuration > 0 ? Math.min(100, (elapsed / _phaseDuration) * 100) : 0;
    const isRun     = _phase === "running";

    const phaseEl    = document.getElementById("cycle-phase-label");
    const countEl    = document.getElementById("cycle-countdown");
    const barEl      = document.getElementById("cycle-progress-bar");

    if (phaseEl) {
        phaseEl.textContent = isRun ? t("cycle.phase.run") : t("cycle.phase.stop");
        phaseEl.style.color = isRun ? "var(--success)" : "var(--fg-subtle)";
    }
    if (countEl)  countEl.textContent  = (remaining / 1000).toFixed(1) + "s";
    if (barEl) {
        barEl.style.width      = pct + "%";
        barEl.style.background = isRun ? "var(--success)" : "var(--fg-subtle)";
    }
}

// ── Public API ─────────────────────────────────────────────────────────────
export function startCycle() {
    if (_enabled) return;
    _enabled = true;
    _refreshButton();
    _showInfoRow(true);
    _startDisplay();
    _doRun();
}

export function stopCycle() {
    if (!_enabled) return;
    _enabled = false;
    if (_phaseTimer) { clearTimeout(_phaseTimer); _phaseTimer = null; }
    _stopDisplay();
    sendUART(UART_CMD.CONVEYOR_STOP);
    _phase = "stopped";
    _showInfoRow(false);
    _refreshButton();
}

export function toggleCycle() {
    _enabled ? stopCycle() : startCycle();
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function _showInfoRow(show) {
    const row    = document.getElementById("cycle-info-row");
    const badge  = document.getElementById("cycle-status-badge");
    if (row)   row.style.display   = show ? "" : "none";
    if (badge) {
        badge.textContent = show ? "ON" : "OFF";
        badge.className   = show
            ? "ml-auto uart-state-badge uart-state-on"
            : "ml-auto uart-state-badge uart-state-off";
    }
}

function _refreshButton() {
    const icon  = document.getElementById("btn-cycle-icon");
    const label = document.getElementById("btn-cycle-label");
    const btn   = document.getElementById("btn-cycle-toggle");
    if (!btn) return;
    if (_enabled) {
        btn.className  = "sf-btn sf-btn-danger";
        if (icon)  icon.className  = "fas fa-stop";
        if (label) label.textContent = t("cycle.stop_btn");
    } else {
        btn.className  = "sf-btn sf-btn-primary";
        if (icon)  icon.className  = "fas fa-play";
        if (label) label.textContent = t("cycle.start");
    }
}

/** Call once on DOMContentLoaded to wire up the toggle button. */
export function initCycleControls() {
    document.getElementById("btn-cycle-toggle")
        ?.addEventListener("click", toggleCycle);

    // Re-render button text when language changes
    window.addEventListener("sf-lang-change", _refreshButton);
}
