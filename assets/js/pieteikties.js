const appointmentForm = document.getElementById("appointmentForm");
const appointmentLoginRequiredMessage = window.APPOINTMENT_LOGIN_REQUIRED_MESSAGE
    || "Lai pieteiktos uz procedūru, Jums ir jābūt reģistrētam lietotājam!";
const doctorAppointmentRestrictedMessage = window.DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE
    || "Ārsta kontam procedūru pieteikšana nav pieejama.";
const ALLOWED_TIME_MINUTES = new Set(["00", "15", "30", "45"]);

function setDoctorSelectPlaceholder(message, disabled = true) {
    const doctorSelect = document.getElementById("arstId");
    if (!doctorSelect) {
        return;
    }

    doctorSelect.innerHTML = "";

    const option = document.createElement("option");
    option.value = "";
    option.textContent = message;
    option.disabled = true;
    option.selected = true;
    option.defaultSelected = true;

    doctorSelect.appendChild(option);
    doctorSelect.disabled = disabled;
}

async function populateDoctorOptions(procedura, selectedDoctorId = "") {
    const doctorSelect = document.getElementById("arstId");
    if (!doctorSelect) {
        return;
    }

    if (!procedura) {
        setDoctorSelectPlaceholder("Vispirms izvēlieties procedūru*");
        return;
    }

    setDoctorSelectPlaceholder("Ielādējam ārstus...");

    try {
        const response = await fetch(`/api/doctors?procedura=${encodeURIComponent(procedura)}`);

        if (response.status === 401) {
            alert(appointmentLoginRequiredMessage);
            window.location.href = "login.html";
            return;
        }

        if (response.status === 403) {
            const data = await response.json();
            alert((data && data.error) || doctorAppointmentRestrictedMessage);
            window.location.href = "user_cab.html";
            return;
        }

        const doctors = await response.json();
        if (!response.ok) {
            throw new Error((doctors && doctors.error) || "Neizdevās ielādēt ārstus.");
        }

        if (!Array.isArray(doctors) || !doctors.length) {
            setDoctorSelectPlaceholder("Šai procedūrai ārsti nav pieejami");
            return;
        }

        doctorSelect.innerHTML = "";
        doctorSelect.disabled = false;

        const placeholderOption = document.createElement("option");
        placeholderOption.value = "";
        placeholderOption.textContent = "Izvēlieties ārstu*";
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        placeholderOption.defaultSelected = true;
        doctorSelect.appendChild(placeholderOption);

        doctors.forEach((doctor) => {
            const option = document.createElement("option");
            option.value = String(doctor.id);
            option.textContent = doctor.full_name || `${doctor.name || ""} ${doctor.surname || ""}`.trim();

            if (String(doctor.id) === String(selectedDoctorId)) {
                option.selected = true;
                placeholderOption.selected = false;
            }

            doctorSelect.appendChild(option);
        });
    } catch (error) {
        console.error("Neizdevās ielādēt ārstus:", error);
        setDoctorSelectPlaceholder("Neizdevās ielādēt ārstus");
    }
}

function formatDateForInput(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function formatTimeValue(hour, minute) {
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function getMaxAppointmentDate(baseDate = new Date()) {
    const maxDate = new Date(baseDate);
    const originalDay = maxDate.getDate();
    maxDate.setMonth(maxDate.getMonth() + 3);

    if (maxDate.getDate() !== originalDay) {
        maxDate.setDate(0);
    }

    maxDate.setHours(0, 0, 0, 0);
    return maxDate;
}

function parseDateInputValue(value) {
    if (!value) {
        return null;
    }

    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) {
        return null;
    }

    const parsedDate = new Date(year, month - 1, day);
    parsedDate.setHours(0, 0, 0, 0);

    if (
        parsedDate.getFullYear() !== year
        || parsedDate.getMonth() !== month - 1
        || parsedDate.getDate() !== day
    ) {
        return null;
    }

    return parsedDate;
}

function getWorkingHoursForDate(dateValue) {
    const selectedDate = parseDateInputValue(dateValue);
    if (!selectedDate) {
        return null;
    }

    const weekday = selectedDate.getDay();
    if (weekday >= 1 && weekday <= 5) {
        return {
            openingHour: 9,
            closingHour: 21,
            closedMessage: "Darba dienās var pieteikties tikai laikā no 9:00 līdz 21:00."
        };
    }

    if (weekday === 6) {
        return {
            openingHour: 10,
            closingHour: 20,
            closedMessage: "Sestdienās var pieteikties tikai laikā no 10:00 līdz 20:00."
        };
    }

    return {
        openingHour: null,
        closingHour: null,
        closedMessage: "Svētdienā medicīnas centrs ir slēgts."
    };
}

function validateAppointmentDate(dateValue) {
    const selectedDate = parseDateInputValue(dateValue);
    if (!selectedDate) {
        return "Lūdzu izvēlieties korektu datumu.";
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const maxDate = getMaxAppointmentDate(today);
    if (selectedDate < today || selectedDate > maxDate) {
        return "Pieteikties var tikai no šodienas līdz 3 mēnešiem uz priekšu.";
    }

    const workingHours = getWorkingHoursForDate(dateValue);
    if (workingHours && workingHours.openingHour === null) {
        return workingHours.closedMessage;
    }

    return null;
}

function validateAppointmentTime(dateValue, timeValue) {
    if (!timeValue) {
        return "Lūdzu izvēlieties laiku.";
    }

    const [hours, minutes] = timeValue.split(":");
    if (hours === undefined || minutes === undefined) {
        return "Lūdzu izvēlieties korektu laiku.";
    }

    if (!ALLOWED_TIME_MINUTES.has(minutes)) {
        return "Lūdzu izvēlieties laiku ar 15 minūšu soli: 00, 15, 30 vai 45.";
    }

    const workingHours = getWorkingHoursForDate(dateValue);
    if (!workingHours) {
        return "Lūdzu vispirms izvēlieties datumu.";
    }

    if (workingHours.openingHour === null) {
        return workingHours.closedMessage;
    }

    const totalMinutes = Number(hours) * 60 + Number(minutes);
    const openingMinutes = workingHours.openingHour * 60;
    const closingMinutes = workingHours.closingHour * 60;

    if (totalMinutes < openingMinutes || totalMinutes > closingMinutes) {
        return workingHours.closedMessage;
    }

    return null;
}

function populateTimeOptions(dateValue, selectedValue = "") {
    const timeSelect = document.getElementById("velamaisLaiks");
    if (!timeSelect) {
        return;
    }

    timeSelect.innerHTML = "";

    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.disabled = true;
    placeholderOption.selected = true;
    placeholderOption.defaultSelected = true;

    const workingHours = getWorkingHoursForDate(dateValue);
    if (!dateValue) {
        placeholderOption.textContent = "Vispirms izvēlieties datumu*";
        timeSelect.disabled = true;
        timeSelect.appendChild(placeholderOption);
        return;
    }

    if (!workingHours) {
        placeholderOption.textContent = "Izvēlieties korektu datumu*";
        timeSelect.disabled = true;
        timeSelect.appendChild(placeholderOption);
        return;
    }

    if (workingHours.openingHour === null) {
        placeholderOption.textContent = "Svētdienā nestrādājam";
        timeSelect.disabled = true;
        timeSelect.appendChild(placeholderOption);
        return;
    }

    placeholderOption.textContent = "Izvēlieties laiku*";
    timeSelect.disabled = false;
    timeSelect.appendChild(placeholderOption);

    const openingMinutes = workingHours.openingHour * 60;
    const closingMinutes = workingHours.closingHour * 60;

    for (let totalMinutes = openingMinutes; totalMinutes <= closingMinutes; totalMinutes += 15) {
        const optionValue = formatTimeValue(
            Math.floor(totalMinutes / 60),
            totalMinutes % 60
        );
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;

        if (optionValue === selectedValue) {
            option.selected = true;
            placeholderOption.selected = false;
        }

        timeSelect.appendChild(option);
    }
}

async function prefillCurrentUser() {
    try {
        const response = await fetch("/api/me");
        if (response.status === 401) {
            alert(appointmentLoginRequiredMessage);
            window.location.href = "login.html";
            return;
        }

        if (!response.ok) {
            return;
        }

        const user = await response.json();
        if (!user.can_book_appointments) {
            alert(doctorAppointmentRestrictedMessage);
            window.location.href = "user_cab.html";
            return;
        }

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
    const doctorId = document.getElementById("arstId").value;
    const dateValue = document.getElementById("velamaisDatums").value;
    const timeValue = document.getElementById("velamaisLaiks").value;

    if (!doctorId) {
        alert("Lūdzu izvēlieties ārstu.");
        return;
    }

    const dateError = validateAppointmentDate(dateValue);
    if (dateError) {
        alert(dateError);
        return;
    }

    const timeError = validateAppointmentTime(dateValue, timeValue);
    if (timeError) {
        alert(timeError);
        return;
    }

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
                doctor_id: doctorId,
                datums: dateValue,
                laiks: timeValue,
                adrese: location,
                comment: ""
            })
        });

        if (response.status === 401) {
            alert(appointmentLoginRequiredMessage);
            window.location.href = "login.html";
            return;
        }

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevas saglabat pieteikumu.");
        }

        alert("Pieteikums veiksmigi saglabats.");
        appointmentForm.reset();
        document.getElementById("gimenesArstsOptions").style.display = "none";
        document.getElementById("filialeSelect").style.display = "block";
        document.getElementById("filialeSelect").required = true;
        document.getElementById("kurNotiks").value = "";
        document.getElementById("adrese").value = "";
        document.getElementById("filiale").value = "";
        document.getElementById("adreseInput").style.display = "none";
        document.getElementById("filialeInput").style.display = "none";
        setDoctorSelectPlaceholder("Vispirms izvēlieties procedūru*");
        populateTimeOptions("");
        await prefillCurrentUser();
    } catch (error) {
        alert(error.message);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("velamaisDatums");
    const procedureInput = document.getElementById("procedura");
    if (dateInput) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        dateInput.min = formatDateForInput(today);
        dateInput.max = formatDateForInput(getMaxAppointmentDate(today));
        dateInput.addEventListener("change", (event) => {
            populateTimeOptions(event.target.value);
        });
    }

    if (procedureInput) {
        procedureInput.addEventListener("change", (event) => {
            populateDoctorOptions(event.target.value);
        });
    }

    if (procedureInput && procedureInput.value) {
        populateDoctorOptions(procedureInput.value);
    } else {
        setDoctorSelectPlaceholder("Vispirms izvēlieties procedūru*");
    }
    populateTimeOptions("");
    prefillCurrentUser();
});

if (appointmentForm) {
    appointmentForm.addEventListener("submit", submitAppointment);
}
