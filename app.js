const items = [];
const meetings = [];
const news = [];

const focusData = {
  meetings: {
    title: "Meetings",
    meta: () => `${meetings.length} scheduled`,
    items: () => meetings.map((meeting) => ({
      id: meeting.id,
      title: meeting.title,
      detail: meeting.detail
    }))
  },
  tasks: {
    title: "Tasks",
    meta: () => `${items.filter((item) => item.type === "task" && item.status !== "dismissed").length} open`,
    items: () => items
      .filter((item) => item.type === "task" && item.status !== "dismissed")
      .map((item) => ({
        id: item.id,
        title: item.title,
        detail: `${item.time} - ${Math.round(item.confidence * 100)}% confidence`
      }))
  },
  news: {
    title: "News Feed",
    meta: () => `${news.length} updates`,
    items: () => news.map((story, index) => ({
      id: `news-${index}`,
      title: story.title,
      detail: story.detail
    }))
  }
};

const typeIcon = {
  task: "T",
  meeting: "M",
  needs_review: "!"
};

const typeLabel = {
  task: "Task",
  meeting: "Meeting",
  needs_review: "Needs review"
};

let focusOrder = ["meetings", "tasks", "news"];
let activeFilter = "all";
let query = "";
let createdFromFilter = "";
let createdToFilter = "";
let dueFromFilter = "";
let dueToFilter = "";
let priorityFilter = "all";
let activeMetricFilter = null;
let selectedCalendarDate = "";
let toastTimer;
let stackMenuOpen = false;
let draggedSection = null;
let openDateMenu = null;
let activeTheme = "light";
let accountStates = {
  gmail: false,
  outlook: false
};
const sourceCounts = {
  gmail: 0,
  outlook: 0
};
const todayIso = "2026-06-27";
const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const queueList = document.querySelector("#queueList");
const searchInput = document.querySelector("#searchInput");
const createdFromFilterInput = document.querySelector("#createdFromFilter");
const createdToFilterInput = document.querySelector("#createdToFilter");
const dueFromFilterInput = document.querySelector("#dueFromFilter");
const dueToFilterInput = document.querySelector("#dueToFilter");
const priorityFilterInput = document.querySelector("#priorityFilter");
const resetFiltersBtn = document.querySelector("#resetFiltersBtn");
const createdDateLabel = document.querySelector("#createdDateLabel");
const dueDateLabel = document.querySelector("#dueDateLabel");
const calendarGrid = document.querySelector("#calendarGrid");
const calendarMonthLabel = document.querySelector("#calendarMonthLabel");
const calendarMonthSelect = document.querySelector("#calendarMonthSelect");
const calendarYearInput = document.querySelector("#calendarYearInput");
const prevMonthBtn = document.querySelector("#prevMonthBtn");
const nextMonthBtn = document.querySelector("#nextMonthBtn");
const drawer = document.querySelector("#detailDrawer");
const drawerContent = document.querySelector("#drawerContent");
const settingsPanel = document.querySelector("#settingsPanel");
const settingsNavButton = document.querySelector('[data-action="open-settings"]');
const confidenceThresholdInput = document.querySelector("#confidenceThreshold");
const confidenceValue = document.querySelector("#confidenceValue");
const toast = document.querySelector("#toast");
const systemThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");

let calendarMonth = 5;
let calendarYear = 2026;

function dateInRange(dateText, fromText, toText) {
  if (!dateText) return !fromText && !toText;
  if (fromText && dateText < fromText) return false;
  if (toText && dateText > toText) return false;
  return true;
}

function isValidIsoDate(value) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const [, year, month, day] = match.map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

function normalizeDateInput(value) {
  const trimmed = value.trim();
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length === 8) {
    return `${digits.slice(4, 8)}-${digits.slice(2, 4)}-${digits.slice(0, 2)}`;
  }
  const slashMatch = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    const [, day, month, year] = slashMatch;
    return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  return trimmed;
}

function setDateRange(kind, boundary, value) {
  const normalized = normalizeDateInput(value);
  if (!normalized) {
    if (kind === "created" && boundary === "from") createdFromFilter = "";
    if (kind === "created" && boundary === "to") createdToFilter = "";
    if (kind === "due" && boundary === "from") dueFromFilter = "";
    if (kind === "due" && boundary === "to") dueToFilter = "";
    return true;
  }

  if (!isValidIsoDate(normalized)) {
    showToast("Use DD/MM/YYYY.");
    return false;
  }

  if (kind === "due" && normalized < todayIso) {
    showToast("Choose today or a future date.");
    return false;
  }

  const fromValue = kind === "created" ? createdFromFilter : dueFromFilter;
  const toValue = kind === "created" ? createdToFilter : dueToFilter;

  if (boundary === "to" && fromValue && normalized < fromValue) {
    showToast("To date cannot be before From date.");
    return false;
  }

  if (boundary === "from" && toValue && toValue < normalized) {
    showToast("From date cannot be after To date.");
    return false;
  }

  if (kind === "created" && boundary === "from") createdFromFilter = normalized;
  if (kind === "created" && boundary === "to") createdToFilter = normalized;
  if (kind === "due" && boundary === "from") dueFromFilter = normalized;
  if (kind === "due" && boundary === "to") dueToFilter = normalized;
  return true;
}

function toDisplayDate(dateText) {
  if (!dateText) return "";
  const [year, month, day] = dateText.split("-");
  return `${day}/${month}/${year}`;
}

function formatDate(dateText) {
  if (!dateText) return "No date";
  return toDisplayDate(dateText);
}

function formatDateRange(fromText, toText) {
  if (!fromText && !toText) return "Any date";
  if (fromText && toText) return `${formatDate(fromText)} - ${formatDate(toText)}`;
  if (fromText) return `From ${formatDate(fromText)}`;
  return `To ${formatDate(toText)}`;
}

function visibleItems() {
  return items.filter((item) => {
    if (item.status === "dismissed") return false;
    const matchesFilter = activeFilter === "all" || item.type === activeFilter;
    const matchesCreated = dateInRange(item.createdAt, createdFromFilter, createdToFilter);
    const matchesDue = dateInRange(item.dueAt, dueFromFilter, dueToFilter);
    const matchesPriority = priorityFilter === "all" || item.priority === priorityFilter;
    const searchable = `${item.title} ${item.owner} ${item.source} ${item.summary}`.toLowerCase();
    return matchesFilter && matchesCreated && matchesDue && matchesPriority && searchable.includes(query.toLowerCase());
  });
}

function calendarCounts() {
  return items.reduce((counts, item) => {
    if (item.status === "dismissed" || !item.dueAt) return counts;
    counts[item.dueAt] = (counts[item.dueAt] || 0) + 1;
    return counts;
  }, {});
}

function renderCalendar() {
  const counts = calendarCounts();
  const days = [];
  const firstDay = new Date(Date.UTC(calendarYear, calendarMonth, 1));
  const daysInMonth = new Date(Date.UTC(calendarYear, calendarMonth + 1, 0)).getUTCDate();
  const firstDayOffset = (firstDay.getUTCDay() + 6) % 7;

  for (let index = 0; index < firstDayOffset; index += 1) {
    days.push('<button class="calendar-day" type="button" disabled></button>');
  }

  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = `${calendarYear}-${String(calendarMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const count = counts[date] || 0;
    const heat = count === 0 ? 0 : Math.min(4, Math.ceil(count / 2));
    const classes = [
      "calendar-day",
      count ? "has-items" : "",
      heat ? `heat-${heat}` : "",
      date === selectedCalendarDate ? "selected" : "",
      date === todayIso ? "today" : ""
    ].filter(Boolean).join(" ");

    days.push(`<button class="${classes}" data-calendar-date="${date}" type="button" title="${formatDate(date)}: ${count} item${count === 1 ? "" : "s"}"><span>${day}</span></button>`);
  }

  calendarGrid.innerHTML = days.join("");
  calendarMonthLabel.textContent = `${monthNames[calendarMonth]} ${calendarYear}`;
  calendarMonthSelect.value = String(calendarMonth);
  calendarYearInput.value = String(calendarYear);
}

function renderCalendarSelectors() {
  calendarMonthSelect.innerHTML = monthNames.map((month, index) => `<option value="${index}">${month}</option>`).join("");
  calendarMonthSelect.value = String(calendarMonth);
  calendarYearInput.value = String(calendarYear);
}

function setCalendarMonth(month, year) {
  calendarMonth = month;
  calendarYear = year;
  renderCalendar();
}

function shiftCalendarMonth(offset) {
  const date = new Date(Date.UTC(calendarYear, calendarMonth + offset, 1));
  setCalendarMonth(date.getUTCMonth(), date.getUTCFullYear());
}

function priorityTag(priority, type) {
  const reviewClass = type === "needs_review" ? "review" : "";
  return `<span class="tag ${priority} ${reviewClass}">${priority}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderQueue() {
  const cards = visibleItems().map((item) => `
    <article class="item-card ${item.status === "done" ? "done" : ""}" data-id="${escapeHtml(item.id)}">
      <div class="item-type" aria-hidden="true">${typeIcon[item.type]}</div>
      <div class="item-main">
        <div class="item-meta">
          <span>${typeLabel[item.type]}</span>
          <span>${escapeHtml(item.time)}</span>
          <span>${Math.round(item.confidence * 100)}% confidence</span>
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        <div class="item-source">
          ${priorityTag(item.priority, item.type)}
          <span class="tag">${escapeHtml(item.source)}</span>
          <span class="tag">${escapeHtml(item.owner)}</span>
        </div>
      </div>
      <div class="item-actions">
        <button class="icon-button" data-action="inspect" data-id="${escapeHtml(item.id)}" title="Inspect item">i</button>
        <button class="icon-button" data-action="approve" data-id="${escapeHtml(item.id)}" title="Mark reviewed">v</button>
        <button class="icon-button" data-action="dismiss" data-id="${escapeHtml(item.id)}" title="Dismiss">x</button>
      </div>
    </article>
  `).join("");

  queueList.innerHTML = cards || `<p class="empty-state">No items match the current filter.</p>`;
  updateMetrics();
  renderCalendar();
}

function syncFilterInputs() {
  createdFromFilterInput.value = toDisplayDate(createdFromFilter);
  createdToFilterInput.value = toDisplayDate(createdToFilter);
  dueFromFilterInput.value = toDisplayDate(dueFromFilter);
  dueToFilterInput.value = toDisplayDate(dueToFilter);
  priorityFilterInput.value = priorityFilter;
  createdDateLabel.textContent = formatDateRange(createdFromFilter, createdToFilter);
  dueDateLabel.textContent = formatDateRange(dueFromFilter, dueToFilter);
  document.querySelectorAll("[data-calendar-target]").forEach((input) => {
    const target = document.querySelector(`#${input.dataset.calendarTarget}`);
    input.value = normalizeDateInput(target.value);
    input.min = input.dataset.calendarTarget.startsWith("due") ? todayIso : "";
  });
  document.querySelector('[data-calendar-target="createdToFilter"]').min = createdFromFilter || "";
  document.querySelector('[data-calendar-target="dueToFilter"]').min = dueFromFilter || todayIso;
}

function renderDateMenus() {
  document.querySelectorAll("[data-date-menu]").forEach((container) => {
    const isOpen = container.dataset.dateMenu === openDateMenu;
    container.querySelector(".date-menu").classList.toggle("open", isOpen);
    container.querySelector(".filter-trigger").classList.toggle("active", isOpen);
  });
}

function toggleDateMenu(menu) {
  openDateMenu = openDateMenu === menu ? null : menu;
  renderDateMenus();
}

function renderFocusStack() {
  const stack = document.querySelector("#focusStack");
  stack.innerHTML = focusOrder.map((kind) => {
    const section = focusData[kind];
    const sectionItems = section.items();
    const rows = sectionItems.length
      ? sectionItems.map((entry) => `
          <button class="compact-item text-button" ${entry.id ? `data-action="inspect" data-id="${escapeHtml(entry.id)}"` : `data-note="${escapeHtml(entry.title)}"`}>
            <strong>${escapeHtml(entry.title)}</strong>
            <span>${escapeHtml(entry.detail)}</span>
          </button>
        `).join("")
      : `<p class="empty-state">No ${section.title.toLowerCase()} yet.</p>`;

    return `
      <section class="mini-section" data-kind="${kind}">
        <div class="section-title">
          <div>
            <h3>${section.title}</h3>
            <span>${section.meta()}</span>
          </div>
        </div>
        <div class="compact-list">${rows}</div>
        <div class="section-foot">
          <span><strong>${sectionItems.length}</strong> total</span>
          <span>Scroll list</span>
        </div>
      </section>
    `;
  }).join("");

  renderStackMenu();
}

function renderStackMenu() {
  const menu = document.querySelector("#stackMenu");
  const button = document.querySelector("#stackSettingsBtn");
  if (!menu || !button) return;

  button.classList.toggle("active", stackMenuOpen);
  menu.classList.toggle("open", stackMenuOpen);
  menu.innerHTML = focusOrder.map((kind, index) => {
    const section = focusData[kind];
    return `
      <div class="stack-menu-row" draggable="true" data-kind="${kind}">
        <span class="drag-handle" aria-hidden="true">::</span>
        <div>
          <strong>${section.title}</strong>
          <span>Drag to position ${index + 1}</span>
        </div>
      </div>
    `;
  }).join("");
}

function updateMetrics() {
  const openItems = items.filter((item) => item.status !== "dismissed");
  document.querySelector("#taskCount").textContent = openItems.filter((item) => item.type === "task").length;
  document.querySelector("#dueTodayCount").textContent = openItems.filter((item) => item.dueAt === todayIso).length;
  document.querySelector("#weeklyMeetingCount").textContent = meetings.length;
  document.querySelector("#reviewCount").textContent = openItems.filter((item) => item.type === "needs_review").length;
  document.querySelectorAll("[data-metric-filter]").forEach((metric) => {
    metric.classList.toggle("active", metric.dataset.metricFilter === activeMetricFilter);
  });
  renderFocusStack();
}

function inspectItem(id) {
  const item = items.find((entry) => entry.id === id);
  if (!item) return;

  closeSettings();
  drawerContent.innerHTML = `
    <p class="eyebrow">${typeLabel[item.type]}</p>
    <h2>${escapeHtml(item.title)}</h2>
    <div class="item-source">
      ${priorityTag(item.priority, item.type)}
      <span class="tag">${escapeHtml(item.source)}</span>
      <span class="tag">${escapeHtml(item.owner)}</span>
    </div>
    <div class="drawer-block">
      <h3>Source Summary</h3>
      <p>${escapeHtml(item.summary)}</p>
    </div>
    <div class="drawer-block">
      <h3>Suggested Next Step</h3>
      <p>${escapeHtml(item.next)}</p>
    </div>
    <div class="drawer-block">
      <h3>Confidence</h3>
      <div class="confidence-meter" aria-label="Confidence ${Math.round(item.confidence * 100)} percent">
        <span style="width: ${Math.round(item.confidence * 100)}%"></span>
      </div>
    </div>
    <div class="drawer-block item-actions">
      <button class="secondary-button" data-action="approve" data-id="${escapeHtml(item.id)}">Mark reviewed</button>
      <button class="text-button" data-action="dismiss" data-id="${escapeHtml(item.id)}">Dismiss</button>
    </div>
  `;
  drawer.classList.add("open");
}

function renderAccountStates() {
  document.querySelectorAll("[data-action='toggle-account']").forEach((button) => {
    const account = button.dataset.account;
    const connected = accountStates[account];
    button.textContent = connected ? "Connected" : "Connect";
    button.classList.toggle("connected", connected);
  });

  Object.entries(sourceCounts).forEach(([account, count]) => {
    const countElement = document.querySelector(`#${account}SourceCount`);
    if (countElement) countElement.textContent = String(count);
  });
}

function registerEmailScan(result) {
  const provider = String(result.provider || "").toLowerCase();
  if (provider in sourceCounts) {
    sourceCounts[provider] = Array.isArray(result.source_items) ? result.source_items.length : 0;
    accountStates[provider] = sourceCounts[provider] > 0;
    renderAccountStates();
  }
}

function toggleAccount(account) {
  accountStates = {
    ...accountStates,
    [account]: !accountStates[account]
  };
  if (!accountStates[account]) {
    sourceCounts[account] = 0;
  }
  renderAccountStates();
  showToast(`${account} ${accountStates[account] ? "connected" : "disconnected"} locally.`);
}

function addAgentDashboardUpdate(update) {
  const incomingItems = Array.isArray(update.dashboard_items) ? update.dashboard_items : [];
  const incomingNews = Array.isArray(update.dashboard_news) ? update.dashboard_news : [];
  const existingIds = new Set(items.map((item) => item.id));
  let addedCount = 0;

  incomingItems.forEach((item) => {
    if (!item || existingIds.has(item.id)) return;
    const normalized = {
      id: String(item.id),
      type: ["task", "meeting", "needs_review"].includes(item.type) ? item.type : "task",
      title: String(item.title || "Email item"),
      owner: String(item.owner || "Email"),
      source: String(item.source || "Email"),
      time: String(item.time || "From email"),
      createdAt: String(item.createdAt || todayIso),
      dueAt: String(item.dueAt || item.createdAt || todayIso),
      priority: ["low", "medium", "high"].includes(item.priority) ? item.priority : "medium",
      confidence: Number.isFinite(Number(item.confidence)) ? Number(item.confidence) : 0,
      summary: String(item.summary || ""),
      next: String(item.next || "Review the source email."),
      status: "open"
    };

    items.unshift(normalized);
    existingIds.add(normalized.id);
    addedCount += 1;

    if (normalized.type === "meeting") {
      meetings.unshift({
        id: normalized.id,
        title: normalized.title,
        detail: `${normalized.time} - ${normalized.next}`
      });
    }
  });

  incomingNews.forEach((story) => {
    if (!story) return;
    news.unshift({
      title: String(story.title || "Email update"),
      detail: String(story.detail || "")
    });
  });

  renderQueue();
  showToast(`Dashboard updated from ${addedCount + incomingNews.length} AI result${addedCount + incomingNews.length === 1 ? "" : "s"}.`);
}

window.LifeAdminDashboard = {
  addAgentDashboardUpdate,
  registerEmailScan
};

function showToast(message) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function openSettings() {
  settingsPanel.classList.add("open");
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  settingsNavButton.classList.add("active");
  drawer.classList.remove("open");
}

function closeSettings() {
  settingsPanel.classList.remove("open");
  settingsNavButton.classList.remove("active");
  document.querySelectorAll(".nav-item[data-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === activeFilter);
  });
}

function setTheme(theme) {
  activeTheme = theme;
  const useDark = theme === "dark" || (theme === "system" && systemThemeQuery.matches);
  document.body.classList.toggle("dark-theme", useDark);

  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.classList.toggle("active", button.dataset.themeOption === theme);
  });
}

function updateConfidenceThreshold(value) {
  confidenceValue.textContent = `${value}%`;
}

function handleAction(action, id) {
  const item = items.find((entry) => entry.id === id);
  if (!item) return;

  if (action === "inspect") {
    inspectItem(id);
    return;
  }

  if (action === "approve") {
    item.status = "done";
    showToast("Item marked reviewed. No external action was taken.");
  }

  if (action === "dismiss") {
    item.status = "dismissed";
    showToast("Item dismissed from the working queue.");
  }

  renderQueue();
}

function moveSection(kind, direction) {
  const index = focusOrder.indexOf(kind);
  if (index === -1) return;
  const targetIndex = direction === "up" ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= focusOrder.length) return;

  const updatedOrder = [...focusOrder];
  [updatedOrder[index], updatedOrder[targetIndex]] = [updatedOrder[targetIndex], updatedOrder[index]];
  focusOrder = updatedOrder;
  stackMenuOpen = true;
  renderFocusStack();
  showToast(`${focusData[kind].title} moved ${direction}.`);
}

function reorderSection(fromKind, toKind) {
  if (!fromKind || !toKind || fromKind === toKind) return;

  const fromIndex = focusOrder.indexOf(fromKind);
  const toIndex = focusOrder.indexOf(toKind);
  if (fromIndex === -1 || toIndex === -1) return;

  const updatedOrder = [...focusOrder];
  const [moved] = updatedOrder.splice(fromIndex, 1);
  updatedOrder.splice(toIndex, 0, moved);
  focusOrder = updatedOrder;
  stackMenuOpen = true;
  renderFocusStack();
  showToast(`${focusData[fromKind].title} moved.`);
}

function toggleStackMenu() {
  stackMenuOpen = !stackMenuOpen;
  renderStackMenu();
}

function setFilter(filter) {
  activeFilter = filter;
  closeSettings();
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === filter);
  });
  renderQueue();
}

function resetFilters() {
  createdFromFilter = "";
  createdToFilter = "";
  dueFromFilter = "";
  dueToFilter = "";
  priorityFilter = "all";
  activeMetricFilter = null;
  selectedCalendarDate = "";
  query = "";
  searchInput.value = "";
  syncFilterInputs();
  renderQueue();
  showToast("Filters reset.");
}

function applyCalendarDate(date) {
  selectedCalendarDate = date;
  const [year, month] = date.split("-").map(Number);
  calendarYear = year;
  calendarMonth = month - 1;
  activeMetricFilter = null;
  activeFilter = "all";
  createdFromFilter = "";
  createdToFilter = "";
  dueFromFilter = date;
  dueToFilter = date;
  priorityFilter = "all";
  query = "";
  searchInput.value = "";
  syncFilterInputs();
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === "all");
  });
  renderQueue();
  showToast(`Showing items due on ${formatDate(date)}.`);
}

function applyMetricFilter(metric) {
  activeMetricFilter = metric;
  createdFromFilter = "";
  createdToFilter = "";
  dueFromFilter = "";
  dueToFilter = "";
  priorityFilter = "all";

  if (metric === "outstanding") {
    activeFilter = "task";
  }

  if (metric === "due_today") {
    activeFilter = "all";
    dueFromFilter = todayIso;
    dueToFilter = todayIso;
  }

  if (metric === "weekly_meetings") {
    activeFilter = "meeting";
    dueFromFilter = todayIso;
  }

  if (metric === "review_required") {
    activeFilter = "needs_review";
  }

  syncFilterInputs();
  closeSettings();
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === activeFilter);
  });
  renderQueue();
}

document.addEventListener("click", (event) => {
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    if (actionButton.dataset.action === "open-settings") {
      openSettings();
      return;
    }

    if (actionButton.dataset.action === "toggle-date-menu") {
      toggleDateMenu(actionButton.dataset.menu);
      return;
    }

    if (actionButton.dataset.action === "toggle-account") {
      toggleAccount(actionButton.dataset.account);
      return;
    }

    if (actionButton.dataset.action === "move-section") {
      moveSection(actionButton.dataset.kind, actionButton.dataset.direction);
      return;
    }

    handleAction(actionButton.dataset.action, actionButton.dataset.id);
    return;
  }

  const filterButton = event.target.closest("[data-filter]");
  if (filterButton) {
    activeMetricFilter = null;
    setFilter(filterButton.dataset.filter);
    return;
  }

  const metricButton = event.target.closest("[data-metric-filter]");
  if (metricButton) {
    applyMetricFilter(metricButton.dataset.metricFilter);
    return;
  }

  const calendarButton = event.target.closest("[data-calendar-date]");
  if (calendarButton) {
    applyCalendarDate(calendarButton.dataset.calendarDate);
    return;
  }

  const card = event.target.closest(".item-card");
  if (card) {
    inspectItem(card.dataset.id);
    return;
  }

  const noteButton = event.target.closest("[data-note]");
  if (noteButton) {
    showToast(`${noteButton.dataset.note} opened in preview.`);
    return;
  }

  if (!event.target.closest(".stack-menu") && !event.target.closest("#stackSettingsBtn") && stackMenuOpen) {
    stackMenuOpen = false;
    renderStackMenu();
  }

  if (!event.target.closest("[data-date-menu]") && openDateMenu) {
    openDateMenu = null;
    renderDateMenus();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;

  if (openDateMenu) {
    openDateMenu = null;
    renderDateMenus();
  }

  if (stackMenuOpen) {
    stackMenuOpen = false;
    renderStackMenu();
  }

  if (settingsPanel.classList.contains("open")) {
    closeSettings();
  }

  if (drawer.classList.contains("open")) {
    drawer.classList.remove("open");
  }
});

document.querySelector("#stackSettingsBtn").addEventListener("click", (event) => {
  event.stopPropagation();
  toggleStackMenu();
});

document.querySelector("#stackMenu").addEventListener("dragstart", (event) => {
  const row = event.target.closest(".stack-menu-row");
  if (!row) return;

  draggedSection = row.dataset.kind;
  row.classList.add("dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", draggedSection);
});

document.querySelector("#stackMenu").addEventListener("dragover", (event) => {
  const row = event.target.closest(".stack-menu-row");
  if (!row || row.dataset.kind === draggedSection) return;

  event.preventDefault();
  document.querySelectorAll(".stack-menu-row").forEach((entry) => entry.classList.remove("drop-target"));
  row.classList.add("drop-target");
  event.dataTransfer.dropEffect = "move";
});

document.querySelector("#stackMenu").addEventListener("dragleave", (event) => {
  const row = event.target.closest(".stack-menu-row");
  if (row) row.classList.remove("drop-target");
});

document.querySelector("#stackMenu").addEventListener("drop", (event) => {
  const row = event.target.closest(".stack-menu-row");
  if (!row) return;

  event.preventDefault();
  reorderSection(draggedSection, row.dataset.kind);
});

document.querySelector("#stackMenu").addEventListener("dragend", () => {
  draggedSection = null;
  document.querySelectorAll(".stack-menu-row").forEach((row) => {
    row.classList.remove("dragging", "drop-target");
  });
});

searchInput.addEventListener("input", (event) => {
  query = event.target.value;
  renderQueue();
});

createdFromFilterInput.addEventListener("change", (event) => {
  activeMetricFilter = null;
  setDateRange("created", "from", event.target.value);
  syncFilterInputs();
  renderQueue();
});

createdToFilterInput.addEventListener("change", (event) => {
  activeMetricFilter = null;
  setDateRange("created", "to", event.target.value);
  syncFilterInputs();
  renderQueue();
});

dueFromFilterInput.addEventListener("change", (event) => {
  activeMetricFilter = null;
  setDateRange("due", "from", event.target.value);
  syncFilterInputs();
  renderQueue();
});

dueToFilterInput.addEventListener("change", (event) => {
  activeMetricFilter = null;
  setDateRange("due", "to", event.target.value);
  syncFilterInputs();
  renderQueue();
});

document.querySelectorAll("[data-calendar-target]").forEach((input) => {
  input.addEventListener("change", () => {
    const target = document.querySelector(`#${input.dataset.calendarTarget}`);
    target.value = toDisplayDate(input.value);
    target.dispatchEvent(new Event("change", { bubbles: true }));
  });
});

priorityFilterInput.addEventListener("change", (event) => {
  activeMetricFilter = null;
  priorityFilter = event.target.value;
  renderQueue();
});

resetFiltersBtn.addEventListener("click", resetFilters);

prevMonthBtn.addEventListener("click", () => shiftCalendarMonth(-1));
nextMonthBtn.addEventListener("click", () => shiftCalendarMonth(1));
calendarMonthSelect.addEventListener("change", (event) => {
  setCalendarMonth(Number(event.target.value), calendarYear);
});
calendarYearInput.addEventListener("change", (event) => {
  const nextYear = Math.min(2100, Math.max(2000, Number(event.target.value) || calendarYear));
  setCalendarMonth(calendarMonth, nextYear);
});

document.querySelector("#closeDrawer").addEventListener("click", () => drawer.classList.remove("open"));
document.querySelector("#closeSettings").addEventListener("click", closeSettings);

systemThemeQuery.addEventListener("change", () => {
  if (activeTheme === "system") setTheme("system");
});

document.querySelectorAll("[data-theme-option]").forEach((button) => {
  button.addEventListener("click", () => {
    setTheme(button.dataset.themeOption);
    showToast(`Theme set to ${button.textContent}.`);
  });
});

document.querySelector("#regionSelect").addEventListener("change", () => {
  showToast("Region preferences updated.");
});

document.querySelector("#timezoneSelect").addEventListener("change", () => {
  showToast("Timezone updated for deadline grouping.");
});

document.querySelector("#workdayStart").addEventListener("change", () => {
  showToast("Workday start saved.");
});

document.querySelector("#digestTime").addEventListener("change", () => {
  showToast("Daily digest time saved.");
});

document.querySelectorAll("[data-setting-toast]").forEach((control) => {
  control.addEventListener("change", () => {
    showToast(control.dataset.settingToast);
  });
});

confidenceThresholdInput.addEventListener("input", (event) => {
  updateConfidenceThreshold(event.target.value);
});

document.querySelectorAll(".toggle-row input").forEach((input) => {
  input.addEventListener("change", () => {
    showToast("Preference saved.");
  });
});

setTheme(activeTheme);
updateConfidenceThreshold(confidenceThresholdInput.value);
renderAccountStates();
syncFilterInputs();
renderCalendarSelectors();
renderQueue();
