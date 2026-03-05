const statusEl = document.getElementById("status");
const copyBtn = document.getElementById("copyBtn");
const saveBtn = document.getElementById("saveBtn");
const hintEl = document.getElementById("hint");

let currentToken = null;

function maskToken(token) {
  if (token.length <= 20) return token.slice(0, 6) + "..." + token.slice(-4);
  return token.slice(0, 10) + "..." + token.slice(-6);
}

function showToken(token) {
  currentToken = token;
  statusEl.className = "status found";
  statusEl.innerHTML = `Token captured<div class="token-preview">${maskToken(token)}</div>`;
  copyBtn.disabled = false;
  saveBtn.disabled = false;
  hintEl.textContent = "";
}

function showWaiting() {
  statusEl.className = "status waiting";
  statusEl.textContent = "No token captured yet";
  hintEl.textContent = "Open Discord in a tab and navigate around to capture the token.";
}

// Get token from background
chrome.runtime.sendMessage({ type: "getToken" }, (response) => {
  if (response?.token) {
    showToken(response.token);
  } else {
    showWaiting();
  }
});

copyBtn.addEventListener("click", async () => {
  if (!currentToken) return;
  await navigator.clipboard.writeText(currentToken);
  copyBtn.textContent = "Copied!";
  setTimeout(() => (copyBtn.textContent = "Copy Token"), 1500);
});

saveBtn.addEventListener("click", () => {
  if (!currentToken) return;
  const blob = new Blob([currentToken], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download(
    { url, filename: ".token", saveAs: true },
    () => {
      saveBtn.textContent = "Saved!";
      setTimeout(() => (saveBtn.textContent = "Save .token"), 1500);
    }
  );
});
