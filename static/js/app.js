function getCookie(name) {
  const cookieValue = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`));
  return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
}

function csrfToken(form = null) {
  return (
    getCookie("csrftoken") ||
    form?.querySelector?.("input[name='csrfmiddlewaretoken']")?.value ||
    document.querySelector("input[name='csrfmiddlewaretoken']")?.value ||
    ""
  );
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
    if (key === "csrfmiddlewaretoken") {
      return;
    }
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

function projectCreateInlineSurface() {
  return document.querySelector("[data-project-create-inline] [data-project-create-surface]");
}

function projectCreateSurface(node = null) {
  return (
    node?.closest?.("[data-project-create-surface]") ||
    projectCreateInlineSurface() ||
    projectModalNode()?.querySelector("[data-project-create-surface]") ||
    document.querySelector("[data-project-create-surface]")
  );
}

function projectCreateFormNode(root = document) {
  return root?.querySelector?.("[data-project-create-form]") || null;
}

function projectCreateErrorsNode(surface) {
  return surface?.querySelector?.("[data-project-errors]") || null;
}

function projectCreateSubmitNode(surface) {
  return surface?.querySelector?.("[data-project-submit]") || null;
}

function closeDocumentSuggestionMenus(exceptShell = null) {
  document.querySelectorAll("[data-document-create-shell]").forEach((shell) => {
    if (exceptShell && shell === exceptShell) {
      return;
    }
    setDocumentSuggestionMenuState(shell, false);
  });
}

function setDocumentSuggestionMenuState(shell, isOpen) {
  if (!shell) {
    return;
  }
  const menu = shell.querySelector("[data-document-suggestions-menu]");
  const toggle = shell.querySelector("[data-document-suggestions-toggle]");
  if (menu) {
    menu.hidden = !isOpen;
  }
  shell.dataset.dropdownOpen = isOpen ? "true" : "false";
  if (toggle) {
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}

function documentSuggestionMenuIsOpen(shell) {
  return shell?.dataset?.dropdownOpen === "true";
}

function documentEditorFormNode() {
  return document.querySelector("[data-document-editor-form]");
}

function documentEditorSnapshot(form) {
  return JSON.stringify(serializeForm(form));
}

function setDocumentEditorAutosaveStatus(form, state, label = "") {
  const statusNode = form?.querySelector?.("[data-document-autosave-status]");
  if (!statusNode) {
    return;
  }

  const text = label || {
    dirty: "Unsaved",
    saving: "Saving...",
    saved: "Saved",
    error: "Save failed",
  }[state] || "Saved";

  statusNode.textContent = text;
  statusNode.classList.remove(
    "border-gray-200",
    "bg-white/90",
    "text-gray-500",
    "border-amber-200",
    "bg-amber-50",
    "text-amber-700",
    "border-blue-200",
    "bg-blue-50",
    "text-blue-700",
    "border-red-200",
    "bg-red-50",
    "text-red-700"
  );

  if (state === "dirty") {
    statusNode.classList.add("border-amber-200", "bg-amber-50", "text-amber-700");
    return;
  }

  if (state === "saving") {
    statusNode.classList.add("border-blue-200", "bg-blue-50", "text-blue-700");
    return;
  }

  if (state === "error") {
    statusNode.classList.add("border-red-200", "bg-red-50", "text-red-700");
    return;
  }

  statusNode.classList.add("border-gray-200", "bg-white/90", "text-gray-500");
}

async function flushDocumentEditorAutosave(controller, { force = false } = {}) {
  if (!controller?.form) {
    return;
  }

  window.clearTimeout(controller.timer);
  controller.timer = null;

  const currentSnapshot = documentEditorSnapshot(controller.form);
  const needsSave = force || controller.lastSavedSnapshot !== currentSnapshot;

  if (!needsSave) {
    controller.dirty = false;
    setDocumentEditorAutosaveStatus(controller.form, "saved");
    if (controller.navigateTo) {
      const href = controller.navigateTo;
      controller.navigateTo = "";
      window.location.assign(href);
    }
    return;
  }

  if (controller.inFlight) {
    controller.pendingAfterSave = true;
    return controller.inFlight;
  }

  controller.dirty = false;
  setDocumentEditorAutosaveStatus(controller.form, "saving");

  controller.inFlight = postJson(
    controller.form.dataset.apiForm,
    { ...serializeForm(controller.form), __form: controller.form },
    controller.form.dataset.apiMethod || "POST"
  )
    .then(() => {
      controller.lastSavedSnapshot = documentEditorSnapshot(controller.form);
      const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setDocumentEditorAutosaveStatus(controller.form, "saved", `Saved ${stamp}`);
    })
    .catch((error) => {
      console.error(error);
      controller.dirty = true;
      if (!error.message.startsWith("Authentication required")) {
        setDocumentEditorAutosaveStatus(controller.form, "error");
      }
      throw error;
    })
    .finally(async () => {
      controller.inFlight = null;

      if (controller.pendingAfterSave) {
        controller.pendingAfterSave = false;
        try {
          await flushDocumentEditorAutosave(controller, { force: true });
        } catch (error) {
          console.error(error);
        }
        return;
      }

      if (controller.navigateTo) {
        const href = controller.navigateTo;
        controller.navigateTo = "";
        window.location.assign(href);
      }
    });

  return controller.inFlight;
}

function initializeDocumentEditorAutosave() {
  const form = documentEditorFormNode();
  if (!form || form.dataset.autosaveInitialized === "true") {
    return;
  }

  form.dataset.autosaveInitialized = "true";

  const editorInput = form.querySelector("[data-document-editor-input]");
  if (!editorInput) {
    return;
  }

  const controller = {
    form,
    timer: null,
    inFlight: null,
    pendingAfterSave: false,
    dirty: false,
    navigateTo: "",
    lastSavedSnapshot: documentEditorSnapshot(form),
  };

  setDocumentEditorAutosaveStatus(form, "saved");

  const scheduleAutosave = () => {
    const nextSnapshot = documentEditorSnapshot(form);
    if (nextSnapshot === controller.lastSavedSnapshot) {
      controller.dirty = false;
      setDocumentEditorAutosaveStatus(form, "saved");
      window.clearTimeout(controller.timer);
      controller.timer = null;
      return;
    }

    controller.dirty = true;
    setDocumentEditorAutosaveStatus(form, "dirty");
    window.clearTimeout(controller.timer);
    controller.timer = window.setTimeout(() => {
      flushDocumentEditorAutosave(controller).catch((error) => {
        console.error(error);
      });
    }, 900);
  };

  editorInput.addEventListener("input", scheduleAutosave);
  editorInput.addEventListener("blur", () => {
    flushDocumentEditorAutosave(controller).catch((error) => {
      console.error(error);
    });
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    flushDocumentEditorAutosave(controller, { force: true }).catch((error) => {
      console.error(error);
    });
  });

  document.querySelectorAll("[data-document-link]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      if (!controller.dirty && !controller.inFlight && documentEditorSnapshot(form) === controller.lastSavedSnapshot) {
        return;
      }

      event.preventDefault();
      controller.navigateTo = link.href;
      try {
        await flushDocumentEditorAutosave(controller, { force: true });
      } catch (error) {
        console.error(error);
        const href = controller.navigateTo || link.href;
        controller.navigateTo = "";
        window.location.assign(href);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      flushDocumentEditorAutosave(controller, { force: true }).catch((error) => {
        console.error(error);
      });
    }
  });
}

function initializeDocumentCreateControls() {
  document.querySelectorAll("[data-document-create-shell]").forEach((shell) => {
    if (shell.dataset.documentControlsInitialized === "true") {
      return;
    }

    shell.dataset.documentControlsInitialized = "true";

    const form = shell.closest("[data-document-create-form]");
    const toggle = shell.querySelector("[data-document-suggestions-toggle]");
    const menu = shell.querySelector("[data-document-suggestions-menu]");
    const mainSubmit = shell.querySelector("[data-document-submit-main]");

    if (!form || !toggle || !menu) {
      return;
    }

    setDocumentSuggestionMenuState(shell, false);

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const nextOpenState = !documentSuggestionMenuIsOpen(shell);
      closeDocumentSuggestionMenus(shell);
      setDocumentSuggestionMenuState(shell, nextOpenState);
    });

    menu.querySelectorAll("[data-document-suggestion-title]").forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const titleInput = form.querySelector("input[name='title']");
        const typeInput = form.querySelector("input[name='document_type']");

        if (titleInput) {
          titleInput.value = option.dataset.documentSuggestionTitle || "";
        }

        if (typeInput) {
          typeInput.value = option.dataset.documentSuggestionType || "custom";
        }

        closeDocumentSuggestionMenus();
        form.requestSubmit();
      });
    });

    mainSubmit?.addEventListener("click", () => {
      const typeInput = form.querySelector("input[name='document_type']");
      if (typeInput) {
        typeInput.value = "custom";
      }
      closeDocumentSuggestionMenus();
    });
  });
}

function syncExportDocumentSelection(form) {
  const hiddenInput = form?.querySelector?.("[data-document-slugs-input]");
  if (!hiddenInput) {
    return;
  }
  const selected = Array.from(
    form.querySelectorAll("[data-export-document-checkbox]:checked")
  ).map((checkbox) => checkbox.value);
  hiddenInput.value = selected.join(",");
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

function hydrateProjectCreateForm(form, payload = {}) {
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

function clearProjectCreateErrorsForSurface(surface) {
  const summary = projectCreateErrorsNode(surface);
  if (summary) {
    summary.textContent = "";
    summary.classList.add("hidden");
  }
  surface?.querySelectorAll("[data-project-field-error]").forEach((fieldError) => {
    fieldError.textContent = "";
    fieldError.classList.add("hidden");
  });
}

function showProjectCreateErrors(surface, errors = {}) {
  clearProjectCreateErrorsForSurface(surface);
  const summaryMessages = [];

  Object.entries(errors).forEach(([field, messages]) => {
    const normalized = Array.isArray(messages) ? messages : [messages];
    const fieldError = surface?.querySelector?.(`[data-project-field-error='${field}']`);
    if (fieldError && normalized.length) {
      fieldError.textContent = normalized.join(" ");
      fieldError.classList.remove("hidden");
      return;
    }
    summaryMessages.push(...normalized);
  });

  if (summaryMessages.length) {
    const summary = projectCreateErrorsNode(surface);
    if (summary) {
      summary.textContent = summaryMessages.join(" ");
      summary.classList.remove("hidden");
    }
  }
}

function setProjectCreateSubmitting(surface, isSubmitting) {
  const submitButton = projectCreateSubmitNode(surface);
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
  const surface = modal.querySelector("[data-project-create-surface]");
  const form = projectCreateFormNode(surface);
  closeAuthModal();
  clearProjectCreateErrorsForSurface(surface);
  hydrateProjectCreateForm(form, loadProjectCreateDraft());
  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
  const activeInput = form?.querySelector("input[name='project_name']");
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

async function postJson(url, payload = {}, method = "POST") {
  const form = payload && typeof payload === "object" ? payload.__form || null : null;
  const requestPayload = payload && typeof payload === "object" && "__form" in payload
    ? Object.fromEntries(Object.entries(payload).filter(([key]) => key !== "__form"))
    : payload;
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": csrfToken(form)
    },
    credentials: "same-origin",
    body: JSON.stringify(requestPayload)
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
    const surface = projectCreateSurface(projectCreateForm);
    clearProjectCreateErrorsForSurface(surface);
    setProjectCreateSubmitting(surface, true);
    try {
      const payload = serializeForm(projectCreateForm);
      saveProjectCreateDraft(payload);
      if (!isAuthenticated()) {
        openAuthModal("signup");
        return;
      }
      const responsePayload = await postJson(projectCreateForm.action, { ...payload, __form: projectCreateForm });
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
      if (surface?.closest("[data-project-modal]")) {
        openProjectModal();
      }
      showProjectCreateErrors(surface, error.payload?.errors || { __all__: ["Project could not be created. Please try again."] });
    } finally {
      setProjectCreateSubmitting(surface, false);
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
  syncExportDocumentSelection(form);
  const payload = serializeForm(form);
  const method = form.dataset.apiMethod || "POST";
  try {
    await postJson(form.dataset.apiForm, { ...payload, __form: form }, method);
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

  if (!event.target.closest("[data-document-create-shell]")) {
    closeDocumentSuggestionMenus();
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

  const aiDraftButton = event.target.closest("[data-ai-draft-request]");
  if (aiDraftButton) {
    event.preventDefault();
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }
    const streamInput = document.querySelector("[data-stream-input]");
    if (!streamInput) {
      return;
    }
    const sectionTitle = aiDraftButton.dataset.sectionTitle || "this section";
    const projectName = aiDraftButton.dataset.projectName || "this project";
    const customPrompt = aiDraftButton.dataset.aiDraftPrompt || "";
    streamInput.value = customPrompt || `Help me draft the "${sectionTitle}" section for ${projectName}. Propose a concise summary and a detailed body I can paste into the spec.`;
    streamInput.scrollIntoView({ block: "nearest" });
    streamInput.focus();
    streamInput.dispatchEvent(new Event("input", { bubbles: true }));
    if (typeof streamInput.setSelectionRange === "function") {
      streamInput.setSelectionRange(streamInput.value.length, streamInput.value.length);
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
  closeDocumentSuggestionMenus();
  closeAuthModal();
  closeProjectModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeAuthModal();
  }
});

document.addEventListener("input", (event) => {
  const documentCreateForm = event.target.closest("[data-document-create-form]");
  if (documentCreateForm && event.target.name === "title") {
    const typeInput = documentCreateForm.querySelector("input[name='document_type']");
    if (typeInput) {
      typeInput.value = "custom";
    }
  }

  const apiForm = event.target.closest("[data-api-form]");
  if (apiForm?.querySelector?.("[data-document-slugs-input]")) {
    syncExportDocumentSelection(apiForm);
  }

  const projectCreateForm = event.target.closest("[data-project-create-form]");
  if (!projectCreateForm) {
    return;
  }
  saveProjectCreateDraft(serializeForm(projectCreateForm));
});

initializeDocumentCreateControls();
initializeDocumentEditorAutosave();
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

const savedProjectCreateDraft = loadProjectCreateDraft();
if (savedProjectCreateDraft) {
  const inlineSurface = projectCreateInlineSurface();
  const inlineForm = projectCreateFormNode(inlineSurface);
  if (inlineForm) {
    hydrateProjectCreateForm(inlineForm, savedProjectCreateDraft);
  } else if (isAuthenticated() && projectModalNode()) {
    openProjectModal();
  }
}
