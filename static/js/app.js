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

function projectSettingsModalNode() {
  return document.querySelector("[data-project-settings-modal]");
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

function projectSettingsSurface(node = null) {
  return (
    node?.closest?.("[data-project-settings-surface]") ||
    projectSettingsModalNode()?.querySelector("[data-project-settings-surface]") ||
    document.querySelector("[data-project-settings-surface]")
  );
}

function projectSettingsFormNode(root = document) {
  return root?.querySelector?.("[data-project-settings-form]") || null;
}

function projectSettingsErrorsNode(surface) {
  return surface?.querySelector?.("[data-project-settings-errors]") || null;
}

function projectSettingsSubmitNode(surface) {
  return surface?.querySelector?.("[data-project-settings-submit]") || null;
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

function closeSectionStatusMenus(exceptShell = null) {
  document.querySelectorAll("[data-section-status-shell]").forEach((shell) => {
    if (exceptShell && shell === exceptShell) {
      return;
    }
    setSectionStatusMenuState(shell, false);
  });
}

function setSectionStatusMenuState(shell, isOpen) {
  if (!shell) {
    return;
  }
  const menu = shell.querySelector("[data-section-status-menu]");
  const toggle = shell.querySelector("[data-section-status-toggle]");
  if (menu) {
    menu.hidden = !isOpen;
  }
  shell.dataset.sectionStatusOpen = isOpen ? "true" : "false";
  if (toggle) {
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}

function sectionStatusMenuIsOpen(shell) {
  return shell?.dataset?.sectionStatusOpen === "true";
}

function closeSectionActionMenus(exceptShell = null) {
  document.querySelectorAll("[data-section-actions-shell]").forEach((shell) => {
    if (exceptShell && shell === exceptShell) {
      return;
    }
    setSectionActionMenuState(shell, false);
  });
}

function setSectionActionMenuState(shell, isOpen) {
  if (!shell) {
    return;
  }
  const menu = shell.querySelector("[data-section-actions-menu]");
  const toggle = shell.querySelector("[data-section-actions-toggle]");
  if (menu) {
    menu.hidden = !isOpen;
  }
  shell.dataset.sectionActionsOpen = isOpen ? "true" : "false";
  if (toggle) {
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}

function sectionActionMenuIsOpen(shell) {
  return shell?.dataset?.sectionActionsOpen === "true";
}

function closeSectionAiMenus(exceptShell = null) {
  document.querySelectorAll("[data-section-ai-shell]").forEach((shell) => {
    if (exceptShell && shell === exceptShell) {
      return;
    }
    setSectionAiMenuState(shell, false);
  });
}

function setSectionAiMenuState(shell, isOpen) {
  if (!shell) {
    return;
  }
  const menu = shell.querySelector("[data-section-ai-menu]");
  const toggle = shell.querySelector("[data-section-ai-toggle]");
  if (menu) {
    menu.hidden = !isOpen;
  }
  shell.dataset.sectionAiOpen = isOpen ? "true" : "false";
  if (toggle) {
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}

function sectionAiMenuIsOpen(shell) {
  return shell?.dataset?.sectionAiOpen === "true";
}

const documentEditorAutosaveControllers = [];
const specSectionAutosaveControllers = [];
let specNavigationCleanup = null;

function documentEditorFormNodes() {
  return Array.from(document.querySelectorAll("[data-document-editor-form]"));
}

function documentEditorSnapshot(form) {
  return JSON.stringify(serializeForm(form));
}

function resizeDocumentEditorInput(input) {
  if (!input) {
    return;
  }
  input.style.height = "auto";
  input.style.height = `${Math.max(input.scrollHeight, 320)}px`;
}

function setAutosaveStatus(statusNode, state, label = "") {
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
    "text-gray-400",
    "text-gray-500",
    "text-amber-600",
    "text-blue-600",
    "text-red-600"
  );

  if (state === "dirty") {
    statusNode.classList.add("text-amber-600");
    return;
  }

  if (state === "saving") {
    statusNode.classList.add("text-blue-600");
    return;
  }

  if (state === "error") {
    statusNode.classList.add("text-red-600");
    return;
  }

  statusNode.classList.add("text-gray-400");
}

function setDocumentEditorAutosaveStatus(form, state, label = "") {
  const statusNode = form?.querySelector?.("[data-document-autosave-status]");
  setAutosaveStatus(statusNode, state, label);
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
      }
    });

  return controller.inFlight;
}

const SPEC_EDITOR_HEADING_PATTERN = /^\s{0,3}(#{1,6})\s+(.*?)\s*$/;
const SPEC_EDITOR_LIST_PATTERN = /^(\s*)([-*]|\d+\.)\s+(.*)$/;

function escapeHtml(value) {
  return `${value || ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function specNormalizedMarkTypes(marks) {
  const normalized = [];
  (marks || []).forEach((mark) => {
    const markType = typeof mark === "string" ? mark : mark?.type;
    if ((markType === "bold" || markType === "italic") && !normalized.includes(markType)) {
      normalized.push(markType);
    }
  });
  return ["bold", "italic"].filter((markType) => normalized.includes(markType));
}

function specMarkObjects(markTypes) {
  return specNormalizedMarkTypes(markTypes).map((type) => ({ type }));
}

function specMarkSignature(node) {
  return specNormalizedMarkTypes(node?.marks || []).join("|");
}

function specAppendInlineText(nodes, text, marks = []) {
  if (!text) {
    return;
  }
  const normalizedMarks = specMarkObjects(marks);
  const signature = specNormalizedMarkTypes(normalizedMarks).join("|");
  const previous = nodes[nodes.length - 1];
  if (previous?.type === "text" && specMarkSignature(previous) === signature) {
    previous.text = `${previous.text || ""}${text}`;
    return;
  }
  nodes.push(specTextNode(text, normalizedMarks));
}

function specTextNode(text, marks = []) {
  const node = { type: "text", text: `${text || ""}` };
  const normalizedMarks = specMarkObjects(marks);
  if (normalizedMarks.length) {
    node.marks = normalizedMarks;
  }
  return node;
}

function specInlineNodes(value) {
  if (typeof value === "string") {
    return parseSpecInlineMarkdown(value);
  }
  if (!Array.isArray(value)) {
    return [];
  }

  const nodes = [];
  value.forEach((node) => {
    if (!node || typeof node !== "object") {
      return;
    }
    if (node.type === "text") {
      specAppendInlineText(nodes, `${node.text || ""}`, node.marks || []);
      return;
    }
    (Array.isArray(node.content) ? node.content : []).forEach((child) => {
      specInlineNodes([child]).forEach((grandchild) => {
        specAppendInlineText(nodes, `${grandchild.text || ""}`, grandchild.marks || []);
      });
    });
  });
  return nodes;
}

function specParagraphNode(text = "") {
  const content = specInlineNodes(text);
  return content.length
    ? { type: "paragraph", content }
    : { type: "paragraph", content: [] };
}

function specHeadingNode(text = "", level = 2) {
  const normalizedLevel = Math.max(1, Math.min(Number.parseInt(level || 2, 10) || 2, 6));
  return {
    type: "heading",
    attrs: { level: normalizedLevel },
    content: specInlineNodes(text),
  };
}

function specListItemNode(text = "", children = []) {
  const paragraphContent = specInlineNodes(text);
  const content = [];
  if (paragraphContent.length || !children.length) {
    content.push(specParagraphNode(paragraphContent));
  }
  content.push(...children);
  return { type: "listItem", content };
}

function specBulletListNode(items = []) {
  return {
    type: "bulletList",
    content: items
      .map((item) => (typeof item === "string" ? specListItemNode(item) : item))
      .filter((item) => item && typeof item === "object"),
  };
}

function specOrderedListNode(items = [], start = 1) {
  return {
    type: "orderedList",
    attrs: { start: Math.max(Number.parseInt(start || 1, 10) || 1, 1) },
    content: items
      .map((item) => (typeof item === "string" ? specListItemNode(item) : item))
      .filter((item) => item && typeof item === "object"),
  };
}

function specInlineTextFromNode(node) {
  if (!node || typeof node !== "object") {
    return "";
  }
  if (node.type === "text") {
    return `${node.text || ""}`;
  }
  return Array.isArray(node.content)
    ? node.content.map((child) => specInlineTextFromNode(child)).join("")
    : "";
}

function specSliceInlineContent(content, offset) {
  const nodes = [];
  let remainingOffset = Math.max(Number.parseInt(offset || 0, 10) || 0, 0);
  (Array.isArray(content) ? content : []).forEach((node) => {
    if (!node || node.type !== "text") {
      return;
    }
    const text = `${node.text || ""}`;
    if (!text) {
      return;
    }
    if (remainingOffset >= text.length) {
      remainingOffset -= text.length;
      return;
    }
    specAppendInlineText(nodes, text.slice(remainingOffset), node.marks || []);
    remainingOffset = 0;
  });
  return nodes;
}

function specMarkdownShortcutMatch(text) {
  const normalized = `${text || ""}`
    .replace(/\u200B/g, "")
    .replace(/\u00a0/g, " ");

  const headingMatch = normalized.match(/^(#{1,6})(\s+)(.*)$/);
  if (headingMatch) {
    return {
      type: "heading",
      level: headingMatch[1].length,
      prefixLength: headingMatch[1].length + headingMatch[2].length,
      text: headingMatch[3] || "",
    };
  }

  const listMatch = normalized.match(/^([-*]|\d+\.)(\s+)(.*)$/);
  if (listMatch) {
    return {
      type: listMatch[1].endsWith(".") ? "orderedList" : "bulletList",
      start: listMatch[1].endsWith(".") ? Math.max(Number.parseInt(listMatch[1], 10) || 1, 1) : 1,
      prefixLength: listMatch[1].length + listMatch[2].length,
      text: listMatch[3] || "",
    };
  }

  return null;
}

function specMarkdownShortcutBlockFromParagraphContent(content) {
  const inlineContent = Array.isArray(content) ? content : [];
  const match = specMarkdownShortcutMatch(specInlineTextFromNode({ content: inlineContent }));
  if (!match) {
    return null;
  }
  const bodyContent = specSliceInlineContent(inlineContent, match.prefixLength);
  if (match.type === "heading") {
    return specHeadingNode(bodyContent, match.level);
  }
  const item = specListItemNode(bodyContent);
  return match.type === "orderedList"
    ? specOrderedListNode([item], match.start)
    : specBulletListNode([item]);
}

function specEscapeInlineMarkdown(text) {
  return `${text || ""}`
    .replaceAll("\\", "\\\\")
    .replaceAll("*", "\\*")
    .replaceAll("_", "\\_");
}

function specInlineMarkdownFromNode(node) {
  if (!node || typeof node !== "object") {
    return "";
  }
  if (node.type === "text") {
    const text = specEscapeInlineMarkdown(node.text || "");
    const markTypes = new Set(specNormalizedMarkTypes(node.marks || []));
    if (markTypes.has("bold") && markTypes.has("italic")) {
      return `***${text}***`;
    }
    if (markTypes.has("bold")) {
      return `**${text}**`;
    }
    if (markTypes.has("italic")) {
      return `*${text}*`;
    }
    return text;
  }
  return Array.isArray(node.content)
    ? node.content.map((child) => specInlineMarkdownFromNode(child)).join("")
    : "";
}

function specBlockIsEmpty(block) {
  if (!block || typeof block !== "object") {
    return true;
  }
  if (block.type === "paragraph" || block.type === "heading") {
    return !specInlineTextFromNode(block).trim();
  }
  if (block.type === "listItem") {
    return !(Array.isArray(block.content) && block.content.some((child) => !specBlockIsEmpty(child)));
  }
  if (block.type === "bulletList" || block.type === "orderedList") {
    return !(Array.isArray(block.content) && block.content.some((item) => !specBlockIsEmpty(item)));
  }
  return !specInlineTextFromNode(block).trim();
}

function normalizeSpecBlocks(blocks) {
  const normalized = Array.isArray(blocks)
    ? blocks.filter((block) => !specBlockIsEmpty(block))
    : [];
  return normalized.length ? normalized : [specParagraphNode("")];
}

function specLineIndent(line) {
  return (line.match(/^ */) || [""])[0].length;
}

function nextNonBlankSpecLineIndex(lines, startIndex) {
  let index = startIndex;
  while (index < lines.length && !lines[index].trim()) {
    index += 1;
  }
  return index;
}

function specUnderscoreMarkerIsWordInternal(text, index, token) {
  if (!token.startsWith("_")) {
    return false;
  }
  const before = index > 0 ? text[index - 1] : "";
  const after = index + token.length < text.length ? text[index + token.length] : "";
  return /\w/.test(before) && /\w/.test(after);
}

function specFindClosingInlineToken(text, token, startIndex) {
  let index = startIndex;
  while (index < text.length) {
    if (text[index] === "\\") {
      index += 2;
      continue;
    }
    if (text.startsWith(token, index)) {
      if (token.startsWith("_") && specUnderscoreMarkerIsWordInternal(text, index, token)) {
        index += 1;
        continue;
      }
      return index;
    }
    index += 1;
  }
  return -1;
}

function parseSpecInlineMarkdown(text, activeMarks = []) {
  const value = `${text || ""}`;
  const nodes = [];
  let buffer = "";
  let index = 0;
  const markers = [
    ["***", ["bold", "italic"]],
    ["___", ["bold", "italic"]],
    ["**", ["bold"]],
    ["__", ["bold"]],
    ["*", ["italic"]],
    ["_", ["italic"]],
  ];

  while (index < value.length) {
    if (value[index] === "\\" && index + 1 < value.length) {
      buffer += value[index + 1];
      index += 2;
      continue;
    }

    let matched = false;
    for (const [token, tokenMarks] of markers) {
      if (!value.startsWith(token, index)) {
        continue;
      }
      if (token.startsWith("_") && specUnderscoreMarkerIsWordInternal(value, index, token)) {
        continue;
      }
      const closingIndex = specFindClosingInlineToken(value, token, index + token.length);
      const innerText = closingIndex >= 0 ? value.slice(index + token.length, closingIndex) : "";
      if (closingIndex < 0 || !innerText) {
        continue;
      }
      if (buffer) {
        specAppendInlineText(nodes, buffer, activeMarks);
        buffer = "";
      }
      parseSpecInlineMarkdown(
        innerText,
        [...specNormalizedMarkTypes(activeMarks), ...tokenMarks]
      ).forEach((node) => {
        specAppendInlineText(nodes, `${node.text || ""}`, node.marks || []);
      });
      index = closingIndex + token.length;
      matched = true;
      break;
    }

    if (matched) {
      continue;
    }

    buffer += value[index];
    index += 1;
  }

  if (buffer) {
    specAppendInlineText(nodes, buffer, activeMarks);
  }
  return nodes;
}

function parseSpecParagraph(lines, startIndex, currentIndent) {
  const parts = [];
  let index = startIndex;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      break;
    }
    if (SPEC_EDITOR_HEADING_PATTERN.test(line) && specLineIndent(line) <= currentIndent) {
      break;
    }
    const listMatch = line.match(SPEC_EDITOR_LIST_PATTERN);
    if (listMatch && specLineIndent(line) <= currentIndent) {
      break;
    }
    if (currentIndent && specLineIndent(line) <= currentIndent && parts.length) {
      break;
    }
    parts.push(line.trim());
    index += 1;
  }
  return [specParagraphNode(parts.join(" ").trim()), index];
}

function parseSpecList(lines, startIndex, currentIndent) {
  const firstMatch = lines[startIndex]?.match(SPEC_EDITOR_LIST_PATTERN);
  if (!firstMatch) {
    return [specParagraphNode(lines[startIndex] || ""), startIndex + 1];
  }

  const ordered = firstMatch[2].endsWith(".");
  const startNumber = ordered ? Number.parseInt(firstMatch[2].slice(0, -1), 10) || 1 : 1;
  const items = [];
  let index = startIndex;

  while (index < lines.length) {
    index = nextNonBlankSpecLineIndex(lines, index);
    if (index >= lines.length) {
      break;
    }
    const match = lines[index].match(SPEC_EDITOR_LIST_PATTERN);
    if (!match || specLineIndent(lines[index]) !== currentIndent) {
      break;
    }
    if (match[2].endsWith(".") !== ordered) {
      break;
    }

    const bodyParts = match[3].trim() ? [match[3].trim()] : [];
    const children = [];
    index += 1;

    while (index < lines.length) {
      if (!lines[index].trim()) {
        const nextIndex = nextNonBlankSpecLineIndex(lines, index);
        if (nextIndex >= lines.length) {
          index = nextIndex;
          break;
        }
        const nextMatch = lines[nextIndex].match(SPEC_EDITOR_LIST_PATTERN);
        const nextIndent = specLineIndent(lines[nextIndex]);
        if (nextMatch && nextIndent === currentIndent) {
          index = nextIndex;
          break;
        }
        if (nextMatch && nextIndent > currentIndent) {
          index = nextIndex;
          const [nestedList, nestedIndex] = parseSpecList(lines, index, nextIndent);
          children.push(nestedList);
          index = nestedIndex;
          continue;
        }
        if (nextIndent <= currentIndent) {
          index = nextIndex;
          break;
        }
        bodyParts.push(lines[nextIndex].trim());
        index = nextIndex + 1;
        continue;
      }

      const nextMatch = lines[index].match(SPEC_EDITOR_LIST_PATTERN);
      const nextIndent = specLineIndent(lines[index]);
      if (nextMatch && nextIndent === currentIndent) {
        break;
      }
      if (nextMatch && nextIndent > currentIndent) {
        const [nestedList, nestedIndex] = parseSpecList(lines, index, nextIndent);
        children.push(nestedList);
        index = nestedIndex;
        continue;
      }
      if (nextIndent <= currentIndent) {
        break;
      }
      bodyParts.push(lines[index].trim());
      index += 1;
    }

    items.push(specListItemNode(bodyParts.join(" ").trim(), children.filter((child) => !specBlockIsEmpty(child))));
  }

  return [
    ordered ? specOrderedListNode(items, startNumber) : specBulletListNode(items),
    index,
  ];
}

function specMarkdownToBlocks(markdown) {
  const value = `${markdown || ""}`.trim();
  if (!value) {
    return [specParagraphNode("")];
  }

  const lines = value.split(/\r?\n/).map((line) => line.replace(/\s+$/, ""));
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const headingMatch = line.match(SPEC_EDITOR_HEADING_PATTERN);
    if (headingMatch) {
      blocks.push(specHeadingNode(headingMatch[2].trim(), headingMatch[1].length));
      index += 1;
      continue;
    }

    const listMatch = line.match(SPEC_EDITOR_LIST_PATTERN);
    if (listMatch) {
      const [block, nextIndex] = parseSpecList(lines, index, specLineIndent(line));
      blocks.push(block);
      index = nextIndex;
      continue;
    }

    const [block, nextIndex] = parseSpecParagraph(lines, index, 0);
    blocks.push(block);
    index = nextIndex;
  }

  return normalizeSpecBlocks(blocks);
}

function markdownLinesFromSpecListItem(item, indent, marker) {
  const content = Array.isArray(item?.content) ? item.content : [];
  const paragraph = content.find((child) => child?.type === "paragraph");
  const nestedLists = content.filter((child) => child?.type === "bulletList" || child?.type === "orderedList");
  const otherChildren = content.filter((child) => (
    child?.type !== "paragraph"
    && child?.type !== "bulletList"
    && child?.type !== "orderedList"
  ));
  const lines = [`${" ".repeat(indent)}${marker} ${specInlineMarkdownFromNode(paragraph || {}).trim()}`.trimEnd()];
  nestedLists.forEach((child) => {
    const childMarkdown = markdownFromSpecBlock(child, indent + 2);
    if (childMarkdown) {
      lines.push(...childMarkdown.split("\n"));
    }
  });
  otherChildren.forEach((child) => {
    const childText = specInlineMarkdownFromNode(child).trim();
    if (childText) {
      lines.push(`${" ".repeat(indent + 2)}${childText}`);
    }
  });
  return lines;
}

function markdownFromSpecBlock(block, indent = 0) {
  if (!block || typeof block !== "object") {
    return "";
  }
  if (block.type === "paragraph") {
    return specInlineMarkdownFromNode(block).trim();
  }
  if (block.type === "heading") {
    const level = Math.max(1, Math.min(Number.parseInt(block.attrs?.level || 1, 10) || 1, 6));
    return `${"#".repeat(level)} ${specInlineMarkdownFromNode(block).trim()}`.trimEnd();
  }
  if (block.type === "bulletList" || block.type === "orderedList") {
    const start = Math.max(Number.parseInt(block.attrs?.start || 1, 10) || 1, 1);
    const lines = [];
    (block.content || []).forEach((item, offset) => {
      const marker = block.type === "orderedList" ? `${start + offset}.` : "-";
      lines.push(...markdownLinesFromSpecListItem(item, indent, marker));
    });
    return lines.join("\n");
  }
  return specInlineMarkdownFromNode(block).trim();
}

function specBlocksToMarkdown(blocks) {
  return normalizeSpecBlocks(blocks)
    .map((block) => markdownFromSpecBlock(block).trim())
    .filter(Boolean)
    .join("\n\n")
    .trim();
}

function specInlineHtmlFromNode(node) {
  if (!node || typeof node !== "object") {
    return "";
  }
  if (node.type === "text") {
    let html = escapeHtml(node.text || "");
    const markTypes = new Set(specNormalizedMarkTypes(node.marks || []));
    if (markTypes.has("italic")) {
      html = `<em>${html}</em>`;
    }
    if (markTypes.has("bold")) {
      html = `<strong>${html}</strong>`;
    }
    return html;
  }
  return Array.isArray(node.content)
    ? node.content.map((child) => specInlineHtmlFromNode(child)).join("")
    : "";
}

function specBlockToEditorHtml(block) {
  if (!block || typeof block !== "object") {
    return "";
  }
  if (block.type === "paragraph") {
    const text = specInlineHtmlFromNode(block);
    return `<p>${text || "<br>"}</p>`;
  }
  if (block.type === "heading") {
    const level = Math.max(1, Math.min(Number.parseInt(block.attrs?.level || 2, 10) || 2, 6));
    const text = specInlineHtmlFromNode(block);
    return `<h${level}>${text || "<br>"}</h${level}>`;
  }
  if (block.type === "bulletList" || block.type === "orderedList") {
    const tag = block.type === "orderedList" ? "ol" : "ul";
    const start = block.type === "orderedList"
      ? ` start="${Math.max(Number.parseInt(block.attrs?.start || 1, 10) || 1, 1)}"`
      : "";
    const items = (block.content || []).map((item) => specListItemToEditorHtml(item)).join("");
    return `<${tag}${start}>${items}</${tag}>`;
  }
  return "";
}

function specListItemToEditorHtml(item) {
  const content = Array.isArray(item?.content) ? item.content : [];
  const paragraph = content.find((child) => child?.type === "paragraph");
  const nestedLists = content.filter((child) => child?.type === "bulletList" || child?.type === "orderedList");
  const text = specInlineHtmlFromNode(paragraph || {});
  const nestedHtml = nestedLists.map((child) => specBlockToEditorHtml(child)).join("");
  return `<li>${text || (!nestedHtml ? "<br>" : "")}${nestedHtml}</li>`;
}

function specBlocksToEditorHtml(blocks) {
  const html = normalizeSpecBlocks(blocks).map((block) => specBlockToEditorHtml(block)).join("");
  return html || "<p><br></p>";
}

function specElementStyleMarks(element) {
  if (!(element instanceof HTMLElement)) {
    return [];
  }
  const marks = [];
  const fontWeight = `${element.style?.fontWeight || ""}`.toLowerCase();
  const fontWeightValue = Number.parseInt(fontWeight, 10);
  if (
    element.tagName?.toLowerCase() === "strong"
    || element.tagName?.toLowerCase() === "b"
    || fontWeight === "bold"
    || fontWeight === "bolder"
    || (!Number.isNaN(fontWeightValue) && fontWeightValue >= 600)
  ) {
    marks.push("bold");
  }
  if (
    element.tagName?.toLowerCase() === "em"
    || element.tagName?.toLowerCase() === "i"
    || `${element.style?.fontStyle || ""}`.toLowerCase() === "italic"
  ) {
    marks.push("italic");
  }
  return marks;
}

function specInlineNodesFromDom(node, activeMarks = []) {
  if (!node) {
    return [];
  }
  if (node.nodeType === Node.TEXT_NODE) {
    const text = `${node.textContent || ""}`.replace(/\u200B/g, "");
    return text ? [specTextNode(text, activeMarks)] : [];
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return [];
  }

  const tag = node.tagName.toLowerCase();
  if (tag === "br") {
    return [];
  }

  const nextMarks = [...specNormalizedMarkTypes(activeMarks), ...specElementStyleMarks(node)];
  const nodes = [];
  Array.from(node.childNodes).forEach((child) => {
    specInlineNodesFromDom(child, nextMarks).forEach((inlineNode) => {
      specAppendInlineText(nodes, `${inlineNode.text || ""}`, inlineNode.marks || []);
    });
  });
  return nodes;
}

function specBlockFromElement(element) {
  if (!element || element.nodeType !== Node.ELEMENT_NODE) {
    return null;
  }
  const tag = element.tagName.toLowerCase();
  if (tag === "p" || tag === "div") {
    const inlineContent = specInlineNodesFromDom(element);
    return specMarkdownShortcutBlockFromParagraphContent(inlineContent) || specParagraphNode(inlineContent);
  }
  if (/^h[1-6]$/.test(tag)) {
    return specHeadingNode(specInlineNodesFromDom(element), Number.parseInt(tag.slice(1), 10));
  }
  if (tag === "ul" || tag === "ol") {
    return specListNodeFromElement(element);
  }
  return null;
}

function specBlocksFromContainerElement(element) {
  const block = specBlockFromElement(element);
  return block ? [block] : [];
}

function specListItemFromElement(element) {
  const inlineNodes = [];
  const children = [];
  Array.from(element.childNodes).forEach((child) => {
    if (child.nodeType === Node.ELEMENT_NODE) {
      const tag = child.tagName.toLowerCase();
      if (tag === "ul" || tag === "ol") {
        children.push(specListNodeFromElement(child));
        return;
      }
      if (tag === "br") {
        return;
      }
    }
    specInlineNodesFromDom(child).forEach((inlineNode) => {
      specAppendInlineText(inlineNodes, `${inlineNode.text || ""}`, inlineNode.marks || []);
    });
  });
  return specListItemNode(
    inlineNodes,
    children.filter((child) => !specBlockIsEmpty(child))
  );
}

function specListNodeFromElement(element) {
  const tag = element.tagName.toLowerCase();
  const items = Array.from(element.children)
    .filter((child) => child.tagName?.toLowerCase() === "li")
    .map((child) => specListItemFromElement(child))
    .filter((item) => !specBlockIsEmpty(item));
  const start = tag === "ol"
    ? Math.max(Number.parseInt(element.getAttribute("start") || "1", 10) || 1, 1)
    : 1;
  return tag === "ol"
    ? specOrderedListNode(items, start)
    : specBulletListNode(items);
}

function specBlocksFromDomNode(node) {
  if (!node) {
    return [];
  }
  if (node.nodeType === Node.TEXT_NODE) {
    const text = `${node.textContent || ""}`.replace(/\u200B/g, "").trim();
    return text ? [specParagraphNode(text)] : [];
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return [];
  }

  const tag = node.tagName.toLowerCase();
  if (tag === "p" || tag === "div") {
    return specBlocksFromContainerElement(node);
  }
  if (/^h[1-6]$/.test(tag)) {
    return [specHeadingNode(specInlineNodesFromDom(node), Number.parseInt(tag.slice(1), 10))];
  }
  if (tag === "ul" || tag === "ol") {
    return [specListNodeFromElement(node)];
  }
  if (tag === "br") {
    return [];
  }
  return Array.from(node.childNodes).flatMap((child) => specBlocksFromDomNode(child));
}

function specBlocksFromEditor(editor) {
  if (!editor) {
    return [specParagraphNode("")];
  }
  return normalizeSpecBlocks(
    Array.from(editor.childNodes).flatMap((node) => specBlocksFromDomNode(node))
  );
}

function specSectionFormNodes() {
  return Array.from(document.querySelectorAll("[data-spec-section-form]"));
}

function specEditorNode(form) {
  return form?.querySelector?.("[data-spec-section-editor]") || null;
}

function specMarkdownNode(form) {
  return form?.querySelector?.("[data-spec-section-markdown]") || null;
}

function initialSpecSectionBlocks(form) {
  const scriptId = form?.dataset?.sectionContentScriptId || "";
  const scriptNode = scriptId ? document.getElementById(scriptId) : null;
  if (!scriptNode) {
    return [specParagraphNode("")];
  }
  try {
    return normalizeSpecBlocks(JSON.parse(scriptNode.textContent || "[]"));
  } catch (error) {
    console.error(error);
    return [specParagraphNode("")];
  }
}

function specClosestEditableBlock(node, editor) {
  let element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  if (!element || !editor) {
    return null;
  }
  const block = element.closest("p, li, h1, h2, h3, h4, h5, h6");
  return block && editor.contains(block) ? block : null;
}

function firstSpecEditableBlock(editor) {
  return editor?.querySelector?.("p, li, h1, h2, h3, h4, h5, h6") || null;
}

function specListItemText(item) {
  if (!item) {
    return "";
  }
  const textParts = [];
  Array.from(item.childNodes).forEach((child) => {
    if (child.nodeType === Node.ELEMENT_NODE) {
      const tag = child.tagName.toLowerCase();
      if (tag === "ul" || tag === "ol") {
        return;
      }
    }
    textParts.push(child.textContent || "");
  });
  return textParts.join(" ").replace(/\s+/g, " ").trim();
}

function specMarkdownMarkerForBlock(block) {
  if (!block) {
    return "";
  }
  const tag = block.tagName.toLowerCase();
  if (/^h[1-6]$/.test(tag)) {
    return `${"#".repeat(Number.parseInt(tag.slice(1), 10) || 1)} `;
  }
  if (tag === "li") {
    const list = block.parentElement;
    if (!list) {
      return "- ";
    }
    if (list.tagName.toLowerCase() === "ol") {
      const start = Math.max(Number.parseInt(list.getAttribute("start") || "1", 10) || 1, 1);
      const siblings = Array.from(list.children).filter((item) => item.tagName?.toLowerCase() === "li");
      const index = Math.max(siblings.indexOf(block), 0);
      return `${start + index}. `;
    }
    return "- ";
  }
  return "";
}

function refreshSpecEditorActiveState(form) {
  const editor = specEditorNode(form);
  if (!editor) {
    return;
  }

  editor.querySelectorAll("[data-live-md-active]").forEach((node) => {
    node.removeAttribute("data-live-md-active");
    node.removeAttribute("data-live-md-marker");
  });

  const selection = window.getSelection();
  if (!selection?.anchorNode || !editor.contains(selection.anchorNode)) {
    return;
  }

  const block = specClosestEditableBlock(selection.anchorNode, editor);
  const marker = specMarkdownMarkerForBlock(block);
  if (!block || !marker) {
    return;
  }

  block.dataset.liveMdActive = "true";
  block.dataset.liveMdMarker = marker;
}

function ensureSpecEditorCaretVisible(form) {
  const editor = specEditorNode(form);
  const selection = window.getSelection();
  if (!editor || !selection) {
    return;
  }
  if (selection.anchorNode && editor.contains(selection.anchorNode)) {
    return;
  }
  const block = firstSpecEditableBlock(editor) || editor;
  setCaretInElement(block);
}

function refreshAllSpecEditorActiveStates() {
  specSectionFormNodes().forEach((form) => {
    refreshSpecEditorActiveState(form);
  });
}

function renderSpecSectionEditor(form, blocks) {
  const editor = specEditorNode(form);
  if (!editor) {
    return;
  }
  editor.innerHTML = specBlocksToEditorHtml(blocks);
  refreshSpecEditorActiveState(form);
}

function setSpecSectionBlocks(form, blocks) {
  const normalizedBlocks = normalizeSpecBlocks(blocks);
  renderSpecSectionEditor(form, normalizedBlocks);
  const markdownInput = specMarkdownNode(form);
  if (markdownInput) {
    markdownInput.value = specBlocksToMarkdown(normalizedBlocks);
    resizeDocumentEditorInput(markdownInput);
  }
}

function getSpecSectionBlocks(form) {
  return specBlocksFromEditor(specEditorNode(form));
}

function getSpecSectionMarkdown(form) {
  return specBlocksToMarkdown(getSpecSectionBlocks(form));
}

function setSpecSectionMarkdown(form, markdown) {
  const blocks = specMarkdownToBlocks(markdown);
  setSpecSectionBlocks(form, blocks);
  return blocks;
}

function activeSpecContentInput(form) {
  return specEditorNode(form);
}

function moveCaretToEnd(node) {
  if (!node || node.nodeType !== Node.ELEMENT_NODE) {
    return;
  }
  const selection = window.getSelection();
  if (!selection) {
    return;
  }
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(false);
  selection.removeAllRanges();
  selection.addRange(range);
}

function ensureSpecCaretTextNode(element) {
  if (!element) {
    return null;
  }
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  const firstText = walker.nextNode();
  if (firstText) {
    return firstText;
  }
  const textNode = document.createTextNode("");
  element.insertBefore(textNode, element.firstChild || null);
  return textNode;
}

function setCaretInElement(element, offset = null) {
  if (!element) {
    return;
  }
  const textNode = ensureSpecCaretTextNode(element);
  const targetOffset = Math.min(
    offset ?? (textNode.textContent || "").length,
    (textNode.textContent || "").length,
  );
  const selection = window.getSelection();
  if (!selection) {
    return;
  }
  const range = document.createRange();
  range.setStart(textNode, targetOffset);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
}

function specSelectionRangeWithinEditor(editor) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount < 1) {
    return null;
  }
  const range = selection.getRangeAt(0);
  if (!editor) {
    return null;
  }
  const anchorInside = !selection.anchorNode || editor.contains(selection.anchorNode);
  const focusInside = !selection.focusNode || editor.contains(selection.focusNode);
  return anchorInside && focusInside ? range : null;
}

function specEditorForCurrentSelection() {
  const selection = window.getSelection();
  if (!selection) {
    return null;
  }
  const anchorElement = selection.anchorNode?.nodeType === Node.TEXT_NODE
    ? selection.anchorNode.parentElement
    : selection.anchorNode;
  const focusElement = selection.focusNode?.nodeType === Node.TEXT_NODE
    ? selection.focusNode.parentElement
    : selection.focusNode;
  const anchorEditor = anchorElement?.closest?.("[data-spec-section-editor]");
  const focusEditor = focusElement?.closest?.("[data-spec-section-editor]");
  if (anchorEditor && focusEditor && anchorEditor === focusEditor) {
    return anchorEditor;
  }
  return anchorEditor || focusEditor || null;
}

function specUnwrapElement(element) {
  if (!element?.parentNode) {
    return;
  }
  while (element.firstChild) {
    element.parentNode.insertBefore(element.firstChild, element);
  }
  element.remove();
}

function specClosestFormatElement(node, editor, tagName) {
  let element = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  while (element && element !== editor) {
    if (element.tagName?.toLowerCase() === tagName) {
      return element;
    }
    element = element.parentElement;
  }
  return null;
}

function specRangeCoversElementText(range, element) {
  if (!range || !element) {
    return false;
  }
  const probe = document.createRange();
  probe.selectNodeContents(element);
  return range.toString() && range.toString() === probe.toString();
}

function specWrapRangeWithTag(range, tagName) {
  if (!range || range.collapsed) {
    return false;
  }
  const fragment = range.extractContents();
  if (!fragment.textContent?.replace(/\u200B/g, "").trim() && !fragment.querySelector?.("*")) {
    return false;
  }
  const wrapper = document.createElement(tagName);
  wrapper.appendChild(fragment);
  range.insertNode(wrapper);
  const selection = window.getSelection();
  if (selection) {
    const nextRange = document.createRange();
    nextRange.selectNodeContents(wrapper);
    selection.removeAllRanges();
    selection.addRange(nextRange);
  }
  return true;
}

function specSelectionAtBlockStart(block) {
  const selection = window.getSelection();
  if (!selection || !selection.isCollapsed || !block || !selection.anchorNode) {
    return false;
  }
  const range = document.createRange();
  range.selectNodeContents(block);
  range.setEnd(selection.anchorNode, selection.anchorOffset);
  return !range.toString();
}

function replaceSpecBlockNode(block, replacement, caretTarget = null) {
  if (!block || !replacement) {
    return;
  }
  block.replaceWith(replacement);
  const target = caretTarget || replacement;
  if (target.tagName?.toLowerCase() === "ul" || target.tagName?.toLowerCase() === "ol") {
    setCaretInElement(target.querySelector("li"));
  } else {
    setCaretInElement(target);
  }
}

function maybeTransformSpecMarkdownPrefix(editor) {
  const selection = window.getSelection();
  const block = specClosestEditableBlock(selection?.anchorNode, editor);
  if (!block) {
    return false;
  }

  const tag = block.tagName.toLowerCase();
  if (tag !== "p" && tag !== "div") {
    return false;
  }

  const text = (block.textContent || "").replace(/\u200B/g, "").replace(/\u00a0/g, " ");
  const match = specMarkdownShortcutMatch(text);
  if (!match) {
    return false;
  }

  if (match.type === "heading") {
    const heading = document.createElement(`h${match.level}`);
    if (match.text) {
      heading.textContent = match.text;
    } else {
      heading.innerHTML = "<br>";
    }
    replaceSpecBlockNode(block, heading, heading);
    return true;
  }

  if (match.type === "bulletList" || match.type === "orderedList") {
    const ordered = match.type === "orderedList";
    const list = document.createElement(ordered ? "ol" : "ul");
    if (ordered) {
      list.setAttribute("start", `${match.start}`);
    }
    const item = document.createElement("li");
    if (match.text) {
      item.textContent = match.text;
    } else {
      item.innerHTML = "<br>";
    }
    list.appendChild(item);
    replaceSpecBlockNode(block, list, item);
    return true;
  }

  return false;
}

function applySpecInlineFormat(editor, command) {
  if (!editor || !command) {
    return false;
  }
  const range = specSelectionRangeWithinEditor(editor);
  const tagName = command === "bold" ? "strong" : command === "italic" ? "em" : "";
  if (range && !range.collapsed && tagName) {
    const formatAncestor = specClosestFormatElement(range.commonAncestorContainer, editor, tagName);
    if (formatAncestor && specRangeCoversElementText(range, formatAncestor)) {
      specUnwrapElement(formatAncestor);
      return true;
    }
    return specWrapRangeWithTag(range, tagName);
  }
  try {
    document.execCommand("styleWithCSS", false, false);
  } catch (error) {
    console.debug(error);
  }
  try {
    return document.execCommand(command, false);
  } catch (error) {
    console.error(error);
    return false;
  }
}

function serializeSpecSectionForm(form) {
  return {
    title: form?.querySelector?.("input[name='title']")?.value || "",
    status: form?.querySelector?.("[data-section-status-input]")?.value || "iterating",
    content_json: getSpecSectionBlocks(form),
  };
}

function specSectionSnapshot(form) {
  return JSON.stringify(serializeSpecSectionForm(form));
}

function setSpecSectionAutosaveStatus(form, state, label = "") {
  const statusNode = form?.closest?.("[data-spec-section]")?.querySelector?.("[data-spec-section-autosave-status]");
  setAutosaveStatus(statusNode, state, label);
}

async function flushSpecSectionAutosave(controller, { force = false } = {}) {
  if (!controller?.form) {
    return;
  }

  window.clearTimeout(controller.timer);
  controller.timer = null;

  const currentSnapshot = specSectionSnapshot(controller.form);
  const needsSave = force || controller.lastSavedSnapshot !== currentSnapshot;

  if (!needsSave) {
    controller.dirty = false;
    setSpecSectionAutosaveStatus(controller.form, "saved");
    return;
  }

  if (controller.inFlight) {
    controller.pendingAfterSave = true;
    return controller.inFlight;
  }

  controller.dirty = false;
  setSpecSectionAutosaveStatus(controller.form, "saving");

  controller.inFlight = postJson(
    controller.form.dataset.apiForm,
    { ...serializeSpecSectionForm(controller.form), __form: controller.form },
    controller.form.dataset.apiMethod || "POST"
  )
    .then(() => {
      controller.lastSavedSnapshot = specSectionSnapshot(controller.form);
      const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setSpecSectionAutosaveStatus(controller.form, "saved", `Saved ${stamp}`);
    })
    .catch((error) => {
      console.error(error);
      controller.dirty = true;
      if (!error.message.startsWith("Authentication required")) {
        setSpecSectionAutosaveStatus(controller.form, "error");
      }
      throw error;
    })
    .finally(async () => {
      controller.inFlight = null;
      if (controller.pendingAfterSave) {
        controller.pendingAfterSave = false;
        try {
          await flushSpecSectionAutosave(controller, { force: true });
        } catch (error) {
          console.error(error);
        }
      }
    });

  return controller.inFlight;
}

function initializeDocumentEditorAutosave() {
  documentEditorFormNodes().forEach((form) => {
    if (form.dataset.autosaveInitialized === "true") {
      return;
    }

    form.dataset.autosaveInitialized = "true";

    const editorInput = form.querySelector("[data-document-editor-input]");
    if (!editorInput) {
      return;
    }

    resizeDocumentEditorInput(editorInput);

    const controller = {
      form,
      timer: null,
      inFlight: null,
      pendingAfterSave: false,
      dirty: false,
      lastSavedSnapshot: documentEditorSnapshot(form),
    };

    documentEditorAutosaveControllers.push(controller);
    setDocumentEditorAutosaveStatus(form, "saved");

    const scheduleAutosave = () => {
      resizeDocumentEditorInput(editorInput);
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
  });

  if (document.body.dataset.documentAutosaveHotkeyInitialized === "true") {
    return;
  }
  document.body.dataset.documentAutosaveHotkeyInitialized = "true";

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      documentEditorAutosaveControllers.forEach((controller) => {
        flushDocumentEditorAutosave(controller, { force: true }).catch((error) => {
          console.error(error);
        });
      });
      specSectionAutosaveControllers.forEach((controller) => {
        flushSpecSectionAutosave(controller, { force: true }).catch((error) => {
          console.error(error);
        });
      });
    }
  });
}

function initializeSpecSectionEditors() {
  specSectionFormNodes().forEach((form) => {
    if (form.dataset.editorInitialized === "true") {
      return;
    }

    form.dataset.editorInitialized = "true";
    const editor = specEditorNode(form);
    const markdownInput = specMarkdownNode(form);

    if (!editor || !markdownInput) {
      return;
    }

    setSpecSectionBlocks(form, initialSpecSectionBlocks(form));

    editor.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = event.clipboardData?.getData("text/plain") || "";
      document.execCommand("insertText", false, text);
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    });

    editor.addEventListener("focus", () => {
      ensureSpecEditorCaretVisible(form);
      refreshSpecEditorActiveState(form);
    });

    editor.addEventListener("keydown", (event) => {
      if (event.key === "Tab") {
        event.preventDefault();
        document.execCommand(event.shiftKey ? "outdent" : "indent", false);
        editor.dispatchEvent(new Event("input", { bubbles: true }));
        return;
      }

      if (event.key === "Backspace") {
        const selection = window.getSelection();
        let node = selection?.anchorNode || null;
        if (node?.nodeType === Node.TEXT_NODE) {
          node = node.parentElement;
        }
        const block = specClosestEditableBlock(node, editor);
        if (block && specSelectionAtBlockStart(block)) {
          if (/^h[1-6]$/.test(block.tagName.toLowerCase())) {
            event.preventDefault();
            const paragraph = document.createElement("p");
            paragraph.textContent = block.textContent || "";
            replaceSpecBlockNode(block, paragraph, paragraph);
            editor.dispatchEvent(new Event("input", { bubbles: true }));
            return;
          }
          if (block.tagName.toLowerCase() === "li") {
            event.preventDefault();
            document.execCommand("outdent", false);
            editor.dispatchEvent(new Event("input", { bubbles: true }));
            return;
          }
        }
      }

      if (event.key !== "Enter") {
        return;
      }

      const selection = window.getSelection();
      let node = selection?.anchorNode || null;
      if (node?.nodeType === Node.TEXT_NODE) {
        node = node.parentElement;
      }
      const listItem = node?.closest?.("li");
      const listNode = node?.closest?.("ul, ol");
      if (listItem && listNode && !listItem.textContent.replace(/\u200B/g, "").trim() && !listItem.querySelector("ul, ol")) {
        event.preventDefault();
        document.execCommand("outdent", false);
        document.execCommand("formatBlock", false, "P");
        editor.dispatchEvent(new Event("input", { bubbles: true }));
      }
    });

    editor.addEventListener("input", () => {
      if (maybeTransformSpecMarkdownPrefix(editor)) {
        refreshSpecEditorActiveState(form);
      }
      markdownInput.value = specBlocksToMarkdown(specBlocksFromEditor(editor));
      refreshSpecEditorActiveState(form);
    });

    editor.addEventListener("click", () => {
      ensureSpecEditorCaretVisible(form);
      refreshSpecEditorActiveState(form);
    });
  });

  if (document.body.dataset.specEditorSelectionInitialized === "true") {
    return;
  }
  document.body.dataset.specEditorSelectionInitialized = "true";
  document.addEventListener("selectionchange", () => {
    refreshAllSpecEditorActiveStates();
  });

  if (document.body.dataset.specEditorInlineFormatInitialized === "true") {
    return;
  }
  document.body.dataset.specEditorInlineFormatInitialized = "true";

  const handleSpecInlineFormat = (command) => {
    const editor = specEditorForCurrentSelection();
    if (!editor) {
      return false;
    }
    applySpecInlineFormat(editor, command);
    window.requestAnimationFrame(() => {
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    });
    return true;
  };

  document.addEventListener("beforeinput", (event) => {
    if (event.inputType !== "formatBold" && event.inputType !== "formatItalic") {
      return;
    }
    if (!specEditorForCurrentSelection()) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    handleSpecInlineFormat(event.inputType === "formatBold" ? "bold" : "italic");
  }, true);

  document.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey) || event.altKey) {
      return;
    }
    const code = `${event.code || ""}`.toLowerCase();
    const key = `${event.key || ""}`.toLowerCase();
    const isBold = code === "keyb" || key === "b";
    const isItalic = code === "keyi" || key === "i" || key === "ı";
    if (!isBold && !isItalic) {
      return;
    }
    if (!specEditorForCurrentSelection()) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    handleSpecInlineFormat(isBold ? "bold" : "italic");
  }, true);
}

function initializeSpecSectionAutosave() {
  specSectionFormNodes().forEach((form) => {
    if (form.dataset.autosaveInitialized === "true") {
      return;
    }

    form.dataset.autosaveInitialized = "true";
    const titleInput = form.querySelector("input[name='title']");
    const statusInput = form.querySelector("[data-section-status-input]");
    const editor = specEditorNode(form);
    const markdownInput = specMarkdownNode(form);
    if (!titleInput || !statusInput || !editor || !markdownInput) {
      return;
    }

    const controller = {
      form,
      timer: null,
      inFlight: null,
      pendingAfterSave: false,
      dirty: false,
      lastSavedSnapshot: specSectionSnapshot(form),
    };

    specSectionAutosaveControllers.push(controller);
    setSpecSectionAutosaveStatus(form, "saved");

    const scheduleAutosave = () => {
      const nextSnapshot = specSectionSnapshot(form);
      if (nextSnapshot === controller.lastSavedSnapshot) {
        controller.dirty = false;
        setSpecSectionAutosaveStatus(form, "saved");
        window.clearTimeout(controller.timer);
        controller.timer = null;
        return;
      }

      controller.dirty = true;
      setSpecSectionAutosaveStatus(form, "dirty");
      window.clearTimeout(controller.timer);
      controller.timer = window.setTimeout(() => {
        flushSpecSectionAutosave(controller).catch((error) => {
          console.error(error);
        });
      }, 900);
    };

    [titleInput, statusInput].forEach((field) => {
      field.addEventListener("input", scheduleAutosave);
      field.addEventListener("change", scheduleAutosave);
      if (field.type !== "hidden") {
        field.addEventListener("blur", () => {
          flushSpecSectionAutosave(controller).catch((error) => {
            console.error(error);
          });
        });
      }
    });

    editor.addEventListener("input", scheduleAutosave);
    editor.addEventListener("blur", () => {
      flushSpecSectionAutosave(controller).catch((error) => {
        console.error(error);
      });
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      flushSpecSectionAutosave(controller, { force: true }).catch((error) => {
        console.error(error);
      });
    });
  });
}

function resetSpecSectionAutosaveControllers() {
  specSectionAutosaveControllers.forEach((controller) => {
    window.clearTimeout(controller?.timer);
    if (controller) {
      controller.timer = null;
      controller.pendingAfterSave = false;
    }
  });
  specSectionAutosaveControllers.length = 0;
}

async function flushAllPendingAutosaves() {
  const pendingSaves = [
    ...documentEditorAutosaveControllers.map((controller) => flushDocumentEditorAutosave(controller, { force: true })),
    ...specSectionAutosaveControllers.map((controller) => flushSpecSectionAutosave(controller, { force: true })),
  ];
  await Promise.all(pendingSaves);
}

function applySectionStatusState(shell, statusValue) {
  if (!shell) {
    return;
  }

  const normalizedStatus = `${statusValue || "iterating"}`.trim().toLowerCase() || "iterating";
  const toggle = shell.querySelector("[data-section-status-toggle]");
  const label = shell.querySelector("[data-section-status-label]");

  if (label) {
    label.textContent = normalizedStatus;
  }

  if (toggle) {
    toggle.classList.remove(
      "border-green-100",
      "bg-green-50",
      "text-green-700",
      "hover:border-green-200",
      "hover:bg-green-100/70",
      "border-red-100",
      "bg-red-50",
      "text-red-700",
      "hover:border-red-200",
      "hover:bg-red-100/70",
      "border-amber-100",
      "bg-amber-50",
      "text-amber-700",
      "hover:border-amber-200",
      "hover:bg-amber-100/70"
    );

    if (normalizedStatus === "aligned") {
      toggle.classList.add("border-green-100", "bg-green-50", "text-green-700", "hover:border-green-200", "hover:bg-green-100/70");
    } else if (normalizedStatus === "blocked") {
      toggle.classList.add("border-red-100", "bg-red-50", "text-red-700", "hover:border-red-200", "hover:bg-red-100/70");
    } else {
      toggle.classList.add("border-amber-100", "bg-amber-50", "text-amber-700", "hover:border-amber-200", "hover:bg-amber-100/70");
    }
  }
}

function initializeSectionStatusControls() {
  document.querySelectorAll("[data-section-status-shell]").forEach((shell) => {
    if (shell.dataset.sectionStatusInitialized === "true") {
      return;
    }

    shell.dataset.sectionStatusInitialized = "true";
    const toggle = shell.querySelector("[data-section-status-toggle]");
    const sectionNode = shell.closest("[data-spec-section]");
    const statusInput = sectionNode?.querySelector?.("[data-section-status-input]");
    if (!toggle || !statusInput) {
      return;
    }

    applySectionStatusState(shell, statusInput.value);
    setSectionStatusMenuState(shell, false);

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const nextOpenState = !sectionStatusMenuIsOpen(shell);
      closeSectionAiMenus();
      closeSectionActionMenus();
      closeSectionStatusMenus(shell);
      setSectionStatusMenuState(shell, nextOpenState);
    });

    shell.querySelectorAll("[data-section-status-option]").forEach((option) => {
      option.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const nextStatus = option.dataset.statusValue || "";
        if (!nextStatus || statusInput.value === nextStatus) {
          setSectionStatusMenuState(shell, false);
          return;
        }

        statusInput.value = nextStatus;
        applySectionStatusState(shell, nextStatus);
        statusInput.dispatchEvent(new Event("input", { bubbles: true }));
        statusInput.dispatchEvent(new Event("change", { bubbles: true }));
        setSectionStatusMenuState(shell, false);
      });
    });
  });
}

function initializeSectionAiControls() {
  document.querySelectorAll("[data-section-ai-shell]").forEach((shell) => {
    if (shell.dataset.sectionAiInitialized === "true") {
      return;
    }

    shell.dataset.sectionAiInitialized = "true";

    const toggle = shell.querySelector("[data-section-ai-toggle]");
    const menu = shell.querySelector("[data-section-ai-menu]");
    const sectionNode = shell.closest("[data-spec-section]");
    const form = sectionNode?.querySelector?.("[data-spec-section-form]");
    const editor = specEditorNode(form);
    const markdownInput = specMarkdownNode(form);
    const titleInput = form?.querySelector?.("input[name='title']");
    const promptInput = menu?.querySelector?.("[data-section-ai-prompt]");
    const runButton = menu?.querySelector?.("[data-section-ai-run]");

    if (!toggle || !menu || !form || !editor || !markdownInput || !promptInput || !runButton) {
      return;
    }

    setSectionAiMenuState(shell, false);

    const setBusy = (isBusy) => {
      shell.dataset.sectionAiBusy = isBusy ? "true" : "false";
      toggle.disabled = isBusy;
      promptInput.disabled = isBusy;
      setAsyncButtonSubmitting(runButton, isBusy);
      menu.querySelectorAll("[data-section-ai-preset]").forEach((button) => {
        button.disabled = isBusy;
      });
    };

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (shell.dataset.sectionAiBusy === "true") {
        return;
      }
      closeSectionStatusMenus();
      closeSectionActionMenus();
      const nextOpenState = !sectionAiMenuIsOpen(shell);
      closeSectionAiMenus(shell);
      setSectionAiMenuState(shell, nextOpenState);
      if (nextOpenState) {
        promptInput.focus();
      }
    });

    menu.querySelectorAll("[data-section-ai-preset]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        promptInput.value = button.dataset.sectionAiPreset || "";
        promptInput.focus();
        if (typeof promptInput.setSelectionRange === "function") {
          promptInput.setSelectionRange(promptInput.value.length, promptInput.value.length);
        }
      });
    });

    runButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();

      if (!isAuthenticated()) {
        openAuthModal("login");
        return;
      }

      if (!promptInput.value.trim()) {
        promptInput.focus();
        window.alert("Enter a revision prompt first.");
        return;
      }

      setBusy(true);
      setSpecSectionAutosaveStatus(form, "saving", "AI editing...");

      try {
        const currentBody = getSpecSectionMarkdown(form);
        const responsePayload = await postJson(
          `${form.dataset.apiForm}/revise-with-ai`,
          {
            prompt: promptInput.value || "",
            title: titleInput?.value || "",
            body: currentBody,
            __form: form,
          }
        );
        const revisedBody = `${responsePayload?.body || ""}`;
        if (!revisedBody.trim()) {
          setSpecSectionAutosaveStatus(form, "error", "AI failed");
          window.alert("AI revision failed. No revised section text was returned.");
          return;
        }

        if (revisedBody.trim() === currentBody.trim()) {
          setSpecSectionAutosaveStatus(form, "saved", "No AI changes");
          setSectionAiMenuState(shell, false);
          return;
        }

        setSpecSectionMarkdown(form, revisedBody);
        setSectionAiMenuState(shell, false);
        const activeInput = activeSpecContentInput(form);
        activeInput?.dispatchEvent?.(new Event("input", { bubbles: true }));
        editor.focus();
        moveCaretToEnd(editor);
      } catch (error) {
        console.error(error);
        if (error.message.startsWith("Authentication required")) {
          return;
        }
        setSpecSectionAutosaveStatus(form, "error", "AI failed");
        const message = error.payload?.errors?.section?.[0] || "AI revision failed. Check the console for details.";
        window.alert(message);
      } finally {
        setBusy(false);
      }
    });
  });
}

function initializeSectionActionControls() {
  document.querySelectorAll("[data-section-actions-shell]").forEach((shell) => {
    if (shell.dataset.sectionActionsInitialized === "true") {
      return;
    }

    shell.dataset.sectionActionsInitialized = "true";
    const toggle = shell.querySelector("[data-section-actions-toggle]");
    if (!toggle) {
      return;
    }

    setSectionActionMenuState(shell, false);

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const nextOpenState = !sectionActionMenuIsOpen(shell);
      closeSectionAiMenus();
      closeSectionStatusMenus();
      closeSectionActionMenus(shell);
      setSectionActionMenuState(shell, nextOpenState);
    });
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

function syncExportSelection(form) {
  const hiddenInput = form?.querySelector?.("[data-section-ids-input]");
  if (!hiddenInput) {
    return;
  }
  const selected = Array.from(
    form.querySelectorAll("[data-export-section-checkbox]:checked")
  ).map((checkbox) => checkbox.value);
  hiddenInput.value = selected.join(",");
}

function scrollToSpecSection(workspace, sectionId, behavior = "smooth") {
  const container = workspace?.querySelector?.("[data-spec-scroll-container]");
  const target = workspace?.querySelector?.(
    `[data-spec-section][data-section-id='${sectionId}']`
  );
  if (!container || !target) {
    return false;
  }
  const containerRect = container.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const targetTop = targetRect.top - containerRect.top + container.scrollTop;
  container.scrollTo({
    top: Math.max(targetTop - 96, 0),
    behavior,
  });
  return true;
}

function hashSpecSectionId() {
  const rawHash = `${window.location.hash || ""}`;
  return rawHash.startsWith("#spec-section-") ? rawHash.replace("#spec-section-", "") : "";
}

const WORKSPACE_SPLIT_RATIO_KEY = "specbridge:workspace-split-ratio";
const MIN_WORKSPACE_STREAM_PANE_PX = 440;
const MIN_WORKSPACE_SPEC_PANE_PX = 520;
const MAX_WORKSPACE_STREAM_PANE_PX = 760;
const WORKSPACE_SPLIT_STEP_PX = 32;

function loadWorkspaceSplitRatio() {
  try {
    const rawRatio = window.localStorage.getItem(WORKSPACE_SPLIT_RATIO_KEY);
    const parsedRatio = Number.parseFloat(rawRatio || "");
    if (!Number.isFinite(parsedRatio) || parsedRatio <= 0 || parsedRatio >= 1) {
      return null;
    }
    return parsedRatio;
  } catch (error) {
    console.warn("Unable to read workspace split ratio", error);
    return null;
  }
}

function saveWorkspaceSplitRatio(ratio) {
  try {
    if (!Number.isFinite(ratio) || ratio <= 0 || ratio >= 1) {
      return;
    }
    window.localStorage.setItem(WORKSPACE_SPLIT_RATIO_KEY, `${ratio}`);
  } catch (error) {
    console.warn("Unable to save workspace split ratio", error);
  }
}

function focusStreamInput(prompt = "", mode = "replace") {
  const streamInput = document.querySelector("[data-stream-input]");
  if (!streamInput) {
    return false;
  }

  const nextPrompt = `${prompt || ""}`;
  if (mode === "append" && streamInput.value.trim()) {
    const needsSpacer = !streamInput.value.endsWith(" ") && nextPrompt && !nextPrompt.startsWith(" ");
    streamInput.value = `${streamInput.value}${needsSpacer ? " " : ""}${nextPrompt}`;
  } else {
    streamInput.value = nextPrompt;
  }

  streamInput.scrollIntoView({ block: "nearest" });
  streamInput.focus();
  streamInput.dispatchEvent(new Event("input", { bubbles: true }));
  if (typeof streamInput.setSelectionRange === "function") {
    streamInput.setSelectionRange(streamInput.value.length, streamInput.value.length);
  }
  return true;
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1).replace(/\\.0$/, "")} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1).replace(/\\.0$/, "")} MB`;
}

const DEFAULT_STREAM_ATTACHMENT_PROMPT = "Update the current spec to align with this document.";

function streamComposerFileInput(form) {
  return form?.querySelector?.("[data-stream-file-input]") || null;
}

function streamComposerFileList(form) {
  return form?.querySelector?.("[data-stream-file-list]") || null;
}

function streamComposerTextInput(form) {
  return form?.querySelector?.("[data-stream-input]") || null;
}

function streamComposerSelectedFiles(form) {
  return Array.from(streamComposerFileInput(form)?.files || []);
}

function streamComposerFileKey(file) {
  return [file?.name || "", file?.size || 0, file?.lastModified || 0].join(":");
}

function setStreamComposerFiles(form, files) {
  const input = streamComposerFileInput(form);
  if (!input) {
    return;
  }
  const dataTransfer = new DataTransfer();
  files.forEach((file) => {
    dataTransfer.items.add(file);
  });
  input.files = dataTransfer.files;
}

function setStreamComposerDefaultPrompt(form) {
  const input = streamComposerTextInput(form);
  if (!input) {
    return;
  }
  const currentValue = `${input.value || ""}`.trim();
  if (currentValue && currentValue !== DEFAULT_STREAM_ATTACHMENT_PROMPT) {
    return;
  }
  input.value = DEFAULT_STREAM_ATTACHMENT_PROMPT;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  if (typeof input.setSelectionRange === "function") {
    input.setSelectionRange(input.value.length, input.value.length);
  }
}

function syncStreamComposerFiles(form) {
  const fileList = streamComposerFileList(form);
  if (!fileList) {
    return;
  }

  const files = streamComposerSelectedFiles(form);
  fileList.innerHTML = "";

  if (!files.length) {
    fileList.classList.add("hidden");
    return;
  }

  fileList.classList.remove("hidden");
  setStreamComposerDefaultPrompt(form);

  files.forEach((file, index) => {
    const chip = document.createElement("div");
    chip.className = "inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700";

    const name = document.createElement("span");
    name.className = "max-w-[220px] truncate font-medium";
    name.textContent = `${file.name} (${formatFileSize(file.size)})`;
    chip.appendChild(name);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "text-gray-400 transition hover:text-gray-700";
    removeButton.dataset.streamFileRemove = `${index}`;
    removeButton.setAttribute("aria-label", `Remove ${file.name}`);
    removeButton.innerHTML = '<iconify-icon icon="lucide:x" class="text-sm"></iconify-icon>';
    chip.appendChild(removeButton);
    fileList.appendChild(chip);
  });
}

function mergeStreamComposerFiles(form, nextFiles, { baseFiles = null } = {}) {
  const mergedFiles = Array.isArray(baseFiles) ? [...baseFiles] : streamComposerSelectedFiles(form);
  const existingKeys = new Set(mergedFiles.map(streamComposerFileKey));
  Array.from(nextFiles || []).forEach((file) => {
    const fileKey = streamComposerFileKey(file);
    if (existingKeys.has(fileKey)) {
      return;
    }
    existingKeys.add(fileKey);
    mergedFiles.push(file);
  });
  setStreamComposerFiles(form, mergedFiles);
  syncStreamComposerFiles(form);
}

function initializeWorkspaceSplitPane() {
  const root = document.querySelector("[data-workspace-split-root]");
  const streamPane = root?.querySelector?.("[data-workspace-stream-pane]");
  const handle = root?.querySelector?.("[data-workspace-resize-handle]");
  const indicator = handle?.querySelector?.("[data-workspace-resize-indicator]");
  if (!root || !streamPane || !handle || root.dataset.workspaceSplitInitialized === "true") {
    return;
  }
  root.dataset.workspaceSplitInitialized = "true";

  const desktopMedia = window.matchMedia("(min-width: 1024px)");
  let currentRatio = loadWorkspaceSplitRatio();
  let dragging = false;

  const streamPaneBounds = (rootWidth) => {
    const maxWidth = Math.min(MAX_WORKSPACE_STREAM_PANE_PX, rootWidth - MIN_WORKSPACE_SPEC_PANE_PX);
    if (!desktopMedia.matches || maxWidth <= MIN_WORKSPACE_STREAM_PANE_PX) {
      return null;
    }
    return {
      minWidth: MIN_WORKSPACE_STREAM_PANE_PX,
      maxWidth,
      defaultWidth: Math.round((MIN_WORKSPACE_STREAM_PANE_PX + maxWidth) / 2),
    };
  };

  const clampStreamPaneWidth = (rootWidth, nextWidth) => {
    const bounds = streamPaneBounds(rootWidth);
    if (!bounds) {
      return null;
    }
    return Math.min(Math.max(nextWidth, bounds.minWidth), bounds.maxWidth);
  };

  const resetStreamPaneWidth = () => {
    streamPane.style.flex = "";
    streamPane.style.maxWidth = "";
  };

  const applyStreamPaneWidth = (nextWidth, { persist = false } = {}) => {
    if (nextWidth === null) {
      resetStreamPaneWidth();
      return;
    }

    const rootWidth = root.getBoundingClientRect().width;
    const clampedWidth = clampStreamPaneWidth(rootWidth, nextWidth);
    if (clampedWidth === null) {
      resetStreamPaneWidth();
      return;
    }

    streamPane.style.flex = `0 0 ${clampedWidth}px`;
    streamPane.style.maxWidth = `${clampedWidth}px`;
    currentRatio = clampedWidth / rootWidth;

    if (persist) {
      saveWorkspaceSplitRatio(currentRatio);
    }
  };

  const preferredStreamPaneWidth = () => {
    const rootWidth = root.getBoundingClientRect().width;
    const bounds = streamPaneBounds(rootWidth);
    if (!bounds) {
      return null;
    }
    if (currentRatio) {
      return rootWidth * currentRatio;
    }
    return bounds.defaultWidth;
  };

  const syncToViewport = () => {
    applyStreamPaneWidth(preferredStreamPaneWidth());
  };

  const setDraggingState = (isDragging) => {
    dragging = isDragging;
    document.body.dataset.workspaceResizing = isDragging ? "true" : "false";
    document.body.style.cursor = isDragging ? "col-resize" : "";
    document.body.style.userSelect = isDragging ? "none" : "";
    indicator?.classList.toggle("bg-gray-600", isDragging);
    indicator?.classList.toggle("bg-gray-400", !isDragging);
  };

  const stopDrag = () => {
    if (!dragging) {
      return;
    }
    setDraggingState(false);
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", stopDrag);
    window.removeEventListener("pointercancel", stopDrag);
    if (currentRatio) {
      saveWorkspaceSplitRatio(currentRatio);
    }
  };

  function onPointerMove(event) {
    if (!dragging) {
      return;
    }
    event.preventDefault();
    const rootRect = root.getBoundingClientRect();
    applyStreamPaneWidth(event.clientX - rootRect.left);
  }

  handle.addEventListener("pointerdown", (event) => {
    if (!desktopMedia.matches) {
      return;
    }
    event.preventDefault();
    setDraggingState(true);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopDrag);
    window.addEventListener("pointercancel", stopDrag);
  });

  handle.addEventListener("keydown", (event) => {
    if (!desktopMedia.matches) {
      return;
    }

    const currentWidth = streamPane.getBoundingClientRect().width;
    let nextWidth = currentWidth;

    if (event.key === "ArrowLeft") {
      nextWidth -= WORKSPACE_SPLIT_STEP_PX;
    } else if (event.key === "ArrowRight") {
      nextWidth += WORKSPACE_SPLIT_STEP_PX;
    } else if (event.key === "Home") {
      nextWidth = MIN_WORKSPACE_STREAM_PANE_PX;
    } else if (event.key === "End") {
      nextWidth = root.getBoundingClientRect().width - MIN_WORKSPACE_SPEC_PANE_PX;
    } else {
      return;
    }

    event.preventDefault();
    applyStreamPaneWidth(nextWidth, { persist: true });
  });

  if (typeof desktopMedia.addEventListener === "function") {
    desktopMedia.addEventListener("change", syncToViewport);
  } else if (typeof desktopMedia.addListener === "function") {
    desktopMedia.addListener(syncToViewport);
  }

  window.addEventListener("resize", syncToViewport);
  syncToViewport();
}

function initializeSpecNavigation({ preserveScroll = false } = {}) {
  if (typeof specNavigationCleanup === "function") {
    specNavigationCleanup();
    specNavigationCleanup = null;
  }

  const workspace = document.querySelector("[data-spec-workspace]");
  const container = workspace?.querySelector?.("[data-spec-scroll-container]");
  const navScroller = workspace?.querySelector?.("[data-spec-nav]");
  const sections = Array.from(workspace?.querySelectorAll?.("[data-spec-section]") || []);
  const navLinks = Array.from(workspace?.querySelectorAll?.("[data-spec-nav-link]") || []);
  const fadeLeft = workspace?.querySelector?.("[data-spec-nav-fade-left]");
  const fadeRight = workspace?.querySelector?.("[data-spec-nav-fade-right]");
  if (!workspace || !container || !navScroller || !sections.length || !navLinks.length) {
    return;
  }

  let activeSectionId = "";

  const updateNavFades = () => {
    if (!fadeLeft || !fadeRight) {
      return;
    }
    const hasLeftOverflow = navScroller.scrollLeft > 0;
    const hasRightOverflow = Math.ceil(navScroller.scrollLeft + navScroller.clientWidth) < navScroller.scrollWidth - 2;
    fadeLeft.classList.toggle("opacity-0", !hasLeftOverflow);
    fadeLeft.classList.toggle("opacity-100", hasLeftOverflow);
    fadeRight.classList.toggle("opacity-0", !hasRightOverflow);
    fadeRight.classList.toggle("opacity-100", hasRightOverflow);
  };

  const updateActiveSection = () => {
    let currentId = sections[0]?.dataset.sectionId || "";
    const containerRect = container.getBoundingClientRect();
    sections.forEach((section) => {
      const sectionTop = section.getBoundingClientRect().top - containerRect.top + container.scrollTop;
      if (container.scrollTop >= sectionTop - 160) {
        currentId = section.dataset.sectionId || currentId;
      }
    });

    navLinks.forEach((link) => {
      const isActive = link.dataset.sectionId === currentId;
      link.classList.toggle("border-brand-decision", isActive);
      link.classList.toggle("text-brand-decision", isActive);
      link.classList.toggle("border-transparent", !isActive);
      link.classList.toggle("text-gray-500", !isActive);
    });

    if (currentId && currentId !== activeSectionId) {
      activeSectionId = currentId;
      const activeLink = navLinks.find((link) => link.dataset.sectionId === currentId);
      activeLink?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  };

  const navLinkListeners = navLinks.map((link) => {
    const onClick = (event) => {
      event.preventDefault();
      const sectionId = link.dataset.sectionId;
      if (!scrollToSpecSection(workspace, sectionId)) {
        return;
      }
      window.history.replaceState(null, "", `#spec-section-${sectionId}`);
    };
    link.addEventListener("click", onClick);
    return [link, onClick];
  });

  const onContainerScroll = () => {
    updateActiveSection();
  };
  const onNavScroll = () => {
    updateNavFades();
  };
  const onWindowResize = () => {
    updateNavFades();
  };

  container.addEventListener("scroll", onContainerScroll);
  navScroller.addEventListener("scroll", onNavScroll);
  window.addEventListener("resize", onWindowResize);

  specNavigationCleanup = () => {
    container.removeEventListener("scroll", onContainerScroll);
    navScroller.removeEventListener("scroll", onNavScroll);
    window.removeEventListener("resize", onWindowResize);
    navLinkListeners.forEach(([link, listener]) => {
      link.removeEventListener("click", listener);
    });
  };

  const initialTarget = hashSpecSectionId() || workspace.dataset.scrollTargetSection;
  if (!preserveScroll && initialTarget) {
    window.setTimeout(() => {
      scrollToSpecSection(workspace, initialTarget, hashSpecSectionId() ? "auto" : "smooth");
    }, 120);
  }

  updateActiveSection();
  window.setTimeout(updateNavFades, 100);
}

function sectionActionPayload(button) {
  const rawPayload = button?.dataset?.actionPayload || "";
  if (!rawPayload) {
    return {};
  }
  try {
    return JSON.parse(rawPayload);
  } catch (error) {
    console.error("Invalid section action payload", error);
    return {};
  }
}

function sectionActionTitle(button) {
  const sectionNode = button?.closest?.("[data-spec-section]");
  const titleInput = sectionNode?.querySelector?.("input[name='title']");
  const titleHeading = sectionNode?.querySelector?.("h2");
  return (titleInput?.value || titleHeading?.textContent || "").trim() || "this section";
}

function sectionActionRedirectUrl(sectionId = "") {
  return sectionId ? `${currentPath()}#spec-section-${sectionId}` : currentPath();
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

function hydrateProjectSettingsForm(form, payload = {}) {
  hydrateProjectCreateForm(form, payload);
}

function projectSettingsDefaults(form) {
  if (!form) {
    return {};
  }
  return {
    project_name: form.elements.namedItem("project_name")?.defaultValue || "",
    tagline: form.elements.namedItem("tagline")?.defaultValue || ""
  };
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
  closeProjectSettingsModal();
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

function clearProjectSettingsErrorsForSurface(surface) {
  const summary = projectSettingsErrorsNode(surface);
  if (summary) {
    summary.textContent = "";
    summary.classList.add("hidden");
  }
  surface?.querySelectorAll("[data-project-settings-field-error]").forEach((fieldError) => {
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

function showProjectSettingsErrors(surface, errors = {}) {
  clearProjectSettingsErrorsForSurface(surface);
  const summaryMessages = [];

  Object.entries(errors).forEach(([field, messages]) => {
    const normalized = Array.isArray(messages) ? messages : [messages];
    const fieldError = surface?.querySelector?.(`[data-project-settings-field-error='${field}']`);
    if (fieldError && normalized.length) {
      fieldError.textContent = normalized.join(" ");
      fieldError.classList.remove("hidden");
      return;
    }
    summaryMessages.push(...normalized);
  });

  if (summaryMessages.length) {
    const summary = projectSettingsErrorsNode(surface);
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

function setProjectSettingsSubmitting(surface, isSubmitting) {
  const submitButton = projectSettingsSubmitNode(surface);
  if (!submitButton) {
    return;
  }
  submitButton.disabled = isSubmitting;
  submitButton.classList.toggle("opacity-70", isSubmitting);
  submitButton.classList.toggle("cursor-wait", isSubmitting);
  submitButton.innerHTML = isSubmitting
    ? '<iconify-icon icon="lucide:loader-circle" class="animate-spin"></iconify-icon>Saving...'
    : '<iconify-icon icon="lucide:save"></iconify-icon>Save Changes';
}

function asyncButtonIconNode(button) {
  return button?.querySelector?.("[data-api-button-icon]") || null;
}

function asyncButtonLabelNode(button) {
  return button?.querySelector?.("[data-api-button-label]") || null;
}

function setAsyncButtonSubmitting(button, isSubmitting) {
  if (!button) {
    return;
  }

  const labelNode = asyncButtonLabelNode(button);
  const iconNode = asyncButtonIconNode(button);
  const loadingLabel = button.dataset.apiLoadingLabel || "";

  if (labelNode && !button.dataset.apiIdleLabel) {
    button.dataset.apiIdleLabel = labelNode.textContent.trim();
  }

  button.disabled = isSubmitting;
  button.setAttribute("aria-busy", isSubmitting ? "true" : "false");
  button.classList.toggle("opacity-70", isSubmitting);
  button.classList.toggle("cursor-wait", isSubmitting);

  if (iconNode) {
    iconNode.classList.toggle("animate-spin", isSubmitting);
  }

  if (labelNode && loadingLabel) {
    labelNode.textContent = isSubmitting ? loadingLabel : button.dataset.apiIdleLabel || labelNode.textContent;
  }
}

function openProjectModal() {
  const modal = projectModalNode();
  if (!modal) {
    return;
  }
  const surface = modal.querySelector("[data-project-create-surface]");
  const form = projectCreateFormNode(surface);
  closeAuthModal();
  closeProjectSettingsModal();
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

function openProjectSettingsModal(payload = null) {
  const modal = projectSettingsModalNode();
  if (!modal) {
    return;
  }
  const surface = modal.querySelector("[data-project-settings-surface]");
  const form = projectSettingsFormNode(surface);
  closeAuthModal();
  closeProjectModal();
  clearProjectSettingsErrorsForSurface(surface);
  hydrateProjectSettingsForm(form, payload || projectSettingsDefaults(form));
  modal.classList.remove("hidden");
  document.body.classList.add("overflow-hidden");
  const activeInput = form?.querySelector("input[name='project_name']");
  activeInput?.focus();
  activeInput?.select();
}

function closeProjectSettingsModal() {
  const modal = projectSettingsModalNode();
  if (!modal) {
    return;
  }
  modal.classList.add("hidden");
  document.body.classList.remove("overflow-hidden");
}

function workspaceLiveRefreshRoot() {
  return document.querySelector("[data-workspace-live-refresh-root]");
}

function workspaceHeaderRegionNode(root = document) {
  return root?.querySelector?.("[data-workspace-header-region]") || null;
}

function workspaceStreamLiveRegionNode(root = document) {
  return root?.querySelector?.("[data-workspace-stream-live-region]") || null;
}

function workspaceStreamScrollNode(root = document) {
  return root?.querySelector?.("[data-workspace-stream-scroll]") || null;
}

function workspaceSpecRegionNode(root = document) {
  return root?.querySelector?.("[data-workspace-spec-region]") || null;
}

function workspaceSpecScrollNode(root = document) {
  return root?.querySelector?.("[data-spec-scroll-container]") || null;
}

function workspaceSpecNavNode(root = document) {
  return root?.querySelector?.("[data-spec-nav]") || null;
}

function workspaceLiveRefreshEnabled() {
  return Boolean(workspaceLiveRefreshRoot() && workspaceHeaderRegionNode() && workspaceStreamLiveRegionNode());
}

function workspaceLiveRefreshUrl() {
  const url = new URL(currentPath(), window.location.origin);
  url.searchParams.set("_fragment", "workspace-live");
  return url.toString();
}

function hasBlockingAutosaveState() {
  const controllers = [...documentEditorAutosaveControllers, ...specSectionAutosaveControllers];
  return controllers.some((controller) => controller?.dirty || controller?.inFlight);
}

function workspaceUiRefreshBlocked() {
  if (authModalNode() && !authModalNode().classList.contains("hidden")) {
    return true;
  }
  if (projectModalNode() && !projectModalNode().classList.contains("hidden")) {
    return true;
  }
  if (projectSettingsModalNode() && !projectSettingsModalNode().classList.contains("hidden")) {
    return true;
  }
  if (document.body.dataset.workspaceResizing === "true") {
    return true;
  }
  return false;
}

function shouldPauseBackgroundRefresh() {
  if (document.hidden) {
    return true;
  }
  const tagName = document.activeElement?.tagName?.toLowerCase();
  if (tagName === "textarea" || tagName === "input" || tagName === "select") {
    return true;
  }
  if (workspaceUiRefreshBlocked()) {
    return true;
  }
  return false;
}

function shouldPauseWorkspaceSpecRefresh() {
  if (document.hidden || workspaceUiRefreshBlocked()) {
    return true;
  }
  return Boolean(document.activeElement?.closest?.("[data-workspace-spec-region]"));
}

function reinitializeWorkspaceSpecPane({ preserveScroll = false } = {}) {
  resetSpecSectionAutosaveControllers();
  initializeSpecSectionAutosave();
  initializeSectionStatusControls();
  initializeSectionActionControls();
  initializeSectionAiControls();
  initializeSpecNavigation({ preserveScroll });
}

function workspaceActionUpdatesDocument(button = null) {
  if (button?.dataset?.workspaceRefreshSpec === "true") {
    return true;
  }
  const actionUrl = `${button?.dataset?.apiPost || ""}`;
  return (
    /\/concern-proposals\/\d+\/changes\/\d+\/accept\/?$/.test(actionUrl) ||
    /\/agent-suggestions\/\d+\/apply\/?$/.test(actionUrl)
  );
}

let workspaceLiveRefreshInFlight = null;

async function refreshWorkspaceLiveRegions({ force = false, includeSpec = true } = {}) {
  if (!workspaceLiveRefreshEnabled()) {
    return false;
  }
  const blockingAutosave = hasBlockingAutosaveState();
  if (!force && (shouldPauseBackgroundRefresh() || blockingAutosave)) {
    return false;
  }
  if (workspaceLiveRefreshInFlight) {
    return workspaceLiveRefreshInFlight;
  }

  const currentHeader = workspaceHeaderRegionNode();
  const currentStream = workspaceStreamLiveRegionNode();
  const currentSpec = workspaceSpecRegionNode();
  if (!currentHeader || !currentStream) {
    return false;
  }

  const previousScrollTop = workspaceStreamScrollNode()?.scrollTop || 0;
  const shouldRefreshSpec = Boolean(
    includeSpec && currentSpec && !blockingAutosave && !shouldPauseWorkspaceSpecRefresh()
  );
  const previousSpecScrollTop = shouldRefreshSpec ? workspaceSpecScrollNode()?.scrollTop || 0 : 0;
  const previousSpecNavScrollLeft = shouldRefreshSpec ? workspaceSpecNavNode()?.scrollLeft || 0 : 0;
  workspaceLiveRefreshInFlight = fetch(workspaceLiveRefreshUrl(), {
    method: "GET",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "Accept": "text/html"
    },
    credentials: "same-origin",
    cache: "no-store"
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Workspace live refresh failed: ${response.status}`);
      }
      return response.text();
    })
    .then((html) => {
      const parsedDocument = new DOMParser().parseFromString(html, "text/html");
      const nextHeader = workspaceHeaderRegionNode(parsedDocument);
      const nextStream = workspaceStreamLiveRegionNode(parsedDocument);
      const nextSpec = shouldRefreshSpec ? workspaceSpecRegionNode(parsedDocument) : null;
      if (!nextHeader || !nextStream) {
        throw new Error("Workspace live refresh response missing regions.");
      }
      if (shouldRefreshSpec && !nextSpec) {
        throw new Error("Workspace live refresh response missing spec region.");
      }
      currentHeader.replaceWith(nextHeader);
      currentStream.replaceWith(nextStream);
      if (shouldRefreshSpec) {
        currentSpec.replaceWith(nextSpec);
        reinitializeWorkspaceSpecPane({ preserveScroll: true });
        const nextSpecScroll = workspaceSpecScrollNode();
        const nextSpecNav = workspaceSpecNavNode();
        if (nextSpecScroll) {
          nextSpecScroll.scrollTop = previousSpecScrollTop;
          nextSpecScroll.dispatchEvent(new Event("scroll"));
        }
        if (nextSpecNav) {
          nextSpecNav.scrollLeft = previousSpecNavScrollLeft;
          nextSpecNav.dispatchEvent(new Event("scroll"));
        }
      }
      const nextScrollNode = workspaceStreamScrollNode();
      if (nextScrollNode) {
        nextScrollNode.scrollTop = previousScrollTop;
      }
      return true;
    })
    .catch((error) => {
      console.error(error);
      return false;
    })
    .finally(() => {
      workspaceLiveRefreshInFlight = null;
    });

  return workspaceLiveRefreshInFlight;
}

function streamComposerNode(form) {
  return form?.matches?.("[data-workspace-stream-composer]") ? form : form?.closest?.("[data-workspace-stream-composer]");
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

async function postMultipart(url, formData, form, method = "POST") {
  const response = await fetch(url, {
    method,
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": csrfToken(form),
    },
    credentials: "same-origin",
    body: formData,
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
  if (event.defaultPrevented) {
    return;
  }
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

  const projectSettingsForm = event.target.closest("[data-project-settings-form]");
  if (projectSettingsForm) {
    event.preventDefault();
    const surface = projectSettingsSurface(projectSettingsForm);
    clearProjectSettingsErrorsForSurface(surface);
    setProjectSettingsSubmitting(surface, true);
    const payload = serializeForm(projectSettingsForm);
    try {
      await postJson(projectSettingsForm.action, { ...payload, __form: projectSettingsForm });
      closeProjectSettingsModal();
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      openProjectSettingsModal(payload);
      showProjectSettingsErrors(
        surface,
        error.payload?.errors || { __all__: ["Project settings could not be saved. Please try again."] }
      );
    } finally {
      setProjectSettingsSubmitting(surface, false);
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
  syncExportSelection(form);
  const payload = serializeForm(form);
  const method = form.dataset.apiMethod || "POST";
  const submitButton = form.querySelector("[data-api-submit-button]") || form.querySelector("button[type='submit']");
  const isStreamComposer = Boolean(streamComposerNode(form));
  const isFileBackedStreamSubmit = isStreamComposer && streamComposerSelectedFiles(form).length > 0;
  try {
    if (!isFileBackedStreamSubmit) {
      setAsyncButtonSubmitting(submitButton, true);
    }
    let responsePayload;
    if (isStreamComposer) {
      responsePayload = await postMultipart(form.dataset.apiForm, new FormData(form), form, method);
    } else {
      responsePayload = await postJson(form.dataset.apiForm, { ...payload, __form: form }, method);
    }
    if (workspaceLiveRefreshEnabled() && isStreamComposer) {
      form.reset();
      syncStreamComposerFiles(form);
      form.querySelector("[data-stream-input]")?.focus();
      const refreshed = await refreshWorkspaceLiveRegions({ force: true, includeSpec: false });
      if (!refreshed) {
        window.location.reload();
      }
      if (responsePayload?.processing_pending && responsePayload?.processing_url) {
        postJson(responsePayload.processing_url, {})
          .catch((error) => {
            console.error(error);
          })
          .finally(async () => {
            const nextRefresh = await refreshWorkspaceLiveRegions({ force: true, includeSpec: true });
            if (!nextRefresh) {
              window.location.reload();
            }
          });
      }
      return;
    }
    window.location.reload();
  } catch (error) {
    console.error(error);
    if (error.message.startsWith("Authentication required")) {
      return;
    }
    window.alert("Action failed. Check the console for details.");
  } finally {
    if (!isFileBackedStreamSubmit) {
      setAsyncButtonSubmitting(submitButton, false);
    }
  }
});

document.addEventListener("click", async (event) => {
  const projectTrigger = event.target.closest("[data-project-modal-trigger]");
  if (projectTrigger) {
    event.preventDefault();
    openProjectModal();
    return;
  }

  const projectSettingsTrigger = event.target.closest("[data-project-settings-trigger]");
  if (projectSettingsTrigger) {
    event.preventDefault();
    openProjectSettingsModal();
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

  const projectSettingsClose = event.target.closest("[data-project-settings-modal-close]");
  if (projectSettingsClose) {
    event.preventDefault();
    closeProjectSettingsModal();
    return;
  }

  const streamFilesTrigger = event.target.closest("[data-stream-files-trigger]");
  if (streamFilesTrigger) {
    event.preventDefault();
    const form = streamFilesTrigger.closest("[data-workspace-stream-composer]");
    const input = streamComposerFileInput(form);
    if (!input) {
      return;
    }
    input.__previousFiles = streamComposerSelectedFiles(form);
    input.click();
    return;
  }

  const streamFileRemoveButton = event.target.closest("[data-stream-file-remove]");
  if (streamFileRemoveButton) {
    event.preventDefault();
    const form = streamFileRemoveButton.closest("[data-workspace-stream-composer]");
    const fileIndex = Number.parseInt(streamFileRemoveButton.dataset.streamFileRemove || "", 10);
    if (!form || Number.isNaN(fileIndex)) {
      return;
    }
    const files = streamComposerSelectedFiles(form);
    files.splice(fileIndex, 1);
    setStreamComposerFiles(form, files);
    syncStreamComposerFiles(form);
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

  const projectSettingsBackdrop = event.target.closest("[data-project-settings-modal]");
  if (projectSettingsBackdrop && event.target === projectSettingsBackdrop) {
    closeProjectSettingsModal();
    return;
  }

  if (!event.target.closest("[data-document-create-shell]")) {
    closeDocumentSuggestionMenus();
  }

  if (!event.target.closest("[data-section-ai-shell]")) {
    closeSectionAiMenus();
  }

  if (!event.target.closest("[data-section-status-shell]")) {
    closeSectionStatusMenus();
  }

  if (!event.target.closest("[data-section-actions-shell]")) {
    closeSectionActionMenus();
  }

  const specLink = event.target.closest("a[href^='#spec-section-']");
  if (specLink) {
    const workspace = document.querySelector("[data-spec-workspace]");
    const sectionId = specLink.getAttribute("href")?.replace("#spec-section-", "") || "";
    if (workspace && sectionId) {
      event.preventDefault();
      if (scrollToSpecSection(workspace, sectionId)) {
        window.history.replaceState(null, "", `#spec-section-${sectionId}`);
      }
      return;
    }
  }

  const sectionActionButton = event.target.closest("[data-section-structure-action]");
  if (sectionActionButton) {
    event.preventDefault();
    if (sectionActionButton.disabled) {
      return;
    }
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }

    if (sectionActionButton.dataset.actionConfirm === "true") {
      const sectionTitle = sectionActionTitle(sectionActionButton);
      if (!window.confirm(`Delete "${sectionTitle}"? This cannot be undone.`)) {
        return;
      }
    }

    try {
      await flushAllPendingAutosaves();
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      window.alert("Save failed. Resolve any pending section errors and try again.");
      return;
    }

    const actionShell = sectionActionButton.closest("[data-section-actions-shell]");
    const actionToggle = actionShell?.querySelector?.("[data-section-actions-toggle]");
    const requestUrl = sectionActionButton.dataset.actionUrl || "";
    const requestMethod = sectionActionButton.dataset.actionMethod || "POST";
    const requestPayload = sectionActionPayload(sectionActionButton);

    closeSectionAiMenus();
    closeSectionActionMenus();
    sectionActionButton.disabled = true;
    if (actionToggle) {
      actionToggle.disabled = true;
    }

    try {
      const responsePayload = await postJson(requestUrl, requestPayload, requestMethod);
      const focusSectionId = responsePayload?.section_id || responsePayload?.focus_section_id || "";
      window.location.assign(sectionActionRedirectUrl(focusSectionId));
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      const message = error.payload?.errors?.section?.[0] || "Action failed. Check the console for details.";
      window.alert(message);
    } finally {
      sectionActionButton.disabled = false;
      if (actionToggle) {
        actionToggle.disabled = false;
      }
    }
    return;
  }

  const button = event.target.closest("[data-api-post]");
  if (button) {
    event.preventDefault();
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }
    const confirmMessage = button.dataset.apiConfirm || "";
    if (confirmMessage && !window.confirm(confirmMessage)) {
      return;
    }
    setAsyncButtonSubmitting(button, true);
    try {
      await postJson(button.dataset.apiPost, {});
      if (workspaceLiveRefreshEnabled() && button.closest("[data-workspace-stream-live-region]")) {
        const refreshed = await refreshWorkspaceLiveRegions({
          force: true,
          includeSpec: workspaceActionUpdatesDocument(button),
        });
        if (!refreshed) {
          window.location.reload();
        }
      } else {
        window.location.reload();
      }
    } catch (error) {
      console.error(error);
      if (error.message.startsWith("Authentication required")) {
        return;
      }
      window.alert("Action failed. Check the console for details.");
    } finally {
      setAsyncButtonSubmitting(button, false);
    }
    return;
  }

  const streamPromptButton = event.target.closest("[data-stream-prompt]");
  if (streamPromptButton) {
    event.preventDefault();
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }
    focusStreamInput(
      streamPromptButton.dataset.streamPrompt || "",
      streamPromptButton.dataset.streamPromptMode || "replace"
    );
    return;
  }

  const aiDraftButton = event.target.closest("[data-ai-draft-request]");
  if (aiDraftButton) {
    event.preventDefault();
    if (!isAuthenticated()) {
      openAuthModal("login");
      return;
    }
    const sectionTitle = aiDraftButton.dataset.sectionTitle || "this section";
    const projectName = aiDraftButton.dataset.projectName || "this project";
    const customPrompt = aiDraftButton.dataset.aiDraftPrompt || "";
    if (!focusStreamInput(
      customPrompt || `Help me draft the "${sectionTitle}" section for ${projectName}. Propose a concise summary and a detailed body I can paste into the spec.`
    )) {
      return;
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
  closeSectionStatusMenus();
  closeSectionActionMenus();
  closeSectionAiMenus();
  closeAuthModal();
  closeProjectModal();
  closeProjectSettingsModal();
});

document.addEventListener("change", (event) => {
  const fileInput = event.target.closest("[data-stream-file-input]");
  if (!fileInput) {
    return;
  }
  const form = fileInput.closest("[data-workspace-stream-composer]");
  if (!form) {
    return;
  }

  const previousFiles = Array.isArray(fileInput.__previousFiles) ? fileInput.__previousFiles : [];
  delete fileInput.__previousFiles;
  mergeStreamComposerFiles(form, fileInput.files, { baseFiles: previousFiles });
});

document.addEventListener("dragover", (event) => {
  const dropTarget = event.target.closest("[data-stream-drop-target]");
  if (!dropTarget || !event.dataTransfer?.files?.length) {
    return;
  }
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});

document.addEventListener("drop", (event) => {
  const dropTarget = event.target.closest("[data-stream-drop-target]");
  if (!dropTarget || !event.dataTransfer?.files?.length) {
    return;
  }
  event.preventDefault();
  const form = dropTarget.closest("[data-workspace-stream-composer]");
  if (!form) {
    return;
  }
  mergeStreamComposerFiles(form, event.dataTransfer.files);
  dropTarget.focus();
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
  if (apiForm?.querySelector?.("[data-section-ids-input]")) {
    syncExportSelection(apiForm);
  }

  const projectCreateForm = event.target.closest("[data-project-create-form]");
  if (projectCreateForm) {
    saveProjectCreateDraft(serializeForm(projectCreateForm));
  }
});

initializeDocumentCreateControls();
initializeDocumentEditorAutosave();
initializeSpecSectionEditors();
initializeSpecSectionAutosave();
initializeSectionStatusControls();
initializeSectionActionControls();
initializeSectionAiControls();
initializeWorkspaceSplitPane();
initializeSpecNavigation();
document.querySelectorAll("[data-workspace-stream-composer]").forEach((form) => {
  syncStreamComposerFiles(form);
});
setAuthMode("login");

const autoRefreshMs = Number(document.body.dataset.autoRefresh || 0);
if (autoRefreshMs > 0) {
  window.setInterval(() => {
    if (workspaceLiveRefreshEnabled()) {
      refreshWorkspaceLiveRegions().catch((error) => {
        console.error(error);
      });
      return;
    }
    if (shouldPauseBackgroundRefresh()) {
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
