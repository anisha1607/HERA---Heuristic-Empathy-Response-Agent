const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");

let isLoading = false;

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, s => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[s]));
}

function nowTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage({ role, text, metaChips = [], refused = false }) {
  const msg = document.createElement("div");
  msg.className = `msg ${role}${refused ? " refused" : ""}`;

  const row = document.createElement("div");
  row.className = "msg-row";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "U" : "H";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  row.appendChild(avatar);
  row.appendChild(bubble);

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML = `<span>${esc(nowTime())}</span>` + metaChips.map(c => c).join("");

  msg.appendChild(row);
  msg.appendChild(meta);

  chatEl.appendChild(msg);
  scrollToBottom();
}

function chip(text, kind = "good") {
  return `<span class="chip ${kind}">${esc(text)}</span>`;
}

function setLoading(v) {
  isLoading = v;
  sendBtn.disabled = v;
  inputEl.disabled = v;
}

function showTyping(show) {
  const existing = document.getElementById("typing");
  if (show) {
    if (existing) return;
    const wrap = document.createElement("div");
    wrap.id = "typing";
    wrap.className = "typing";
    wrap.innerHTML = `<span class="dot"></span><span class="dot"></span><span class="dot"></span>`;
    chatEl.appendChild(wrap);
    scrollToBottom();
  } else {
    if (existing) existing.remove();
  }
}

async function send() {
  const situation = inputEl.value.trim();
  if (!situation || isLoading) return;

  addMessage({ role: "user", text: situation });
  inputEl.value = "";
  inputEl.style.height = "auto";

  setLoading(true);
  showTyping(true);

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ situation })
    });

    const data = await res.json();

    showTyping(false);

    const g = data.guard_label ?? "UNKNOWN";
    const conf = typeof data.guard_confidence === "number" ? data.guard_confidence : null;
    const refused = !!data.refused;

    const confText = conf === null ? "" : ` ${conf.toFixed(2)}`;
    const guardChipKind = refused ? "bad" : (conf !== null && conf < 0.45 ? "warn" : "good");

    const chips = [
      chip(`guard=${g}${confText}`, guardChipKind),
      refused ? chip("REFUSED", "bad") : chip("OK", "good"),
    ];

    addMessage({
      role: "hera",
      text: (data.response ?? "").trim(),
      metaChips: chips,
      refused
    });

  } catch (err) {
    showTyping(false);
    addMessage({
      role: "hera",
      text: "Sorry — something went wrong calling the server. Check the backend logs and Ollama.",
      metaChips: [chip("ERROR", "bad")],
      refused: true
    });
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

function clearChat() {
  chatEl.innerHTML = "";
  // small welcome
  addMessage({
    role: "hera",
    text:
`Hi, I am HERA. Tell me what you’re noticing with your child, and I will help you
find a calm way to respond.`,
    metaChips: [chip("ready", "good")]
  });
}

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
});

sendBtn.addEventListener("click", send);
clearBtn.addEventListener("click", clearChat);

// init
clearChat();