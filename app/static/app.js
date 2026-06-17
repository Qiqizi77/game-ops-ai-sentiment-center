const state = {
  meta: null,
  charts: {},
  selectedVersions: ["3.0", "2.8", "2.1"],
};

const palette = {
  red: "#e94560",
  yellow: "#f6c85f",
  green: "#41d3a2",
  cyan: "#4cc9f0",
  blue: "#5b8def",
  violet: "#b388ff",
  gray: "#94a3b8",
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", async () => {
  lucide.createIcons();
  await loadMeta();
  bindEvents();
  await refreshAll();
});

async function loadMeta() {
  state.meta = await getJSON("/api/meta");
  fillSelect($("versionSelect"), state.meta.versions.map((item) => ({
    value: item.version,
    label: `${item.version} ${item.name}`,
  })));
  fillSelect($("platformSelect"), [
    { value: "all", label: "全部平台" },
    ...Object.entries(state.meta.platforms).map(([value, label]) => ({ value, label })),
  ]);
  fillSelect($("categorySelect"), [
    { value: "all", label: "全部分类" },
    ...state.meta.categories.map((label) => ({ value: label, label })),
  ]);
  renderCompareChecks();
}

function bindEvents() {
  ["versionSelect", "rangeSelect", "platformSelect", "categorySelect"].forEach((id) => {
    $(id).addEventListener("change", refreshAll);
  });
  $("refreshButton").addEventListener("click", refreshAll);
  $("searchButton").addEventListener("click", loadPosts);
  $("searchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadPosts();
  });
  $("exportButton").addEventListener("click", () => {
    window.location.href = "/api/export/daily-report";
  });
  $("copyReportButton").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("dailyReport").textContent);
    toast("日报已复制");
  });
  $("collectButton").addEventListener("click", collectNow);
  $("agentRunButton").addEventListener("click", runAgents);
}

async function refreshAll() {
  await Promise.all([
    loadV2AgentCenter(),
    loadV2Nlp(),
    loadV2Enterprise(),
    loadVarsapura(),
    loadOverview(),
    loadVersion(),
    loadComparison(),
    loadPosts(),
    loadReport(),
  ]);
  lucide.createIcons();
}

async function loadOverview() {
  const query = buildQuery({
    version: $("versionSelect").value,
    platform: $("platformSelect").value,
    category: $("categorySelect").value,
    range: $("rangeSelect").value,
  });
  const data = await getJSON(`/api/overview?${query}`);
  $("totalComments").textContent = formatNumber(data.total_comments);
  $("avgSentiment").textContent = data.avg_sentiment.toFixed(1);
  $("negativeCount").textContent = formatNumber(data.negative_count);
  $("highWarningCount").textContent = formatNumber(data.high_warning_count);
  renderSentimentChart(data.sentiment_trend);
  renderPlatformChart(data.platform_distribution);
}

async function loadVersion() {
  const version = $("versionSelect").value;
  const data = await getJSON(`/api/version/${encodeURIComponent(version)}?range=${$("rangeSelect").value}`);
  $("currentVersionName").textContent = `${data.version} ${data.name}`;
  $("currentVersionDate").textContent = `Release ${data.release_date}`;
  $("earlyFeedbackBadge").textContent = `初期反馈 ${data.early_feedback_count}`;
  $("versionDays").textContent = `${data.days_since_release}天`;
  $("versionComments").textContent = formatNumber(data.total_comments);
  $("versionSentiment").textContent = data.avg_sentiment.toFixed(1);
  $("versionPositive").textContent = `${data.positive_rate.toFixed(1)}%`;
  $("topIssues").innerHTML = (data.top_issues.length ? data.top_issues : ["暂无集中问题"]).map((issue) => (
    `<li class="rounded-md bg-[#0d1730] px-3 py-2">${escapeHTML(issue)}</li>`
  )).join("");
}

async function loadComparison() {
  const versionsQuery = state.selectedVersions.map((version) => `versions=${encodeURIComponent(version)}`).join("&");
  const data = await getJSON(`/api/version-comparison?${versionsQuery}&range=${$("rangeSelect").value}`);
  renderLifecycleChart(data.lifecycle_curves);
  $("comparisonRows").innerHTML = data.versions.map((item) => `
    <tr>
      <td><span class="font-semibold">${escapeHTML(item.version)}</span><span class="ml-2 text-slate-400">${escapeHTML(item.name)}</span></td>
      <td><span class="badge badge-cyan">${escapeHTML(item.phase)}</span></td>
      <td>${item.days_since_release}天</td>
      <td>${item.remaining_days}天</td>
      <td>${formatNumber(item.total_comments)}</td>
      <td>${formatNumber(item.peak_comments)}</td>
      <td><span class="${sentimentClass(item.sentiment_day1)}">${Number(item.sentiment_day1).toFixed(1)}</span></td>
      <td><span class="${sentimentClass(item.sentiment_day7)}">${Number(item.sentiment_day7).toFixed(1)}</span></td>
      <td>${trendBadge(item.sentiment_trend)}</td>
      <td>${item.bug_rate.toFixed(1)}%</td>
      <td>${item.complaint_rate.toFixed(1)}%</td>
      <td>${item.positive_rate.toFixed(1)}%</td>
    </tr>
  `).join("");
}

async function loadPosts() {
  const query = buildQuery({
    version: $("versionSelect").value,
    platform: $("platformSelect").value,
    category: $("categorySelect").value,
    range: $("rangeSelect").value,
    q: $("searchInput").value.trim(),
    limit: 80,
  });
  const posts = await getJSON(`/api/posts?${query}`);
  $("postRows").innerHTML = posts.map((post) => `
    <tr>
      <td>${escapeHTML(post.platform_name)}</td>
      <td><span class="badge badge-cyan">${escapeHTML(post.game_version)}</span></td>
      <td>${categoryBadge(post.category)}</td>
      <td><span class="${sentimentClass(post.sentiment_score)}">${post.sentiment_score.toFixed(1)}</span></td>
      <td>${warningBadge(post.warning_level)}</td>
      <td>
        <div class="max-w-2xl">
          <a class="font-semibold text-white hover:text-[#4cc9f0]" href="${escapeAttr(post.url)}" target="_blank" rel="noreferrer">${escapeHTML(post.title)}</a>
          <p class="mt-1 line-clamp-2 text-sm text-slate-400">${escapeHTML(post.content)}</p>
          <p class="mt-1 text-xs text-slate-500">${escapeHTML(post.author)} · ${formatDate(post.publish_time)}</p>
        </div>
      </td>
      <td class="text-sm text-slate-300">赞 ${formatNumber(post.like_count)}<br />评 ${formatNumber(post.reply_count)}</td>
    </tr>
  `).join("");
}

async function loadReport() {
  const data = await getJSON("/api/daily-report");
  $("dailyReport").textContent = data.markdown;
}

async function collectNow() {
  const button = $("collectButton");
  button.disabled = true;
  button.innerHTML = '<i data-lucide="loader-2"></i><span>采集中</span>';
  lucide.createIcons();
  try {
    const result = await postJSON("/api/collect/run", {});
    toast(`采集完成：新增 ${result.inserted} 条`);
    await refreshAll();
  } catch (error) {
    toast(`采集失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.innerHTML = '<i data-lucide="radio"></i><span>采集</span>';
    lucide.createIcons();
  }
}

async function runAgents() {
  const button = $("agentRunButton");
  button.disabled = true;
  button.innerHTML = '<i data-lucide="loader-2"></i><span>运行中</span>';
  lucide.createIcons();
  try {
    const result = await postJSON("/api/v2/agents/run", {});
    toast(`Agent 链路完成：${result.results.length} 个节点`);
    await refreshAll();
  } catch (error) {
    toast(`Agent 运行失败：${error.message}`);
  } finally {
    button.disabled = false;
    button.innerHTML = '<i data-lucide="bot"></i><span>Agent</span>';
    lucide.createIcons();
  }
}

async function loadV2AgentCenter() {
  const [agentData, insights] = await Promise.all([
    getJSON("/api/v2/agents"),
    getJSON("/api/v2/analysis/insights?limit=120"),
  ]);
  $("agentCards").innerHTML = agentData.agents.map((agent) => `
    <article class="metric-card p-4">
      <div class="flex items-center justify-between text-slate-400">
        <span>${agentName(agent.agent_type)}</span>
        ${statusBadge(agent.status)}
      </div>
      <div class="mt-3 text-2xl font-black">${Math.round(agent.success_rate * 100)}%</div>
      <div class="mt-2 text-sm text-slate-400">成功 ${agent.success_count} · 失败 ${agent.failure_count} · ${Math.round(agent.avg_latency_ms)}ms</div>
    </article>
  `).join("");
  $("agentMessageRows").innerHTML = agentData.recent_messages.map((message) => `
    <tr>
      <td>${formatDate(message.created_at)}</td>
      <td>${escapeHTML(message.source_agent)}</td>
      <td>${escapeHTML(message.target_agent)}</td>
      <td>${escapeHTML(message.message_type)}</td>
      <td>${statusBadge(message.status)}</td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="text-slate-400">暂无消息</td></tr>';
  renderEmotionChart(insights);
}

async function loadV2Nlp() {
  const [clusters, keywords] = await Promise.all([
    getJSON("/api/v2/nlp/clusters?limit=8"),
    getJSON("/api/v2/nlp/keywords?limit=20"),
  ]);
  $("clusterList").innerHTML = clusters.length ? clusters.map((cluster) => `
    <article class="rounded-md bg-[#0d1730] p-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="font-semibold">${escapeHTML(cluster.label)}</div>
          <div class="mt-1 text-sm text-slate-400">${cluster.size} 条 · 近2小时 ${cluster.growth_2h} 条 · 情绪 ${Number(cluster.avg_sentiment).toFixed(1)}</div>
        </div>
        ${warningBadge(cluster.severity)}
      </div>
      <div class="mt-3 flex flex-wrap gap-2">${cluster.keywords.map((item) => `<span class="badge badge-cyan">${escapeHTML(item)}</span>`).join("")}</div>
    </article>
  `).join("") : '<div class="text-sm text-slate-400">暂无稳定聚类</div>';
  $("keywordCloud").innerHTML = keywords.keywords.map((item, index) => `
    <span class="badge ${index < 5 ? "badge-red" : "badge-cyan"}" style="font-size:${Math.min(20, 12 + item.score / 3)}px">${escapeHTML(item.keyword)}</span>
  `).join("");
  $("newTerms").innerHTML = keywords.new_terms.map((item) => `<span class="badge badge-yellow">${escapeHTML(item.keyword)}</span>`).join("") || '<span class="text-sm text-slate-400">暂无</span>';
}

async function loadV2Enterprise() {
  const [monitoring, alerts, workOrders] = await Promise.all([
    getJSON("/api/v2/monitoring"),
    getJSON("/api/v2/alerts?status=open&limit=12"),
    getJSON("/api/v2/work-orders"),
  ]);
  $("systemHealth").textContent = monitoring.system_health;
  $("systemHealth").className = `mt-2 text-2xl font-black ${monitoring.system_health === "healthy" ? "text-[#41d3a2]" : "text-[#f6c85f]"}`;
  $("openAlerts").textContent = monitoring.open_alerts;
  $("duplicateRate").textContent = `${monitoring.data_quality.duplicate_rate}%`;
  $("emptyRate").textContent = `${monitoring.data_quality.empty_content_rate}%`;
  $("alertRows").innerHTML = alerts.map((alert) => `
    <tr>
      <td>${warningBadge(alert.level)}</td>
      <td>${escapeHTML(alert.title)}</td>
      <td>${escapeHTML(alert.reason)}</td>
      <td>${escapeHTML(alert.push_channel)}</td>
    </tr>
  `).join("") || '<tr><td colspan="4" class="text-slate-400">暂无开放告警</td></tr>';
  $("workOrders").innerHTML = workOrders.slice(0, 5).map((order) => `
    <div class="rounded-md bg-[#0d1730] px-3 py-2 text-sm">
      <div class="font-semibold">${escapeHTML(order.external_ref)} · ${escapeHTML(order.priority)}</div>
      <div class="mt-1 text-slate-400">${escapeHTML(order.title)}</div>
    </div>
  `).join("") || '<div class="text-sm text-slate-400">暂无工单</div>';
}

async function loadVarsapura() {
  const data = await getJSON("/api/v2/varsapura");
  $("varsapuraDimensions").innerHTML = data.special_dimensions.map((item) => `<span class="badge badge-cyan">${escapeHTML(item)}</span>`).join("");
  $("varsapuraRegions").innerHTML = data.global_launch.regions.map((item) => `<span class="badge badge-yellow">${escapeHTML(item)}</span>`).join("");
  $("varsapuraWorkflows").innerHTML = data.ai_workflows.map((item) => `<li class="rounded-md bg-[#0d1730] px-3 py-2">${escapeHTML(item)}</li>`).join("");
}

function renderCompareChecks() {
  $("compareChecks").innerHTML = state.meta.versions.slice(0, 9).map((item) => `
    <label class="ghost-button cursor-pointer">
      <input class="compare-check accent-[#e94560]" type="checkbox" value="${escapeAttr(item.version)}" ${state.selectedVersions.includes(item.version) ? "checked" : ""} />
      <span>${escapeHTML(item.version)}</span>
    </label>
  `).join("");
  document.querySelectorAll(".compare-check").forEach((input) => {
    input.addEventListener("change", () => {
      const checked = [...document.querySelectorAll(".compare-check:checked")].map((item) => item.value);
      state.selectedVersions = checked.length ? checked.slice(0, 3) : [$("versionSelect").value];
      document.querySelectorAll(".compare-check").forEach((box) => {
        box.checked = state.selectedVersions.includes(box.value);
      });
      loadComparison();
    });
  });
}

function renderLifecycleChart(curves) {
  const labels = Array.from({ length: 30 }, (_, index) => index + 1);
  const colors = [palette.red, palette.green, palette.yellow, palette.cyan, palette.violet];
  const datasets = curves.map((curve, index) => {
    const pointMap = new Map(curve.points.map((point) => [point.day, point.score]));
    return {
      label: `${curve.version} ${curve.name}`,
      data: labels.map((day) => pointMap.get(day) ?? null),
      borderColor: colors[index % colors.length],
      backgroundColor: colors[index % colors.length],
      tension: 0.32,
      spanGaps: true,
    };
  });
  state.charts.lifecycle = upsertChart("lifecycleChart", state.charts.lifecycle, "line", labels, datasets, {
    scales: {
      x: { title: { display: true, text: "发布后第 N 天", color: "#9fb1d1" } },
      y: { min: 0, max: 10 },
    },
  });
}

function renderSentimentChart(points) {
  state.charts.sentiment = upsertChart("sentimentChart", state.charts.sentiment, "line", points.map((item) => item.date), [{
    label: "平均情绪",
    data: points.map((item) => item.score),
    borderColor: palette.green,
    backgroundColor: "rgba(65, 211, 162, 0.18)",
    tension: 0.32,
    fill: true,
  }], { scales: { y: { min: 0, max: 10 } } });
}

function renderPlatformChart(distribution) {
  const labels = Object.keys(distribution);
  const values = Object.values(distribution);
  state.charts.platform = upsertChart("platformChart", state.charts.platform, "doughnut", labels, [{
    data: values,
    backgroundColor: [palette.red, palette.yellow, palette.green, palette.cyan, palette.blue, palette.violet, palette.gray],
    borderColor: "#16213e",
  }], { cutout: "58%" });
}

function renderEmotionChart(insights) {
  const counts = insights.reduce((acc, item) => {
    acc[item.emotion] = (acc[item.emotion] || 0) + 1;
    return acc;
  }, {});
  state.charts.emotion = upsertChart("emotionChart", state.charts.emotion, "doughnut", Object.keys(counts), [{
    data: Object.values(counts),
    backgroundColor: [palette.red, palette.yellow, palette.gray, palette.green, palette.cyan, palette.violet, palette.blue],
    borderColor: "#16213e",
  }], { cutout: "58%" });
}

function upsertChart(canvasId, oldChart, type, labels, datasets, extraOptions = {}) {
  if (oldChart) oldChart.destroy();
  const context = $(canvasId);
  return new Chart(context, {
    type,
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#d7def0", boxWidth: 12 } },
        tooltip: { mode: "index", intersect: false },
      },
      scales: type === "doughnut" ? undefined : {
        x: { ticks: { color: "#9fb1d1" }, grid: { color: "rgba(255,255,255,0.06)" } },
        y: { ticks: { color: "#9fb1d1" }, grid: { color: "rgba(255,255,255,0.06)" } },
      },
      ...extraOptions,
    },
  });
}

function fillSelect(select, options) {
  select.innerHTML = options.map((item) => `<option value="${escapeAttr(item.value)}">${escapeHTML(item.label)}</option>`).join("");
}

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "all") {
      query.set(key, value);
    }
  });
  return query.toString();
}

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function categoryBadge(category) {
  if (category.includes("BUG")) return `<span class="badge badge-red">${escapeHTML(category)}</span>`;
  if (category.includes("吐槽")) return `<span class="badge badge-yellow">${escapeHTML(category)}</span>`;
  if (category.includes("正面")) return `<span class="badge badge-green">${escapeHTML(category)}</span>`;
  return `<span class="badge badge-cyan">${escapeHTML(category)}</span>`;
}

function warningBadge(level) {
  if (level >= 2) return '<span class="badge badge-red">Level 2</span>';
  if (level === 1) return '<span class="badge badge-yellow">Level 1</span>';
  return '<span class="badge badge-green">Level 0</span>';
}

function statusBadge(status) {
  const normalized = String(status || "");
  if (["idle", "done", "success", "healthy"].includes(normalized)) return `<span class="badge badge-green">${escapeHTML(normalized)}</span>`;
  if (["running", "processing", "pending"].includes(normalized)) return `<span class="badge badge-yellow">${escapeHTML(normalized)}</span>`;
  return `<span class="badge badge-red">${escapeHTML(normalized)}</span>`;
}

function trendBadge(trend) {
  if (trend === "上升") return '<span class="badge badge-green">上升</span>';
  if (trend === "下降") return '<span class="badge badge-red">下降</span>';
  return '<span class="badge badge-yellow">平稳</span>';
}

function agentName(type) {
  return {
    collector: "采集 Agent",
    analyzer: "分析 Agent",
    alert: "预警 Agent",
    reporter: "报告 Agent",
  }[type] || type;
}

function sentimentClass(value) {
  if (value >= 7) return "font-bold text-[#41d3a2]";
  if (value >= 4) return "font-bold text-[#f6c85f]";
  return "font-bold text-[#e94560]";
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
}

function formatDate(value) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHTML(value);
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "fixed bottom-5 right-5 z-50 rounded-md bg-[#e94560] px-4 py-3 text-sm font-semibold text-white shadow-lg";
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 2600);
}
