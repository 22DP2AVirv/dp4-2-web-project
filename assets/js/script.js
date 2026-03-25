const DARK_MODE_KEY = "darkMode";
const APPOINTMENT_LOGIN_REQUIRED_MESSAGE = "Lai pieteiktos uz procedūru, Jums ir jābūt reģistrētam lietotājam!";
const DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE = "Ārsta kontam procedūru pieteikšana nav pieejama.";
const DOCTOR_REGISTRATION_PATH = "arsts.html";
const CHATBOT_HISTORY_STORAGE_KEY = "clinicChatbotHistory";
const CHATBOT_OPEN_STORAGE_KEY = "clinicChatbotOpen";
const CHATBOT_SESSION_KEY_STORAGE_KEY = "clinicChatbotSessionKey";
const CHATBOT_MAX_HISTORY_ITEMS = 18;
const CHATBOT_WELCOME_MESSAGE = "Sveiki! Esmu Health and Care virtuālais asistents. Varu palīdzēt ar jautājumiem par klīniku, pakalpojumiem, cenām, ārstiem, darba laiku un pieraksta kārtību.";
const CHATBOT_DISABLED_PAGES = new Set([
    "admin-login.html",
    "admin-panel.html",
    "admin-users.html",
    "admin-doctors.html",
    "admin-services.html",
    "admin-prices.html",
    "admin-about.html",
    "admin-messages.html",
    "pieteikumi-adm.html"
]);

let sessionUserPromise = null;
const chatbotState = {
    open: false,
    history: [],
    loading: false
};

function escapeChatbotHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function safeSessionStorageGet(key) {
    try {
        return window.sessionStorage.getItem(key);
    } catch (error) {
        return null;
    }
}

function safeSessionStorageSet(key, value) {
    try {
        window.sessionStorage.setItem(key, value);
    } catch (error) {
        console.warn("Neizdevās saglabāt čatbota stāvokli:", error);
    }
}

function safeSessionStorageRemove(key) {
    try {
        window.sessionStorage.removeItem(key);
    } catch (error) {
        console.warn("Neizdevās notīrīt čatbota stāvokli:", error);
    }
}

function getDefaultChatbotHistory() {
    return [
        {
            role: "assistant",
            content: CHATBOT_WELCOME_MESSAGE
        }
    ];
}

function getCurrentPageName() {
    const path = window.location.pathname || "";
    const segments = path.split("/").filter(Boolean);
    return segments.length ? segments[segments.length - 1].toLowerCase() : "index.html";
}

function isChatbotDisabledPage() {
    return CHATBOT_DISABLED_PAGES.has(getCurrentPageName());
}

function getChatbotSessionKey(account) {
    if (!account || !account.role || !account.id) {
        return "guest";
    }

    return `${account.role}:${account.id}`;
}

function loadChatbotState() {
    const storedHistory = safeSessionStorageGet(CHATBOT_HISTORY_STORAGE_KEY);
    const storedOpenState = safeSessionStorageGet(CHATBOT_OPEN_STORAGE_KEY);

    if (storedHistory) {
        try {
            const parsedHistory = JSON.parse(storedHistory);
            if (Array.isArray(parsedHistory)) {
                chatbotState.history = parsedHistory
                    .filter((item) => item && ["user", "assistant"].includes(item.role) && typeof item.content === "string")
                    .slice(-CHATBOT_MAX_HISTORY_ITEMS);
            }
        } catch (error) {
            chatbotState.history = [];
        }
    }

    chatbotState.open = storedOpenState === "true";

    if (!chatbotState.history.length) {
        chatbotState.history = getDefaultChatbotHistory();
        persistChatbotState();
    }
}

function persistChatbotState() {
    safeSessionStorageSet(
        CHATBOT_HISTORY_STORAGE_KEY,
        JSON.stringify(chatbotState.history.slice(-CHATBOT_MAX_HISTORY_ITEMS))
    );
    safeSessionStorageSet(CHATBOT_OPEN_STORAGE_KEY, chatbotState.open ? "true" : "false");
}

function resetChatbotConversation(options = {}) {
    const shouldRemoveSessionKey = options.removeSessionKey === true;
    chatbotState.history = getDefaultChatbotHistory();
    chatbotState.loading = false;
    chatbotState.open = false;

    if (shouldRemoveSessionKey) {
        safeSessionStorageRemove(CHATBOT_SESSION_KEY_STORAGE_KEY);
    }

    persistChatbotState();

    const shell = document.getElementById("clinicChatbotShell");
    if (shell) {
        shell.classList.remove("open");
        const toggle = document.getElementById("clinicChatbotToggle");
        if (toggle) {
            toggle.setAttribute("aria-expanded", "false");
        }
        renderChatbotMessages();
    }
}

function syncChatbotSession(account) {
    const nextSessionKey = getChatbotSessionKey(account);
    const previousSessionKey = safeSessionStorageGet(CHATBOT_SESSION_KEY_STORAGE_KEY);

    if (!previousSessionKey && nextSessionKey !== "guest") {
        resetChatbotConversation();
    } else if (previousSessionKey && previousSessionKey !== nextSessionKey) {
        resetChatbotConversation();
    }

    safeSessionStorageSet(CHATBOT_SESSION_KEY_STORAGE_KEY, nextSessionKey);
}

function ensureChatbotStyles() {
    if (document.getElementById("clinicChatbotStyles")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "clinicChatbotStyles";
    style.textContent = `
        .clinic-chatbot-shell {
            position: fixed;
            right: clamp(16px, 2vw, 24px);
            bottom: clamp(16px, 2vw, 24px);
            z-index: 1200;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 12px;
            pointer-events: none;
        }

        .clinic-chatbot-toggle,
        .clinic-chatbot-panel {
            pointer-events: auto;
        }

        .clinic-chatbot-toggle {
            width: 58px;
            height: 58px;
            border: none;
            border-radius: 50%;
            background: linear-gradient(135deg, #194E60, #2AA7B3);
            color: #fff;
            font-size: 0.95rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            box-shadow: 0 18px 34px rgba(25, 78, 96, 0.28);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .clinic-chatbot-toggle:hover {
            transform: translateY(-2px);
            box-shadow: 0 22px 38px rgba(25, 78, 96, 0.34);
        }

        .clinic-chatbot-panel {
            width: min(360px, calc(100vw - 24px));
            max-height: min(520px, 72vh);
            display: none;
            flex-direction: column;
            overflow: hidden;
            border-radius: 22px;
            background: rgba(255, 255, 255, 0.98);
            border: 1px solid rgba(25, 78, 96, 0.12);
            box-shadow: 0 24px 50px rgba(18, 43, 51, 0.2);
            backdrop-filter: blur(10px);
        }

        .clinic-chatbot-shell.open .clinic-chatbot-panel {
            display: flex;
        }

        .clinic-chatbot-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding: 16px 18px;
            background: linear-gradient(135deg, #194E60, #267B8A);
            color: #fff;
        }

        .clinic-chatbot-title {
            margin: 0;
            font-size: 1rem;
            font-weight: 800;
        }

        .clinic-chatbot-subtitle {
            margin: 4px 0 0;
            font-size: 0.84rem;
            opacity: 0.88;
        }

        .clinic-chatbot-close {
            border: none;
            background: rgba(255, 255, 255, 0.14);
            color: #fff;
            width: 34px;
            height: 34px;
            border-radius: 50%;
            font-size: 1.1rem;
            line-height: 1;
        }

        .clinic-chatbot-messages {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            background: linear-gradient(180deg, rgba(25, 78, 96, 0.04), rgba(255, 255, 255, 0.9));
        }

        .clinic-chatbot-message {
            max-width: 88%;
            padding: 12px 14px;
            border-radius: 16px;
            line-height: 1.5;
            font-size: 0.95rem;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .clinic-chatbot-message.assistant {
            align-self: flex-start;
            background: #edf7f8;
            color: #173d4a;
            border-bottom-left-radius: 6px;
        }

        .clinic-chatbot-message.user {
            align-self: flex-end;
            background: #194E60;
            color: #fff;
            border-bottom-right-radius: 6px;
        }

        .clinic-chatbot-message.typing {
            font-style: italic;
            opacity: 0.85;
        }

        .clinic-chatbot-form {
            padding: 14px;
            border-top: 1px solid rgba(25, 78, 96, 0.1);
            background: rgba(255, 255, 255, 0.96);
        }

        .clinic-chatbot-input-row {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }

        .clinic-chatbot-input {
            flex: 1;
            min-height: 44px;
            max-height: 120px;
            resize: vertical;
            border-radius: 14px;
            border: 1px solid rgba(25, 78, 96, 0.18);
            padding: 11px 13px;
            font-size: 0.95rem;
            color: #173d4a;
            background: #fbfdff;
        }

        .clinic-chatbot-submit {
            border: none;
            border-radius: 14px;
            padding: 12px 16px;
            background: #194E60;
            color: #fff;
            font-weight: 700;
            min-width: 86px;
        }

        .clinic-chatbot-note {
            margin-top: 10px;
            font-size: 0.78rem;
            color: #5e737c;
        }

        body.dark-mode .clinic-chatbot-panel {
            background: rgba(38, 38, 38, 0.98);
            border-color: rgba(255, 255, 255, 0.08);
        }

        body.dark-mode .clinic-chatbot-messages,
        body.dark-mode .clinic-chatbot-form {
            background: rgba(38, 38, 38, 0.98);
        }

        body.dark-mode .clinic-chatbot-message.assistant {
            background: rgba(255, 255, 255, 0.08);
            color: #f4f7f8;
        }

        body.dark-mode .clinic-chatbot-input {
            background: #2f2f2f;
            border-color: rgba(255, 255, 255, 0.1);
            color: #fff;
        }

        body.dark-mode .clinic-chatbot-note {
            color: #b8c7cc;
        }

        @media (max-width: 640px) {
            .clinic-chatbot-shell {
                right: 12px;
                bottom: 12px;
            }

            .clinic-chatbot-panel {
                width: min(92vw, 360px);
                max-height: 68vh;
            }
        }
    `;

    document.head.appendChild(style);
}

function renderChatbotMessages() {
    const messagesContainer = document.getElementById("clinicChatbotMessages");
    if (!messagesContainer) {
        return;
    }

    messagesContainer.innerHTML = chatbotState.history.map((message) => `
        <div class="clinic-chatbot-message ${escapeChatbotHtml(message.role)}">
            ${escapeChatbotHtml(message.content)}
        </div>
    `).join("");

    if (chatbotState.loading) {
        const typing = document.createElement("div");
        typing.className = "clinic-chatbot-message assistant typing";
        typing.textContent = "Asistents raksta atbildi...";
        messagesContainer.appendChild(typing);
    }

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function setChatbotOpenState(isOpen) {
    const shell = document.getElementById("clinicChatbotShell");
    const toggle = document.getElementById("clinicChatbotToggle");
    if (!shell || !toggle) {
        return;
    }

    chatbotState.open = isOpen;
    shell.classList.toggle("open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    persistChatbotState();

    if (isOpen) {
        document.getElementById("clinicChatbotInput")?.focus();
    }
}

function appendChatbotMessage(role, content) {
    chatbotState.history.push({
        role,
        content: String(content || "").trim()
    });
    chatbotState.history = chatbotState.history
        .filter((item) => item.content)
        .slice(-CHATBOT_MAX_HISTORY_ITEMS);
    persistChatbotState();
    renderChatbotMessages();
}

async function sendChatbotMessage(rawMessage) {
    const message = String(rawMessage || "").trim();
    if (!message || chatbotState.loading) {
        return;
    }

    appendChatbotMessage("user", message);
    chatbotState.loading = true;
    renderChatbotMessages();

    try {
        const conversationHistory = chatbotState.history.slice(0, -1).slice(-8);
        const response = await fetch("/api/chatbot", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message,
                history: conversationHistory
            })
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās saņemt čatbota atbildi.");
        }

        appendChatbotMessage("assistant", (data && data.reply) || "Atvainojiet, šobrīd atbilde nav pieejama.");
    } catch (error) {
        appendChatbotMessage(
            "assistant",
            error.message || "Atvainojiet, šobrīd neizdevās apstrādāt Jūsu ziņu."
        );
    } finally {
        chatbotState.loading = false;
        renderChatbotMessages();
    }
}

function createChatbotWidget() {
    if (isChatbotDisabledPage()) {
        return;
    }

    if (document.getElementById("clinicChatbotShell")) {
        return;
    }

    ensureChatbotStyles();
    loadChatbotState();

    const shell = document.createElement("div");
    shell.id = "clinicChatbotShell";
    shell.className = "clinic-chatbot-shell";
    shell.innerHTML = `
        <div class="clinic-chatbot-panel" aria-live="polite">
            <div class="clinic-chatbot-header">
                <div>
                    <p class="clinic-chatbot-title">Klīnikas asistents</p>
                    <p class="clinic-chatbot-subtitle">Atbild tikai par Health and Care</p>
                </div>
                <button id="clinicChatbotClose" class="clinic-chatbot-close" type="button" aria-label="Aizvērt čatu">&times;</button>
            </div>
            <div id="clinicChatbotMessages" class="clinic-chatbot-messages"></div>
            <form id="clinicChatbotForm" class="clinic-chatbot-form">
                <div class="clinic-chatbot-input-row">
                    <textarea
                        id="clinicChatbotInput"
                        class="clinic-chatbot-input"
                        rows="2"
                        maxlength="1200"
                        placeholder="Uzdod jautājumu par klīniku..."
                    ></textarea>
                    <button class="clinic-chatbot-submit" type="submit">Sūtīt</button>
                </div>
                <div class="clinic-chatbot-note">Asistents atbild tikai par klīnikas tēmu.</div>
            </form>
        </div>
        <button id="clinicChatbotToggle" class="clinic-chatbot-toggle" type="button" aria-expanded="false" aria-label="Atvērt čatu">AI</button>
    `;

    document.body.appendChild(shell);
    renderChatbotMessages();
    setChatbotOpenState(chatbotState.open);

    document.getElementById("clinicChatbotToggle")?.addEventListener("click", () => {
        setChatbotOpenState(!chatbotState.open);
    });

    document.getElementById("clinicChatbotClose")?.addEventListener("click", () => {
        setChatbotOpenState(false);
    });

    document.getElementById("clinicChatbotForm")?.addEventListener("submit", async (event) => {
        event.preventDefault();

        const input = document.getElementById("clinicChatbotInput");
        if (!input) {
            return;
        }

        const message = input.value.trim();
        if (!message) {
            return;
        }

        input.value = "";
        setChatbotOpenState(true);
        await sendChatbotMessage(message);
    });

    document.getElementById("clinicChatbotInput")?.addEventListener("keydown", async (event) => {
        if (event.key !== "Enter" || event.shiftKey) {
            return;
        }

        event.preventDefault();

        const input = event.currentTarget;
        const message = input.value.trim();
        if (!message) {
            return;
        }

        input.value = "";
        setChatbotOpenState(true);
        await sendChatbotMessage(message);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && chatbotState.open) {
            setChatbotOpenState(false);
        }
    });
}

async function fetchSessionUser() {
    if (!sessionUserPromise) {
        sessionUserPromise = fetch("/api/me", {
            headers: {
                Accept: "application/json"
            }
        })
            .then(async (response) => {
                if (!response.ok) {
                    return null;
                }

                return response.json();
            })
            .catch((error) => {
                console.error("Neizdevās pārbaudīt aktīvo sesiju:", error);
                return null;
            });
    }

    return sessionUserPromise;
}

function pointButtonToAccount(button) {
    if (!button) {
        return;
    }

    button.textContent = "Konts";
    button.type = "button";

    const parentLink = button.closest("a");
    if (parentLink) {
        parentLink.href = "user_cab.html";
        return;
    }

    button.onclick = () => {
        window.location.href = "user_cab.html";
    };
}

function removeDoctorRegistrationButton() {
    document.getElementById("doctorRegistrationButton")?.remove();
}

function ensureDoctorRegistrationButton() {
    const actions = document.querySelector(".dark-mode-toggle");
    if (!actions || document.getElementById("doctorRegistrationButton")) {
        return;
    }

    const doctorButton = document.createElement("button");
    doctorButton.id = "doctorRegistrationButton";
    doctorButton.type = "button";
    doctorButton.textContent = "Ārsts";
    doctorButton.addEventListener("click", () => {
        window.location.href = DOCTOR_REGISTRATION_PATH;
    });

    const darkModeButton = document.getElementById("dark-mode-btn");
    if (darkModeButton) {
        actions.insertBefore(doctorButton, darkModeButton);
        return;
    }

    actions.appendChild(doctorButton);
}

async function updateSessionNavigation() {
    const account = await fetchSessionUser();
    syncChatbotSession(account);

    if (account) {
        removeDoctorRegistrationButton();

        const headerButton = document.getElementById("registracija");
        pointButtonToAccount(headerButton);

        document.querySelectorAll("button.Logins").forEach((button) => {
            pointButtonToAccount(button);
        });
        return account;
    }

    ensureDoctorRegistrationButton();
    return account;
}

function setDarkMode(isDark) {
    document.body.classList.toggle("dark-mode", isDark);

    const toggleButton = document.getElementById("dark-mode-btn");
    if (toggleButton) {
        toggleButton.textContent = isDark ? "Gaišais režīms" : "Tumsas režīms";
    }

    localStorage.setItem(DARK_MODE_KEY, isDark ? "enabled" : "disabled");
}

function toggleMenu() {
    const menu = document.querySelector(".navbar .menu");
    if (menu) {
        menu.classList.toggle("active");
    }
}

function showWorkTime() {
    const modal = document.getElementById("workTimeModal");
    if (modal) {
        modal.style.display = "block";
    }
}

function closeWorkTime() {
    const modal = document.getElementById("workTimeModal");
    if (modal) {
        modal.style.display = "none";
    }
}

function isAppointmentLink(link) {
    if (!link) {
        return false;
    }

    const href = link.getAttribute("href");
    if (!href) {
        return false;
    }

    const normalizedHref = href.split("#")[0].split("?")[0];
    return normalizedHref.endsWith("pieteikties.html");
}

window.toggleMenu = toggleMenu;
window.showWorkTime = showWorkTime;
window.closeWorkTime = closeWorkTime;
window.APPOINTMENT_LOGIN_REQUIRED_MESSAGE = APPOINTMENT_LOGIN_REQUIRED_MESSAGE;
window.DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE = DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE;
window.clearClinicChatbotConversation = () => {
    resetChatbotConversation({ removeSessionKey: true });
};

document.addEventListener("DOMContentLoaded", () => {
    const darkModeStatus = localStorage.getItem(DARK_MODE_KEY);
    setDarkMode(darkModeStatus === "enabled");

    const toggleButton = document.getElementById("dark-mode-btn");
    if (toggleButton) {
        toggleButton.addEventListener("click", () => {
            const isDark = !document.body.classList.contains("dark-mode");
            setDarkMode(isDark);
        });
    }

    const carousel = document.querySelector("#main-slider");
    if (carousel && window.bootstrap && window.bootstrap.Carousel) {
        new bootstrap.Carousel(carousel, {
            interval: 3000,
            ride: "carousel"
        });
    }

    document.querySelectorAll("form").forEach((form) => {
        if ([
            "appointmentForm",
            "registrationForm",
            "doctorRegistrationForm",
            "loginForm",
            "contactForm",
            "profileForm",
            "passwordForm"
        ].includes(form.id)) {
            return;
        }

        form.addEventListener("submit", (event) => {
            event.preventDefault();
            alert("Paldies! Mēs ar jums drīz sazināsimies.");
            form.reset();
        });
    });

    updateSessionNavigation().finally(() => {
        createChatbotWidget();
    });
});

document.addEventListener("click", async (event) => {
    const appointmentLink = event.target.closest("a");
    if (!isAppointmentLink(appointmentLink)) {
        return;
    }

    event.preventDefault();

    const account = await fetchSessionUser();
    if (!account) {
        alert(APPOINTMENT_LOGIN_REQUIRED_MESSAGE);
        return;
    }

    if (account.can_book_appointments) {
        window.location.assign(appointmentLink.href);
        return;
    }

    alert(DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE);
});
