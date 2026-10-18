const state = {
  page: 1,
  limit: 20,
  health: null,
  summary: null,
  quality: null,
  ordersPage: null,
  errors: [],
  refreshing: false,
  stale: false,
  lastChecked: null,
};

const qualityRuleLabels = {
  duplicate_order_id: "Duplicate order IDs",
  invalid_order_status: "Invalid statuses",
  invalid_total_amount: "Invalid amounts",
  malformed_order_date: "Malformed dates",
  missing_required_fields: "Missing required fields",
};

const elements = {
  refresh: document.querySelector("#refresh-button"),
  overallState: document.querySelector("#overall-state"),
  overallStateLabel: document.querySelector("#overall-state-label"),
  notice: document.querySelector("#notice"),
  search: document.querySelector("#order-search"),
  statusFilter: document.querySelector("#status-filter"),
  pageSize: document.querySelector("#page-size"),
  ordersBody: document.querySelector("#orders-body"),
  tableWrap: document.querySelector("#table-wrap"),
  previous: document.querySelector("#previous-page"),
  next: document.querySelector("#next-page"),
};

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function formatCount(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "short", day: "2-digit",
  }).format(date);
}

function formatAmount(value) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function currentStatus() {
  if (state.refreshing) return ["loading", "REFRESHING"];
  if (state.stale) return ["stale", "STALE SNAPSHOT"];
  if (state.errors.length) {
    const hasPartialData = state.summary || state.quality || state.ordersPage;
    return hasPartialData ? ["partial", "PARTIAL DATA"] : ["error", "DATA UNAVAILABLE"];
  }
  return ["ready", "OPERATIONAL"];
}

function renderStatus() {
  const [stateName, label] = currentStatus();
  elements.overallState.dataset.state = stateName;
  elements.overallStateLabel.textContent = label;
  elements.refresh.disabled = state.refreshing;
  elements.tableWrap.setAttribute("aria-busy", String(state.refreshing));

  if (state.errors.length) {
    elements.notice.hidden = false;
    elements.notice.dataset.kind = state.stale || !state.summary ? "error" : "warning";
    const prefix = state.stale
      ? "Refresh failed. Showing the last successful snapshot. "
      : "Some dashboard data is unavailable. ";
    elements.notice.textContent = `${prefix}${state.errors.join(" ")}`;
  } else {
    elements.notice.hidden = true;
    elements.notice.textContent = "";
  }

  setText("#footer-health", state.health?.status === "ok"
    ? "API connected"
    : state.errors.length ? "API or data source unavailable" : "API connection pending");
  setText("#checked-at", state.lastChecked
    ? `Checked ${new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(state.lastChecked)}`
    : "Not checked");
}

function renderMetrics() {
  const summary = state.summary;
  setText("#input-count", summary ? formatCount(summary.input_count) : "--");
  setText("#accepted-count", summary ? formatCount(summary.accepted_count) : "--");
  setText("#rejected-count", summary ? formatCount(summary.rejected_count) : "--");
  setText("#bronze-count", summary ? formatCount(summary.bronze_row_count) : "--");

  if (summary) {
    const acceptedRate = summary.input_count
      ? Math.round((summary.accepted_count / summary.input_count) * 100)
      : 0;
    setText("#accepted-rate", `${acceptedRate}% of input records`);
    setText("#raw-value", `${formatCount(summary.input_count)} records`);
    setText("#bronze-value", `${formatCount(summary.bronze_row_count)} rows`);
  } else {
    setText("#accepted-rate", "Awaiting quality report");
    setText("#raw-value", "Unavailable");
    setText("#bronze-value", "Unavailable");
  }

  if (state.quality) {
    const { accepted_count: accepted, input_count: input, rejected_count: rejected } = state.quality;
    const percentage = input ? Math.round((accepted / input) * 100) : 0;
    setText("#quality-score", `${percentage}%`);
    setText("#quality-summary", rejected === 0
      ? "All records passed validation"
      : `${formatCount(rejected)} records rejected by validation`);
    setText("#quality-value", rejected === 0 ? "Passed" : `${formatCount(rejected)} rejected`);
    document.querySelector("#quality-step").dataset.state = rejected === 0 ? "ready" : "warning";
    renderQualityRules(state.quality);
  } else {
    setText("#quality-score", "--");
    setText("#quality-summary", "Latest quality report unavailable");
    setText("#quality-value", "Unavailable");
    document.querySelector("#quality-step").dataset.state = "unavailable";
    document.querySelector("#reason-list").innerHTML = '<p class="empty-inline">Quality rules are unavailable.</p>';
  }

  document.querySelector("#raw-step").dataset.state = summary?.input_count ? "ready" : "unavailable";
  document.querySelector("#bronze-step").dataset.state = summary?.bronze_row_count ? "ready" : "unavailable";
}

function renderQualityRules(report) {
  const reasons = Object.entries(report.reason_counts || {});
  const maxCount = Math.max(1, ...reasons.map(([, count]) => Number(count)));
  const list = document.querySelector("#reason-list");
  list.replaceChildren();

  if (!reasons.length) {
    const empty = document.createElement("p");
    empty.className = "empty-inline";
    empty.textContent = "No rule-level counts in this report.";
    list.append(empty);
    return;
  }

  for (const [rule, count] of reasons) {
    const item = document.createElement("div");
    item.className = "reason-item";
    const head = document.createElement("div");
    head.className = "reason-head";
    const name = document.createElement("span");
    name.className = "reason-name";
    name.textContent = qualityRuleLabels[rule] || rule.replaceAll("_", " ");
    const number = document.createElement("span");
    number.className = "reason-count";
    number.textContent = formatCount(count);
    head.append(name, number);

    const track = document.createElement("div");
    track.className = "reason-track";
    track.setAttribute("role", "img");
    track.setAttribute("aria-label", `${name.textContent}: ${formatCount(count)} records`);
    const fill = document.createElement("div");
    fill.className = "reason-fill";
    fill.style.width = `${Math.min(100, (Number(count) / maxCount) * 100)}%`;
    track.append(fill);
    item.append(head, track);
    list.append(item);
  }
}

function filteredOrders() {
  const search = elements.search.value.trim().toLowerCase();
  const status = elements.statusFilter.value;
  const orders = state.ordersPage?.items || [];
  return orders.filter((order) => {
    const matchesSearch = !search
      || order.order_id.toLowerCase().includes(search)
      || order.customer_id.toLowerCase().includes(search);
    return matchesSearch && (!status || order.order_status === status);
  });
}

function renderOrders() {
  const pageData = state.ordersPage;
  const items = filteredOrders();
  elements.ordersBody.replaceChildren();
  setText("#page-count", pageData
    ? `${formatCount(pageData.total)} total orders`
    : "Order data unavailable");
  setText("#pagination-info", pageData
    ? `Page ${pageData.page} · ${items.length} shown on this page`
    : `Page ${state.page}`);
  elements.previous.disabled = !pageData || state.page <= 1 || state.refreshing;
  elements.next.disabled = !pageData || state.page * state.limit >= pageData.total || state.refreshing;

  if (!pageData || !items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.className = "table-message";
    cell.colSpan = 5;
    if (!pageData) {
      cell.textContent = state.refreshing ? "Loading order data" : "Order data is unavailable.";
    } else if (pageData.total === 0) {
      cell.textContent = "No orders are available in the latest Bronze dataset.";
    } else {
      cell.textContent = "No orders on this page match the current filters.";
    }
    row.append(cell);
    elements.ordersBody.append(row);
    return;
  }

  for (const order of items) {
    const row = document.createElement("tr");
    const values = [
      [order.order_id, "order-id"],
      [order.customer_id, ""],
      [formatDate(order.order_date), ""],
    ];
    for (const [value, className] of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (className) cell.className = className;
      row.append(cell);
    }

    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `status-pill status-${order.order_status.toLowerCase()}`;
    status.textContent = order.order_status.toLowerCase();
    statusCell.append(status);
    row.append(statusCell);

    const amount = document.createElement("td");
    amount.className = "amount";
    amount.textContent = formatAmount(order.total_amount);
    row.append(amount);
    elements.ordersBody.append(row);
  }
}

function render() {
  renderStatus();
  renderMetrics();
  renderOrders();
}

async function refreshDashboard() {
  if (state.refreshing) return;
  const hadSnapshot = Boolean(state.summary || state.quality || state.ordersPage);
  state.refreshing = true;
  state.stale = false;
  state.errors = [];
  render();

  const initialResults = await Promise.allSettled([
    fetchJson("/health"),
    fetchJson("/api/v1/data-quality/latest"),
  ]);
  if (initialResults[0].status === "fulfilled") state.health = initialResults[0].value;
  else state.errors.push("Health check failed.");
  if (initialResults[1].status === "fulfilled") state.quality = initialResults[1].value;
  else state.errors.push("Quality report could not be loaded.");

  try {
    state.summary = await fetchJson("/api/v1/metrics/summary");
  } catch {
    state.errors.push("Summary metrics could not be loaded.");
  }

  try {
    state.ordersPage = await fetchJson(`/api/v1/orders?page=${state.page}&limit=${state.limit}`);
  } catch {
    state.errors.push("Orders could not be loaded.");
  }

  state.refreshing = false;
  state.stale = hadSnapshot && state.errors.length > 0;
  if (!state.errors.length || state.summary || state.quality || state.ordersPage) {
    state.lastChecked = new Date();
  }
  render();
}

elements.refresh.addEventListener("click", refreshDashboard);
elements.search.addEventListener("input", renderOrders);
elements.statusFilter.addEventListener("change", renderOrders);
elements.pageSize.addEventListener("change", () => {
  state.limit = Number(elements.pageSize.value);
  state.page = 1;
  refreshDashboard();
});
elements.previous.addEventListener("click", () => {
  if (state.page > 1) {
    state.page -= 1;
    refreshDashboard();
  }
});
elements.next.addEventListener("click", () => {
  if (state.ordersPage && state.page * state.limit < state.ordersPage.total) {
    state.page += 1;
    refreshDashboard();
  }
});

refreshDashboard();