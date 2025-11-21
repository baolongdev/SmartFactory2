import { COLOR_API_BASE } from "./helpers.js";

/* ============================================================
   LOAD CONFIG
============================================================ */
export async function loadColorConfig() {
    try {
        const res = await fetch(`${COLOR_API_BASE}/`);
        const data = await res.json();

        return Array.isArray(data.colors) ? data.colors : [];
    } catch (err) {
        console.error("[ColorConfig] Load failed:", err);
        return [];
    }
}

/* ============================================================
   SAVE CONFIG
============================================================ */
export async function saveColorConfigToServer(colors) {
    try {
        const res = await fetch(`${COLOR_API_BASE}/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(colors),
        });

        return await res.json();
    } catch (err) {
        console.error("[ColorConfig] Save failed:", err);
        return { status: "error" };
    }
}

/* ============================================================
   BUILD 1 TABLE ROW
============================================================ */
export function buildColorRow(color) {
    const name = color.name || "red";
    const action = color.action_id ?? 0;
    const duration = color.duration_ms ?? 1000;

    const options = [
        "red", "green", "blue",
        "yellow", "orange", "purple", "pink"
    ].map(m =>
        `<option value="${m}" style="color:#000;"
            ${name === m ? "selected" : ""}>
            ${m.charAt(0).toUpperCase() + m.slice(1)}
        </option>`
    ).join("");


    return `
        <tr class="color-row color-${name}">
            <td>
                <select class="color-name" onchange="updateRowColor(this)">
                    ${options}
                </select>
            </td>

            <td>
                <input type="number" class="color-action" value="${action}" min="1" max="10">
            </td>

            <td>
                <input type="number" class="color-duration" value="${duration}" min="2000" max="10000">
            </td>

            <td>
                <button class="color-remove-btn" onclick="this.closest('tr').remove()">
                    X
                </button>
            </td>
        </tr>
    `;
}

/* ============================================================
   RENDER TABLE
============================================================ */
export async function renderColorTable() {
    const table = document.getElementById("color-table-body");
    const list = await loadColorConfig();

    if (!list.length) {
        table.innerHTML = `<tr><td colspan="4" style="text-align:center;color:#777;">No Colors</td></tr>`;
        return;
    }

    table.innerHTML = list.map(buildColorRow).join("");
}

/* ============================================================
   SAVE (FROM TABLE → SERVER)
============================================================ */
export async function saveColorConfig() {
    const rows = document.querySelectorAll("#color-table-body tr");
    const colors = [];

    rows.forEach(row => {
        const name = row.querySelector(".color-name").value;
        const action = parseInt(row.querySelector(".color-action").value, 10);
        const duration = parseInt(row.querySelector(".color-duration").value, 10);

        colors.push({
            name,
            action_id: isNaN(action) ? 0 : action,
            duration_ms: isNaN(duration) ? 1000 : duration,
        });
    });

    const res = await saveColorConfigToServer(colors);

    if (res.status === "success") {
        alert("Color Configuration Saved!");
    } else {
        alert("Save Failed!");
    }
}

/* ============================================================
   ADD NEW ROW
============================================================ */
export function addNewColorRow() {
    const table = document.getElementById("color-table-body");
    table.insertAdjacentHTML(
        "beforeend",
        buildColorRow({
            name: "red",
            action_id: 0,
            duration_ms: 1000
        })
    );
}
