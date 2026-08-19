/**
 * Netools Web App - Real-Time In-Browser DoH Benchmark & ISP Detector
 * Multi-Protocol DoH Engine: RFC 8484 POST Wireformat, RFC 8484 GET Base64URL, and DoH JSON API.
 * Real-Time Streaming & Parallel Concurrency.
 */

function uint8ArrayToBase64Url(uint8) {
  let binary = "";
  const len = uint8.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(uint8[i]);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function buildDnsQueryPacket(domain, txId = 0x1234, qtype = 1) {
  const cleanDomain = domain.trim().replace(/^\.+|\.+$/g, "");
  const parts = cleanDomain.split(".");
  
  let qnameLen = 0;
  for (const part of parts) {
    qnameLen += 1 + part.length;
  }
  qnameLen += 1;
  
  const buffer = new ArrayBuffer(12 + qnameLen + 4);
  const view = new DataView(buffer);
  const uint8 = new Uint8Array(buffer);
  
  view.setUint16(0, txId, false);
  view.setUint16(2, 0x0100, false);
  view.setUint16(4, 1, false);
  view.setUint16(6, 0, false);
  view.setUint16(8, 0, false);
  view.setUint16(10, 0, false);
  
  let offset = 12;
  for (const part of parts) {
    uint8[offset++] = part.length;
    for (let i = 0; i < part.length; i++) {
      uint8[offset++] = part.charCodeAt(i);
    }
  }
  uint8[offset++] = 0;
  
  view.setUint16(offset, qtype, false);
  view.setUint16(offset + 2, 1, false);
  
  return uint8;
}

// State variables
let currentRegion = "web_ready";
let currentDataset = "indonesia";
let isRunning = false;
let benchmarkResults = [];
let sortState = { col: "score", reverse: false };
let userNetwork = {
  ip: "Detecting...",
  isp: "Detecting...",
  asn: "...",
  location: "Detecting...",
  countryCode: ""
};

document.addEventListener("DOMContentLoaded", () => {
  detectUserNetwork();
  renderProviderList();
});

async function detectUserNetwork() {
  const ipBadge = document.getElementById("user-ip");
  const ispBadge = document.getElementById("user-isp");
  const locBadge = document.getElementById("user-location");

  try {
    const res = await fetch("https://ipapi.co/json/", { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      userNetwork.ip = data.ip || "Unknown";
      userNetwork.isp = data.org || data.asn || "Unknown ISP";
      userNetwork.asn = data.asn || "";
      userNetwork.location = `${data.city || ""}, ${data.country_name || ""}`;
      userNetwork.countryCode = (data.country_code || "").toLowerCase();

      ipBadge.textContent = userNetwork.ip;
      ispBadge.textContent = `${userNetwork.isp} (${userNetwork.asn})`;
      locBadge.textContent = userNetwork.location;
      return;
    }
  } catch (e) {
    console.warn("ipapi fallback error:", e);
  }

  try {
    const cfRes = await fetch("https://cloudflare.com/cdn-cgi/trace");
    if (cfRes.ok) {
      const text = await cfRes.text();
      const lines = text.split("\n");
      const map = {};
      lines.forEach(l => {
        const [k, v] = l.split("=");
        if (k && v) map[k] = v;
      });
      userNetwork.ip = map["ip"] || "Detected";
      userNetwork.location = `${map["loc"] || "Global"} (${map["colo"] || ""})`;
      userNetwork.isp = "Direct Carrier Network";

      ipBadge.textContent = userNetwork.ip;
      ispBadge.textContent = userNetwork.isp;
      locBadge.textContent = userNetwork.location;
    }
  } catch (err) {
    ipBadge.textContent = "Offline / Protected";
    ispBadge.textContent = "Local Network";
    locBadge.textContent = "Local";
  }
}

function getFilteredProviders() {
  return DOH_PROVIDERS.filter(p => {
    if (currentRegion === "web_ready") return p.cors === true;
    if (currentRegion === "all") return true;
    if (currentRegion === "asia") return p.region === "asia" || p.region === "global";
    if (currentRegion === "europe") return p.region === "europe" || p.region === "global";
    if (currentRegion === "north_america") return p.region === "north_america" || p.region === "global";
    if (currentRegion === "security") return p.category === "security";
    if (currentRegion === "adblock") return p.category === "adblock";
    return true;
  });
}

function setRegionFilter(reg) {
  currentRegion = reg;
  document.querySelectorAll(".region-btn").forEach(b => {
    b.classList.remove("bg-sky-600", "text-white", "font-bold");
    b.classList.add("bg-slate-800", "text-slate-300");
  });
  const activeBtn = document.getElementById(`filter-${reg}`);
  if (activeBtn) {
    activeBtn.classList.remove("bg-slate-800", "text-slate-300");
    activeBtn.classList.add("bg-sky-600", "text-white", "font-bold");
  }
  if (!isRunning) {
    renderProviderList();
  }
}

function setDataset(ds) {
  currentDataset = ds;
  document.querySelectorAll(".dataset-btn").forEach(b => {
    b.classList.remove("border-sky-500", "text-sky-400", "bg-sky-950/40");
    b.classList.add("border-slate-700", "text-slate-400");
  });
  const activeBtn = document.getElementById(`ds-${ds}`);
  if (activeBtn) {
    activeBtn.classList.remove("border-slate-700", "text-slate-400");
    activeBtn.classList.add("border-sky-500", "text-sky-400", "bg-sky-950/40");
  }
  const thTld = document.getElementById("th-tld");
  if (thTld) {
    thTld.textContent = ds === "indonesia" ? "🟡 TLD (.id) ↕" : "🟡 TLD (.com) ↕";
  }
}

function renderProviderList() {
  const tbody = document.getElementById("results-tbody");
  tbody.innerHTML = "";
  const list = getFilteredProviders();

  list.forEach((p, idx) => {
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-800 hover:bg-slate-800/40 transition-colors";
    tr.id = `row-${p.id}`;

    const badgeCors = p.cors 
      ? `<span class="ml-1.5 px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Web Ready</span>`
      : `<span class="ml-1.5 px-1.5 py-0.5 text-[9px] rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">Desktop App</span>`;

    tr.innerHTML = `
      <td class="py-3.5 px-4 text-center font-mono text-slate-400">#${idx + 1}</td>
      <td class="py-3.5 px-4">
        <div class="flex items-center gap-2">
          <span class="text-xl">${p.flag}</span>
          <div>
            <div class="font-semibold text-slate-200 flex items-center">${p.name} ${badgeCors}</div>
            <div class="text-xs text-slate-400">${p.country} &bull; ${p.ips[0] || ""}</div>
          </div>
        </div>
      </td>
      <td class="py-3.5 px-4 text-right font-mono text-slate-400" id="cached-${p.id}">-</td>
      <td class="py-3.5 px-4 text-right font-mono text-slate-400" id="uncached-${p.id}">-</td>
      <td class="py-3.5 px-4 text-right font-mono text-slate-400" id="tld-${p.id}">-</td>
      <td class="py-3.5 px-4 text-right font-mono font-bold text-slate-400" id="score-${p.id}">-</td>
      <td class="py-3.5 px-4 text-center" id="bar-${p.id}">
        <span class="text-xs text-slate-500">${p.cors ? 'Ready' : 'Desktop Only'}</span>
      </td>
      <td class="py-3.5 px-4 text-right">
        <button onclick="copyConfig('${p.id}')" class="px-2.5 py-1 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-sky-400 rounded border border-slate-700 transition-all cursor-pointer">
          📋 Copy
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function queryDoH(p, domain, timeoutMs = 2500) {
  if (p.cors === false) return null;

  const packet = buildDnsQueryPacket(domain);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const t0 = performance.now();
  try {
    let res = null;
    if (p.method === "get_b64") {
      const b64 = uint8ArrayToBase64Url(packet);
      res = await fetch(`${p.doh}?dns=${b64}`, {
        method: "GET",
        headers: { "Accept": "application/dns-message" },
        signal: controller.signal
      });
    } else if (p.method === "json") {
      res = await fetch(`${p.doh}?name=${encodeURIComponent(domain)}&type=1`, {
        method: "GET",
        headers: { "Accept": "application/dns-json, application/json" },
        signal: controller.signal
      });
    } else {
      res = await fetch(p.doh, {
        method: "POST",
        headers: { "Content-Type": "application/dns-message", "Accept": "application/dns-message" },
        body: packet,
        signal: controller.signal
      });
    }

    clearTimeout(timeoutId);
    if (res && res.ok) {
      return performance.now() - t0;
    }
  } catch (e) {
    clearTimeout(timeoutId);
  }
  return null;
}

async function testSingleProvider(p, targetDomains) {
  if (p.cors === false) {
    return {
      ...p,
      avgCached: 9999,
      avgUncached: 9999,
      avgTld: 9999,
      grcScore: 9999,
      totalSuccess: 0,
      totalExpected: 1,
      reliability: 0,
      status: "Desktop Only"
    };
  }

  await queryDoH(p, "google.com", 2000);

  const cachedTargets = ["google.com", "youtube.com", "facebook.com"];
  const cachedLats = [];
  for (const dom of cachedTargets) {
    const lat = await queryDoH(p, dom, 2000);
    if (lat !== null) cachedLats.push(lat);
  }

  const uncachedLats = [];
  for (let i = 0; i < 3; i++) {
    const randDom = `bench-${Math.random().toString(36).substring(2, 8)}.example.org`;
    const lat = await queryDoH(p, randDom, 2500);
    if (lat !== null) uncachedLats.push(lat);
  }

  const tldLats = [];
  const sampleTld = targetDomains.slice(0, 6);
  for (const dom of sampleTld) {
    const lat = await queryDoH(p, dom, 2500);
    if (lat !== null) tldLats.push(lat);
  }

  const penaltyMs = 3500;
  const avgCached = cachedLats.length > 0 ? (cachedLats.reduce((a, b) => a + b, 0) / cachedLats.length) : penaltyMs;
  const avgUncached = uncachedLats.length > 0 ? (uncachedLats.reduce((a, b) => a + b, 0) / uncachedLats.length) : penaltyMs;
  const avgTld = tldLats.length > 0 ? (tldLats.reduce((a, b) => a + b, 0) / tldLats.length) : penaltyMs;

  const totalSuccess = cachedLats.length + uncachedLats.length + tldLats.length;
  const totalExpected = cachedTargets.length + 3 + sampleTld.length;
  const reliability = (totalSuccess / totalExpected) * 100;

  const grcScore = (0.45 * avgCached) + (0.35 * avgUncached) + (0.20 * avgTld);

  return {
    ...p,
    avgCached,
    avgUncached,
    avgTld,
    grcScore,
    totalSuccess,
    totalExpected,
    reliability,
    status: reliability >= 75 ? "Stable" : (reliability > 20 ? "Partial" : "Failed")
  };
}

function generateVisualBar(cached, uncached, tld, status) {
  if (status === "Desktop Only") {
    return `<span class="px-2 py-0.5 text-xs rounded bg-slate-800 text-amber-400 border border-slate-700">🖥️ Desktop App</span>`;
  }
  if (status === "Failed") {
    return `<span class="px-2 py-0.5 text-xs rounded bg-red-950/60 text-red-400 border border-red-800">❌ Failed</span>`;
  }
  const cBar = Math.min(4, Math.max(1, Math.floor(cached / 35)));
  const uBar = Math.min(4, Math.max(1, Math.floor(uncached / 45)));
  const tBar = Math.min(4, Math.max(1, Math.floor(tld / 45)));

  return `
    <div class="flex items-center gap-1 justify-center text-xs font-mono">
      <span title="Cached: ${cached.toFixed(1)}ms">${"🟢".repeat(cBar)}</span>
      <span title="Uncached: ${uncached.toFixed(1)}ms">${"🔵".repeat(uBar)}</span>
      <span title="TLD: ${tld.toFixed(1)}ms">${"🟡".repeat(tBar)}</span>
    </div>
  `;
}

function sortTable(col) {
  if (benchmarkResults.length === 0) return;

  if (sortState.col === col) {
    sortState.reverse = !sortState.reverse;
  } else {
    sortState.col = col;
    sortState.reverse = false;
  }

  const rev = sortState.reverse;
  benchmarkResults.sort((a, b) => {
    if (col === "name") {
      return rev ? b.name.localeCompare(a.name) : a.name.localeCompare(b.name);
    } else if (col === "cached") {
      return rev ? b.avgCached - a.avgCached : a.avgCached - b.avgCached;
    } else if (col === "uncached") {
      return rev ? b.avgUncached - a.avgUncached : a.avgUncached - b.avgUncached;
    } else if (col === "tld") {
      return rev ? b.avgTld - a.avgTld : a.avgTld - b.avgTld;
    } else if (col === "score") {
      return rev ? b.grcScore - a.grcScore : a.grcScore - b.grcScore;
    }
    return 0;
  });

  renderSortedResults();
}

// Live Real-Time Parallel Benchmark
async function startBenchmark() {
  if (isRunning) return;
  isRunning = true;
  benchmarkResults = [];

  const startBtn = document.getElementById("btn-start");
  const progressContainer = document.getElementById("progress-container");
  const progressBar = document.getElementById("progress-bar");
  const statusText = document.getElementById("status-text");

  startBtn.disabled = true;
  startBtn.classList.add("opacity-50", "cursor-not-allowed");
  progressContainer.classList.remove("hidden");

  const providers = getFilteredProviders();
  const dataset = DOMAIN_DATASETS[currentDataset] || DOMAIN_DATASETS.indonesia;
  const targetDomains = dataset.domains;

  let completed = 0;
  const total = providers.length;

  statusText.textContent = `⚡ Live Benchmarking ${total} DoH resolvers for ${userNetwork.isp}...`;

  // Parallel worker pool (3 concurrent workers)
  const concurrency = 3;
  let queueIdx = 0;

  async function worker() {
    while (queueIdx < providers.length) {
      const p = providers[queueIdx++];
      const barCell = document.getElementById(`bar-${p.id}`);
      if (barCell) barCell.innerHTML = `<span class="text-xs text-sky-400 animate-pulse">⚡ Live...</span>`;

      const res = await testSingleProvider(p, targetDomains);
      benchmarkResults.push(res);
      completed++;

      const pct = Math.round((completed / total) * 100);
      progressBar.style.width = `${pct}%`;

      // Live update single row
      const isOk = res.status === "Stable" || res.status === "Partial";
      const cCell = document.getElementById(`cached-${p.id}`);
      if (cCell) cCell.textContent = isOk ? `${res.avgCached.toFixed(1)} ms` : (res.status === "Desktop Only" ? "N/A" : "Fail");
      const uCell = document.getElementById(`uncached-${p.id}`);
      if (uCell) uCell.textContent = isOk ? `${res.avgUncached.toFixed(1)} ms` : (res.status === "Desktop Only" ? "N/A" : "Fail");
      const tCell = document.getElementById(`tld-${p.id}`);
      if (tCell) tCell.textContent = isOk ? `${res.avgTld.toFixed(1)} ms` : (res.status === "Desktop Only" ? "N/A" : "Fail");

      const scoreCell = document.getElementById(`score-${p.id}`);
      if (scoreCell) {
        scoreCell.textContent = isOk ? res.grcScore.toFixed(1) : (res.status === "Desktop Only" ? "DESKTOP" : "FAIL");
        scoreCell.className = `py-3.5 px-4 text-right font-mono font-bold ${res.grcScore < 60 ? 'text-emerald-400' : (res.grcScore < 120 ? 'text-amber-400' : 'text-slate-400')}`;
      }

      const bCell = document.getElementById(`bar-${p.id}`);
      if (bCell) bCell.innerHTML = generateVisualBar(res.avgCached, res.avgUncached, res.avgTld, res.status);

      statusText.textContent = `⚡ Live Progress: ${completed}/${total} completed...`;
    }
  }

  const workers = [];
  for (let i = 0; i < concurrency; i++) {
    workers.push(worker());
  }
  await Promise.all(workers);

  // Sort and re-render sorted table
  benchmarkResults.sort((a, b) => {
    if (a.status === "Stable" && b.status !== "Stable") return -1;
    if (b.status === "Stable" && a.status !== "Stable") return 1;
    return a.grcScore - b.grcScore;
  });

  renderSortedResults();
  highlightFastestRecommendation();

  const valid = benchmarkResults.filter(r => r.status === "Stable" || r.status === "Partial");
  if (valid.length > 0) {
    statusText.textContent = `✓ Benchmark finished! Fastest DNS: ${valid[0].name} (${valid[0].grcScore.toFixed(1)} score)`;
  } else {
    statusText.textContent = `✓ Benchmark completed.`;
  }
  startBtn.disabled = false;
  startBtn.classList.remove("opacity-50", "cursor-not-allowed");
  isRunning = false;
}

function renderSortedResults() {
  const tbody = document.getElementById("results-tbody");
  tbody.innerHTML = "";

  const valid = benchmarkResults.filter(r => r.status === "Stable" || r.status === "Partial");

  benchmarkResults.forEach((res, idx) => {
    const isTop1 = valid.length > 0 && res.id === valid[0].id;
    const rankLabel = isTop1 ? "🥇 #1" : (idx === 1 ? "🥈 #2" : (idx === 2 ? "🥉 #3" : `#${idx + 1}`));
    const tr = document.createElement("tr");
    tr.className = `border-b border-slate-800 hover:bg-slate-800/50 transition-colors ${isTop1 ? 'bg-emerald-950/20 border-emerald-900/40' : ''}`;

    const badgeCors = res.cors 
      ? `<span class="ml-1.5 px-1.5 py-0.5 text-[9px] rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Web Ready</span>`
      : `<span class="ml-1.5 px-1.5 py-0.5 text-[9px] rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">Desktop App</span>`;

    const isOk = res.status === "Stable" || res.status === "Partial";

    tr.innerHTML = `
      <td class="py-3.5 px-4 text-center font-mono font-bold ${isTop1 ? 'text-amber-300' : 'text-slate-400'}">${rankLabel}</td>
      <td class="py-3.5 px-4">
        <div class="flex items-center gap-2">
          <span class="text-xl">${res.flag}</span>
          <div>
            <div class="font-semibold text-slate-200 flex items-center">${res.name} ${isTop1 ? '<span class="ml-1.5 px-1.5 py-0.5 text-[10px] rounded bg-emerald-500 text-slate-950 font-bold uppercase">FASTEST</span>' : badgeCors}</div>
            <div class="text-xs text-slate-400">${res.country} &bull; ${res.ips[0] || ""}</div>
          </div>
        </div>
      </td>
      <td class="py-3.5 px-4 text-right font-mono text-emerald-400">${isOk ? res.avgCached.toFixed(1) + ' ms' : 'N/A'}</td>
      <td class="py-3.5 px-4 text-right font-mono text-sky-400">${isOk ? res.avgUncached.toFixed(1) + ' ms' : 'N/A'}</td>
      <td class="py-3.5 px-4 text-right font-mono text-amber-400">${isOk ? res.avgTld.toFixed(1) + ' ms' : 'N/A'}</td>
      <td class="py-3.5 px-4 text-right font-mono font-bold ${res.grcScore < 60 ? 'text-emerald-400' : (res.grcScore < 120 ? 'text-amber-400' : 'text-slate-400')}">
        ${isOk ? res.grcScore.toFixed(1) : (res.status === 'Desktop Only' ? 'DESKTOP' : 'FAIL')}
      </td>
      <td class="py-3.5 px-4 text-center">
        ${generateVisualBar(res.avgCached, res.avgUncached, res.avgTld, res.status)}
      </td>
      <td class="py-3.5 px-4 text-right">
        <button onclick="copyConfig('${res.id}')" class="px-2.5 py-1 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-sky-400 rounded border border-slate-700 transition-all cursor-pointer">
          📋 Copy
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function highlightFastestRecommendation() {
  const valid = benchmarkResults.filter(r => r.status === "Stable" || r.status === "Partial");
  if (valid.length === 0) return;
  const fastest = valid[0];
  const card = document.getElementById("recommendation-card");
  card.classList.remove("hidden");

  document.getElementById("rec-name").textContent = `${fastest.flag} ${fastest.name}`;
  document.getElementById("rec-score").textContent = `${fastest.grcScore.toFixed(1)} ms Score`;
  document.getElementById("rec-ips").textContent = fastest.ips.join(", ");
  document.getElementById("rec-doh").textContent = fastest.doh;
  document.getElementById("rec-desc").textContent = `${fastest.desc} (Optimized for ${userNetwork.isp}).`;
}

function exportSmartMix() {
  const stable = benchmarkResults.filter(r => r.status === "Stable" || r.status === "Partial");
  if (stable.length === 0) {
    alert("Please run benchmark first!");
    return;
  }
  const bestCached = stable.reduce((min, p) => p.avgCached < min.avgCached ? p : min, stable[0]);
  const uncachedList = stable.filter(p => p.id !== bestCached.id);
  const bestUncached = uncachedList.length > 0 ? uncachedList.reduce((min, p) => p.avgUncached < min.avgUncached ? p : min, uncachedList[0]) : bestCached;
  const tldList = stable.filter(p => p.id !== bestCached.id && p.id !== bestUncached.id);
  const bestTld = tldList.length > 0 ? tldList.reduce((min, p) => p.avgTld < min.avgTld ? p : min, tldList[0]) : bestUncached;

  const modal = document.getElementById("config-modal");
  modal.classList.remove("hidden");

  document.getElementById("modal-title").textContent = `🎯 Smart Mix Configuration (Cached + Uncached + TLD)`;
  document.getElementById("modal-linux").textContent = `# DNS 1 (Cached): ${bestCached.name} (${bestCached.ips[0]})\n# DNS 2 (Uncached): ${bestUncached.name} (${bestUncached.ips[0]})\n# DNS 3 (TLD): ${bestTld.name} (${bestTld.ips[0]})\nsudo resolvectl dns $(ip route show default | awk '{print $5}') ${bestCached.ips[0]} ${bestUncached.ips[0]} ${bestTld.ips[0]}\nsudo resolvectl flush-caches`;
  document.getElementById("modal-singbox").textContent = JSON.stringify({
    "dns": {
      "servers": [
        { "tag": "dns-cached", "address": bestCached.doh, "detour": "direct" },
        { "tag": "dns-uncached", "address": bestUncached.doh, "detour": "direct" },
        { "tag": "dns-tld", "address": bestTld.doh, "detour": "direct" }
      ]
    }
  }, null, 2);
  document.getElementById("modal-dnscrypt").textContent = `server_names = ['${bestCached.id}', '${bestUncached.id}', '${bestTld.id}']`;
  document.getElementById("modal-win").textContent = `Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses ("${bestCached.ips[0]}", "${bestUncached.ips[0]}", "${bestTld.ips[0]}")\nClear-DnsClientCache`;
}

function copyConfig(providerId) {
  const p = DOH_PROVIDERS.find(x => x.id === providerId) || benchmarkResults.find(x => x.id === providerId);
  if (!p) return;

  const modal = document.getElementById("config-modal");
  modal.classList.remove("hidden");

  document.getElementById("modal-title").textContent = `Configuration for ${p.name}`;
  document.getElementById("modal-linux").textContent = `sudo resolvectl dns $(ip route show default | awk '{print $5}') ${p.ips.join(" ")}\nsudo resolvectl dnsovertls $(ip route show default | awk '{print $5}') opportunistic\nsudo resolvectl flush-caches`;
  document.getElementById("modal-singbox").textContent = JSON.stringify({
    "tag": `dns-${p.id}`,
    "address": p.doh,
    "detour": "direct"
  }, null, 2);
  document.getElementById("modal-dnscrypt").textContent = `server_names = ['${p.id}']\n\n[static.'${p.id}']\nstamp = '...' # Or use DoH URL directly: ${p.doh}`;
  document.getElementById("modal-win").textContent = `Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses ("${p.ips.join('", "')}")\nClear-DnsClientCache`;
}

function copySnippet(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text);
  alert("✓ Copied to clipboard!");
}

function closeModal() {
  document.getElementById("config-modal").classList.add("hidden");
}
