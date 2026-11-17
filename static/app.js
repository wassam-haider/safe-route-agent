const newId = () => (self.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Math.random()).slice(2);
let sessionId = newId();

const log = document.getElementById("log");
const input = document.getElementById("msg");
const sendBtn = document.getElementById("send");
const resetBtn = document.getElementById("reset");
const micBtn = document.getElementById("mic");
const legendEl = document.getElementById("legend");

// Scoring weights shown under the comparison table (edit to match your backend preset).
const WEIGHTS = [["Distance", 10], ["Time", 20], ["Traffic", 10], ["Crime", 30], ["Protests", 20], ["Weather", 10]];
// Steps shown while the agent works (cosmetic timer unless the backend sends data.steps).
const AGENT_STEPS = [
  "Finding start and destination",
  "Fetching route alternatives",
  "Checking news and upcoming protests",
  "Checking crime data",
  "Scoring routes",
];
const ROUTE_COLORS = ["#15803d", "#eab308", "#dc2626"]; // route 1 green, 2 yellow, 3 red
const ALT_COLOR = "#8b97a6";

const map = L.map("map").setView([24.8607, 67.0011], 11);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
let layers = [];
let routeLines = [];
let selected = -1;

/* ---------- DOM helpers ---------- */
function add(parent, tag, text, cls) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  parent.appendChild(e);
  return e;
}

function scrollDown() { log.scrollTop = log.scrollHeight; }

function bubble(text, cls, who) {
  const d = add(log, "div", undefined, "bubble " + cls);
  if (who) add(d, "b", who, "who");
  d.appendChild(document.createTextNode(text));
  scrollDown();
  return d;
}

function greet() {
  bubble("Tell me where you're starting, where you're going, and how you'll travel (car, motorcycle, bicycle, walking or public transport).", "bot", "SafeRoute Agent");
}

/* ---------- Agent steps ---------- */
function pendingSteps() {
  const box = add(log, "div", undefined, "steps");
  add(box, "h3", "Agent is working...");
  const ol = add(box, "ol");
  const items = AGENT_STEPS.map((s) => add(ol, "li", s));
  let i = 0;
  items[0].className = "active";
  const timer = setInterval(() => {
    if (i >= items.length - 1) return;
    items[i].className = "done";
    items[++i].className = "active";
  }, 2500);
  scrollDown();
  return { el: box, stop() { clearInterval(timer); box.remove(); } };
}

function showSteps(steps) {
  if (!Array.isArray(steps) || !steps.length) return;
  const box = add(log, "details", undefined, "steps");
  add(box, "summary", "Thinking");
  const ol = add(box, "ol");
  steps.forEach((s) => add(ol, "li", typeof s === "string" ? s : JSON.stringify(s), "done"));
}

/* ---------- Map ---------- */
function clearMap() {
  layers.forEach((l) => map.removeLayer(l));
  layers = [];
  routeLines = [];
  selected = -1;
  legendEl.hidden = true;
  legendEl.replaceChildren();
}

const routeColor = (i) => ROUTE_COLORS[i] || ALT_COLOR;

const letter = (i) => String.fromCharCode(65 + i);

function pin(p, cls, text, label) {
  const icon = L.divIcon({
    className: "",
    html: `<div class="pin ${cls}"><span>${text}</span></div>`,
    iconSize: [26, 26],
    iconAnchor: [4, 26],
  });
  return L.marker([p.lat, p.lng], { icon }).addTo(map).bindTooltip(label);
}

function drawLegend(routes) {
  legendEl.replaceChildren();
  add(legendEl, "h2", "Route options");
  routes.forEach((r, i) => {
    const row = add(legendEl, "div", undefined, "leg-row route-row");
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.dataset.idx = i;
    row.addEventListener("click", () => selectRoute(i, true));
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectRoute(i, true); }
    });
    const sw = add(row, "span", undefined, "swatch");
    sw.style.borderTopColor = routeColor(i);
    add(row, "b", letter(i));
    const t = add(row, "span", r.label || `Route ${letter(i)}`);
    if (r.is_best) add(t, "small", " (recommended)");
  });
  add(legendEl, "div", undefined, "leg-sep");
  const s = add(legendEl, "div", undefined, "leg-row");
  add(s, "span", "S", "pin start").style.cssText = "width:16px;height:16px;border-radius:50%;transform:none;font-size:10px;";
  add(s, "span", "Start");
  const d = add(legendEl, "div", undefined, "leg-row");
  add(d, "span", "E", "pin end").style.cssText = "width:16px;height:16px;border-radius:50%;transform:none;font-size:10px;";
  add(d, "span", "Destination");
  legendEl.hidden = false;
}

// Highlight one route, dim the others, and sync the legend.
function selectRoute(i, zoom) {
  if (!routeLines[i]) return;
  selected = i;
  routeLines.forEach((line, j) => {
    const on = j === i;
    line.setStyle({ weight: on ? 7 : 4, opacity: on ? 1 : 0.4, dashArray: on ? null : "8 6" });
    if (on) line.bringToFront();
  });
  legendEl.querySelectorAll(".route-row").forEach((row) => {
    const on = Number(row.dataset.idx) === i;
    row.classList.toggle("active", on);
    row.setAttribute("aria-pressed", String(on));
  });
  if (zoom) map.fitBounds(routeLines[i].getBounds(), { padding: [30, 30] });
}

function drawMap(m) {
  clearMap();
  if (!m) return;
  const all = [];
  m.routes.forEach((r, i) => {
    const line = L.polyline(r.points, { color: routeColor(i), weight: 4, opacity: 0.8 })
      .addTo(map).bindTooltip(r.label);
    line.on("click", () => selectRoute(i, false));
    routeLines[i] = line;
    layers.push(line);
    all.push(...r.points);
  });
  layers.push(pin(m.origin, "start", "S", "Start"));
  layers.push(pin(m.destination, "end", "E", "Destination"));
  if (all.length) map.fitBounds(all, { padding: [30, 30] });
  drawLegend(m.routes);
  const best = m.routes.findIndex((r) => r.is_best);
  selectRoute(best >= 0 ? best : 0, false);
}

/* ---------- Result card ---------- */
function showResult(rec, m) {
  const card = add(log, "div", undefined, "result");
  add(card, "h3", `${rec.recommended_route} - ${rec.travel_time_minutes} min, ${rec.distance_km} km`);

  // Route letters follow the map's route order; alternatives take the remaining letters.
  const letters = m && m.routes ? m.routes.map((_, i) => letter(i)) : [];
  const bestIdx = m && m.routes ? m.routes.findIndex((r) => r.is_best) : -1;
  const bestLetter = bestIdx >= 0 ? letters[bestIdx] : "";
  const altLetters = letters.filter((_, i) => i !== bestIdx);
  const altIdx = letters.map((_, i) => i).filter((i) => i !== bestIdx);

  const wrap = add(card, "div", undefined, "table-wrap");
  const table = add(wrap, "table");
  const head = add(add(table, "thead"), "tr");
  ["Route", "Safety", "Time (min)", "Dist (km)", "Traffic", "Crime", "Protest", "Weather", "Conf.", "Final"]
    .forEach((h) => add(head, "th", h));
  const body = add(table, "tbody");
  const row = (cells, cls, idx) => {
    const tr = add(body, "tr", undefined, cls);
    cells.forEach((c, k) => {
      const td = add(tr, "td");
      if (k === 0 && idx >= 0) add(td, "span", undefined, "dot").style.background = routeColor(idx);
      td.appendChild(document.createTextNode(String(c)));
    });
  };
  row([
    `${bestLetter ? bestLetter + " - " : ""}${rec.recommended_route}`,
    rec.safety_score, rec.travel_time_minutes, rec.distance_km,
    rec.traffic_score, rec.crime_score, rec.protest_risk, rec.weather_risk,
    `${Math.round(rec.confidence * 100)}%`, rec.route_score,
  ], "best", bestIdx);
  (rec.alternatives || []).forEach((a, i) => {
    row([
      `${altLetters[i] ? altLetters[i] + " - " : ""}${a.summary}`,
      "-", a.travel_time_minutes, a.distance_km, "-", "-", "-", "-", "-", a.route_score,
    ], undefined, altIdx[i] === undefined ? -1 : altIdx[i]);
  });

  const w = add(card, "div", undefined, "weights");
  add(w, "b", "Weights:");
  WEIGHTS.forEach(([k, v]) => add(w, "span", `${k} ${v}%`));

  const list = (title, items) => {
    if (!items || !items.length) return;
    add(card, "h4", title);
    const ul = add(card, "ul");
    items.forEach((t) => add(ul, "li", t));
  };
  list("Why this route", rec.reasons);
  list("Caveats", rec.warnings);
  scrollDown();
}

/* ---------- Chat ---------- */
async function send() {
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  bubble(text, "user");
  const wait = pendingSteps();
  sendBtn.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (_) {}
      throw new Error(msg);
    }
    const data = await res.json();
    wait.stop();
    showSteps(data.steps);
    if (data.type === "route") {
      showResult(data.recommendation, data.map);
      drawMap(data.map);
    }
    bubble(data.message, "bot", "SafeRoute Agent");
  } catch (e) {
    wait.stop();
    bubble("Error: " + e.message, "bot err");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener("click", send);
input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

resetBtn.addEventListener("click", async () => {
  try {
    await fetch("/api/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch (_) {}
  sessionId = newId();
  log.replaceChildren();
  clearMap();
  greet();
});

/* ---------- Voice input (only shown where the browser supports it) ---------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  micBtn.hidden = false;
  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = false;
  rec.onresult = (e) => { input.value = e.results[0][0].transcript; input.focus(); };
  rec.onend = () => micBtn.classList.remove("on");
  rec.onerror = () => micBtn.classList.remove("on");
  micBtn.addEventListener("click", () => {
    if (micBtn.classList.contains("on")) { rec.stop(); return; }
    micBtn.classList.add("on");
    try { rec.start(); } catch (_) { micBtn.classList.remove("on"); }
  });
}

greet();