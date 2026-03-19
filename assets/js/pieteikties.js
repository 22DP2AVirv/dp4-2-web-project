const appointmentForm = document.getElementById("appointmentForm");

async function prefillCurrentUser() {
    try {
        const response = await fetch("/api/me");
        if (!response.ok) {
            return;
        }

        const user = await response.json();
        document.getElementById("name").value = user.name || "";
        document.getElementById("surname").value = user.surname || "";
        document.getElementById("phone").value = user.phone || "";
        document.getElementById("email").value = user.email || "";
    } catch (error) {
        console.error("Neizdevas ieladet lietotaja datus:", error);
    }
}

function getAppointmentLocation(procedura) {
    const kurNotiks = document.getElementById("kurNotiks");
    const adrese = document.getElementById("adrese");
    const filiale = document.getElementById("filiale");
    const filialeSelect = document.getElementById("filialeSelect");

    if (procedura === "gimenesArsts") {
        if (!kurNotiks.value) {
            alert("Ludzu izvelieties, kur notiks procedura.");
            return null;
        }

        if (kurNotiks.value === "majas") {
            if (!adrese.value.trim()) {
                alert("Ludzu ievadiet adresi.");
                return null;
            }
            return adrese.value.trim();
        }

        if (!filiale.value) {
            alert("Ludzu izvelieties filiali.");
            return null;
        }

        return filiale.value;
    }

    if (!filialeSelect.value) {
        alert("Ludzu izvelieties filiali.");
        return null;
    }

    return filialeSelect.value;
}

async function submitAppointment(event) {
    event.preventDefault();

    const procedura = document.getElementById("procedura").value;
    const location = getAppointmentLocation(procedura);
    if (!location) {
        return;
    }

    try {
        const response = await fetch("/api/appointments", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: document.getElementById("name").value.trim(),
                surname: document.getElementById("surname").value.trim(),
                phone: document.getElementById("phone").value.trim(),
                email: document.getElementById("email").value.trim().toLowerCase(),
                procedura,
                datums: document.getElementById("velamaisDatums").value,
                laiks: document.getElementById("velamaisLaiks").value,
                adrese: location,
                comment: ""
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevas saglabat pieteikumu.");
        }

        alert("Pieteikums veiksmigi saglabats.");
        appointmentForm.reset();
        document.getElementById("gimenesArstsOptions").style.display = "none";
        document.getElementById("filialeSelect").style.display = "block";
        document.getElementById("filialeSelect").required = true;
        await prefillCurrentUser();
    } catch (error) {
        alert(error.message);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("velamaisDatums");
    if (dateInput) {
        dateInput.min = new Date().toISOString().split("T")[0];
    }

    prefillCurrentUser();
});

if (appointmentForm) {
    appointmentForm.addEventListener("submit", submitAppointment);
}
