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

async function renderUsers() {
    const userList = document.getElementById("userList");
    if (!userList) {
        return;
    }

    const users = await getUsers();
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

    const doctors = await getDoctors();
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

    const services = await getServices();
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

    const prices = await getPrices();
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

async function renderAppointments() {
    const appointmentList = document.getElementById("appointmentList");
    if (!appointmentList) {
        return;
    }

    const appointments = await getAppointments();
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

document.addEventListener("DOMContentLoaded", async () => {
    try {
        await Promise.all([
            renderUsers(),
            renderDoctors(),
            renderServices(),
            renderPrices(),
            renderAppointments()
        ]);
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
});
