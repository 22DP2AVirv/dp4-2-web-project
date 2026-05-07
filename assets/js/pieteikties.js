const appointmentForm = document.getElementById("appointmentForm");
const appointmentLoginRequiredMessage = window.APPOINTMENT_LOGIN_REQUIRED_MESSAGE
    || "Lai pieteiktos uz procedūru, Jums ir jābūt reģistrētam lietotājam!";
const doctorAppointmentRestrictedMessage = window.DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE
    || "Ārsta kontam procedūru pieteikšana nav pieejama.";
const ALLOWED_TIME_MINUTES = new Set(["00", "15", "30", "45"]);
const appointmentState = {
    availableDates: [],
    availableTimes: [],
    dateRequestId: 0,
    availabilityRequestId: 0
};

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

function setDateSelectPlaceholder(message, disabled = true) {
    const dateSelect = document.getElementById("velamaisDatums");
    if (!dateSelect) {
        return;
    }

    appointmentState.availableDates = [];
    dateSelect.innerHTML = "";

    const option = document.createElement("option");
    option.value = "";
    option.textContent = message;
    option.disabled = true;
    option.selected = true;
    option.defaultSelected = true;

    dateSelect.appendChild(option);
    dateSelect.disabled = disabled;
}

function setTimeSelectPlaceholder(message, disabled = true) {
    const timeSelect = document.getElementById("velamaisLaiks");
    if (!timeSelect) {
        return;
    }

    appointmentState.availableTimes = [];
    timeSelect.innerHTML = "";

    const option = document.createElement("option");
    option.value = "";
    option.textContent = message;
    option.disabled = true;
    option.selected = true;
    option.defaultSelected = true;

    timeSelect.appendChild(option);
    timeSelect.disabled = disabled;
}

async function populateDoctorOptions(procedura, selectedDoctorId = "") {
    const doctorSelect = document.getElementById("arstId");
    if (!doctorSelect) {
        return;
    }

    if (!procedura) {
        setDoctorSelectPlaceholder("Vispirms izvēlieties procedūru*");
        setDateSelectPlaceholder("Vispirms izvēlieties ārstu*");
        setTimeSelectPlaceholder("Vispirms izvēlieties ārstu*");
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
            setDateSelectPlaceholder("Šai procedūrai nav pieejamu datumu");
            setTimeSelectPlaceholder("Šai procedūrai nav pieejamu laiku");
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

        if (selectedDoctorId) {
            await populateDateOptions(selectedDoctorId, procedura);
        }
    } catch (error) {
        console.error("Neizdevās ielādēt ārstus:", error);
        setDoctorSelectPlaceholder("Neizdevās ielādēt ārstus");
        setDateSelectPlaceholder("Neizdevās ielādēt datumus");
        setTimeSelectPlaceholder("Neizdevās ielādēt laikus");
    }
}

async function populateDateOptions(doctorId, procedureValue, selectedDate = "") {
    const dateSelect = document.getElementById("velamaisDatums");
    if (!dateSelect) {
        return;
    }

    if (!doctorId) {
        setDateSelectPlaceholder("Vispirms izvēlieties ārstu*");
        setTimeSelectPlaceholder("Vispirms izvēlieties datumu*");
        return;
    }

    setDateSelectPlaceholder("Ielādējam datumus...");
    const requestId = ++appointmentState.dateRequestId;

    try {
        const response = await fetch(
            `/api/doctors/${encodeURIComponent(doctorId)}/available-dates?procedura=${encodeURIComponent(procedureValue)}`
        );

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

        const data = await response.json();
        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās ielādēt pieejamos datumus.");
        }

        if (requestId !== appointmentState.dateRequestId) {
            return;
        }

        const availableDates = Array.isArray(data.available_dates) ? data.available_dates : [];
        appointmentState.availableDates = availableDates;
        dateSelect.innerHTML = "";

        const placeholderOption = document.createElement("option");
        placeholderOption.value = "";
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        placeholderOption.defaultSelected = true;

        if (!availableDates.length) {
            placeholderOption.textContent = "Ārstam šobrīd nav brīvu datumu";
            dateSelect.disabled = true;
            dateSelect.appendChild(placeholderOption);
            setTimeSelectPlaceholder("Ārstam nav pieejamu laiku");
            return;
        }

        placeholderOption.textContent = "Izvēlieties datumu*";
        dateSelect.disabled = false;
        dateSelect.appendChild(placeholderOption);

        availableDates.forEach((entry) => {
            const option = document.createElement("option");
            option.value = entry.date;
            option.textContent = formatDateLabel(entry.date, entry.open_slots);

            if (entry.date === selectedDate) {
                option.selected = true;
                placeholderOption.selected = false;
            }

            dateSelect.appendChild(option);
        });

        if (selectedDate) {
            await refreshAvailableTimeOptions();
        } else {
            setTimeSelectPlaceholder("Vispirms izvēlieties datumu*");
        }
    } catch (error) {
        console.error("Neizdevās ielādēt datumus:", error);
        if (requestId !== appointmentState.dateRequestId) {
            return;
        }

        setDateSelectPlaceholder("Neizdevās ielādēt datumus");
        setTimeSelectPlaceholder("Neizdevās ielādēt laikus");
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

function formatDateLabel(dateValue, openSlots = 0) {
    const parsedDate = parseDateInputValue(dateValue);
    if (!parsedDate) {
        return dateValue;
    }

    const baseLabel = new Intl.DateTimeFormat("lv-LV", {
        weekday: "short",
        day: "2-digit",
        month: "long"
    }).format(parsedDate);

    if (!openSlots) {
        return baseLabel;
    }

    return `${baseLabel} (${openSlots} brīvi laiki)`;
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

    if (
        appointmentState.availableDates.length
        && !appointmentState.availableDates.some((entry) => entry.date === dateValue)
    ) {
        return "Lūdzu izvēlieties datumu no ārsta pieejamā saraksta.";
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

    if (!appointmentState.availableTimes.includes(timeValue)) {
        return "Šis laiks vairs nav pieejams. Lūdzu izvēlieties citu laiku.";
    }

    return null;
}

async function populateTimeOptions(dateValue, doctorId, procedureValue, selectedValue = "") {
    const timeSelect = document.getElementById("velamaisLaiks");
    if (!timeSelect) {
        return;
    }

    if (!dateValue) {
        setTimeSelectPlaceholder("Vispirms izvēlieties datumu*");
        return;
    }

    if (!doctorId) {
        setTimeSelectPlaceholder("Vispirms izvēlieties ārstu*");
        return;
    }

    const dateError = validateAppointmentDate(dateValue);
    if (dateError) {
        setTimeSelectPlaceholder(dateError);
        return;
    }

    setTimeSelectPlaceholder("Ielādējam laikus...");
    const requestId = ++appointmentState.availabilityRequestId;

    try {
        const response = await fetch(
            `/api/doctors/${encodeURIComponent(doctorId)}/available-slots?procedura=${encodeURIComponent(procedureValue)}&date=${encodeURIComponent(dateValue)}`
        );

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

        const data = await response.json();
        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās ielādēt ārsta pieejamos laikus.");
        }

        if (requestId !== appointmentState.availabilityRequestId) {
            return;
        }

        const availableTimes = Array.isArray(data.available_times) ? data.available_times : [];
        appointmentState.availableTimes = availableTimes;
        timeSelect.innerHTML = "";

        const placeholderOption = document.createElement("option");
        placeholderOption.value = "";
        placeholderOption.disabled = true;
        placeholderOption.selected = true;
        placeholderOption.defaultSelected = true;

        if (!availableTimes.length) {
            placeholderOption.textContent = "Ārsts šajā dienā nav pieejams";
            timeSelect.disabled = true;
            timeSelect.appendChild(placeholderOption);
            return;
        }

        placeholderOption.textContent = "Izvēlieties laiku*";
        timeSelect.disabled = false;
        timeSelect.appendChild(placeholderOption);

        availableTimes.forEach((optionValue) => {
            const option = document.createElement("option");
            option.value = optionValue;
            option.textContent = optionValue;

            if (optionValue === selectedValue) {
                option.selected = true;
                placeholderOption.selected = false;
            }

            timeSelect.appendChild(option);
        });
    } catch (error) {
        console.error("Neizdevās ielādēt pieejamos laikus:", error);
        if (requestId !== appointmentState.availabilityRequestId) {
            return;
        }
        setTimeSelectPlaceholder("Neizdevās ielādēt laikus");
    }
}

async function refreshAvailableTimeOptions(selectedValue = "") {
    const dateInput = document.getElementById("velamaisDatums");
    const doctorSelect = document.getElementById("arstId");
    const procedureInput = document.getElementById("procedura");

    await populateTimeOptions(
        dateInput ? dateInput.value : "",
        doctorSelect ? doctorSelect.value : "",
        procedureInput ? procedureInput.value : "",
        selectedValue
    );
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
        setDateSelectPlaceholder("Vispirms izvēlieties ārstu*");
        setTimeSelectPlaceholder("Vispirms izvēlieties ārstu*");
        await prefillCurrentUser();
    } catch (error) {
        alert(error.message);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const dateInput = document.getElementById("velamaisDatums");
    const procedureInput = document.getElementById("procedura");
    const doctorSelect = document.getElementById("arstId");
    if (dateInput) {
        dateInput.addEventListener("change", () => {
            refreshAvailableTimeOptions().catch((error) => {
                console.error("Neizdevās atjaunot laikus:", error);
            });
        });
    }

    if (procedureInput) {
        procedureInput.addEventListener("change", (event) => {
            populateDoctorOptions(event.target.value).catch((error) => {
                console.error("Neizdevās ielādēt ārstus:", error);
            });
            setDateSelectPlaceholder("Vispirms izvēlieties ārstu*");
            setTimeSelectPlaceholder("Vispirms izvēlieties ārstu*");
        });
    }

    if (doctorSelect) {
        doctorSelect.addEventListener("change", () => {
            populateDateOptions(
                doctorSelect.value,
                procedureInput ? procedureInput.value : ""
            ).catch((error) => {
                console.error("Neizdevās ielādēt datumus:", error);
            });
        });
    }

    if (procedureInput && procedureInput.value) {
        populateDoctorOptions(procedureInput.value).catch((error) => {
            console.error("Neizdevās ielādēt ārstus:", error);
        });
    } else {
        setDoctorSelectPlaceholder("Vispirms izvēlieties procedūru*");
    }
    setDateSelectPlaceholder("Vispirms izvēlieties ārstu*");
    setTimeSelectPlaceholder("Vispirms izvēlieties ārstu*");
    prefillCurrentUser();
});

if (appointmentForm) {
    appointmentForm.addEventListener("submit", submitAppointment);
}
