// EduSpark Support - frontend chat logic (vanilla JS, no build step needed)

let sessionId = null;
const DEMO_USER_ID = "user_101"; // pretend a logged-in user for personalization demo

const chatWindow = document.getElementById("chat-window");
const input = document.getElementById("msg-input");
const sendBtn = document.getElementById("send-btn");
const suggestions = document.getElementById("suggestions");

function addRow(role, text, opts = {}) {
  const row = document.createElement("div");
  row.className = `row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble" + (opts.escalated ? " escalated" : "");
  bubble.textContent = text;
  row.appendChild(bubble);

  if (opts.meta) {
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = opts.meta;
    row.appendChild(meta);
  }

  if (role === "bot" && opts.messageId) {
    const fb = document.createElement("div");
    fb.className = "feedback";
    const up = document.createElement("button");
    up.textContent = "👍 Helpful";
    const down = document.createElement("button");
    down.textContent = "👎 Not helpful";

    up.onclick = () => sendFeedback(opts.messageId, "up", up, down);
    down.onclick = () => sendFeedback(opts.messageId, "down", up, down);

    fb.appendChild(up);
    fb.appendChild(down);
    row.appendChild(fb);
  }

  chatWindow.appendChild(row);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addTyping() {
  const el = document.createElement("div");
  el.className = "typing";
  el.id = "typing-indicator";
  el.textContent = "EduSpark bot is typing...";
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

async function sendFeedback(messageId, rating, upBtn, downBtn) {
  upBtn.classList.remove("active-up");
  downBtn.classList.remove("active-down");
  if (rating === "up") upBtn.classList.add("active-up");
  if (rating === "down") downBtn.classList.add("active-down");

  try {
    await fetch(`${API_BASE_URL}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: messageId, session_id: sessionId, rating }),
    });
  } catch (e) {
    console.error("Feedback failed:", e);
  }
}

async function startSession() {
  try {
    const res = await fetch(`${API_BASE_URL}/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: DEMO_USER_ID }),
    });
    const data = await res.json();
    sessionId = data.session_id;
    // trigger a greeting turn
    await sendMessage("hi", { silent_user_bubble: true });
  } catch (e) {
    addRow("bot", "Could not connect to the backend. Make sure the API server is running (see README).");
    console.error(e);
  }
}

async function sendMessage(text, opts = {}) {
  if (!text.trim()) return;
  if (!opts.silent_user_bubble) {
    addRow("user", text);
  }
  input.value = "";
  sendBtn.disabled = true;
  addTyping();

  try {
    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text, user_id: DEMO_USER_ID }),
    });
    const data = await res.json();
    removeTyping();

    let metaParts = [];
    if (data.sentiment && data.sentiment.label) metaParts.push(`sentiment: ${data.sentiment.label}`);
    if (data.similarity_score !== null && data.similarity_score !== undefined) {
      metaParts.push(`match confidence: ${(data.similarity_score * 100).toFixed(0)}%`);
    }
    if (data.escalated) metaParts.push("escalated to human agent");

    addRow("bot", data.reply, {
      meta: metaParts.join(" · "),
      messageId: data.message_id,
      escalated: data.escalated,
    });
  } catch (e) {
    removeTyping();
    addRow("bot", "Something went wrong reaching the server. Please try again.");
    console.error(e);
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", () => sendMessage(input.value));
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage(input.value);
});
suggestions.addEventListener("click", (e) => {
  if (e.target.tagName === "BUTTON") {
    sendMessage(e.target.dataset.q);
  }
});

startSession();
