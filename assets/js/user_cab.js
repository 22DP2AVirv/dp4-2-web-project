const PROCEDURE_LABELS = {
    datortomografija: "Datortomogrāfija",
    gimenesArsts: "Ģimenes ārsts",
    vakcinacija: "Vakcinācija"
};

const LOCATION_LABELS = {
    riga: "Rīga, Brīvības iela",
    jelgava: "Jelgava, Zemgales prospekts",
    liepaja: "Liepāja, Rožu iela"
};

const cabinetState = {
    user: null,
    appointments: []
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

async function readJsonResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
        return null;
    }

    return response.json();
}

async function fetchCurrentUser() {
    const response = await fetch("/api/me");
    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }

    const data = await readJsonResponse(response);
    if (!response.ok || !data) {
        throw new Error("Neizdevās ielādēt konta datus.");
    }

    return data;
}

async function fetchMyAppointments() {
    const response = await fetch("/api/my-appointments");
    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }

    const data = await readJsonResponse(response);
    if (!response.ok || !Array.isArray(data)) {
        throw new Error((data && data.error) || "Neizdevās ielādēt pieteikumus.");
    }

    return data;
}

async function cancelMyAppointment(appointmentId) {
    const response = await fetch(`/api/my-appointments/${appointmentId}`, {
        method: "DELETE"
    });
    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }

    const data = await readJsonResponse(response);
    if (!response.ok) {
        throw new Error((data && data.error) || "Neizdevās atcelt pieteikumu.");
    }

    return data;
}

async function logoutUser() {
    await fetch("/api/logout", { method: "POST" });
    if (typeof window.clearClinicChatbotConversation === "function") {
        window.clearClinicChatbotConversation();
    }
    window.location.href = "index.html";
}

function formatDate(value) {
    if (!value) {
        return "Nav norādīts";
    }

    const date = value.includes("T")
        ? new Date(value)
        : new Date(`${value}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat("lv-LV", {
        day: "2-digit",
        month: "long",
        year: "numeric"
    }).format(date);
}

function formatTime(value) {
    if (!value) {
        return "Nav norādīts";
    }

    return String(value).slice(0, 5);
}

function formatProcedure(value) {
    return PROCEDURE_LABELS[value] || value || "Nav norādīts";
}

function formatLocation(value) {
    return LOCATION_LABELS[value] || value || "Nav norādīta";
}

function formatDoctorName(value) {
    return value || "Nav piešķirts";
}

function getUserInitials(user) {
    const first = (user.name || "").trim().charAt(0);
    const second = (user.surname || "").trim().charAt(0);
    return `${first}${second}`.toUpperCase() || "HC";
}

function setPanelMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }

    element.textContent = message;
    element.className = `panel-message visible ${type}`;
}

function clearPanelMessage(elementId) {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }

    element.textContent = "";
    element.className = "panel-message";
}

function setCabinetRolePresentation(user) {
    const badge = document.getElementById("cabinetRoleBadge");
    if (badge) {
        badge.innerHTML = user.role === "doctor"
            ? '<i class="fa-solid fa-user-doctor"></i> Ārsta kabinets'
            : '<i class="fa-solid fa-user-gear"></i> Lietotāja kabinets';
    }

    const subtitle = document.querySelector(".cabinet-subtitle");
    if (subtitle) {
        subtitle.textContent = user.role === "doctor"
            ? "Šeit vari pārvaldīt savu ārsta profilu, mainīt paroli, atjaunināt specializāciju un pārskatīt savus pierakstus."
            : "Šeit vari pārvaldīt savu profilu, mainīt paroli un pārskatīt visus savus pieteikumus vienuviet.";
    }

    const appointmentCountCard = document.getElementById("summaryAppointmentCount")?.closest(".profile-stat");
    const procedureCard = document.getElementById("summaryProcedureCard");
    const appointmentsPanel = document.getElementById("appointmentsPanel");
    const appointmentsNavButton = document.getElementById("appointmentsNavButton");
    const procedureGroup = document.getElementById("profileProcedureGroup");
    const appointmentCountLabel = document.getElementById("summaryAppointmentCountLabel");
    const appointmentsPanelTitle = document.getElementById("appointmentsPanelTitle");
    const appointmentsPanelIntro = document.getElementById("appointmentsPanelIntro");

    if (appointmentCountCard) {
        appointmentCountCard.hidden = false;
    }

    if (procedureCard) {
        procedureCard.hidden = user.role !== "doctor";
    }

    if (appointmentsPanel) {
        appointmentsPanel.hidden = false;
    }

    if (appointmentsNavButton) {
        appointmentsNavButton.hidden = false;
        appointmentsNavButton.textContent = user.role === "doctor"
            ? "Mani pieraksti"
            : "Mani pieteikumi";
    }

    if (procedureGroup) {
        procedureGroup.hidden = user.role !== "doctor";
    }

    if (appointmentCountLabel) {
        appointmentCountLabel.textContent = user.role === "doctor"
            ? "Pierakstu skaits"
            : "Pieteikumu skaits";
    }

    if (appointmentsPanelTitle) {
        appointmentsPanelTitle.textContent = user.role === "doctor"
            ? "Mani pieraksti"
            : "Mani pieteikumi";
    }

    if (appointmentsPanelIntro) {
        appointmentsPanelIntro.textContent = user.role === "doctor"
            ? "Šeit redzami visi pacientu pieraksti pie tevis ar procedūru, datumu, laiku un kontaktinformāciju."
            : "Šeit redzami visi tavi izveidotie procedūru pieteikumi ar datumu, laiku, ārstu un norādīto atrašanās vietu.";
    }
}

function fillProfileForm(user) {
    document.getElementById("profileName").value = user.name || "";
    document.getElementById("profileSurname").value = user.surname || "";
    document.getElementById("profilePhone").value = user.phone || "";
    document.getElementById("profileEmail").value = user.email || "";

    const procedureInput = document.getElementById("profileProcedure");
    if (procedureInput) {
        procedureInput.value = user.procedure || "datortomografija";
    }
}

function renderUserSummary(user) {
    cabinetState.user = user;
    setCabinetRolePresentation(user);

    document.getElementById("welcome").textContent = `Sveiki, ${user.name || "lietotāj"}!`;
    document.getElementById("profileInitials").textContent = getUserInitials(user);
    document.getElementById("summaryName").textContent = `${user.name || ""} ${user.surname || ""}`.trim() || "Lietotājs";
    document.getElementById("summaryEmail").textContent = user.email || "Nav norādīts";
    document.getElementById("summaryPhone").textContent = user.phone || "Nav norādīts";
    document.getElementById("summaryCreatedAt").textContent = formatDate(user.created_at);
    document.getElementById("summaryPasswordUpdatedAt").textContent = formatDate(user.password_updated_at);
    document.getElementById("currentPassword").value = "Drošības nolūkos netiek rādīta";

    const procedureSummary = document.getElementById("summaryProcedure");
    if (procedureSummary) {
        procedureSummary.textContent = user.role === "doctor"
            ? formatProcedure(user.procedure)
            : "-";
    }

    fillProfileForm(user);
}

function renderAppointments(appointments) {
    cabinetState.appointments = appointments;
    document.getElementById("summaryAppointmentCount").textContent = String(appointments.length);

    const list = document.getElementById("appointmentsList");
    if (!list) {
        return;
    }

    const isDoctorView = cabinetState.user?.role === "doctor";

    if (!appointments.length) {
        list.innerHTML = isDoctorView
            ? `
                <div class="empty-state">
                    <h3>Tev vēl nav pierakstu</h3>
                    <p>Kad pacienti pierakstīsies pie tevis, tie parādīsies šajā sadaļā.</p>
                </div>
            `
            : `
                <div class="empty-state">
                    <h3>Tev vēl nav pieteikumu</h3>
                    <p>Kad izveidosi savu pirmo pieteikumu, tas parādīsies šajā sadaļā.</p>
                    <a href="pieteikties.html">
                        <button class="appointments-action" type="button">Pieteikties procedūrai</button>
                    </a>
                </div>
            `;
        return;
    }

    list.innerHTML = appointments.map((appointment) => {
        if (isDoctorView) {
            const patientFullName = `${appointment.name || ""} ${appointment.surname || ""}`.trim() || "Nav norādīts";
            return `
                <article class="appointment-card">
                    <div class="appointment-head">
                        <div>
                            <h3>${escapeHtml(formatProcedure(appointment.procedura))}</h3>
                            <div class="panel-text">Pacients: ${escapeHtml(patientFullName)}</div>
                        </div>
                        <div class="appointment-date">
                            <i class="fa-regular fa-calendar"></i>
                            ${escapeHtml(formatDate(appointment.datums))}, ${escapeHtml(formatTime(appointment.laiks))}
                        </div>
                    </div>
                    <div class="appointment-grid">
                        <div class="appointment-field">
                            <span>Pacienta tālrunis</span>
                            <strong>${escapeHtml(appointment.phone || "Nav norādīts")}</strong>
                        </div>
                        <div class="appointment-field">
                            <span>Pacienta e-pasts</span>
                            <strong>${escapeHtml(appointment.email || "Nav norādīts")}</strong>
                        </div>
                        <div class="appointment-field">
                            <span>Vieta</span>
                            <strong>${escapeHtml(formatLocation(appointment.adrese))}</strong>
                        </div>
                        <div class="appointment-field">
                            <span>Pēdējās izmaiņas</span>
                            <strong>${escapeHtml(formatDate(appointment.updated_at))}</strong>
                        </div>
                    </div>
                </article>
            `;
        }

        return `
            <article class="appointment-card">
                <div class="appointment-head">
                    <div>
                        <h3>${escapeHtml(formatProcedure(appointment.procedura))}</h3>
                        <div class="panel-text">Izveidots: ${escapeHtml(formatDate(appointment.created_at))}</div>
                    </div>
                    <div class="appointment-date">
                        <i class="fa-regular fa-calendar"></i>
                        ${escapeHtml(formatDate(appointment.datums))}, ${escapeHtml(formatTime(appointment.laiks))}
                    </div>
                </div>
                <div class="appointment-grid">
                    <div class="appointment-field">
                        <span>Ārsts</span>
                        <strong>${escapeHtml(formatDoctorName(appointment.doctor_full_name))}</strong>
                    </div>
                    <div class="appointment-field">
                        <span>Vieta</span>
                        <strong>${escapeHtml(formatLocation(appointment.adrese))}</strong>
                    </div>
                    <div class="appointment-field">
                        <span>Telefons</span>
                        <strong>${escapeHtml(appointment.phone || "Nav norādīts")}</strong>
                    </div>
                    <div class="appointment-field">
                        <span>E-pasts</span>
                        <strong>${escapeHtml(appointment.email || "Nav norādīts")}</strong>
                    </div>
                    <div class="appointment-field">
                        <span>Pēdējās izmaiņas</span>
                        <strong>${escapeHtml(formatDate(appointment.updated_at))}</strong>
                    </div>
                </div>
                <div class="appointment-actions">
                    <button
                        class="cancel-appointment-action"
                        type="button"
                        data-appointment-id="${escapeHtml(appointment.id)}"
                    >
                        Atcelt pieteikumu
                    </button>
                </div>
            </article>
        `;
    }).join("");
}

function setActivePanel(sectionId) {
    document.querySelectorAll(".cabinet-panel").forEach((panel) => {
        panel.classList.toggle("active", panel.id === sectionId && !panel.hidden);
    });

    document.querySelectorAll(".settings-item").forEach((button) => {
        button.classList.toggle("active", button.dataset.section === sectionId && !button.hidden);
    });
}

function closeSettingsDropdown() {
    const dropdown = document.getElementById("settingsDropdown");
    const toggle = document.getElementById("settingsToggle");
    if (!dropdown || !toggle) {
        return;
    }

    dropdown.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
}

function toggleSettingsDropdown() {
    const dropdown = document.getElementById("settingsDropdown");
    const toggle = document.getElementById("settingsToggle");
    if (!dropdown || !toggle) {
        return;
    }

    const isOpen = dropdown.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(isOpen));
}

function setupSettingsNavigation() {
    const toggle = document.getElementById("settingsToggle");
    if (toggle) {
        toggle.addEventListener("click", toggleSettingsDropdown);
    }

    document.querySelectorAll(".settings-item").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.hidden) {
                return;
            }

            setActivePanel(button.dataset.section);
            closeSettingsDropdown();
        });
    });

    document.addEventListener("click", (event) => {
        const dropdown = document.getElementById("settingsDropdown");
        if (dropdown && !dropdown.contains(event.target)) {
            closeSettingsDropdown();
        }
    });
}

async function reloadUserData() {
    const user = await fetchCurrentUser();
    renderUserSummary(user);
}

async function reloadAppointments() {
    const appointments = await fetchMyAppointments();
    renderAppointments(appointments);
}

async function handleAppointmentsClick(event) {
    const cancelButton = event.target.closest(".cancel-appointment-action");
    if (!cancelButton) {
        return;
    }

    clearPanelMessage("appointmentsMessage");

    const appointmentId = cancelButton.dataset.appointmentId;
    if (!appointmentId) {
        return;
    }

    const shouldCancel = window.confirm("Vai tiešām vēlies atcelt šo pieteikumu?");
    if (!shouldCancel) {
        return;
    }

    cancelButton.disabled = true;
    cancelButton.textContent = "Atceļ...";

    try {
        await cancelMyAppointment(appointmentId);
        await reloadAppointments();
        setPanelMessage("appointmentsMessage", "Pieteikums tika veiksmīgi atcelts!", "success");
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            window.location.href = "login.html";
            return;
        }

        setPanelMessage("appointmentsMessage", error.message, "error");
    } finally {
        if (document.body.contains(cancelButton)) {
            cancelButton.disabled = false;
            cancelButton.textContent = "Atcelt pieteikumu";
        }
    }
}

async function updateProfile(event) {
    event.preventDefault();
    clearPanelMessage("profileMessage");

    const currentUser = cabinetState.user || {};
    const payload = {
        name: document.getElementById("profileName").value.trim() || currentUser.name || "",
        surname: document.getElementById("profileSurname").value.trim() || currentUser.surname || "",
        phone: document.getElementById("profilePhone").value.trim() || currentUser.phone || "",
        email: document.getElementById("profileEmail").value.trim().toLowerCase() || (currentUser.email || "").toLowerCase()
    };

    if (currentUser.role === "doctor") {
        payload.procedure = document.getElementById("profileProcedure").value || currentUser.procedure || "";
    }

    if (!payload.name || !payload.surname || !payload.phone || !payload.email) {
        setPanelMessage("profileMessage", "Lūdzu aizpildi visus profila laukus.", "error");
        return;
    }

    if (currentUser.role === "doctor" && !payload.procedure) {
        setPanelMessage("profileMessage", "Lūdzu izvēlies procedūru.", "error");
        return;
    }

    try {
        const response = await fetch("/api/me", {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (response.status === 401) {
            throw new Error("AUTH_REQUIRED");
        }

        const data = await readJsonResponse(response);
        if (!response.ok || !data) {
            throw new Error((data && data.error) || "Neizdevās saglabāt profila izmaiņas.");
        }

        renderUserSummary(data.user);
        await reloadAppointments();
        setPanelMessage("profileMessage", "Izmaiņas tika veiksmīgi saglabātas!", "success");
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            window.location.href = "login.html";
            return;
        }

        setPanelMessage("profileMessage", error.message, "error");
    }
}

async function updatePassword(event) {
    event.preventDefault();
    clearPanelMessage("passwordMessage");

    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (!newPassword) {
        setPanelMessage("passwordMessage", "Lūdzu ievadi jauno paroli.", "error");
        return;
    }

    if (newPassword !== confirmPassword) {
        setPanelMessage("passwordMessage", "Paroles nesakrīt.", "error");
        return;
    }

    try {
        const response = await fetch("/api/update-password", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ password: newPassword })
        });

        if (response.status === 401) {
            throw new Error("AUTH_REQUIRED");
        }

        const data = await readJsonResponse(response);
        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās atjaunināt paroli.");
        }

        document.getElementById("newPassword").value = "";
        document.getElementById("confirmPassword").value = "";
        await reloadUserData();
        setPanelMessage("passwordMessage", "Izmaiņas tika veiksmīgi saglabātas!", "success");
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            window.location.href = "login.html";
            return;
        }

        setPanelMessage("passwordMessage", error.message, "error");
    }
}

async function initializeCabinet() {
    try {
        const user = await fetchCurrentUser();
        renderUserSummary(user);
        const appointments = await fetchMyAppointments();
        renderAppointments(appointments);
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            window.location.href = "login.html";
            return;
        }

        alert(error.message || "Neizdevās ielādēt lietotāja kabinetu.");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    setupSettingsNavigation();

    const logoutButton = document.getElementById("logoutButton");
    if (logoutButton) {
        logoutButton.addEventListener("click", logoutUser);
    }

    const profileForm = document.getElementById("profileForm");
    if (profileForm) {
        profileForm.addEventListener("submit", updateProfile);
    }

    const passwordForm = document.getElementById("passwordForm");
    if (passwordForm) {
        passwordForm.addEventListener("submit", updatePassword);
    }

    const appointmentsList = document.getElementById("appointmentsList");
    if (appointmentsList) {
        appointmentsList.addEventListener("click", handleAppointmentsClick);
    }

    initializeCabinet();
});
