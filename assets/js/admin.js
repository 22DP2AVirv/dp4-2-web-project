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
        throw new Error(message || "Neizdevas izpildit pieprasijumu.");
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

        alert("Sis lauks ir obligats.");
    }
}

function promptOptional(label, currentValue = "") {
    const value = prompt(label, currentValue);
    if (value === null) {
        return null;
    }

    return value.trim();
}

async function getUsers() {
    return apiRequest("/api/admin/users");
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
        userList.innerHTML = '<tr><td colspan="7">Nav registretu lietotaju.</td></tr>';
        return;
    }

    userList.innerHTML = users.map((user) => {
        const fullName = [user.name, user.surname].filter(Boolean).join(" ");

        return `
            <tr>
                <td>${user.id}</td>
                <td>${fullName || "-"}</td>
                <td>${user.email || "-"}</td>
                <td>${user.phone || "-"}</td>
                <td>${formatDate(user.created_at)}</td>
                <td>${formatDate(user.password_updated_at)}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editUser(${user.id})">Rediģēt</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteUser(${user.id})">Dzēst</button>
                </td>
            </tr>
        `;
    }).join("");
}

async function renderServices() {
    const serviceList = document.getElementById("serviceList");
    if (!serviceList) {
        return;
    }

    const services = await getServices();
    if (!services.length) {
        serviceList.innerHTML = '<tr><td colspan="4">Nav saglabatu pakalpojumu.</td></tr>';
        return;
    }

    serviceList.innerHTML = services.map((service) => {
        return `
            <tr>
                <td>${service.id}</td>
                <td>${service.service_name}</td>
                <td>${service.description}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editService(${service.id})">Rediģēt</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteService(${service.id})">Dzēst</button>
                </td>
            </tr>
        `;
    }).join("");
}

async function renderPrices() {
    const priceList = document.getElementById("priceList");
    if (!priceList) {
        return;
    }

    const prices = await getPrices();
    if (!prices.length) {
        priceList.innerHTML = '<tr><td colspan="7">Nav saglabatu cenu ierakstu.</td></tr>';
        return;
    }

    priceList.innerHTML = prices.map((price, index) => {
        return `
            <tr>
                <td>${index + 1}</td>
                <td>${price.title}</td>
                <td>${price.service_name}</td>
                <td>${Number(price.price).toFixed(2)} EUR</td>
                <td>${formatDate(price.created_at, false)}</td>
                <td>${formatDate(price.updated_at)}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editPrice(${price.id})">Rediģēt</button>
                    <button class="btn btn-danger btn-sm" onclick="deletePrice(${price.id})">Dzēst</button>
                </td>
            </tr>
        `;
    }).join("");
}

async function renderAppointments() {
    const appointmentList = document.getElementById("appointmentList");
    if (!appointmentList) {
        return;
    }

    const appointments = await getAppointments();
    if (!appointments.length) {
        appointmentList.innerHTML = '<tr><td colspan="13">Nav saglabatu pieteikumu.</td></tr>';
        return;
    }

    appointmentList.innerHTML = appointments.map((appointment) => {
        return `
            <tr>
                <td>${appointment.id}</td>
                <td>${appointment.name || "-"}</td>
                <td>${appointment.surname || "-"}</td>
                <td>${appointment.phone || "-"}</td>
                <td>${appointment.email || "-"}</td>
                <td>${appointment.procedura || "-"}</td>
                <td>${appointment.datums || "-"}</td>
                <td>${appointment.laiks || "-"}</td>
                <td>${appointment.adrese || "-"}</td>
                <td>${formatDate(appointment.created_at)}</td>
                <td>${formatDate(appointment.updated_at)}</td>
                <td>${appointment.comment || ""}</td>
                <td>
                    <button class="btn btn-secondary btn-sm" onclick="editAppointment(${appointment.id})">Rediģēt</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteAppointment(${appointment.id})">Dzēst</button>
                </td>
            </tr>
        `;
    }).join("");
}

window.logout = async function logout() {
    try {
        await apiRequest("/api/admin/logout", { method: "POST" });
    } finally {
        window.location.href = "admin-login.html";
    }
};

window.deleteUser = async function deleteUser(userId) {
    if (!confirm("Vai tiesam dzest so lietotaju?")) {
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
            throw new Error("Lietotajs nav atrasts.");
        }

        const name = promptRequired("Lietotaja vards:", user.name || "");
        if (name === null) {
            return;
        }

        const surname = promptOptional("Lietotaja uzvards:", user.surname || "");
        if (surname === null) {
            return;
        }

        const email = promptRequired("Lietotaja e-pasts:", user.email || "");
        if (email === null) {
            return;
        }

        const phone = promptOptional("Lietotaja talrunis:", user.phone || "");
        if (phone === null) {
            return;
        }

        const password = promptOptional("Ja gribi nomainit paroli, ievadi jaunu. Citadi atstaj tuksu.", "");
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

window.deleteService = async function deleteService(serviceId) {
    if (!confirm("Vai tiesam dzest so pakalpojumu?")) {
        return;
    }

    try {
        await apiRequest(`/api/admin/services/${serviceId}`, { method: "DELETE" });
        await renderServices();
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
    } catch (error) {
        handleAdminError(error);
    }
};

window.deletePrice = async function deletePrice(priceId) {
    if (!confirm("Vai tiesam dzest so cenu?")) {
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
    if (!confirm("Vai tiesam dzest so pieteikumu?")) {
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

        const name = promptRequired("Vards:", appointment.name || "");
        if (name === null) {
            return;
        }

        const surname = promptRequired("Uzvards:", appointment.surname || "");
        if (surname === null) {
            return;
        }

        const phone = promptRequired("Talrunis:", appointment.phone || "");
        if (phone === null) {
            return;
        }

        const email = promptRequired("Epasts:", appointment.email || "");
        if (email === null) {
            return;
        }

        const procedura = promptRequired("Procedura:", appointment.procedura || "");
        if (procedura === null) {
            return;
        }

        const datums = promptRequired("Velamais datums (YYYY-MM-DD):", appointment.datums || "");
        if (datums === null) {
            return;
        }

        const laiks = promptRequired("Velamais laiks (HH:MM):", appointment.laiks || "");
        if (laiks === null) {
            return;
        }

        const adrese = promptRequired("Adrese vai filiale:", appointment.adrese || "");
        if (adrese === null) {
            return;
        }

        const comment = promptOptional("Komentars:", appointment.comment || "");
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
            const name = promptRequired("Ievadi lietotaja vardu:");
            if (name === null) {
                return;
            }

            const surname = promptOptional("Ievadi lietotaja uzvardu:", "");
            if (surname === null) {
                return;
            }

            const email = promptRequired("Ievadi lietotaja e-pastu:");
            if (email === null) {
                return;
            }

            const phone = promptOptional("Ievadi lietotaja talruni:", "");
            if (phone === null) {
                return;
            }

            const password = promptRequired("Ievadi lietotaja sakuma paroli:");
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
