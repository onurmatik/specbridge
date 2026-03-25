function getCookie(name) {
  const cookieValue = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`));
  return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
}

function serializeForm(form) {
  const data = {};
  const formData = new FormData(form);
  form.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    if (!checkbox.name) {
      return;
    }
    data[checkbox.name] = checkbox.checked;
  });
  formData.forEach((value, key) => {
    if (data[key] === undefined) {
      data[key] = value;
    }
  });
  return data;
}

function isAuthenticated() {
  return document.body.dataset.authenticated === "true";
}

function currentPath() {
  return document.body.dataset.currentPath || `${window.location.pathname}${window.location.search}`;
}

function authModalNode() {
  return document.querySelector("[data-auth-modal]");
}

function projectModalNode() {
  return document.querySelector("[data-project-modal]");
}

function projectCreateFormNode() {
  return document.querySelector("[data-project-create-form]");
}

const PROJECT_CREATE_DRAFT_KEY = "specbridge:create-project-draft";

function saveProjectCreateDraft(payload) {
  try {
    window.sessionStorage.setItem(PROJECT_CREATE_DRAFT_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn("Unable to save project draft", error);
  }
}

function loadProjectCreateDraft() {
  try {
    const rawDraft = window.sessionStorage.getItem(PROJECT_CREATE_DRAFT_KEY);
    return rawDraft ? JSON.parse(rawDraft) : null;
  } catch (error) {
    console.warn("Unable to read project draft", error);
    return null;
  }
}

function clearProjectCreateDraft() {
  try {
    window.sessionStorage.removeItem(PROJECT_CREATE_DRAFT_KEY);
  } catch (error) {
    console.warn("Unable to clear project draft", error);
  }
}

function hydrateProjectCreateForm(payload = {}) {
  const form = projectCreateFormNode();
  if (!form || !payload) {
    return;
  }
  Object.entries(payload).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) {
      return;
    }
    field.value = value;
  });
}

function setAuthMode(mode = "login") {
  document.querySelectorAll("[data-auth-tab-button]").forEach((button) => {
    const isActive = button.dataset.authTabButton === mode;
    button.classList.toggle("bg-white", isActive);
    button.classList.toggle("shadow-sm", isActive);
    button.classList.toggle("text-gray-900", isActive);
    button.classList.toggle("text-gray-500", !isActive);
  });
  document.querySelectorAll("[data-auth-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.authPanel !== mode);
  });
}

function clearAuthErrors(mode) {
  const summary = document.querySelector(`[data-auth-errors='${mode}']`);
  if (summary) {
    summary.textContent = "";
    summary.classList.add("hidden");
  }
  document.querySelectorAll(`[data-auth-field-error^='${mode}:']`).forEach((fieldError) => {
    fieldError.textContent = "";
    fieldError.classList.add("hidden");
  });
}

function showAuthErrors(mode, errors = {}) {
  clearAuthErrors(mode);
  const summaryMessages = [];
  Object.entries(errors).forEach(([field, messages]) => {
    const normalized = Array.isArray(messages) ? messages : [messages];
    if (field === "__all__") {
      summaryMessages.push(...normalized);
      return;
    }
    const fieldError = document.querySelector(`[data-auth-field-error='${mode}:${field}']`);
    if (fieldError && normalized.length) {
      fieldError.textContent = normalized.join(" ");
      fieldError.classList.remove("hidden");
    } else {
      summaryMessages.push(...normalized);
    }
  });

  if (summaryMessages.length) {
    const summary = document.querySelector(`[data-auth-errors='${mode}']`);
    if (summary) {
      summary.textContent = summaryMessages.join(" ");
      summary.classList.remove("hidden");
    }
  }
}

function openAuthModal(mode = "login") {
  const modal = authModalNode();
  if (!modal) {
    window.location.assign(`/login/?next=${encodeURIComponent(currentPath())}`);
    return;
  }
  closeProjectModal();
  setAuthMode(mode);
  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
  const activeInput = modal.querySelector(
    `[data-auth-panel='${mode}'] input:not([type='hidden'])`
  );
  activeInput?.focus();
}

function closeAuthModal() {
  const modal = authModalNode();
  if (!modal) {
    return;
  }
  modal.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

function clearProjectCreateErrors() {
  const summary = document.querySelector("[data-project-errors]");
  if (summary) {
    summary.textContent = "";
    summary.classList.add("hidden");
  }
  document.querySelectorAll("[data-project-field-error]").forEach((fieldError) => {
    fieldError.textContent = "";
    fieldError.classList.add("hidden");
  });
}

function showProjectCreateErrors(errors = {}) {
  clearProjectCreateErrors();
  const summaryMessages = [];

  Object.entries(errors).forEach(([field, messages]) => {
    const normalized = Array.isArray(messages) ? messages : [messages];
    const fieldError = document.querySelector(`[data-project-field-error='${field}']`);
    if (fieldError && normalized.length) {
      fieldError.textContent = normalized.join(" ");
      fieldError.classList.remove("hidden");
      return;
    }
    summaryMessages.push(...normalized);
  });

  if (summaryMessages.length) {
    const summary = document.querySelector("[data-project-errors]");
    if (summary) {
      summary.textContent = summaryMessages.join(" ");
      summary.classList.remove("hidden");
    }
  }
}

function setProjectCreateSubmitting(isSubmitting) {
  const submitButton = document.querySelector("[data-project-submit]");
  if (!submitButton) {
    return;
  }
  submitButton.disabled = isSubmitting;
  submitButton.classList.toggle("opacity-70", isSubmitting);
  submitButton.classList.toggle("cursor-wait", isSubmitting);
  submitButton.innerHTML = isSubmitting
    ? '<iconify-icon icon="lucide:loader-circle" class="animate-spin"></iconify-icon>Creating...'
    : '<iconify-icon icon="lucide:folder-plus"></iconify-icon>Create Project';
}

function openProjectModal() {
  const modal = projectModalNode();
  if (!modal) {
    return;
  }
  closeAuthModal();
  clearProjectCreateErrors();
  hydrateProjectCreateForm(loadProjectCreateDraft());
  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
  const activeInput = modal.querySelector("input[name='project_name']");
  activeInput?.focus();
}

function closeProjectModal() {
  const modal = projectModalNode();
  if (!modal) {
    return;
  }
  modal.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify(payload)
  });
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const responsePayload = isJson ? await response.json().catch(() => null) : null;
  if (response.status === 401 || response.status === 403) {
    openAuthModal("login");
    const error = new Error(`Authentication required: ${response.status}`);
    error.status = response.status;
    error.payload = responsePayload;
    throw error;
  }
  if (!response.ok) {
    const error = new Error(`Request failed: ${response.status}`);
    error.status = response.status;
    error.payload = responsePayload;
    throw error;
  }
  return responsePayload;
}

document.addEventListener("submit", async (event) => {
  const authForm = event.target.closest("[data-auth-form]");
  if (authForm) {
    event.preventDefault();
    const mode = authForm.dataset.authForm;
    clearAuthErrors(mode);
    const response = await fetch(authForm.action, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest"
      },
      body: new FormData(authForm)
    });
    const payload = await response.json();
    if (response.ok && payload.ok) {
      window.location.assign(payload.redirect_to || currentPath());
      return;
    }
    showAuthErrors(mode, payload.errors || {});
    openAuthModal(mode);
    return;
  }

  const projectCreateForm = event.target.closest("[data-project-create-form]");
  if (projectCreateForm) {
    event.preventDefault();
    clearProjectCreateErrors();
    setProjectCreateSubmitting(true);
    try {
      const payload = serializeForm(projectCreateForm);
      saveProjectCreateDraft(payload);
      if (!isAuthenticated()) {
        openAuthModal("signup");
        return;
      }
      const responsePayload = await postJson(projectCreateForm.action, payload);
      clearProjectCreateDraft();
      if (responsePayload?.redirect_to) {
        window.location.assign(responsePayload.redirect_to);
        return;
      }
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      openProjectModal();
      showProjectCreateErrors(error.payload?.errors || { __all__: ["Project could not be created. Please try again."] });
    } finally {
      setProjectCreateSubmitting(false);
    }
    return;
  }

  const form = event.target.closest("[data-api-form]");
  if (!form) {
    return;
  }
  event.preventDefault();
  if (!isAuthenticated()) {
    openAuthModal("login");
    return;
  }
  const payload = serializeForm(form);
  try {
    await postJson(form.dataset.apiForm, payload);
    window.location.reload();
  } catch (error) {
    console.error(error);
    if (error.message.startsWith("Authentication required")) {
      return;
    }
    window.alert("Action failed. Check the console for details.");
  }
});

document.addEventListener("click", async (event) => {
  const projectTrigger = event.target.closest("[data-project-modal-trigger]");
  if (projectTrigger) {
    event.preventDefault();
    openProjectModal();
    return;
  }

  const authTrigger = event.target.closest("[data-auth-modal-trigger]");
  if (authTrigger) {
    event.preventDefault();
    openAuthModal(authTrigger.dataset.authMode || "login");
    return;
  }

  const authSwitch = event.target.closest("[data-auth-switch]");
  if (authSwitch) {
    event.preventDefault();
    setAuthMode(authSwitch.dataset.authSwitch);
    return;
  }

  const authTabButton = event.target.closest("[data-auth-tab-button]");
  if (authTabButton) {
    event.preventDefault();
    setAuthMode(authTabButton.dataset.authTabButton);
    return;
  }

  const authClose = event.target.closest("[data-auth-modal-close]");
  if (authClose) {
    event.preventDefault();
    closeAuthModal();
    return;
  }

  const projectClose = event.target.closest("[data-project-modal-close]");
  if (projectClose) {
    event.preventDefault();
    closeProjectModal();
    return;
  }

  const modalBackdrop = event.target.closest("[data-auth-modal]");
  if (modalBackdrop && event.target === modalBackdrop) {
    closeAuthModal();
    return;
  }

  const projectBackdrop = event.target.closest("[data-project-modal]");
  if (projectBackdrop && event.target === projectBackdrop) {
    closeProjectModal();
    return;
  }

  const button = event.target.closest("[data-api-post]");
  if (button) {
    event.preventDefault();
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }
    try {
      await postJson(button.dataset.apiPost, {});
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      window.alert("Action failed. Check the console for details.");
    }
    return;
  }

  const copyButton = event.target.closest("[data-copy-target]");
  if (copyButton) {
    const target = document.querySelector(copyButton.dataset.copyTarget);
    if (target) {
      await navigator.clipboard.writeText(target.value || target.textContent || "");
      copyButton.textContent = "Copied";
      window.setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1500);
    }
    return;
  }

  const formatButton = event.target.closest("[data-format-button]");
  if (formatButton) {
    const nextValue = formatButton.dataset.formatButton;
    const hiddenInput = document.querySelector("[data-format-input]");
    if (hiddenInput) {
      hiddenInput.value = nextValue;
    }
    document.querySelectorAll("[data-format-button]").forEach((node) => {
      node.classList.remove("border-gray-900", "bg-gray-50", "ring-1", "ring-gray-900");
      node.classList.add("border-gray-100", "bg-white");
    });
    formatButton.classList.remove("border-gray-100", "bg-white");
    formatButton.classList.add("border-gray-900", "bg-gray-50", "ring-1", "ring-gray-900");
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }
  closeAuthModal();
  closeProjectModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeAuthModal();
  }
});

setAuthMode("login");

const autoRefreshMs = Number(document.body.dataset.autoRefresh || 0);
if (autoRefreshMs > 0) {
  window.setInterval(() => {
    const tagName = document.activeElement?.tagName?.toLowerCase();
    if (tagName === "textarea" || tagName === "input" || tagName === "select") {
      return;
    }
    if (authModalNode() && !authModalNode().classList.contains("hidden")) {
      return;
    }
    if (projectModalNode() && !projectModalNode().classList.contains("hidden")) {
      return;
    }
    window.location.reload();
  }, autoRefreshMs);
}

if (isAuthenticated() && loadProjectCreateDraft() && projectModalNode()) {
  openProjectModal();
}
