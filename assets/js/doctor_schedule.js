// Ārsta grafika plānotājs: kalendārs, dienas laiki un saglabāšana backend API.
const scheduleState = {
    user: null,
    today: null,
    maxDate: null,
    currentMonth: null,
    selectedDate: "",
    monthSummary: {},
    daySchedule: null,
    pendingTimes: new Set(),
    saving: false,
    loadingDay: false,
    monthRequestId: 0,
    dayRequestId: 0
};

function startOfDay(date) {
    const copy = new Date(date);
    copy.setHours(0, 0, 0, 0);
    return copy;
}

function startOfMonth(date) {
    return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, amount) {
    return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function getMaxPlanningDate(baseDate) {
    const maxDate = new Date(baseDate);
    const originalDay = maxDate.getDate();
    maxDate.setMonth(maxDate.getMonth() + 3);

    if (maxDate.getDate() !== originalDay) {
        maxDate.setDate(0);
    }

    maxDate.setHours(0, 0, 0, 0);
    return maxDate;
}

function formatDateValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function parseDateValue(value) {
    if (!value) {
        return null;
    }

    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) {
        return null;
    }

    const parsed = new Date(year, month - 1, day);
    parsed.setHours(0, 0, 0, 0);

    if (
        parsed.getFullYear() !== year
        || parsed.getMonth() !== month - 1
        || parsed.getDate() !== day
    ) {
        return null;
    }

    return parsed;
}

function getMonthKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthLabel(date) {
    return new Intl.DateTimeFormat("lv-LV", {
        month: "long",
        year: "numeric"
    }).format(date);
}

function formatLongDate(value) {
    const parsed = parseDateValue(value);
    if (!parsed) {
        return value || "Nav izvēlēts datums";
    }

    return new Intl.DateTimeFormat("lv-LV", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
    }).format(parsed);
}

function getWorkingHoursForDate(date) {
    // Atgriež klīnikas darba laiku konkrētajai dienai.
    const weekday = date.getDay();
    if (weekday >= 1 && weekday <= 5) {
        return {
            openingHour: 9,
            closingHour: 21,
            label: "Darba diena, pieņemšana no 9:00 līdz 21:00."
        };
    }

    if (weekday === 6) {
        return {
            openingHour: 10,
            closingHour: 20,
            label: "Sestdiena, pieņemšana no 10:00 līdz 20:00."
        };
    }

    return null;
}

function buildTimeSlotsForDate(date) {
    // Izveido visus 15 minūšu laika slotus, kurus ārsts var atzīmēt kā pieejamus.
    const workingHours = getWorkingHoursForDate(date);
    if (!workingHours) {
        return [];
    }

    const slots = [];
    for (
        let totalMinutes = workingHours.openingHour * 60;
        totalMinutes <= workingHours.closingHour * 60;
        totalMinutes += 15
    ) {
        const hours = String(Math.floor(totalMinutes / 60)).padStart(2, "0");
        const minutes = String(totalMinutes % 60).padStart(2, "0");
        slots.push(`${hours}:${minutes}`);
    }

    return slots;
}

function readJsonResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
        return null;
    }

    return response.json();
}

function setMessage(elementId, message, type = "success") {
    const element = document.getElementById(elementId);
    if (!element) {
        return;
    }

    if (!message) {
        element.textContent = "";
        element.className = elementId.includes("planner") ? "planner-message" : "schedule-message";
        return;
    }

    element.textContent = message;
    element.className = `${elementId.includes("planner") ? "planner-message" : "schedule-message"} visible ${type}`;
}

function isWithinPlanningWindow(date) {
    const normalized = startOfDay(date);
    return normalized >= scheduleState.today && normalized <= scheduleState.maxDate;
}

function isSameMonth(left, right) {
    return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth();
}

function getPlanningMonthBounds() {
    return {
        minMonth: startOfMonth(scheduleState.today),
        maxMonth: startOfMonth(scheduleState.maxDate)
    };
}

function canNavigateToMonth(targetMonth) {
    const { minMonth, maxMonth } = getPlanningMonthBounds();
    return targetMonth >= minMonth && targetMonth <= maxMonth;
}

function getDefaultDateForMonth(month) {
    const candidate = isSameMonth(month, scheduleState.today)
        ? scheduleState.today
        : startOfMonth(month);
    return candidate > scheduleState.maxDate ? scheduleState.maxDate : candidate;
}

async function fetchCurrentUser() {
    // Pārbauda, vai lapu atver apstiprināts ārsta konts.
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

async function fetchMonthSummary(monthKey) {
    // Ielādē kalendāra mēneša kopsavilkumu ar brīvajiem un aizņemtajiem laikiem.
    const response = await fetch(`/api/doctor/schedule?month=${encodeURIComponent(monthKey)}`);
    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }
    if (response.status === 403) {
        throw new Error("DOCTOR_ONLY");
    }

    const data = await readJsonResponse(response);
    if (!response.ok || !data) {
        throw new Error((data && data.error) || "Neizdevās ielādēt kalendāra datus.");
    }

    return data;
}

async function fetchDaySchedule(dateValue) {
    // Ielādē konkrētas dienas ārsta grafiku.
    const response = await fetch(`/api/doctor/schedule?date=${encodeURIComponent(dateValue)}`);
    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }
    if (response.status === 403) {
        throw new Error("DOCTOR_ONLY");
    }

    const data = await readJsonResponse(response);
    if (!response.ok || !data) {
        throw new Error((data && data.error) || "Neizdevās ielādēt dienas grafiku.");
    }

    return data;
}

async function saveDaySchedule(dateValue, availableTimes) {
    // Saglabā ārsta izvēlētos pieejamos laikus datubāzē.
    const response = await fetch("/api/doctor/schedule", {
        method: "PUT",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            date: dateValue,
            available_times: availableTimes
        })
    });

    if (response.status === 401) {
        throw new Error("AUTH_REQUIRED");
    }
    if (response.status === 403) {
        throw new Error("DOCTOR_ONLY");
    }

    const data = await readJsonResponse(response);
    if (!response.ok || !data) {
        throw new Error((data && data.error) || "Neizdevās saglabāt grafiku.");
    }

    return data;
}

function handleAuthError(error) {
    if (error.message === "AUTH_REQUIRED") {
        window.location.href = "login.html?role=doctor";
        return true;
    }

    if (error.message === "DOCTOR_ONLY") {
        window.location.href = "user_cab.html";
        return true;
    }

    return false;
}

function updateMonthNavigation() {
    const currentMonthLabel = document.getElementById("currentMonthLabel");
    if (currentMonthLabel && scheduleState.currentMonth) {
        currentMonthLabel.textContent = getMonthLabel(scheduleState.currentMonth);
    }

    const prevButton = document.getElementById("prevMonthBtn");
    if (prevButton) {
        prevButton.disabled = !canNavigateToMonth(addMonths(scheduleState.currentMonth, -1));
    }

    const nextButton = document.getElementById("nextMonthBtn");
    if (nextButton) {
        nextButton.disabled = !canNavigateToMonth(addMonths(scheduleState.currentMonth, 1));
    }
}

function renderCalendar() {
    // Uzzīmē mēneša kalendāru un parāda, kurās dienās ir brīvi vai aizņemti laiki.
    const calendarGrid = document.getElementById("calendarGrid");
    if (!calendarGrid || !scheduleState.currentMonth) {
        return;
    }

    updateMonthNavigation();

    const firstDay = startOfMonth(scheduleState.currentMonth);
    const offset = (firstDay.getDay() + 6) % 7;
    const gridStart = new Date(firstDay);
    gridStart.setDate(firstDay.getDate() - offset);

    const cells = [];
    for (let index = 0; index < 42; index += 1) {
        const cellDate = new Date(gridStart);
        cellDate.setDate(gridStart.getDate() + index);

        const dateValue = formatDateValue(cellDate);
        const summary = scheduleState.monthSummary[dateValue] || null;
        const isCurrentMonth = isSameMonth(cellDate, scheduleState.currentMonth);
        const isSelectable = isCurrentMonth && isWithinPlanningWindow(cellDate);
        const isSelected = scheduleState.selectedDate === dateValue;
        const isClosedDay = !getWorkingHoursForDate(cellDate);

        const classes = ["calendar-day"];
        if (!isCurrentMonth) {
            classes.push("is-outside");
        }
        if (isSelected) {
            classes.push("is-selected");
        }
        if (!isSelectable) {
            classes.push("is-disabled");
        }
        if (isClosedDay) {
            classes.push("is-closed");
        }

        const notes = [];
        if (summary?.open_slots) {
            notes.push(`<span class="calendar-count open">Brīvi ${summary.open_slots}</span>`);
        }
        if (summary?.booked_slots) {
            notes.push(`<span class="calendar-count booked">Pieraksti ${summary.booked_slots}</span>`);
        }
        if (!notes.length && isCurrentMonth && isClosedDay) {
            notes.push('<span class="calendar-count closed">Slēgts</span>');
        } else if (!notes.length && isCurrentMonth && isSelectable) {
            notes.push('<span class="calendar-count empty">Nav laiku</span>');
        }

        cells.push(`
            <button
                class="${classes.join(" ")}"
                type="button"
                data-date="${dateValue}"
                ${isSelectable ? "" : "disabled"}
            >
                <span class="calendar-day-number">${cellDate.getDate()}</span>
                <span class="calendar-day-note">${notes.join("")}</span>
            </button>
        `);
    }

    calendarGrid.innerHTML = cells.join("");
}

function renderPlanner() {
    // Uzzīmē izvēlētās dienas laika slotus ar brīvajiem un aizņemtajiem laikiem.
    const dateTitle = document.getElementById("plannerDateTitle");
    const dateSubtitle = document.getElementById("plannerDateSubtitle");
    const note = document.getElementById("plannerNote");
    const timeSlots = document.getElementById("timeSlots");
    const openSlotCount = document.getElementById("openSlotCount");
    const bookedSlotCount = document.getElementById("bookedSlotCount");
    const configuredSlotCount = document.getElementById("configuredSlotCount");
    const selectAllButton = document.getElementById("selectAllBtn");
    const clearDayButton = document.getElementById("clearDayBtn");
    const saveButton = document.getElementById("saveScheduleBtn");

    if (!dateTitle || !dateSubtitle || !note || !timeSlots || !openSlotCount || !bookedSlotCount || !configuredSlotCount) {
        return;
    }

    if (!scheduleState.selectedDate) {
        dateTitle.textContent = "Izvēlies dienu";
        dateSubtitle.textContent = "Te parādīsies konkrētās dienas laika sloti.";
        note.textContent = "Aktīvie sloti ir redzami pacientiem. Slotus ar esošu pierakstu nevar noņemt no grafika.";
        timeSlots.innerHTML = '<div class="planner-empty">Iezīmē dienu kalendārā, lai ielādētu tās pieejamos laikus.</div>';
        openSlotCount.textContent = "0";
        bookedSlotCount.textContent = "0";
        configuredSlotCount.textContent = "0";
        if (selectAllButton) {
            selectAllButton.disabled = true;
        }
        if (clearDayButton) {
            clearDayButton.disabled = true;
        }
        if (saveButton) {
            saveButton.disabled = true;
        }
        return;
    }

    const selectedDate = parseDateValue(scheduleState.selectedDate);
    if (!selectedDate) {
        return;
    }

    if (scheduleState.loadingDay) {
        dateTitle.textContent = formatLongDate(scheduleState.selectedDate);
        dateSubtitle.textContent = "Ielādējam izvēlētās dienas grafiku...";
        note.textContent = "Lūdzu uzgaidi dažas sekundes, kamēr ielādējas laika sloti un esošie pieraksti.";
        timeSlots.innerHTML = '<div class="planner-empty">Ielādējam dienas laika slotus...</div>';
        openSlotCount.textContent = "0";
        bookedSlotCount.textContent = "0";
        configuredSlotCount.textContent = "0";
        if (selectAllButton) {
            selectAllButton.disabled = true;
        }
        if (clearDayButton) {
            clearDayButton.disabled = true;
        }
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.textContent = "Saglabāt grafiku";
        }
        return;
    }

    const workingHours = getWorkingHoursForDate(selectedDate);
    if (!scheduleState.daySchedule) {
        dateTitle.textContent = formatLongDate(scheduleState.selectedDate);
        dateSubtitle.textContent = "Dienas grafiku pagaidām nevarēja ielādēt.";
        note.textContent = "Pamēģini vēlreiz izvēlēties dienu vai pārslēgt mēnesi.";
        timeSlots.innerHTML = '<div class="planner-empty">Dienas laika sloti nav pieejami, jo neizdevās nolasīt datus no servera.</div>';
        openSlotCount.textContent = "0";
        bookedSlotCount.textContent = "0";
        configuredSlotCount.textContent = "0";
        if (selectAllButton) {
            selectAllButton.disabled = true;
        }
        if (clearDayButton) {
            clearDayButton.disabled = true;
        }
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.textContent = "Saglabāt grafiku";
        }
        return;
    }

    const bookedTimes = new Set(scheduleState.daySchedule?.booked_times || []);
    const slotOptions = buildTimeSlotsForDate(selectedDate);
    const openCount = Array.from(scheduleState.pendingTimes).length;
    const bookedCount = bookedTimes.size;

    dateTitle.textContent = formatLongDate(scheduleState.selectedDate);
    dateSubtitle.textContent = workingHours
        ? workingHours.label
        : "Svētdien klīnika ir slēgta, tāpēc pacientu laikus šeit pievienot nevar.";
    note.textContent = bookedCount
        ? "Rezervētie sloti ir bloķēti. Brīvos laikus vari ieslēgt vai izslēgt un pēc tam saglabāt."
        : "Atzīmē laikus, kuros vēlies pieņemt pacientus, un saglabā izmaiņas.";

    openSlotCount.textContent = String(openCount);
    bookedSlotCount.textContent = String(bookedCount);
    configuredSlotCount.textContent = String(openCount + bookedCount);

    if (!workingHours) {
        timeSlots.innerHTML = '<div class="planner-empty">Šī diena ir slēgta. Izvēlies citu datumu, lai ieplānotu pieejamus laikus.</div>';
        if (selectAllButton) {
            selectAllButton.disabled = true;
        }
        if (clearDayButton) {
            clearDayButton.disabled = true;
        }
        if (saveButton) {
            saveButton.disabled = true;
        }
        return;
    }

    timeSlots.innerHTML = slotOptions.map((slot) => {
        const isBooked = bookedTimes.has(slot);
        const isActive = scheduleState.pendingTimes.has(slot);
        const classes = ["schedule-slot"];
        if (isActive) {
            classes.push("is-active");
        }
        if (isBooked) {
            classes.push("is-booked");
        }
        if (scheduleState.saving) {
            classes.push("is-disabled");
        }

        return `
            <button
                class="${classes.join(" ")}"
                type="button"
                data-time="${slot}"
                ${isBooked || scheduleState.saving ? "disabled" : ""}
            >
                ${slot}
            </button>
        `;
    }).join("");

    if (selectAllButton) {
        selectAllButton.disabled = scheduleState.saving;
    }
    if (clearDayButton) {
        clearDayButton.disabled = scheduleState.saving;
    }
    if (saveButton) {
        saveButton.disabled = scheduleState.saving;
        saveButton.textContent = scheduleState.saving ? "Saglabājam..." : "Saglabāt grafiku";
    }
}

async function loadMonthSummary() {
    // Pārlādē mēneša datus pēc grafika izmaiņām.
    const requestId = ++scheduleState.monthRequestId;
    const payload = await fetchMonthSummary(getMonthKey(scheduleState.currentMonth));
    if (requestId !== scheduleState.monthRequestId) {
        return;
    }

    scheduleState.monthSummary = payload.days || {};
    renderCalendar();
}

async function loadDayScheduleView(dateValue) {
    // Pārlādē vienas dienas grafiku un atjauno plānotāja skatu.
    scheduleState.selectedDate = dateValue;
    scheduleState.loadingDay = true;
    scheduleState.daySchedule = null;
    scheduleState.pendingTimes = new Set();
    renderCalendar();
    renderPlanner();
    setMessage("plannerMessage", "");

    const requestId = ++scheduleState.dayRequestId;
    try {
        const payload = await fetchDaySchedule(dateValue);
        if (requestId !== scheduleState.dayRequestId) {
            return;
        }

        scheduleState.daySchedule = payload;
        const bookedTimes = new Set(payload.booked_times || []);
        scheduleState.pendingTimes = new Set(
            (payload.configured_times || []).filter((timeValue) => !bookedTimes.has(timeValue))
        );
    } finally {
        if (requestId === scheduleState.dayRequestId) {
            scheduleState.loadingDay = false;
            renderPlanner();
        }
    }
}

async function changeMonth(offset) {
    const nextMonth = addMonths(scheduleState.currentMonth, offset);
    if (!canNavigateToMonth(nextMonth)) {
        return;
    }

    scheduleState.currentMonth = startOfMonth(nextMonth);
    scheduleState.daySchedule = null;
    scheduleState.pendingTimes = new Set();
    renderCalendar();
    renderPlanner();

    await loadMonthSummary();

    const selectedDate = parseDateValue(scheduleState.selectedDate);
    const nextDate = selectedDate && isSameMonth(selectedDate, scheduleState.currentMonth)
        ? scheduleState.selectedDate
        : formatDateValue(getDefaultDateForMonth(scheduleState.currentMonth));
    await loadDayScheduleView(nextDate);
}

async function saveCurrentDaySchedule() {
    // Saglabā pašreizējā dienā atzīmētos laikus.
    if (!scheduleState.selectedDate || scheduleState.saving) {
        return;
    }

    scheduleState.saving = true;
    renderPlanner();
    setMessage("plannerMessage", "");

    try {
        const payload = await saveDaySchedule(
            scheduleState.selectedDate,
            Array.from(scheduleState.pendingTimes).sort()
        );
        scheduleState.daySchedule = payload;
        const bookedTimes = new Set(payload.booked_times || []);
        scheduleState.pendingTimes = new Set(
            (payload.configured_times || []).filter((timeValue) => !bookedTimes.has(timeValue))
        );
        await loadMonthSummary();
        renderPlanner();
        setMessage("plannerMessage", "Grafiks veiksmīgi saglabāts.", "success");
    } catch (error) {
        if (handleAuthError(error)) {
            return;
        }

        renderPlanner();
        setMessage("plannerMessage", error.message, "error");
    } finally {
        scheduleState.saving = false;
        renderPlanner();
    }
}

function handleCalendarClick(event) {
    // Apstrādā klikšķi uz kalendāra dienas.
    const dayButton = event.target.closest("[data-date]");
    if (!dayButton || dayButton.disabled) {
        return;
    }

    const dateValue = dayButton.dataset.date;
    if (!dateValue) {
        return;
    }

    loadDayScheduleView(dateValue).catch((error) => {
        if (handleAuthError(error)) {
            return;
        }
        setMessage("schedulePageMessage", error.message, "error");
    });
}

function handleTimeSlotClick(event) {
    // Pārslēdz vienu laika slotu starp pieejamu un nepieejamu.
    const slotButton = event.target.closest("[data-time]");
    if (!slotButton || slotButton.disabled) {
        return;
    }

    const slotValue = slotButton.dataset.time;
    if (!slotValue) {
        return;
    }

    if (scheduleState.pendingTimes.has(slotValue)) {
        scheduleState.pendingTimes.delete(slotValue);
    } else {
        scheduleState.pendingTimes.add(slotValue);
    }

    renderPlanner();
}

function selectAllSlots() {
    // Atzīmē visus dienas slotus kā pieejamus, izņemot jau rezervētos.
    const selectedDate = parseDateValue(scheduleState.selectedDate);
    if (!selectedDate) {
        return;
    }

    const bookedTimes = new Set(scheduleState.daySchedule?.booked_times || []);
    scheduleState.pendingTimes = new Set(
        buildTimeSlotsForDate(selectedDate).filter((slot) => !bookedTimes.has(slot))
    );
    renderPlanner();
}

function clearOpenSlots() {
    // Noņem ārsta brīvos slotus, bet saglabā jau rezervētos laikus.
    scheduleState.pendingTimes = new Set();
    renderPlanner();
}

async function initializeDoctorSchedule() {
    // Inicializē ārsta grafika lapu un ielādē sākotnējo mēnesi.
    scheduleState.today = startOfDay(new Date());
    scheduleState.maxDate = getMaxPlanningDate(scheduleState.today);

    try {
        const user = await fetchCurrentUser();
        if (user.role !== "doctor") {
            window.location.href = "user_cab.html";
            return;
        }

        scheduleState.user = user;
        scheduleState.currentMonth = startOfMonth(scheduleState.today);
        scheduleState.selectedDate = formatDateValue(scheduleState.today);

        await loadMonthSummary();
        await loadDayScheduleView(scheduleState.selectedDate);
    } catch (error) {
        if (handleAuthError(error)) {
            return;
        }

        setMessage("schedulePageMessage", error.message || "Neizdevās ielādēt grafika lapu.", "error");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("backToCabinetBtn")?.addEventListener("click", () => {
        window.location.href = "user_cab.html";
    });

    document.getElementById("prevMonthBtn")?.addEventListener("click", () => {
        changeMonth(-1).catch((error) => {
            if (handleAuthError(error)) {
                return;
            }
            setMessage("schedulePageMessage", error.message, "error");
        });
    });

    document.getElementById("nextMonthBtn")?.addEventListener("click", () => {
        changeMonth(1).catch((error) => {
            if (handleAuthError(error)) {
                return;
            }
            setMessage("schedulePageMessage", error.message, "error");
        });
    });

    document.getElementById("calendarGrid")?.addEventListener("click", handleCalendarClick);
    document.getElementById("timeSlots")?.addEventListener("click", handleTimeSlotClick);
    document.getElementById("selectAllBtn")?.addEventListener("click", selectAllSlots);
    document.getElementById("clearDayBtn")?.addEventListener("click", clearOpenSlots);
    document.getElementById("saveScheduleBtn")?.addEventListener("click", () => {
        saveCurrentDaySchedule();
    });

    initializeDoctorSchedule();
});
