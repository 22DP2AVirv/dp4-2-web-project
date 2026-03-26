const PROCEDURE_LABELS = {
    datortomografija: "Datortomogrāfija",
    gimenesArsts: "Ģimenes ārsts",
    vakcinacija: "Vakcinācija"
};

const PROCEDURE_ALIASES = {
    datortomografija: "datortomografija",
    datortomogrāfija: "datortomografija",
    gimenesarsts: "gimenesArsts",
    ģimenesārsts: "gimenesArsts",
    gimenesarsts: "gimenesArsts",
    vakcinacija: "vakcinacija",
    vakcinācija: "vakcinacija"
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function normalizeText(value) {
    return String(value ?? "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, "")
        .toLowerCase();
}

function formatProcedure(value) {
    return PROCEDURE_LABELS[value] || value || "-";
}

function parseProcedureValue(value) {
    const normalized = normalizeText(value);
    return PROCEDURE_ALIASES[normalized] || null;
}

async function apiRequest(url, options = {}) {
    const config = {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    };

    const response = await fetch(url, config);
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

    if (response.status === 401) {
        throw new Error("ADMIN_AUTH_REQUIRED");
    }

    if (!response.ok) {
        const message = typeof data === "string" ? data : data.error;
        throw new Error(message || "Neizdevās izpildīt pieprasījumu.");
    }

    return data;
}

function formatDate(value, withTime = true) {
    if (!value) {
        return "";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return withTime ? date.toLocaleString("lv-LV") : date.toLocaleDateString("lv-LV");
}

function formatFullName(item) {
    return [item.name, item.surname].filter(Boolean).join(" ") || "-";
}

function parseTimestamp(value) {
    if (!value) {
        return 0;
    }

    const timestamp = Date.parse(value);
    return Number.isNaN(timestamp) ? 0 : timestamp;
}

function compareText(left, right) {
    return String(left || "").localeCompare(String(right || ""), "lv", {
        sensitivity: "base"
    });
}

function sortItems(items, { mode, getTextValue, getCreatedAtValue, getUpdatedAtValue = getCreatedAtValue }) {
    const sortedItems = [...items];

    if (mode === "az") {
        sortedItems.sort((a, b) => compareText(getTextValue(a), getTextValue(b)));
        return sortedItems;
    }

    if (mode === "za") {
        sortedItems.sort((a, b) => compareText(getTextValue(b), getTextValue(a)));
        return sortedItems;
    }

    if (mode === "newest") {
        sortedItems.sort((a, b) => parseTimestamp(getCreatedAtValue(b)) - parseTimestamp(getCreatedAtValue(a)));
        return sortedItems;
    }

    if (mode === "updated") {
        sortedItems.sort((a, b) => parseTimestamp(getUpdatedAtValue(b)) - parseTimestamp(getUpdatedAtValue(a)));
        return sortedItems;
    }

    if (mode === "oldest") {
        sortedItems.sort((a, b) => parseTimestamp(getCreatedAtValue(a)) - parseTimestamp(getCreatedAtValue(b)));
        return sortedItems;
    }

    return sortedItems;
}

function getSelectedSortValue(selectId, fallbackValue = "oldest") {
    return document.getElementById(selectId)?.value || fallbackValue;
}

function getUserModalElements() {
    return {
        modal: document.getElementById("userModal"),
        form: document.getElementById("userModalForm"),
        title: document.getElementById("userModalTitle"),
        subtitle: document.getElementById("userModalSubtitle"),
        message: document.getElementById("userModalMessage"),
        submitButton: document.getElementById("userModalSubmitBtn"),
        nameInput: document.getElementById("userModalName"),
        surnameInput: document.getElementById("userModalSurname"),
        emailInput: document.getElementById("userModalEmail"),
        phoneInput: document.getElementById("userModalPhone"),
        passwordInput: document.getElementById("userModalPassword"),
        passwordLabel: document.getElementById("userModalPasswordLabel"),
        passwordHint: document.getElementById("userModalPasswordHint")
    };
}

function clearUserModalMessage() {
    const { message } = getUserModalElements();
    if (!message) {
        return;
    }

    message.textContent = "";
    message.classList.add("d-none");
}

function showUserModalMessage(text) {
    const { message } = getUserModalElements();
    if (!message) {
        return;
    }

    message.textContent = text;
    message.classList.remove("d-none");
}

function clearModalMessage(messageElement) {
    if (!messageElement) {
        return;
    }

    messageElement.textContent = "";
    messageElement.classList.add("d-none");
}

function showModalMessage(messageElement, text) {
    if (!messageElement) {
        return;
    }

    messageElement.textContent = text;
    messageElement.classList.remove("d-none");
}

function createModalState() {
    return {
        instance: null,
        mode: "create",
        recordId: null,
        submitting: false,
        doctors: []
    };
}

function resetUserModal() {
    const elements = getUserModalElements();
    if (!elements.form) {
        return;
    }

    userModalState.mode = "create";
    userModalState.userId = null;
    userModalState.submitting = false;

    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearUserModalMessage();

    elements.title.textContent = "Pievienot lietotāju";
    elements.subtitle.textContent = "Aizpildi lietotāja datus un saglabā izmaiņas.";
    elements.submitButton.textContent = "Saglabāt lietotāju";
    elements.submitButton.disabled = false;
    elements.passwordLabel.textContent = "Parole";
    elements.passwordHint.textContent = "Parole ir obligāta tikai jauna lietotāja izveidē.";
    elements.passwordInput.required = true;
}

async function handleUserModalSubmit(event) {
    event.preventDefault();

    const elements = getUserModalElements();
    if (!elements.form || userModalState.submitting) {
        return;
    }

    clearUserModalMessage();
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const payload = {
        name: elements.nameInput.value.trim(),
        surname: elements.surnameInput.value.trim(),
        email: elements.emailInput.value.trim().toLowerCase(),
        phone: elements.phoneInput.value.trim(),
        password: elements.passwordInput.value.trim()
    };

    userModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        if (userModalState.mode === "edit" && userModalState.userId) {
            await apiRequest(`/api/admin/users/${userModalState.userId}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
        } else {
            await apiRequest("/api/admin/users", {
                method: "POST",
                body: JSON.stringify(payload)
            });
        }

        userModalState.instance.hide();
        await renderUsers();
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showUserModalMessage(error.message);
    } finally {
        userModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function ensureUserModal() {
    const elements = getUserModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!userModalState.instance) {
        userModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handleUserModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetUserModal);
    }

    return elements;
}

function openUserModal(mode, user = null) {
    const elements = ensureUserModal();
    if (!elements) {
        return;
    }

    resetUserModal();
    userModalState.mode = mode;

    if (mode === "edit" && user) {
        userModalState.userId = user.id;
        elements.title.textContent = "Rediģēt lietotāju";
        elements.subtitle.textContent = "Maini nepieciešamos laukus un saglabā izmaiņas.";
        elements.submitButton.textContent = "Saglabāt izmaiņas";
        elements.passwordLabel.textContent = "Jaunā parole";
        elements.passwordHint.textContent = "Atstāj lauku tukšu, ja paroli nevajag mainīt.";
        elements.passwordInput.required = false;

        elements.nameInput.value = user.name || "";
        elements.surnameInput.value = user.surname || "";
        elements.emailInput.value = user.email || "";
        elements.phoneInput.value = user.phone || "";
    }

    userModalState.instance.show();
}

function bindUserModalTriggers() {
    const addUserBtn = document.getElementById("addUserBtn");
    if (addUserBtn) {
        addUserBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            openUserModal("create");
        }, true);
    }
}

function getDoctorModalElements() {
    return {
        modal: document.getElementById("doctorModal"),
        form: document.getElementById("doctorModalForm"),
        title: document.getElementById("doctorModalTitle"),
        subtitle: document.getElementById("doctorModalSubtitle"),
        message: document.getElementById("doctorModalMessage"),
        submitButton: document.getElementById("doctorModalSubmitBtn"),
        nameInput: document.getElementById("doctorModalName"),
        surnameInput: document.getElementById("doctorModalSurname"),
        emailInput: document.getElementById("doctorModalEmail"),
        phoneInput: document.getElementById("doctorModalPhone"),
        procedureInput: document.getElementById("doctorModalProcedure"),
        passwordInput: document.getElementById("doctorModalPassword"),
        passwordLabel: document.getElementById("doctorModalPasswordLabel"),
        passwordHint: document.getElementById("doctorModalPasswordHint")
    };
}

function resetDoctorModal() {
    const elements = getDoctorModalElements();
    if (!elements.form) {
        return;
    }

    doctorModalState.mode = "create";
    doctorModalState.recordId = null;
    doctorModalState.submitting = false;
    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearModalMessage(elements.message);

    elements.title.textContent = "Pievienot ārstu";
    elements.subtitle.textContent = "Aizpildi ārsta datus un saglabā izmaiņas.";
    elements.submitButton.textContent = "Saglabāt ārstu";
    elements.submitButton.disabled = false;
    elements.passwordLabel.textContent = "Parole";
    elements.passwordHint.textContent = "Parole ir obligāta tikai jauna ārsta izveidē.";
    elements.passwordInput.required = true;
}

async function handleDoctorModalSubmit(event) {
    event.preventDefault();

    const elements = getDoctorModalElements();
    if (!elements.form || doctorModalState.submitting) {
        return;
    }

    clearModalMessage(elements.message);
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const payload = {
        name: elements.nameInput.value.trim(),
        surname: elements.surnameInput.value.trim(),
        email: elements.emailInput.value.trim().toLowerCase(),
        phone: elements.phoneInput.value.trim(),
        procedure: elements.procedureInput.value,
        password: elements.passwordInput.value.trim()
    };

    doctorModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        if (doctorModalState.mode === "edit" && doctorModalState.recordId) {
            await apiRequest(`/api/admin/doctors/${doctorModalState.recordId}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
        } else {
            await apiRequest("/api/admin/doctors", {
                method: "POST",
                body: JSON.stringify(payload)
            });
        }

        doctorModalState.instance.hide();
        await renderDoctors();
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showModalMessage(elements.message, error.message);
    } finally {
        doctorModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function ensureDoctorModal() {
    const elements = getDoctorModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!doctorModalState.instance) {
        doctorModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handleDoctorModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetDoctorModal);
    }

    return elements;
}

function openDoctorModal(mode, doctor = null) {
    const elements = ensureDoctorModal();
    if (!elements) {
        return;
    }

    resetDoctorModal();
    doctorModalState.mode = mode;

    if (mode === "edit" && doctor) {
        doctorModalState.recordId = doctor.id;
        elements.title.textContent = "Rediģēt ārstu";
        elements.subtitle.textContent = "Maini ārsta informāciju un saglabā izmaiņas.";
        elements.submitButton.textContent = "Saglabāt izmaiņas";
        elements.passwordLabel.textContent = "Jaunā parole";
        elements.passwordHint.textContent = "Atstāj lauku tukšu, ja paroli nevajag mainīt.";
        elements.passwordInput.required = false;

        elements.nameInput.value = doctor.name || "";
        elements.surnameInput.value = doctor.surname || "";
        elements.emailInput.value = doctor.email || "";
        elements.phoneInput.value = doctor.phone || "";
        elements.procedureInput.value = doctor.procedure || "";
    }

    doctorModalState.instance.show();
}

function bindDoctorModalTriggers() {
    const addDoctorBtn = document.getElementById("addDoctorBtn");
    if (addDoctorBtn) {
        addDoctorBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            openDoctorModal("create");
        }, true);
    }
}

function getServiceModalElements() {
    return {
        modal: document.getElementById("serviceModal"),
        form: document.getElementById("serviceModalForm"),
        title: document.getElementById("serviceModalTitle"),
        subtitle: document.getElementById("serviceModalSubtitle"),
        message: document.getElementById("serviceModalMessage"),
        submitButton: document.getElementById("serviceModalSubmitBtn"),
        nameInput: document.getElementById("serviceModalName"),
        descriptionInput: document.getElementById("serviceModalDescription")
    };
}

function resetServiceModal() {
    const elements = getServiceModalElements();
    if (!elements.form) {
        return;
    }

    serviceModalState.mode = "create";
    serviceModalState.recordId = null;
    serviceModalState.submitting = false;
    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearModalMessage(elements.message);

    elements.title.textContent = "Pievienot pakalpojumu";
    elements.subtitle.textContent = "Aizpildi pakalpojuma informāciju un saglabā izmaiņas.";
    elements.submitButton.textContent = "Saglabāt pakalpojumu";
    elements.submitButton.disabled = false;
}

async function handleServiceModalSubmit(event) {
    event.preventDefault();

    const elements = getServiceModalElements();
    if (!elements.form || serviceModalState.submitting) {
        return;
    }

    clearModalMessage(elements.message);
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const payload = {
        serviceName: elements.nameInput.value.trim(),
        description: elements.descriptionInput.value.trim()
    };

    serviceModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        if (serviceModalState.mode === "edit" && serviceModalState.recordId) {
            await apiRequest(`/api/admin/services/${serviceModalState.recordId}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
        } else {
            await apiRequest("/api/admin/services", {
                method: "POST",
                body: JSON.stringify(payload)
            });
        }

        serviceModalState.instance.hide();
        await renderServices();
        if (document.getElementById("priceList")) {
            await renderPrices();
        }
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showModalMessage(elements.message, error.message);
    } finally {
        serviceModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function ensureServiceModal() {
    const elements = getServiceModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!serviceModalState.instance) {
        serviceModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handleServiceModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetServiceModal);
    }

    return elements;
}

function openServiceModal(mode, service = null) {
    const elements = ensureServiceModal();
    if (!elements) {
        return;
    }

    resetServiceModal();
    serviceModalState.mode = mode;

    if (mode === "edit" && service) {
        serviceModalState.recordId = service.id;
        elements.title.textContent = "Rediģēt pakalpojumu";
        elements.subtitle.textContent = "Maini pakalpojuma nosaukumu vai aprakstu un saglabā izmaiņas.";
        elements.submitButton.textContent = "Saglabāt izmaiņas";

        elements.nameInput.value = service.service_name || "";
        elements.descriptionInput.value = service.description || "";
    }

    serviceModalState.instance.show();
}

function bindServiceModalTriggers() {
    const addServiceBtn = document.getElementById("addServiceBtn");
    if (addServiceBtn) {
        addServiceBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            openServiceModal("create");
        }, true);
    }
}

function getPriceModalElements() {
    return {
        modal: document.getElementById("priceModal"),
        form: document.getElementById("priceModalForm"),
        title: document.getElementById("priceModalTitle"),
        subtitle: document.getElementById("priceModalSubtitle"),
        message: document.getElementById("priceModalMessage"),
        submitButton: document.getElementById("priceModalSubmitBtn"),
        titleInput: document.getElementById("priceModalTitleInput"),
        serviceInput: document.getElementById("priceModalService"),
        priceInput: document.getElementById("priceModalValue")
    };
}

async function populatePriceServices(selectedService = "") {
    const { serviceInput } = getPriceModalElements();
    if (!serviceInput) {
        return;
    }

    const services = await getServices();
    const serviceNames = [...new Set(
        services
            .map((service) => service.service_name)
            .filter(Boolean)
    )].sort((left, right) => compareText(left, right));

    serviceInput.innerHTML = '<option value="">Izvēlies pakalpojumu</option>';

    if (selectedService && !serviceNames.includes(selectedService)) {
        const fallbackOption = document.createElement("option");
        fallbackOption.value = selectedService;
        fallbackOption.textContent = `${selectedService} (esošā vērtība)`;
        serviceInput.appendChild(fallbackOption);
    }

    serviceNames.forEach((serviceName) => {
        const option = document.createElement("option");
        option.value = serviceName;
        option.textContent = serviceName;
        serviceInput.appendChild(option);
    });

    serviceInput.value = selectedService || "";
}

function resetPriceModal() {
    const elements = getPriceModalElements();
    if (!elements.form) {
        return;
    }

    priceModalState.mode = "create";
    priceModalState.recordId = null;
    priceModalState.submitting = false;
    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearModalMessage(elements.message);

    elements.title.textContent = "Pievienot cenu";
    elements.subtitle.textContent = "Aizpildi cenu ieraksta informāciju un saglabā izmaiņas.";
    elements.submitButton.textContent = "Saglabāt cenu";
    elements.submitButton.disabled = false;
    elements.serviceInput.innerHTML = '<option value="">Izvēlies pakalpojumu</option>';
}

async function handlePriceModalSubmit(event) {
    event.preventDefault();

    const elements = getPriceModalElements();
    if (!elements.form || priceModalState.submitting) {
        return;
    }

    clearModalMessage(elements.message);
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const payload = {
        title: elements.titleInput.value.trim(),
        service: elements.serviceInput.value.trim(),
        price: elements.priceInput.value.trim()
    };

    priceModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        if (priceModalState.mode === "edit" && priceModalState.recordId) {
            await apiRequest(`/api/admin/prices/${priceModalState.recordId}`, {
                method: "PUT",
                body: JSON.stringify(payload)
            });
        } else {
            await apiRequest("/api/admin/prices", {
                method: "POST",
                body: JSON.stringify(payload)
            });
        }

        priceModalState.instance.hide();
        await renderPrices();
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showModalMessage(elements.message, error.message);
    } finally {
        priceModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function ensurePriceModal() {
    const elements = getPriceModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!priceModalState.instance) {
        priceModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handlePriceModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetPriceModal);
    }

    return elements;
}

async function openPriceModal(mode, price = null) {
    const elements = ensurePriceModal();
    if (!elements) {
        return;
    }

    resetPriceModal();
    priceModalState.mode = mode;

    if (mode === "edit" && price) {
        priceModalState.recordId = price.id;
        elements.title.textContent = "Rediģēt cenu";
        elements.subtitle.textContent = "Maini cenu ieraksta datus un saglabā izmaiņas.";
        elements.submitButton.textContent = "Saglabāt izmaiņas";
        elements.titleInput.value = price.title || "";
        elements.priceInput.value = price.price ?? "";
        await populatePriceServices(price.service_name || "");
    } else {
        await populatePriceServices("");
    }

    priceModalState.instance.show();
}

function bindPriceModalTriggers() {
    const addPriceBtn = document.getElementById("addPriceBtn");
    if (addPriceBtn) {
        addPriceBtn.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            openPriceModal("create").catch(handleAdminError);
        }, true);
    }
}

function getAppointmentModalElements() {
    return {
        modal: document.getElementById("appointmentModal"),
        form: document.getElementById("appointmentModalForm"),
        message: document.getElementById("appointmentModalMessage"),
        submitButton: document.getElementById("appointmentModalSubmitBtn"),
        nameInput: document.getElementById("appointmentModalName"),
        surnameInput: document.getElementById("appointmentModalSurname"),
        phoneInput: document.getElementById("appointmentModalPhone"),
        emailInput: document.getElementById("appointmentModalEmail"),
        procedureInput: document.getElementById("appointmentModalProcedure"),
        doctorInput: document.getElementById("appointmentModalDoctor"),
        doctorHint: document.getElementById("appointmentModalDoctorHint"),
        dateInput: document.getElementById("appointmentModalDate"),
        timeInput: document.getElementById("appointmentModalTime"),
        addressInput: document.getElementById("appointmentModalAddress"),
        commentInput: document.getElementById("appointmentModalComment")
    };
}

function populateAppointmentDoctors(procedure, selectedDoctorId = "") {
    const elements = getAppointmentModalElements();
    if (!elements.doctorInput) {
        return;
    }

    const doctors = appointmentModalState.doctors
        .filter((doctor) => doctor.procedure === procedure)
        .sort((left, right) => compareText(formatFullName(left), formatFullName(right)));

    elements.doctorInput.innerHTML = '<option value="">Bez piešķirta ārsta</option>';

    doctors.forEach((doctor) => {
        const option = document.createElement("option");
        option.value = String(doctor.id);
        option.textContent = formatFullName(doctor);
        elements.doctorInput.appendChild(option);
    });

    elements.doctorInput.value = selectedDoctorId ? String(selectedDoctorId) : "";
    elements.doctorHint.textContent = doctors.length
        ? "Vari piešķirt konkrētu ārstu vai atstāt šo lauku tukšu."
        : "Šai procedūrai pašlaik nav piesaistīta neviena ārsta konta.";
}

function resetAppointmentModal() {
    const elements = getAppointmentModalElements();
    if (!elements.form) {
        return;
    }

    appointmentModalState.recordId = null;
    appointmentModalState.submitting = false;
    appointmentModalState.doctors = [];
    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearModalMessage(elements.message);
    elements.submitButton.disabled = false;
    elements.doctorInput.innerHTML = '<option value="">Bez piešķirta ārsta</option>';
    elements.doctorHint.textContent = "Ja ārstam nav piesaistes šai procedūrai, atstāj lauku tukšu.";
}

async function handleAppointmentModalSubmit(event) {
    event.preventDefault();

    const elements = getAppointmentModalElements();
    if (!elements.form || appointmentModalState.submitting || !appointmentModalState.recordId) {
        return;
    }

    clearModalMessage(elements.message);
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const payload = {
        name: elements.nameInput.value.trim(),
        surname: elements.surnameInput.value.trim(),
        phone: elements.phoneInput.value.trim(),
        email: elements.emailInput.value.trim().toLowerCase(),
        procedura: elements.procedureInput.value,
        doctor_id: elements.doctorInput.value ? Number(elements.doctorInput.value) : null,
        datums: elements.dateInput.value,
        laiks: elements.timeInput.value,
        adrese: elements.addressInput.value.trim(),
        comment: elements.commentInput.value.trim()
    };

    appointmentModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        await apiRequest(`/api/admin/appointments/${appointmentModalState.recordId}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });

        appointmentModalState.instance.hide();
        await renderAppointments();
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showModalMessage(elements.message, error.message);
    } finally {
        appointmentModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function ensureAppointmentModal() {
    const elements = getAppointmentModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!appointmentModalState.instance) {
        appointmentModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handleAppointmentModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetAppointmentModal);
        elements.procedureInput.addEventListener("change", () => {
            populateAppointmentDoctors(elements.procedureInput.value, "");
        });
    }

    return elements;
}

async function openAppointmentModal(appointment) {
    const elements = ensureAppointmentModal();
    if (!elements) {
        return;
    }

    resetAppointmentModal();
    appointmentModalState.recordId = appointment.id;
    appointmentModalState.doctors = await getDoctors();

    elements.nameInput.value = appointment.name || "";
    elements.surnameInput.value = appointment.surname || "";
    elements.phoneInput.value = appointment.phone || "";
    elements.emailInput.value = appointment.email || "";
    elements.procedureInput.value = appointment.procedura || "";
    elements.dateInput.value = appointment.datums || "";
    elements.timeInput.value = appointment.laiks || "";
    elements.addressInput.value = appointment.adrese || "";
    elements.commentInput.value = appointment.comment || "";
    populateAppointmentDoctors(appointment.procedura || "", appointment.doctor_id || "");

    appointmentModalState.instance.show();
}

function getAboutModalElements() {
    return {
        modal: document.getElementById("aboutModal"),
        form: document.getElementById("aboutModalForm"),
        subtitle: document.getElementById("aboutModalSubtitle"),
        message: document.getElementById("aboutModalMessage"),
        submitButton: document.getElementById("aboutModalSubmitBtn"),
        typeInput: document.getElementById("aboutModalType"),
        formatInput: document.getElementById("aboutModalFormat"),
        titleInput: document.getElementById("aboutModalEntryTitle"),
        contentFields: document.getElementById("aboutModalContentFields"),
        contentLabel: document.getElementById("aboutModalContentLabel"),
        contentInput: document.getElementById("aboutModalContent"),
        contentHint: document.getElementById("aboutModalContentHint"),
        imagePathInput: document.getElementById("aboutModalImagePath"),
        imageAltInput: document.getElementById("aboutModalImageAlt"),
        sortOrderInput: document.getElementById("aboutModalSortOrder")
    };
}

function resetAboutModal() {
    const elements = getAboutModalElements();
    if (!elements.form) {
        return;
    }

    aboutModalState.recordId = null;
    aboutModalState.submitting = false;
    elements.form.reset();
    elements.form.classList.remove("was-validated");
    clearModalMessage(elements.message);
    elements.submitButton.disabled = false;
    elements.contentFields.classList.remove("d-none");
    elements.contentInput.required = false;
    elements.contentHint.textContent = "";
    elements.contentLabel.textContent = "Saturs";
}

function ensureAboutModal() {
    const elements = getAboutModalElements();
    if (!elements.modal || !elements.form) {
        return null;
    }

    if (!aboutModalState.instance) {
        aboutModalState.instance = new bootstrap.Modal(elements.modal);
        elements.form.addEventListener("submit", handleAboutModalSubmit);
        elements.modal.addEventListener("hidden.bs.modal", resetAboutModal);
    }

    return elements;
}

function fillAboutModal(entry) {
    const elements = getAboutModalElements();
    if (!elements.form) {
        return;
    }

    const isPageTitle = entry.entry_type === "page_title";

    elements.typeInput.value = formatAboutEntryType(entry.entry_type);
    elements.formatInput.value = entry.content_format === "list"
        ? "Saraksts"
        : entry.content_format === "paragraph"
            ? "Paragrāfi"
            : "Teksts";
    elements.titleInput.value = entry.title || "";

    if (isPageTitle) {
        elements.subtitle.textContent = "Šis ieraksts kontrolē publiskās “Par mums” lapas virsrakstu.";
        elements.contentFields.classList.add("d-none");
        elements.contentInput.required = false;
        elements.contentInput.value = "";
        elements.imagePathInput.value = "";
        elements.imageAltInput.value = "";
        elements.sortOrderInput.value = "0";
        return;
    }

    elements.subtitle.textContent = "Maini “Par mums” saturu un saglabā izmaiņas.";
    elements.contentFields.classList.remove("d-none");
    elements.contentInput.required = true;
    elements.contentInput.value = entry.content || "";
    elements.imagePathInput.value = entry.image_path || "";
    elements.imageAltInput.value = entry.image_alt || "";
    elements.sortOrderInput.value = String(entry.sort_order ?? 0);

    if (entry.content_format === "list") {
        elements.contentLabel.textContent = "Saturs (katru punktu jaunā rindā)";
        elements.contentHint.textContent = "Katru saraksta punktu raksti atsevišķā rindā.";
    } else if (entry.content_format === "paragraph") {
        elements.contentLabel.textContent = "Saturs";
        elements.contentHint.textContent = "Vari rakstīt vairākus teikumus vai rindkopas.";
    } else {
        elements.contentLabel.textContent = "Teksts";
        elements.contentHint.textContent = "Šis lauks tiks attēlots kā vienkāršs teksts.";
    }
}

async function handleAboutModalSubmit(event) {
    event.preventDefault();

    const elements = getAboutModalElements();
    if (!elements.form || aboutModalState.submitting || !aboutModalState.recordId) {
        return;
    }

    clearModalMessage(elements.message);
    elements.form.classList.add("was-validated");

    if (!elements.form.checkValidity()) {
        return;
    }

    const entry = aboutModalState.entry || {};
    const isPageTitle = entry.entry_type === "page_title";

    const payload = {
        title: elements.titleInput.value.trim(),
        content: isPageTitle ? "" : elements.contentInput.value.trim(),
        content_format: entry.content_format || "paragraph",
        image_path: isPageTitle ? "" : elements.imagePathInput.value.trim(),
        image_alt: isPageTitle ? "" : elements.imageAltInput.value.trim(),
        sort_order: isPageTitle ? 0 : elements.sortOrderInput.value.trim()
    };

    aboutModalState.submitting = true;
    elements.submitButton.disabled = true;

    try {
        await apiRequest(`/api/admin/about-content/${aboutModalState.recordId}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });

        aboutModalState.instance.hide();
        await renderAboutContent();
    } catch (error) {
        if (error.message === "ADMIN_AUTH_REQUIRED") {
            handleAdminError(error);
            return;
        }

        showModalMessage(elements.message, error.message);
    } finally {
        aboutModalState.submitting = false;
        elements.submitButton.disabled = false;
    }
}

function openAboutModal(entry) {
    const elements = ensureAboutModal();
    if (!elements) {
        return;
    }

    resetAboutModal();
    aboutModalState.recordId = entry.id;
    aboutModalState.entry = entry;
    fillAboutModal(entry);
    aboutModalState.instance.show();
}

function handleAdminError(error) {
    if (error.message === "ADMIN_AUTH_REQUIRED") {
        window.location.href = "admin-login.html";
        return;
    }

    alert(error.message);
}

function promptRequired(label, currentValue = "") {
    while (true) {
        const value = prompt(label, currentValue);
        if (value === null) {
            return null;
        }

        const trimmed = value.trim();
        if (trimmed) {
            return trimmed;
        }

        alert("Šis lauks ir obligāts.");
    }
}

function promptOptional(label, currentValue = "") {
    const value = prompt(label, currentValue);
    if (value === null) {
        return null;
    }

    return value.trim();
}

function promptProcedure(currentValue = "") {
    const defaultValue = currentValue ? formatProcedure(currentValue) : "";

    while (true) {
        const value = prompt(
            "Procedūra (Datortomogrāfija, Ģimenes ārsts, Vakcinācija):",
            defaultValue
        );

        if (value === null) {
            return null;
        }

        const parsedValue = parseProcedureValue(value);
        if (parsedValue) {
            return parsedValue;
        }

        alert("Lūdzu ievadi vienu no procedūrām: Datortomogrāfija, Ģimenes ārsts vai Vakcinācija.");
    }
}

async function getUsers() {
    return apiRequest("/api/admin/users");
}

async function getDoctors() {
    return apiRequest("/api/admin/doctors");
}

async function getServices() {
    return apiRequest("/api/admin/services");
}

async function getPrices() {
    return apiRequest("/api/admin/prices");
}

async function getAppointments() {
    return apiRequest("/api/admin/appointments");
}

async function getAboutContent() {
    return apiRequest("/api/admin/about-content");
}

async function getContactMessages() {
    return apiRequest("/api/admin/contact-messages");
}

const userModalState = {
    instance: null,
    mode: "create",
    userId: null,
    submitting: false
};

const doctorModalState = createModalState();
const serviceModalState = createModalState();
const priceModalState = createModalState();
const appointmentModalState = createModalState();
const aboutModalState = createModalState();

function formatAboutEntryType(value) {
    return value === "page_title" ? "Lapas virsraksts" : "Sadaļa";
}

function formatAboutContentPreview(value) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) {
        return "-";
    }

    return text.length > 120 ? `${text.slice(0, 117)}...` : text;
}

function formatContactRole(value) {
    if (value === "user") {
        return "Lietotājs";
    }

    if (value === "doctor") {
        return "Ārsts";
    }

    return "Viesis";
}

async function renderUsers() {
    const userList = document.getElementById("userList");
    if (!userList) {
        return;
    }

    const users = sortItems(await getUsers(), {
        mode: getSelectedSortValue("userSort", "oldest"),
        getTextValue: (item) => formatFullName(item),
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.password_updated_at || item.updated_at || item.created_at
    });
    if (!users.length) {
        userList.innerHTML = '<tr><td colspan="7">Nav reģistrētu lietotāju.</td></tr>';
        return;
    }

    userList.innerHTML = users.map((user) => `
        <tr>
            <td>${user.id}</td>
            <td>${escapeHtml(formatFullName(user))}</td>
            <td>${escapeHtml(user.email || "-")}</td>
            <td>${escapeHtml(user.phone || "-")}</td>
            <td>${escapeHtml(formatDate(user.created_at))}</td>
            <td>${escapeHtml(formatDate(user.password_updated_at))}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editUser(${user.id})">Rediģēt</button>
                <button class="btn btn-danger btn-sm" onclick="deleteUser(${user.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

async function renderDoctors() {
    const doctorList = document.getElementById("doctorList");
    if (!doctorList) {
        return;
    }

    const doctors = sortItems(await getDoctors(), {
        mode: getSelectedSortValue("doctorSort", "oldest"),
        getTextValue: (item) => formatFullName(item),
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.password_updated_at || item.updated_at || item.created_at
    });
    if (!doctors.length) {
        doctorList.innerHTML = '<tr><td colspan="8">Nav reģistrētu ārstu.</td></tr>';
        return;
    }

    doctorList.innerHTML = doctors.map((doctor) => `
        <tr>
            <td>${doctor.id}</td>
            <td>${escapeHtml(formatFullName(doctor))}</td>
            <td>${escapeHtml(doctor.email || "-")}</td>
            <td>${escapeHtml(doctor.phone || "-")}</td>
            <td>${escapeHtml(formatProcedure(doctor.procedure))}</td>
            <td>${escapeHtml(formatDate(doctor.created_at))}</td>
            <td>${escapeHtml(formatDate(doctor.password_updated_at))}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editDoctor(${doctor.id})">Rediģēt</button>
                <button class="btn btn-danger btn-sm" onclick="deleteDoctor(${doctor.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

async function renderServices() {
    const serviceList = document.getElementById("serviceList");
    if (!serviceList) {
        return;
    }

    const services = sortItems(await getServices(), {
        mode: getSelectedSortValue("serviceSort", "oldest"),
        getTextValue: (item) => item.service_name,
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.updated_at || item.created_at
    });
    if (!services.length) {
        serviceList.innerHTML = '<tr><td colspan="4">Nav saglabātu pakalpojumu.</td></tr>';
        return;
    }

    serviceList.innerHTML = services.map((service) => `
        <tr>
            <td>${service.id}</td>
            <td>${escapeHtml(service.service_name)}</td>
            <td>${escapeHtml(service.description)}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editService(${service.id})">Rediģēt</button>
                <button class="btn btn-danger btn-sm" onclick="deleteService(${service.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

async function renderPrices() {
    const priceList = document.getElementById("priceList");
    if (!priceList) {
        return;
    }

    const prices = sortItems(await getPrices(), {
        mode: getSelectedSortValue("priceSort", "oldest"),
        getTextValue: (item) => item.title,
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.updated_at || item.created_at
    });
    if (!prices.length) {
        priceList.innerHTML = '<tr><td colspan="7">Nav saglabātu cenu ierakstu.</td></tr>';
        return;
    }

    priceList.innerHTML = prices.map((price, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(price.title)}</td>
            <td>${escapeHtml(price.service_name)}</td>
            <td>${escapeHtml(Number(price.price).toFixed(2))} EUR</td>
            <td>${escapeHtml(formatDate(price.created_at, false))}</td>
            <td>${escapeHtml(formatDate(price.updated_at))}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editPrice(${price.id})">Rediģēt</button>
                <button class="btn btn-danger btn-sm" onclick="deletePrice(${price.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

async function renderAboutContent() {
    const aboutContentList = document.getElementById("aboutContentList");
    if (!aboutContentList) {
        return;
    }

    const entries = sortItems(await getAboutContent(), {
        mode: getSelectedSortValue("aboutSort", "oldest"),
        getTextValue: (item) => item.title,
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.updated_at || item.created_at
    });
    if (!entries.length) {
        aboutContentList.innerHTML = '<tr><td colspan="7">Nav saglabātu “Par mums” ierakstu.</td></tr>';
        return;
    }

    aboutContentList.innerHTML = entries.map((entry) => `
        <tr>
            <td>${entry.id}</td>
            <td>${escapeHtml(formatAboutEntryType(entry.entry_type))}</td>
            <td>${escapeHtml(entry.title || "-")}</td>
            <td>${escapeHtml(formatAboutContentPreview(entry.content))}</td>
            <td>${escapeHtml(entry.image_path || "-")}</td>
            <td>${escapeHtml(String(entry.sort_order ?? 0))}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editAboutContent(${entry.id})">Rediģēt</button>
            </td>
        </tr>
    `).join("");
}

async function renderContactMessages() {
    const contactMessageList = document.getElementById("contactMessageList");
    if (!contactMessageList) {
        return;
    }

    const messages = sortItems(await getContactMessages(), {
        mode: getSelectedSortValue("messageSort", "newest"),
        getTextValue: (item) => item.name,
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.updated_at || item.created_at
    });
    if (!messages.length) {
        contactMessageList.innerHTML = '<tr><td colspan="7">Nav saņemtu ziņojumu.</td></tr>';
        return;
    }

    contactMessageList.innerHTML = messages.map((message) => `
        <tr>
            <td>${message.id}</td>
            <td>${escapeHtml(formatContactRole(message.sender_role))}</td>
            <td>${escapeHtml(message.name || "-")}</td>
            <td>${escapeHtml(message.email || "-")}</td>
            <td>${escapeHtml(message.message || "-")}</td>
            <td>${escapeHtml(formatDate(message.created_at))}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteContactMessage(${message.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

async function renderAppointments() {
    const appointmentList = document.getElementById("appointmentList");
    if (!appointmentList) {
        return;
    }

    const appointments = sortItems(await getAppointments(), {
        mode: getSelectedSortValue("appointmentSort", "oldest"),
        getTextValue: (item) => formatFullName(item),
        getCreatedAtValue: (item) => item.created_at,
        getUpdatedAtValue: (item) => item.updated_at || item.created_at
    });
    if (!appointments.length) {
        appointmentList.innerHTML = '<tr><td colspan="13">Nav saglabātu pieteikumu.</td></tr>';
        return;
    }

    appointmentList.innerHTML = appointments.map((appointment) => `
        <tr>
            <td>${appointment.id}</td>
            <td>${escapeHtml(appointment.name || "-")}</td>
            <td>${escapeHtml(appointment.surname || "-")}</td>
            <td>${escapeHtml(appointment.phone || "-")}</td>
            <td>${escapeHtml(appointment.email || "-")}</td>
            <td>${escapeHtml(formatProcedure(appointment.procedura))}</td>
            <td>${escapeHtml(appointment.datums || "-")}</td>
            <td>${escapeHtml(appointment.laiks || "-")}</td>
            <td>${escapeHtml(appointment.adrese || "-")}</td>
            <td>${escapeHtml(formatDate(appointment.created_at))}</td>
            <td>${escapeHtml(formatDate(appointment.updated_at))}</td>
            <td>${escapeHtml(appointment.comment || "")}</td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="editAppointment(${appointment.id})">Rediģēt</button>
                <button class="btn btn-danger btn-sm" onclick="deleteAppointment(${appointment.id})">Dzēst</button>
            </td>
        </tr>
    `).join("");
}

window.logout = async function logout() {
    try {
        await apiRequest("/api/admin/logout", { method: "POST" });
    } finally {
        window.location.href = "admin-login.html";
    }
};

function bindAdminLogoutLinks() {
    document.querySelectorAll("[data-admin-logout]").forEach((link) => {
        link.addEventListener("click", async (event) => {
            event.preventDefault();
            await window.logout();
        });
    });
}

function bindSortControls() {
    const renderers = {
        userSort: renderUsers,
        doctorSort: renderDoctors,
        serviceSort: renderServices,
        priceSort: renderPrices,
        aboutSort: renderAboutContent,
        messageSort: renderContactMessages,
        appointmentSort: renderAppointments
    };

    Object.entries(renderers).forEach(([selectId, renderFn]) => {
        const control = document.getElementById(selectId);
        if (!control) {
            return;
        }

        control.addEventListener("change", async () => {
            try {
                await renderFn();
            } catch (error) {
                handleAdminError(error);
            }
        });
    });
}

window.deleteUser = async function deleteUser(userId) {
    if (!confirm("Vai tiešām dzēst šo lietotāju?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/users/${userId}`, { method: "DELETE" });
        await renderUsers();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editUser = async function editUser(userId) {
    try {
        const user = (await getUsers()).find((item) => item.id === userId);
        if (!user) {
            throw new Error("Lietotājs nav atrasts.");
        }

        const name = promptRequired("Lietotāja vārds:", user.name || "");
        if (name === null) {
            return;
        }

        const surname = promptOptional("Lietotāja uzvārds:", user.surname || "");
        if (surname === null) {
            return;
        }

        const email = promptRequired("Lietotāja e-pasts:", user.email || "");
        if (email === null) {
            return;
        }

        const phone = promptOptional("Lietotāja tālrunis:", user.phone || "");
        if (phone === null) {
            return;
        }

        const password = promptOptional("Ja gribi nomainīt paroli, ievadi jaunu. Citādi atstāj tukšu.", "");
        if (password === null) {
            return;
        }

        await apiRequest(`/api/admin/users/${userId}`, {
            method: "PUT",
            body: JSON.stringify({
                name,
                surname,
                email,
                phone,
                password
            })
        });

        await renderUsers();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editUser = async function editUser(userId) {
    try {
        const user = (await getUsers()).find((item) => item.id === userId);
        if (!user) {
            throw new Error("Lietotājs nav atrasts.");
        }

        openUserModal("edit", user);
    } catch (error) {
        handleAdminError(error);
    }
};

window.deleteDoctor = async function deleteDoctor(doctorId) {
    if (!confirm("Vai tiešām dzēst šo ārstu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/doctors/${doctorId}`, { method: "DELETE" });
        await renderDoctors();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editDoctor = async function editDoctor(doctorId) {
    try {
        const doctor = (await getDoctors()).find((item) => item.id === doctorId);
        if (!doctor) {
            throw new Error("Ārsts nav atrasts.");
        }

        const name = promptRequired("Ārsta vārds:", doctor.name || "");
        if (name === null) {
            return;
        }

        const surname = promptOptional("Ārsta uzvārds:", doctor.surname || "");
        if (surname === null) {
            return;
        }

        const email = promptRequired("Ārsta e-pasts:", doctor.email || "");
        if (email === null) {
            return;
        }

        const phone = promptOptional("Ārsta tālrunis:", doctor.phone || "");
        if (phone === null) {
            return;
        }

        const procedure = promptProcedure(doctor.procedure);
        if (procedure === null) {
            return;
        }

        const password = promptOptional("Ja gribi nomainīt paroli, ievadi jaunu. Citādi atstāj tukšu.", "");
        if (password === null) {
            return;
        }

        await apiRequest(`/api/admin/doctors/${doctorId}`, {
            method: "PUT",
            body: JSON.stringify({
                name,
                surname,
                email,
                phone,
                procedure,
                password
            })
        });

        await renderDoctors();
    } catch (error) {
        handleAdminError(error);
    }
};

window.deleteService = async function deleteService(serviceId) {
    if (!confirm("Vai tiešām dzēst šo pakalpojumu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/services/${serviceId}`, { method: "DELETE" });
        await renderServices();
        await renderPrices();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editService = async function editService(serviceId) {
    try {
        const service = (await getServices()).find((item) => item.id === serviceId);
        if (!service) {
            throw new Error("Pakalpojums nav atrasts.");
        }

        const serviceName = promptRequired("Pakalpojuma nosaukums:", service.service_name || "");
        if (serviceName === null) {
            return;
        }

        const description = promptRequired("Pakalpojuma apraksts:", service.description || "");
        if (description === null) {
            return;
        }

        await apiRequest(`/api/admin/services/${serviceId}`, {
            method: "PUT",
            body: JSON.stringify({
                serviceName,
                description
            })
        });

        await renderServices();
        await renderPrices();
    } catch (error) {
        handleAdminError(error);
    }
};

window.deletePrice = async function deletePrice(priceId) {
    if (!confirm("Vai tiešām dzēst šo cenu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/prices/${priceId}`, { method: "DELETE" });
        await renderPrices();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editPrice = async function editPrice(priceId) {
    try {
        const price = (await getPrices()).find((item) => item.id === priceId);
        if (!price) {
            throw new Error("Cena nav atrasta.");
        }

        const title = promptRequired("Cenas ieraksta nosaukums:", price.title || "");
        if (title === null) {
            return;
        }

        const service = promptRequired("Pakalpojuma nosaukums:", price.service_name || "");
        if (service === null) {
            return;
        }

        const newPrice = promptRequired("Cena:", String(price.price ?? ""));
        if (newPrice === null) {
            return;
        }

        await apiRequest(`/api/admin/prices/${priceId}`, {
            method: "PUT",
            body: JSON.stringify({
                title,
                service,
                price: newPrice
            })
        });

        await renderPrices();
    } catch (error) {
        handleAdminError(error);
    }
};

window.deleteAppointment = async function deleteAppointment(appointmentId) {
    if (!confirm("Vai tiešām dzēst šo pieteikumu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/appointments/${appointmentId}`, { method: "DELETE" });
        await renderAppointments();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editAppointment = async function editAppointment(appointmentId) {
    try {
        const appointment = (await getAppointments()).find((item) => item.id === appointmentId);
        if (!appointment) {
            throw new Error("Pieteikums nav atrasts.");
        }

        const name = promptRequired("Vārds:", appointment.name || "");
        if (name === null) {
            return;
        }

        const surname = promptRequired("Uzvārds:", appointment.surname || "");
        if (surname === null) {
            return;
        }

        const phone = promptRequired("Tālrunis:", appointment.phone || "");
        if (phone === null) {
            return;
        }

        const email = promptRequired("E-pasts:", appointment.email || "");
        if (email === null) {
            return;
        }

        const procedura = promptProcedure(appointment.procedura);
        if (procedura === null) {
            return;
        }

        const datums = promptRequired("Vēlamais datums (YYYY-MM-DD):", appointment.datums || "");
        if (datums === null) {
            return;
        }

        const laiks = promptRequired("Vēlamais laiks (HH:MM):", appointment.laiks || "");
        if (laiks === null) {
            return;
        }

        const adrese = promptRequired("Adrese vai filiāle:", appointment.adrese || "");
        if (adrese === null) {
            return;
        }

        const comment = promptOptional("Komentārs:", appointment.comment || "");
        if (comment === null) {
            return;
        }

        await apiRequest(`/api/admin/appointments/${appointmentId}`, {
            method: "PUT",
            body: JSON.stringify({
                name,
                surname,
                phone,
                email,
                procedura,
                datums,
                laiks,
                adrese,
                comment
            })
        });

        await renderAppointments();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editAboutContent = async function editAboutContent(entryId) {
    try {
        const entry = (await getAboutContent()).find((item) => item.id === entryId);
        if (!entry) {
            throw new Error("“Par mums” ieraksts nav atrasts.");
        }

        const title = promptRequired("Virsraksts:", entry.title || "");
        if (title === null) {
            return;
        }

        let content = entry.content || "";
        let imagePath = entry.image_path || "";
        let imageAlt = entry.image_alt || "";
        let sortOrder = entry.sort_order ?? 0;

        if (entry.entry_type !== "page_title") {
            const contentLabel = entry.content_format === "list"
                ? "Saturs (katru saraksta punktu raksti jaunā rindā):"
                : "Saturs:";
            const contentValue = promptRequired(contentLabel, entry.content || "");
            if (contentValue === null) {
                return;
            }
            content = contentValue;

            const nextImagePath = promptRequired("Attēla ceļš:", entry.image_path || "");
            if (nextImagePath === null) {
                return;
            }
            imagePath = nextImagePath;

            const nextImageAlt = promptRequired("Attēla ALT teksts:", entry.image_alt || entry.title || "");
            if (nextImageAlt === null) {
                return;
            }
            imageAlt = nextImageAlt;

            const nextSortOrder = promptRequired("Sadaļas kārtas numurs:", String(entry.sort_order ?? 0));
            if (nextSortOrder === null) {
                return;
            }
            sortOrder = nextSortOrder;
        }

        await apiRequest(`/api/admin/about-content/${entryId}`, {
            method: "PUT",
            body: JSON.stringify({
                title,
                content,
                content_format: entry.content_format || "paragraph",
                image_path: imagePath,
                image_alt: imageAlt,
                sort_order: sortOrder
            })
        });

        await renderAboutContent();
    } catch (error) {
        handleAdminError(error);
    }
};

window.editDoctor = async function editDoctor(doctorId) {
    try {
        const doctor = (await getDoctors()).find((item) => item.id === doctorId);
        if (!doctor) {
            throw new Error("Ārsts nav atrasts.");
        }

        openDoctorModal("edit", doctor);
    } catch (error) {
        handleAdminError(error);
    }
};

window.editService = async function editService(serviceId) {
    try {
        const service = (await getServices()).find((item) => item.id === serviceId);
        if (!service) {
            throw new Error("Pakalpojums nav atrasts.");
        }

        openServiceModal("edit", service);
    } catch (error) {
        handleAdminError(error);
    }
};

window.editPrice = async function editPrice(priceId) {
    try {
        const price = (await getPrices()).find((item) => item.id === priceId);
        if (!price) {
            throw new Error("Cena nav atrasta.");
        }

        await openPriceModal("edit", price);
    } catch (error) {
        handleAdminError(error);
    }
};

window.editAppointment = async function editAppointment(appointmentId) {
    try {
        const appointment = (await getAppointments()).find((item) => item.id === appointmentId);
        if (!appointment) {
            throw new Error("Pieteikums nav atrasts.");
        }

        await openAppointmentModal(appointment);
    } catch (error) {
        handleAdminError(error);
    }
};

window.editAboutContent = async function editAboutContent(entryId) {
    try {
        const entry = (await getAboutContent()).find((item) => item.id === entryId);
        if (!entry) {
            throw new Error("“Par mums” ieraksts nav atrasts.");
        }

        openAboutModal(entry);
    } catch (error) {
        handleAdminError(error);
    }
};

window.deleteContactMessage = async function deleteContactMessage(messageId) {
    if (!confirm("Vai tiešām dzēst šo ziņojumu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/contact-messages/${messageId}`, { method: "DELETE" });
        await renderContactMessages();
    } catch (error) {
        handleAdminError(error);
    }
};

document.addEventListener("DOMContentLoaded", async () => {
    ensureUserModal();
    ensureDoctorModal();
    ensureServiceModal();
    ensurePriceModal();
    ensureAppointmentModal();
    ensureAboutModal();
    bindUserModalTriggers();
    bindDoctorModalTriggers();
    bindServiceModalTriggers();
    bindPriceModalTriggers();
    bindAdminLogoutLinks();
    bindSortControls();

    try {
        const renderTasks = [];

        if (document.getElementById("userList")) {
            renderTasks.push(renderUsers());
        }
        if (document.getElementById("doctorList")) {
            renderTasks.push(renderDoctors());
        }
        if (document.getElementById("serviceList")) {
            renderTasks.push(renderServices());
        }
        if (document.getElementById("priceList")) {
            renderTasks.push(renderPrices());
        }
        if (document.getElementById("aboutContentList")) {
            renderTasks.push(renderAboutContent());
        }
        if (document.getElementById("contactMessageList")) {
            renderTasks.push(renderContactMessages());
        }
        if (document.getElementById("appointmentList")) {
            renderTasks.push(renderAppointments());
        }

        await Promise.all(renderTasks);
    } catch (error) {
        handleAdminError(error);
    }

    const addUserBtn = document.getElementById("addUserBtn");
    if (addUserBtn) {
        addUserBtn.addEventListener("click", async () => {
            const name = promptRequired("Ievadi lietotāja vārdu:");
            if (name === null) {
                return;
            }

            const surname = promptOptional("Ievadi lietotāja uzvārdu:", "");
            if (surname === null) {
                return;
            }

            const email = promptRequired("Ievadi lietotāja e-pastu:");
            if (email === null) {
                return;
            }

            const phone = promptOptional("Ievadi lietotāja tālruni:", "");
            if (phone === null) {
                return;
            }

            const password = promptRequired("Ievadi lietotāja sākuma paroli:");
            if (password === null) {
                return;
            }

            try {
                await apiRequest("/api/admin/users", {
                    method: "POST",
                    body: JSON.stringify({
                        name,
                        surname,
                        email,
                        phone,
                        password
                    })
                });
                await renderUsers();
            } catch (error) {
                handleAdminError(error);
            }
        });
    }

    const addDoctorBtn = document.getElementById("addDoctorBtn");
    if (addDoctorBtn) {
        addDoctorBtn.addEventListener("click", async () => {
            const name = promptRequired("Ievadi ārsta vārdu:");
            if (name === null) {
                return;
            }

            const surname = promptOptional("Ievadi ārsta uzvārdu:", "");
            if (surname === null) {
                return;
            }

            const email = promptRequired("Ievadi ārsta e-pastu:");
            if (email === null) {
                return;
            }

            const phone = promptOptional("Ievadi ārsta tālruni:", "");
            if (phone === null) {
                return;
            }

            const procedure = promptProcedure();
            if (procedure === null) {
                return;
            }

            const password = promptRequired("Ievadi ārsta sākuma paroli:");
            if (password === null) {
                return;
            }

            try {
                await apiRequest("/api/admin/doctors", {
                    method: "POST",
                    body: JSON.stringify({
                        name,
                        surname,
                        email,
                        phone,
                        procedure,
                        password
                    })
                });
                await renderDoctors();
            } catch (error) {
                handleAdminError(error);
            }
        });
    }

    const addServiceBtn = document.getElementById("addServiceBtn");
    if (addServiceBtn) {
        addServiceBtn.addEventListener("click", async () => {
            const serviceName = promptRequired("Ievadi pakalpojuma nosaukumu:");
            if (serviceName === null) {
                return;
            }

            const description = promptRequired("Ievadi pakalpojuma aprakstu:");
            if (description === null) {
                return;
            }

            try {
                await apiRequest("/api/admin/services", {
                    method: "POST",
                    body: JSON.stringify({
                        serviceName,
                        description
                    })
                });
                await renderServices();
            } catch (error) {
                handleAdminError(error);
            }
        });
    }

    const addPriceBtn = document.getElementById("addPriceBtn");
    if (addPriceBtn) {
        addPriceBtn.addEventListener("click", async () => {
            const title = promptRequired("Ievadi cenas ieraksta nosaukumu:");
            if (title === null) {
                return;
            }

            const service = promptRequired("Ievadi pakalpojuma nosaukumu:");
            if (service === null) {
                return;
            }

            const price = promptRequired("Ievadi cenu:");
            if (price === null) {
                return;
            }

            try {
                await apiRequest("/api/admin/prices", {
                    method: "POST",
                    body: JSON.stringify({
                        title,
                        service,
                        price
                    })
                });
                await renderPrices();
            } catch (error) {
                handleAdminError(error);
            }
        });
    }
});
