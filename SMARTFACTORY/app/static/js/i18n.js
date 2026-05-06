/**
 * i18n.js — Internationalisation module
 * Supports: Vietnamese (vi), English (en), Japanese (ja)
 *
 * Usage:
 *   import { t, setLang, applyI18n, getLang } from './i18n.js';
 *   t('cam.start')      → "Start" / "Bắt đầu" / "開始"
 *   setLang('ja')       → switches UI + fires 'sf-lang-change' event
 *   applyI18n()         → re-renders all [data-i18n] elements
 */

/* ================================================================
   TRANSLATION DICTIONARY
================================================================ */
const TRANSLATIONS = {

    /* ── Tiếng Việt ─────────────────────────────────────── */
    vi: {
        // Brand
        "brand.sub":        "ĐIỀU KHIỂN v1.0",

        // Workflow steps
        "step1.title":      "Cài đặt Camera",
        "step1.desc":       "Khởi tạo nguồn",
        "step2.title":      "Nhận diện màu",
        "step2.desc":       "Phân tích HSV",
        "step3.title":      "Theo dõi vật",
        "step3.desc":       "Gán ID đối tượng",
        "step4.title":      "Lệnh băng tải",
        "step4.desc":       "UART Serial",

        // Camera source card
        "cam.title":        "Nguồn Camera",
        "cam.type":         "Loại",
        "cam.usb":          "Camera USB",
        "cam.rtsp":         "RTSP / Camera IP",
        "cam.device":       "Thiết bị",
        "cam.url":          "URL luồng",
        "cam.url.ph":       "rtsp:// hoặc http://",
        "cam.start":        "Bắt đầu",
        "cam.stop":         "Dừng",

        // UART connection card
        "uart.card.title":  "Kết nối UART",
        "uart.card.status": "Trạng thái",
        "uart.card.port":   "Cổng",
        "uart.card.baud":   "Baud rate",
        "uart.card.last":   "Lệnh cuối",

        // Detected objects card
        "det.title":        "Vật thể nhận diện",
        "det.empty":        "Chưa phát hiện vật thể",

        // Color config card
        "color.title":      "Cấu hình màu sắc",
        "color.col":        "Màu",
        "color.action":     "Hành động",
        "color.ms":         "ms",
        "color.add":        "Thêm",
        "color.save":       "Lưu",
        "color.loading":    "Đang tải...",
        "color.empty":      "Chưa có màu nào",

        // UART log card
        "uart.title":       "Nhật ký UART",
        "uart.empty":       "Chưa có dữ liệu...",

        // Camera placeholder
        "cam.ph.title":     "CAMERA CHƯA KHỞI ĐỘNG",
        "cam.ph.sub":       "Chọn nguồn và nhấn Bắt đầu",

        // Camera status text (used in camera_control.js)
        "status.running":   "Camera đang chạy",
        "status.stopped":   "Camera đã dừng",
        "status.error":     "Lỗi Camera",

        // Nav / tooltips
        "nav.wifi":         "WiFi",
        "nav.estop":        "DỪNG KHẨN",
        "tip.uart":         "Kết nối UART",
        "tip.camera":       "Camera",
        "tip.wifi":         "Cài đặt WiFi",
        "tip.fullscreen":   "Toàn màn hình",
        "tip.theme.dark":   "Chuyển sang giao diện sáng",
        "tip.theme.light":  "Chuyển sang giao diện tối",
        "tip.estop":        "Dừng khẩn cấp",
        "tip.fliph":        "Lật ngang",
        "tip.flipv":        "Lật dọc",
        "tip.rotate":       "Xoay 90°",
        "tip.reset":        "Đặt lại",

        // Toasts
        "toast.color.saved": "Đã lưu cấu hình màu",
        "toast.color.fail":  "Lưu thất bại!",
    },

    /* ── English ─────────────────────────────────────────── */
    en: {
        "brand.sub":        "CONTROL v1.0",

        "step1.title":      "Camera Setup",
        "step1.desc":       "Init source",
        "step2.title":      "Color Detect",
        "step2.desc":       "HSV analysis",
        "step3.title":      "Object Track",
        "step3.desc":       "ID assignment",
        "step4.title":      "Conveyor CMD",
        "step4.desc":       "UART send",

        "cam.title":        "Camera Source",
        "cam.type":         "Type",
        "cam.usb":          "USB Camera",
        "cam.rtsp":         "RTSP / IP Camera",
        "cam.device":       "Device",
        "cam.url":          "Stream URL",
        "cam.url.ph":       "rtsp:// or http://",
        "cam.start":        "Start",
        "cam.stop":         "Stop",

        // UART connection card
        "uart.card.title":  "UART Connection",
        "uart.card.status": "Status",
        "uart.card.port":   "Port",
        "uart.card.baud":   "Baud rate",
        "uart.card.last":   "Last command",

        "det.title":        "Detected Objects",
        "det.empty":        "No objects detected",

        "color.title":      "Color Configuration",
        "color.col":        "Color",
        "color.action":     "Action",
        "color.ms":         "ms",
        "color.add":        "Add",
        "color.save":       "Save",
        "color.loading":    "Loading...",
        "color.empty":      "No colors configured",

        "uart.title":       "UART Log",
        "uart.empty":       "No data yet...",

        "cam.ph.title":     "CAMERA NOT STARTED",
        "cam.ph.sub":       "Select a source and press Start",

        "status.running":   "Camera Running",
        "status.stopped":   "Camera Stopped",
        "status.error":     "Camera Error",

        "nav.wifi":         "WiFi",
        "nav.estop":        "E-STOP",
        "tip.uart":         "UART Serial",
        "tip.camera":       "Camera",
        "tip.wifi":         "WiFi Settings",
        "tip.fullscreen":   "Fullscreen",
        "tip.theme.dark":   "Switch to Light Mode",
        "tip.theme.light":  "Switch to Dark Mode",
        "tip.estop":        "Emergency Stop",
        "tip.fliph":        "Flip Horizontal",
        "tip.flipv":        "Flip Vertical",
        "tip.rotate":       "Rotate 90°",
        "tip.reset":        "Reset Transform",

        "toast.color.saved": "Color config saved",
        "toast.color.fail":  "Save failed!",
    },

    /* ── 日本語 ───────────────────────────────────────────── */
    ja: {
        "brand.sub":        "コントロール v1.0",

        "step1.title":      "カメラ設定",
        "step1.desc":       "ソース初期化",
        "step2.title":      "色検出",
        "step2.desc":       "HSV解析",
        "step3.title":      "物体追跡",
        "step3.desc":       "ID割り当て",
        "step4.title":      "搬送指令",
        "step4.desc":       "UART送信",

        "cam.title":        "カメラソース",
        "cam.type":         "種類",
        "cam.usb":          "USBカメラ",
        "cam.rtsp":         "RTSP / IPカメラ",
        "cam.device":       "デバイス",
        "cam.url":          "ストリームURL",
        "cam.url.ph":       "rtsp:// または http://",
        "cam.start":        "開始",
        "cam.stop":         "停止",

        // UART connection card
        "uart.card.title":  "UART接続",
        "uart.card.status": "状態",
        "uart.card.port":   "ポート",
        "uart.card.baud":   "ボーレート",
        "uart.card.last":   "最後のコマンド",

        "det.title":        "検出オブジェクト",
        "det.empty":        "物体未検出",

        "color.title":      "色設定",
        "color.col":        "色",
        "color.action":     "アクション",
        "color.ms":         "ms",
        "color.add":        "追加",
        "color.save":       "保存",
        "color.loading":    "読込中...",
        "color.empty":      "色が設定されていません",

        "uart.title":       "UARTログ",
        "uart.empty":       "データなし...",

        "cam.ph.title":     "カメラ未起動",
        "cam.ph.sub":       "ソースを選択して開始してください",

        "status.running":   "カメラ稼働中",
        "status.stopped":   "カメラ停止",
        "status.error":     "カメラエラー",

        "nav.wifi":         "WiFi",
        "nav.estop":        "緊急停止",
        "tip.uart":         "UARTシリアル",
        "tip.camera":       "カメラ",
        "tip.wifi":         "WiFi設定",
        "tip.fullscreen":   "全画面",
        "tip.theme.dark":   "ライトモードに切替",
        "tip.theme.light":  "ダークモードに切替",
        "tip.estop":        "緊急停止",
        "tip.fliph":        "水平反転",
        "tip.flipv":        "垂直反転",
        "tip.rotate":       "90°回転",
        "tip.reset":        "リセット",

        "toast.color.saved": "色設定を保存しました",
        "toast.color.fail":  "保存に失敗しました！",
    },
};

/* ================================================================
   STATE
================================================================ */
const SUPPORTED = ['vi', 'en', 'ja'];
let _lang = localStorage.getItem('sf-lang') || 'vi';
if (!SUPPORTED.includes(_lang)) _lang = 'vi';

/* ================================================================
   PUBLIC API
================================================================ */

/** Return translated string for key in current language. */
export function t(key) {
    return TRANSLATIONS[_lang]?.[key]
        ?? TRANSLATIONS['en']?.[key]
        ?? key;
}

/** Return current language code. */
export function getLang() { return _lang; }

/**
 * Apply all translations to the DOM.
 * Handles:
 *   [data-i18n]        → element.textContent
 *   [data-i18n-ph]     → element.placeholder
 *   [data-i18n-title]  → element.title
 */
export function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        el.placeholder = t(el.dataset.i18nPh);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = t(el.dataset.i18nTitle);
    });

    // Sync select value
    const sel = document.getElementById('lang-select');
    if (sel) sel.value = _lang;

    // Update <html lang> for accessibility
    document.documentElement.lang = _lang;
}

/**
 * Switch language and re-render all translated elements.
 * Fires 'sf-lang-change' event on window so other modules can react.
 */
export function setLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    _lang = lang;
    localStorage.setItem('sf-lang', lang);
    applyI18n();
    window.dispatchEvent(new CustomEvent('sf-lang-change', { detail: { lang } }));
}
