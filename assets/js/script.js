const DARK_MODE_KEY = "darkMode";
const APPOINTMENT_LOGIN_REQUIRED_MESSAGE = "Lai pieteiktos uz procedūru, Jums ir jābūt reģistrētam lietotājam!";
const DOCTOR_APPOINTMENT_RESTRICTED_MESSAGE = "Ārsta kontam procedūru pieteikšana nav pieejama.";
const DOCTOR_REGISTRATION_PATH = "arsts.html";

let sessionUserPromise = null;

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

    if (account) {
        removeDoctorRegistrationButton();

        const headerButton = document.getElementById("registracija");
        pointButtonToAccount(headerButton);

        document.querySelectorAll("button.Logins").forEach((button) => {
            pointButtonToAccount(button);
        });
        return;
    }

    ensureDoctorRegistrationButton();
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

    updateSessionNavigation();
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
