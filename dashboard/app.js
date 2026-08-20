import { createClient } from "@supabase/supabase-js";
import { cycleLabel, extensionForMime, formatMoney, initials, summarizeRuns, validateScreenshot } from "./logic.js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
const supabase = supabaseUrl && publishableKey
  ? createClient(supabaseUrl, publishableKey, { auth: { persistSession: true, autoRefreshToken: true } })
  : null;

const byId = (id) => document.getElementById(id);
const elements = {
  authView: byId("authView"), appView: byId("appView"), authForm: byId("authForm"),
  authEmail: byId("authEmail"), authPassword: byId("authPassword"), authMessage: byId("authMessage"),
  authTitle: byId("authTitle"), authEyebrow: byId("authEyebrow"), authDescription: byId("authDescription"),
  authSubmit: byId("authSubmit"), authModeToggle: byId("authModeToggle"), displayNameField: byId("displayNameField"),
  displayName: byId("displayName"), signOutButton: byId("signOutButton"), userName: byId("userName"),
  userRole: byId("userRole"), userAvatar: byId("userAvatar"), cyclePill: byId("cyclePill"), cycleLabel: byId("cycleLabel"),
  memberView: byId("memberView"), adminView: byId("adminView"), lockedView: byId("lockedView"), adminNav: byId("adminNav"),
  campaignForm: byId("campaignForm"), campaignMessage: byId("campaignMessage"), campaignSubmit: byId("campaignSubmit"),
  refreshRuns: byId("refreshRuns"), runList: byId("runList"), memberTotal: byId("memberTotal"),
  memberPending: byId("memberPending"), memberReady: byId("memberReady"), memberOutstanding: byId("memberOutstanding"),
  earningsForm: byId("earningsForm"), earningsFile: byId("earningsFile"), earningsFileLabel: byId("earningsFileLabel"),
  earningsSubmit: byId("earningsSubmit"), earningsMessage: byId("earningsMessage"), earningsStatus: byId("earningsStatus"),
  earningsHistory: byId("earningsHistory"), lockUploadForm: byId("lockUploadForm"), lockFile: byId("lockFile"),
  lockFileLabel: byId("lockFileLabel"), lockSubmit: byId("lockSubmit"), lockMessage: byId("lockMessage"),
  adminMemberCount: byId("adminMemberCount"), adminCampaignCount: byId("adminCampaignCount"),
  adminPendingCount: byId("adminPendingCount"), adminReviewCount: byId("adminReviewCount"),
  adminUserRows: byId("adminUserRows"), reviewQueue: byId("reviewQueue"), refreshAdmin: byId("refreshAdmin"),
  reminderDialog: byId("reminderDialog"), reminderUpload: byId("reminderUpload"), toast: byId("toast"),
};

let authMode = "signin";
let session = null;
let access = null;
let refreshTimer = null;
let toastTimer = null;

function setMessage(element, message = "", type = "") {
  element.textContent = message;
  element.className = `form-message${type ? ` ${type}` : ""}`;
}

function setLoading(button, loading, loadingText) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = loading;
  button.textContent = loading ? loadingText : button.dataset.label;
}

function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 4500);
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function formatDate(value, includeTime = false) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium", ...(includeTime ? { timeStyle: "short" } : {}),
  }).format(new Date(value));
}

function statusLabel(status) {
  return { queued: "Queued", processing: "Processing", ready: "Ready", failed: "Needs attention" }[status] || status;
}

function showAuth() {
  clearInterval(refreshTimer);
  elements.authView.hidden = false;
  elements.appView.hidden = true;
  session = null;
  access = null;
}

function setAuthMode(mode) {
  authMode = mode;
  const signup = mode === "signup";
  elements.displayNameField.hidden = !signup;
  elements.displayName.required = signup;
  elements.authEyebrow.textContent = signup ? "Join the team" : "Welcome back";
  elements.authTitle.textContent = signup ? "Create your ClipFarm account" : "Sign in to your workspace";
  elements.authDescription.textContent = signup
    ? "Your seven-day earnings cycle starts when your account is created."
    : "Your campaigns and earnings records are tied to this account.";
  elements.authSubmit.textContent = signup ? "Create account" : "Sign in";
  elements.authModeToggle.textContent = signup ? "Already have an account? Sign in" : "Need an account? Create one";
  elements.authPassword.autocomplete = signup ? "new-password" : "current-password";
  setMessage(elements.authMessage);
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  if (!supabase) return setMessage(elements.authMessage, "This deployment is missing its Supabase configuration.", "error");
  if (!elements.authForm.checkValidity()) return elements.authForm.reportValidity();
  setLoading(elements.authSubmit, true, authMode === "signup" ? "Creating account…" : "Signing in…");
  setMessage(elements.authMessage);
  try {
    if (authMode === "signup") {
      const { data, error } = await supabase.auth.signUp({
        email: elements.authEmail.value.trim(), password: elements.authPassword.value,
        options: { data: { display_name: elements.displayName.value.trim() } },
      });
      if (error) throw error;
      if (!data.session) {
        setMessage(elements.authMessage, "Check your email to confirm the account, then sign in.", "success");
        setAuthMode("signin");
        return;
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({
        email: elements.authEmail.value.trim(), password: elements.authPassword.value,
      });
      if (error) throw error;
    }
  } catch (error) {
    setMessage(elements.authMessage, error.message || "Authentication failed.", "error");
  } finally {
    setLoading(elements.authSubmit, false, "");
  }
}

async function loadAccess() {
  const { data, error } = await supabase.rpc("get_access_status");
  if (error) throw error;
  access = data;
  elements.userName.textContent = access.display_name;
  elements.userRole.textContent = access.role === "admin" ? "Administrator" : "Team member";
  elements.userAvatar.textContent = initials(access.display_name);
  elements.adminNav.hidden = access.role !== "admin";
  elements.cycleLabel.textContent = cycleLabel(access.deadline_at, access.server_time);
  elements.cyclePill.classList.toggle("danger", access.is_locked);
  elements.earningsStatus.textContent = access.is_locked ? "Due now" : `Day ${access.cycle_day} of 7`;
  elements.earningsStatus.classList.toggle("danger", access.is_locked);
  return access;
}

async function enterApp(nextSession) {
  session = nextSession;
  elements.authView.hidden = true;
  elements.appView.hidden = false;
  try {
    await loadAccess();
    if (access.is_locked && access.role !== "admin") {
      showLockedView();
    } else {
      showWorkspace(access.role === "admin" && location.hash === "#admin" ? "admin" : "member");
      await loadMemberData();
      if (access.role === "admin" && location.hash === "#admin") await loadAdminData();
      if (access.reminder_due && !elements.reminderDialog.open) elements.reminderDialog.showModal();
    }
    clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      if (!document.hidden && access && !access.is_locked) loadMemberData().catch(() => {});
    }, 20000);
  } catch (error) {
    showToast(error.message || "Could not load the workspace.");
  }
}

function showLockedView() {
  elements.memberView.hidden = true;
  elements.adminView.hidden = true;
  elements.lockedView.hidden = false;
  document.querySelectorAll(".nav-link").forEach((button) => button.classList.remove("active"));
}

function showWorkspace(view) {
  if (view === "admin" && access?.role !== "admin") view = "member";
  if (view === "member" && access?.is_locked) return showLockedView();
  elements.lockedView.hidden = true;
  elements.memberView.hidden = view !== "member";
  elements.adminView.hidden = view !== "admin";
  document.querySelectorAll(".nav-link").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  history.replaceState(null, "", view === "admin" ? "#admin" : "#campaigns");
}

function numberValue(id) {
  const value = byId(id).value.trim();
  return value === "" ? null : Number(value);
}

async function handleCampaignSubmit(event) {
  event.preventDefault();
  setMessage(elements.campaignMessage);
  if (!elements.campaignForm.checkValidity()) return elements.campaignForm.reportValidity();
  const platforms = [...document.querySelectorAll('input[name="platform"]:checked')].map((input) => input.value);
  if (!platforms.length) return setMessage(elements.campaignMessage, "Select at least one eligible platform.", "error");
  const minimum = numberValue("minimumPayout");
  const maximum = numberValue("maximumPayout");
  if (minimum !== null && maximum !== null && minimum > maximum) {
    return setMessage(elements.campaignMessage, "Minimum payout cannot exceed maximum payout.", "error");
  }
  const body = {
    campaign_name: byId("campaignName").value.trim(), reward_rate: numberValue("rewardRate"),
    minimum_payout: minimum, maximum_payout: maximum, platforms,
    episode_url: byId("episodeUrl").value.trim(), available_content: byId("availableContent").value.trim(),
    requirements: byId("requirements").value.trim(),
  };
  setLoading(elements.campaignSubmit, true, "Starting campaign…");
  try {
    const { data, error } = await supabase.functions.invoke("start-campaign", { body });
    if (error) throw error;
    if (data?.warning) setMessage(elements.campaignMessage, data.warning, "warning");
    else setMessage(elements.campaignMessage, "Campaign queued. Processing will continue in the background.", "success");
    elements.campaignForm.reset();
    [...document.querySelectorAll('input[name="platform"]')].forEach((input) => {
      input.checked = ["tiktok", "instagram", "youtube"].includes(input.value);
    });
    await loadMemberData();
  } catch (error) {
    setMessage(elements.campaignMessage, error.message || "Could not start the campaign.", "error");
  } finally {
    setLoading(elements.campaignSubmit, false, "");
  }
}

async function loadMemberData() {
  const [runsResult, earningsResult, accountResult] = await Promise.all([
    supabase.from("campaign_runs").select("*").order("created_at", { ascending: false }).limit(30),
    supabase.from("earnings_submissions").select("*").order("submitted_at", { ascending: false }).limit(8),
    supabase.from("commission_accounts").select("*").maybeSingle(),
  ]);
  const firstError = runsResult.error || earningsResult.error || accountResult.error;
  if (firstError) throw firstError;
  renderRuns(runsResult.data || []);
  renderEarnings(earningsResult.data || [], accountResult.data);
}

function renderRuns(runs) {
  const summary = summarizeRuns(runs);
  elements.memberTotal.textContent = summary.total;
  elements.memberPending.textContent = summary.pending;
  elements.memberReady.textContent = summary.ready;
  if (!runs.length) {
    elements.runList.innerHTML = `<div class="empty-state"><span>◎</span><strong>No campaigns yet</strong><p>Your first run will appear here after submission.</p></div>`;
    return;
  }
  elements.runList.innerHTML = runs.map((run) => {
    const action = run.status === "ready" && run.github_run_id
      ? `<button class="run-download" data-run-id="${escapeHtml(run.id)}" type="button">Download results ↗</button>`
      : "";
    return `<article class="run-row">
      <div class="run-status ${escapeHtml(run.status)}"><i></i>${escapeHtml(statusLabel(run.status))}</div>
      <div class="run-main"><strong>${escapeHtml(run.campaign_name)}</strong><span>${escapeHtml(run.current_stage)} · ${formatDate(run.created_at, true)}</span>${run.error_message ? `<small class="error-copy">${escapeHtml(run.error_message)}</small>` : ""}</div>
      ${action}
    </article>`;
  }).join("");
}

function renderEarnings(submissions, account) {
  const outstanding = Number(account?.total_owed || 0) - Number(account?.total_paid || 0);
  elements.memberOutstanding.textContent = formatMoney(outstanding);
  if (!submissions.length) {
    elements.earningsHistory.innerHTML = `<p class="quiet-line">No screenshots submitted yet.</p>`;
    return;
  }
  elements.earningsHistory.innerHTML = submissions.slice(0, 3).map((item) => `<div class="compact-row">
    <span><strong>${formatDate(item.submitted_at)}</strong><small>${escapeHtml(item.original_file_name)}</small></span>
    <b class="review-state ${escapeHtml(item.review_status)}">${item.review_status === "reviewed" ? formatMoney(item.confirmed_earnings) : "Pending review"}</b>
  </div>`).join("");
}

async function handleRunDownload(event) {
  const button = event.target.closest("button[data-run-id]");
  if (!button) return;
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "Preparing…";
  try {
    const { data, error } = await supabase.functions.invoke("download-results", {
      body: { run_id: button.dataset.runId },
    });
    if (error) throw error;
    if (!data?.download_url) throw new Error(data?.error || "The result download is unavailable.");
    window.location.assign(data.download_url);
  } catch (error) {
    showToast(error.message || "Could not prepare the result download.");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function uploadScreenshot(file, messageElement, button) {
  const validation = validateScreenshot(file);
  if (validation) return setMessage(messageElement, validation, "error");
  setLoading(button, true, "Uploading…");
  setMessage(messageElement);
  try {
    const submissionId = crypto.randomUUID();
    const path = `${session.user.id}/${submissionId}.${extensionForMime(file.type)}`;
    const { error: uploadError } = await supabase.storage.from("earnings-screenshots")
      .upload(path, file, { contentType: file.type, upsert: false });
    if (uploadError) throw uploadError;
    const { error: finalizeError } = await supabase.rpc("finalize_earnings_submission", {
      p_submission_id: submissionId, p_storage_path: path,
      p_original_file_name: file.name, p_content_type: file.type, p_byte_size: file.size,
    });
    if (finalizeError) throw finalizeError;
    await loadAccess();
    showWorkspace("member");
    await loadMemberData();
    setMessage(elements.earningsMessage, "Screenshot submitted. Your seven-day cycle has restarted.", "success");
    setMessage(elements.lockMessage);
    showToast("Access restored immediately. Your screenshot is awaiting admin review.");
  } catch (error) {
    setMessage(messageElement, error.message || "Screenshot upload failed.", "error");
  } finally {
    setLoading(button, false, "");
  }
}

async function loadAdminData() {
  if (access?.role !== "admin") return;
  const [statsResult, profilesResult, accountsResult, submissionsResult] = await Promise.all([
    supabase.from("admin_user_stats").select("*").order("display_name"),
    supabase.from("profiles").select("id, display_name, role").order("display_name"),
    supabase.from("commission_accounts").select("*"),
    supabase.from("earnings_submissions").select("*").order("submitted_at", { ascending: false }).limit(50),
  ]);
  const error = statsResult.error || profilesResult.error || accountsResult.error || submissionsResult.error;
  if (error) throw error;
  const stats = statsResult.data || [];
  const profiles = new Map((profilesResult.data || []).map((profile) => [profile.id, profile]));
  const accounts = new Map((accountsResult.data || []).map((account) => [account.user_id, account]));
  const submissions = submissionsResult.data || [];
  elements.adminMemberCount.textContent = stats.length;
  elements.adminCampaignCount.textContent = stats.reduce((total, item) => total + item.total_runs, 0);
  elements.adminPendingCount.textContent = stats.reduce((total, item) => total + item.pending_runs, 0);
  elements.adminReviewCount.textContent = submissions.filter((item) => item.review_status === "pending").length;
  renderAdminUsers(stats, accounts);
  renderReviewQueue(submissions, profiles);
}

function renderAdminUsers(stats, accounts) {
  elements.adminUserRows.innerHTML = stats.map((item) => {
    const account = accounts.get(item.id) || {};
    const rate = account.agreed_rate === null || account.agreed_rate === undefined ? "" : Number(account.agreed_rate) * 100;
    const outstanding = Number(account.total_owed || 0) - Number(account.total_paid || 0);
    return `<tr data-user-id="${escapeHtml(item.id)}">
      <td><div class="person-cell"><span>${escapeHtml(initials(item.display_name))}</span><strong>${escapeHtml(item.display_name)}<small>${escapeHtml(item.role)}</small></strong></div></td>
      <td>${item.total_runs}</td><td><b class="number-warn">${item.pending_runs}</b></td><td><b class="number-good">${item.completed_runs}</b></td><td>${item.failed_runs}</td>
      <td><div class="inline-input"><input class="rate-input" type="number" min="0" max="100" step="0.01" value="${escapeHtml(rate)}" placeholder="%"><button data-action="rate" type="button">Save</button></div></td>
      <td><strong>${formatMoney(outstanding)}</strong><small class="table-note">${formatMoney(account.total_paid)} paid</small></td>
      <td><div class="inline-input"><input class="payment-input" type="number" min="0.01" step="0.01" placeholder="$"><button data-action="payment" type="button" ${outstanding <= 0 ? "disabled" : ""}>Record</button></div></td>
    </tr>`;
  }).join("");
}

function renderReviewQueue(submissions, profiles) {
  if (!submissions.length) {
    elements.reviewQueue.innerHTML = `<div class="empty-state wide"><span>✓</span><strong>No earnings submissions yet</strong><p>New screenshots will appear here with the member and timestamp.</p></div>`;
    return;
  }
  elements.reviewQueue.innerHTML = submissions.map((item) => {
    const person = profiles.get(item.user_id);
    return `<article class="review-card ${escapeHtml(item.review_status)}" data-submission-id="${escapeHtml(item.id)}" data-path="${escapeHtml(item.storage_path)}">
      <div class="review-card-top"><div class="person-cell"><span>${escapeHtml(initials(person?.display_name))}</span><strong>${escapeHtml(person?.display_name || "Former member")}<small>${formatDate(item.submitted_at, true)}</small></strong></div><b class="review-state ${escapeHtml(item.review_status)}">${escapeHtml(item.review_status)}</b></div>
      <button class="screenshot-preview" data-action="screenshot" type="button"><span>▧</span><strong>${escapeHtml(item.original_file_name)}</strong><small>Open private screenshot ↗</small></button>
      ${item.review_status === "pending" ? `<div class="review-form"><label>Confirmed earnings <div class="money-field"><b>$</b><input class="confirmed-input" type="number" min="0" step="0.01" placeholder="0.00"></div></label><label>Review note <input class="review-note" maxlength="2000" placeholder="Optional"></label><button class="button button-primary" data-action="review" type="button">Confirm & calculate</button></div>` : `<div class="review-result"><span>Confirmed <strong>${formatMoney(item.confirmed_earnings)}</strong></span><span>Commission <strong>${formatMoney(item.commission_owed)}</strong></span><small>Reviewed by ${escapeHtml(item.reviewer_name_snapshot || "admin")}</small></div>`}
    </article>`;
  }).join("");
}

async function handleAdminTableClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const row = button.closest("tr");
  const userId = row.dataset.userId;
  button.disabled = true;
  try {
    if (button.dataset.action === "rate") {
      const percent = Number(row.querySelector(".rate-input").value);
      if (!Number.isFinite(percent) || percent < 0 || percent > 100) throw new Error("Enter a rate from 0 to 100%.");
      const { error } = await supabase.rpc("admin_set_commission_rate", { p_user_id: userId, p_rate: percent / 100 });
      if (error) throw error;
      showToast("Commission rate saved.");
    } else {
      const amount = Number(row.querySelector(".payment-input").value);
      if (!Number.isFinite(amount) || amount <= 0) throw new Error("Enter a valid payment amount.");
      const { error } = await supabase.rpc("admin_record_payment", { p_user_id: userId, p_amount: amount, p_note: null });
      if (error) throw error;
      showToast("Commission payment recorded.");
    }
    await loadAdminData();
  } catch (error) {
    showToast(error.message || "Admin update failed.");
  } finally {
    button.disabled = false;
  }
}

async function handleReviewClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest(".review-card");
  try {
    if (button.dataset.action === "screenshot") {
      const { data, error } = await supabase.storage.from("earnings-screenshots").createSignedUrl(card.dataset.path, 300);
      if (error) throw error;
      window.open(data.signedUrl, "_blank", "noopener,noreferrer");
      return;
    }
    const confirmed = Number(card.querySelector(".confirmed-input").value);
    if (!Number.isFinite(confirmed) || confirmed < 0) throw new Error("Enter confirmed earnings of zero or more.");
    button.disabled = true;
    const { error } = await supabase.rpc("admin_review_earnings", {
      p_submission_id: card.dataset.submissionId,
      p_confirmed_earnings: confirmed,
      p_notes: card.querySelector(".review-note").value.trim() || null,
    });
    if (error) throw error;
    showToast("Screenshot reviewed and commission calculated.");
    await loadAdminData();
  } catch (error) {
    showToast(error.message || "Could not review the submission.");
  } finally {
    button.disabled = false;
  }
}

elements.authForm.addEventListener("submit", handleAuthSubmit);
elements.authModeToggle.addEventListener("click", () => setAuthMode(authMode === "signin" ? "signup" : "signin"));
elements.signOutButton.addEventListener("click", () => supabase?.auth.signOut());
elements.campaignForm.addEventListener("submit", handleCampaignSubmit);
elements.refreshRuns.addEventListener("click", () => loadMemberData().catch((error) => showToast(error.message)));
elements.runList.addEventListener("click", handleRunDownload);
elements.refreshAdmin.addEventListener("click", () => loadAdminData().catch((error) => showToast(error.message)));
elements.adminUserRows.addEventListener("click", handleAdminTableClick);
elements.reviewQueue.addEventListener("click", handleReviewClick);
elements.earningsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadScreenshot(elements.earningsFile.files[0], elements.earningsMessage, elements.earningsSubmit);
});
elements.lockUploadForm.addEventListener("submit", (event) => {
  event.preventDefault();
  uploadScreenshot(elements.lockFile.files[0], elements.lockMessage, elements.lockSubmit);
});
elements.earningsFile.addEventListener("change", () => { elements.earningsFileLabel.textContent = elements.earningsFile.files[0]?.name || "Choose screenshot"; });
elements.lockFile.addEventListener("change", () => { elements.lockFileLabel.textContent = elements.lockFile.files[0]?.name || "Choose earnings screenshot"; });
document.querySelectorAll(".nav-link").forEach((button) => button.addEventListener("click", async () => {
  showWorkspace(button.dataset.view);
  if (button.dataset.view === "admin") await loadAdminData().catch((error) => showToast(error.message));
}));
elements.reminderUpload.addEventListener("click", (event) => {
  event.preventDefault();
  elements.reminderDialog.close();
  byId("earningsTitle").scrollIntoView({ behavior: "smooth", block: "center" });
  elements.earningsFile.focus();
});

if (!supabase) {
  setMessage(elements.authMessage, "This deployment is missing its Supabase configuration.", "error");
  elements.authSubmit.disabled = true;
} else {
  supabase.auth.onAuthStateChange((_event, nextSession) => {
    if (nextSession) enterApp(nextSession);
    else showAuth();
  });
  const { data } = await supabase.auth.getSession();
  if (data.session) await enterApp(data.session);
  else showAuth();
}
