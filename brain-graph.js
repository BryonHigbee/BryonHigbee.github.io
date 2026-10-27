// DiskAGI Brain — interactive 3D brain graph (three.js).
// Renders the sampled, brain-shaped note graph from brain.json: orbit/zoom controls,
// domain legend filtering, hover tooltips, click-to-inspect, search, and a growth
// scrubber that replays the Brain expanding from 0 to the live note count.
import * as THREE from "./vendor/three.module.min.js";

const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const fmt = (n) => Number(n).toLocaleString("en-US");
const TYPE_NAMES = ["chapter", "concept", "book", "author", "news", "theme"];
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const stage = document.getElementById("brain-stage");
const canvas = document.getElementById("brain-canvas");
const tip = document.getElementById("brain-tip");
const panel = document.getElementById("brain-panel");
const legend = document.getElementById("brain-legend");
const scrub = document.getElementById("brain-scrub");
const countEl = document.getElementById("brain-count");
const searchEl = document.getElementById("brain-search");
const replayBtn = document.getElementById("brain-replay");
const scaleNote = document.getElementById("brain-scale-note");

const domainColor = (i) => {
  const h = (i * 222.5) % 360;
  return new THREE.Color(`hsl(${h}, ${i === 16 ? 8 : 70}%, ${i === 16 ? 55 : 64}%)`);
};

function spriteTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.55)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let scene, camera, renderer, points, linkLines, hoverSprite, selLines;
let N = 0, meta = null, domains = [];
let nodesPos, reveal, adjacency, baseColors, domainArr;
let NODES = [], LINKS = [];
let progress = 0, growAnim = null;
const sel = { index: -1 };
const hiddenDomains = new Set();
let uniforms = null;

// ---- orbit controls (rotate / zoom / inertia / idle auto-rotate)
const orbit = {
  theta: 0.55, phi: 1.22, radius: 7.4, targetRadius: 7.4,
  vTheta: 0, vPhi: 0,
  target: new THREE.Vector3(0, -0.05, 0),
  flyTo: null,
  lastInput: performance.now(),
};
function applyCamera() {
  const sp = Math.sin(orbit.phi), cp = Math.cos(orbit.phi);
  camera.position.set(
    orbit.target.x + orbit.radius * sp * Math.sin(orbit.theta),
    orbit.target.y + orbit.radius * cp,
    orbit.target.z + orbit.radius * sp * Math.cos(orbit.theta)
  );
  camera.lookAt(orbit.target);
}
function bindControls() {
  const pointers = new Map();
  let pinchDist = 0, downX = 0, downY = 0, dragMoved = false;

  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    downX = e.clientX; downY = e.clientY; dragMoved = false;
    orbit.lastInput = performance.now();
  });
  canvas.addEventListener("pointermove", (e) => {
    orbit.lastInput = performance.now();
    if (!pointers.has(e.pointerId)) { updateHover(e); return; }
    const p = pointers.get(e.pointerId);
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) dragMoved = true;
    if (dragMoved) setHover(-1, e);
    if (pointers.size === 1) {
      orbit.vTheta = dx * 0.0042;
      orbit.vPhi = -dy * 0.0032;
      orbit.theta += orbit.vTheta;
      orbit.phi = clamp(orbit.phi + orbit.vPhi, 0.12, Math.PI - 0.12);
    } else if (pointers.size === 2) {
      const pts = [...pointers.values()];
      const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (pinchDist > 0) orbit.targetRadius = clamp(orbit.targetRadius * (pinchDist / d), 2.1, 16);
      pinchDist = d;
    }
  });
  const up = (e) => {
    pointers.delete(e.pointerId);
    pinchDist = 0;
  };
  canvas.addEventListener("pointerup", (e) => {
    up(e);
    if (!dragMoved) {
      updateHover(e);
      if (hoverIdx >= 0) select(hoverIdx); else deselect();
    }
  });
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("pointerleave", () => setHover(-1));
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    orbit.lastInput = performance.now();
    orbit.targetRadius = clamp(orbit.targetRadius * Math.exp(e.deltaY * 0.0011), 2.1, 16);
  }, { passive: false });
}

// ---- graph build
function buildGraph(data) {
  meta = data.meta;
  domains = data.domains.map((d, i) => ({ ...d, i, color: domainColor(i) }));
  NODES = data.nodes;
  LINKS = data.links;
  N = NODES.length;
  nodesPos = new Float32Array(N * 3);
  reveal = new Float32Array(N);
  baseColors = new Float32Array(N * 3);
  domainArr = new Float32Array(N);
  const sizeArr = new Float32Array(N);
  adjacency = NODES.map(() => []);

  NODES.forEach((n, i) => {
    nodesPos[i * 3] = n[5]; nodesPos[i * 3 + 1] = n[6]; nodesPos[i * 3 + 2] = n[7];
    reveal[i] = N > 1 ? i / (N - 1) : 1;
    const c = domains[n[2]] ? domains[n[2]].color : domainColor(16);
    baseColors[i * 3] = c.r; baseColors[i * 3 + 1] = c.g; baseColors[i * 3 + 2] = c.b;
    domainArr[i] = n[2];
    sizeArr[i] = 2.1 + Math.min(3.4, Math.log2(1 + n[4]) * 0.85);
  });

  const lpos = new Float32Array(LINKS.length * 6);
  const lcol = new Float32Array(LINKS.length * 6);
  const lrev = new Float32Array(LINKS.length * 2);
  LINKS.forEach((l, j) => {
    const [a, b, kind] = l;
    lpos.set(
      [nodesPos[a * 3], nodesPos[a * 3 + 1], nodesPos[a * 3 + 2],
       nodesPos[b * 3], nodesPos[b * 3 + 1], nodesPos[b * 3 + 2]], j * 6
    );
    const boost = kind === 0 ? 0.75 : 1.0;
    lcol.set(
      [baseColors[a * 3] * boost, baseColors[a * 3 + 1] * boost, baseColors[a * 3 + 2] * boost,
       baseColors[b * 3] * boost, baseColors[b * 3 + 1] * boost, baseColors[b * 3 + 2] * boost], j * 6
    );
    const rv = Math.max(reveal[a], reveal[b]);
    lrev[j * 2] = rv; lrev[j * 2 + 1] = rv;
    adjacency[a].push(j); adjacency[b].push(j);
  });

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(nodesPos, 3));
  geo.setAttribute("aColor", new THREE.BufferAttribute(baseColors, 3));
  geo.setAttribute("aReveal", new THREE.BufferAttribute(reveal, 1));
  geo.setAttribute("aDomain", new THREE.BufferAttribute(domainArr, 1));
  geo.setAttribute("aSize", new THREE.BufferAttribute(sizeArr, 1));

  uniforms = {
    uProgress: { value: progress },
    uTime: { value: 0 },
    uPixelRatio: { value: Math.min(devicePixelRatio, 2) },
    uMap: { value: spriteTexture() },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute vec3 aColor;
      attribute float aReveal, aDomain, aSize;
      uniform float uProgress, uTime, uPixelRatio;
      varying vec3 vColor; varying float vKill;
      void main() {
        vKill = step(uProgress, aReveal);
        vColor = aColor;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        float pulse = 1.0 + 0.16 * sin(uTime * 2.0 + position.x * 3.7 + position.y * 5.1);
        gl_PointSize = aSize * uPixelRatio * pulse * (140.0 / -mv.z);
        if (vKill > 0.5) gl_PointSize = 0.0;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform sampler2D uMap;
      varying vec3 vColor; varying float vKill;
      void main() {
        if (vKill > 0.5) discard;
        vec4 tex = texture2D(uMap, gl_PointCoord);
        float core = smoothstep(0.0, 0.35, tex.a);
        gl_FragColor = vec4(vColor * (0.85 + core * 0.9), tex.a * 0.95);
      }`,
  });
  points = new THREE.Points(geo, mat);
  scene.add(points);

  const lgeo = new THREE.BufferGeometry();
  lgeo.setAttribute("position", new THREE.BufferAttribute(lpos, 3));
  lgeo.setAttribute("aColor", new THREE.BufferAttribute(lcol, 3));
  lgeo.setAttribute("aReveal", new THREE.BufferAttribute(lrev, 1));
  const luni = { uProgress: uniforms.uProgress, uDim: { value: 0 } };
  linkLines = new THREE.LineSegments(lgeo, new THREE.ShaderMaterial({
    uniforms: luni,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute vec3 aColor; attribute float aReveal;
      uniform float uProgress;
      varying vec3 vColor; varying float vKill;
      void main() {
        vKill = step(uProgress, aReveal);
        vColor = aColor;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      uniform float uDim;
      varying vec3 vColor; varying float vKill;
      void main() {
        if (vKill > 0.5) discard;
        gl_FragColor = vec4(vColor, mix(0.14, 0.8, uDim));
      }`,
  }));
  linkLines.userData.uniforms = luni;
  scene.add(linkLines);

  hoverSprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: uniforms.uMap.value, color: 0xffffff, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  hoverSprite.scale.setScalar(0.0);
  scene.add(hoverSprite);

  selLines = new THREE.LineSegments(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  selLines.visible = false;
  scene.add(selLines);

  buildLegend();
}

function buildLegend() {
  const frag = document.createDocumentFragment();
  domains.forEach((d) => {
    const b = document.createElement("button");
    b.className = "legend-item";
    b.type = "button";
    b.setAttribute("aria-pressed", "true");
    b.innerHTML = `<span class="legend-dot" style="background:#${d.color.getHexString()}"></span>${escapeHtml(d.name)}<span class="legend-count">${fmt(d.count)}</span>`;
    b.addEventListener("click", () => {
      if (hiddenDomains.has(d.i)) hiddenDomains.delete(d.i); else hiddenDomains.add(d.i);
      b.setAttribute("aria-pressed", String(!hiddenDomains.has(d.i)));
      b.classList.toggle("legend-item--off", hiddenDomains.has(d.i));
      applyDomainFilter();
    });
    frag.appendChild(b);
  });
  legend.replaceChildren(frag);
}

function applyDomainFilter() {
  const colAttr = points.geometry.getAttribute("aColor");
  const revAttr = points.geometry.getAttribute("aReveal");
  for (let i = 0; i < N; i++) {
    const off = hiddenDomains.has(domainArr[i]);
    const f = off ? 0.04 : 1.0;
    colAttr.setXYZ(i, baseColors[i * 3] * f, baseColors[i * 3 + 1] * f, baseColors[i * 3 + 2] * f);
    revAttr.setX(i, off ? 2 : reveal[i]);
  }
  const lcol = linkLines.geometry.getAttribute("aColor");
  const lrev = linkLines.geometry.getAttribute("aReveal");
  LINKS.forEach((l, j) => {
    const [a, b] = l;
    const on = !hiddenDomains.has(domainArr[a]) && !hiddenDomains.has(domainArr[b]);
    const rv = on ? Math.max(reveal[a], reveal[b]) : 2;
    const boost = on ? 1 : 0.05;
    lrev.setX(j * 2, rv); lrev.setX(j * 2 + 1, rv);
    lcol.setXYZ(j * 2, baseColors[a * 3] * boost, baseColors[a * 3 + 1] * boost, baseColors[a * 3 + 2] * boost);
    lcol.setXYZ(j * 2 + 1, baseColors[b * 3] * boost, baseColors[b * 3 + 1] * boost, baseColors[b * 3 + 2] * boost);
  });
  colAttr.needsUpdate = true;
  revAttr.needsUpdate = true;
  lrev.needsUpdate = true;
  lcol.needsUpdate = true;
}

// ---- hover / select
const raycaster = new THREE.Raycaster();
raycaster.params.Points = { threshold: 0.06 };
const pointerV = new THREE.Vector2();
let hoverIdx = -1;

function updateHover(e) {
  const r = canvas.getBoundingClientRect();
  pointerV.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  raycaster.setFromCamera(pointerV, camera);
  const hits = raycaster.intersectObject(points);
  setHover(hits.length ? hits[0].index : -1, e);
}

function setHover(i, e) {
  hoverIdx = i;
  if (i >= 0) {
    const n = NODES[i];
    const d = domains[n[2]] || { name: "Other" };
    tip.innerHTML = `<strong>${escapeHtml(n[1])}</strong><span>${escapeHtml(d.name)} · ${TYPE_NAMES[n[3]] ?? "note"} · ${fmt(n[4])} links</span>`;
    tip.style.opacity = "1";
    if (e) {
      const r = stage.getBoundingClientRect();
      tip.style.left = clamp(e.clientX - r.left + 14, 8, r.width - 250) + "px";
      tip.style.top = clamp(e.clientY - r.top - 14, 8, r.height - 60) + "px";
    }
    hoverSprite.position.set(nodesPos[i * 3], nodesPos[i * 3 + 1], nodesPos[i * 3 + 2]);
    hoverSprite.scale.setScalar(0.22);
    canvas.style.cursor = "pointer";
  } else {
    tip.style.opacity = "0";
    hoverSprite.scale.setScalar(0.0);
    canvas.style.cursor = "grab";
  }
}

function select(i) {
  sel.index = i;
  const n = NODES[i];
  const d = domains[n[2]] || { name: "Other", color: domainColor(16) };
  const linked = adjacency[i].length;
  panel.innerHTML = `
    <button class="brain-panel-close" type="button" aria-label="Close">×</button>
    <span class="brain-panel-domain"><i style="background:#${d.color.getHexString()}"></i>${escapeHtml(d.name)}</span>
    <h3>${escapeHtml(n[1])}</h3>
    <dl>
      <div><dt>Type</dt><dd>${TYPE_NAMES[n[3]] ?? "note"}</dd></div>
      <div><dt>Connections</dt><dd>${fmt(n[4])} in sample · note #${fmt(n[0])}</dd></div>
      <div><dt>Live Brain</dt><dd>1 of ${fmt(meta.notes)} notes</dd></div>
    </dl>`;
  panel.classList.add("open");
  panel.querySelector(".brain-panel-close").addEventListener("click", deselect);

  const g = linkLines.geometry.getAttribute("position");
  const pos = [];
  for (const j of adjacency[i]) {
    pos.push(g.getX(j * 2), g.getY(j * 2), g.getZ(j * 2), g.getX(j * 2 + 1), g.getY(j * 2 + 1), g.getZ(j * 2 + 1));
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  selLines.geometry.dispose();
  selLines.geometry = sg;
  selLines.visible = linked > 0;
  linkLines.userData.uniforms.uDim.value = linked > 0 ? 1 : 0;
  orbit.flyTo = {
    p: new THREE.Vector3(nodesPos[i * 3], nodesPos[i * 3 + 1], nodesPos[i * 3 + 2]),
    r: Math.min(orbit.targetRadius, 5.2),
    t0: performance.now(),
    from: orbit.target.clone(),
  };
}

function deselect() {
  sel.index = -1;
  panel.classList.remove("open");
  selLines.visible = false;
  linkLines.userData.uniforms.uDim.value = 0;
}

// ---- search
function runSearch() {
  const q = searchEl.value.trim().toLowerCase();
  searchEl.removeAttribute("data-hit");
  if (!q) return;
  let hit = NODES.findIndex((n, i) => n[1].toLowerCase().includes(q) && reveal[i] <= progress + 1e-6);
  if (hit < 0) hit = NODES.findIndex((n) => n[1].toLowerCase().includes(q));
  if (hit >= 0) select(hit);
  searchEl.setAttribute("data-hit", hit >= 0 ? "1" : "0");
}
searchEl.addEventListener("change", runSearch);
searchEl.addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });

// ---- growth scrubber
function setProgress(p) {
  if (!uniforms) return;
  progress = clamp(p, 0, 1);
  uniforms.uProgress.value = progress;
  linkLines.userData.uniforms.uProgress.value = progress;
  scrub.value = String(Math.round(progress * 1000));
  countEl.textContent = fmt(Math.round(progress * (meta?.notes ?? 0)));
  scaleNote.textContent = `rendering ${fmt(Math.round(progress * N))} of ${fmt(N)} sampled notes · live brain ${fmt(meta?.notes ?? 0)} notes and growing`;
}
function replay() {
  if (reduceMotion) { setProgress(1); return; }
  growAnim = { t0: performance.now(), dur: 3400 };
}
scrub.addEventListener("input", () => { growAnim = null; setProgress(scrub.value / 1000); });
replayBtn.addEventListener("click", replay);

// ---- resize + loop
function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);

function startLoop() {
  renderer.setAnimationLoop(() => {
  if (document.hidden) return;
  const now = performance.now();
  if (growAnim) {
    const k = clamp((now - growAnim.t0) / growAnim.dur, 0, 1);
    setProgress(1 - Math.pow(1 - k, 3));
    if (k >= 1) growAnim = null;
  }
  if (now - orbit.lastInput > 4200 && !reduceMotion) orbit.theta += 0.0016;
  orbit.theta += orbit.vTheta *= 0.90;
  orbit.phi = clamp(orbit.phi + (orbit.vPhi *= 0.90), 0.12, Math.PI - 0.12);
  orbit.radius += (orbit.targetRadius - orbit.radius) * 0.08;
  if (orbit.flyTo) {
    const k = clamp((now - orbit.flyTo.t0) / 700, 0, 1);
    orbit.target.lerpVectors(orbit.flyTo.from, orbit.flyTo.p, k * k * (3 - 2 * k));
    if (k >= 1) orbit.flyTo = null;
  }
  uniforms.uTime.value = now / 1000;
  applyCamera();
  renderer.render(scene, camera);
  });
}

// ---- boot
fetch("brain.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
  .then((data) => {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setClearColor(0x050b18, 1);
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    bindControls();
    buildGraph(data);
    resize();
    startLoop();
    setProgress(reduceMotion ? 1 : 0);
    replay();
    document.getElementById("brain-fallback").hidden = true;
  })
  .catch((err) => {
    const fb = document.getElementById("brain-fallback");
    fb.hidden = false;
    fb.textContent = `3D Brain unavailable (${err.message}).`;
  });
