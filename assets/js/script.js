const DARK_MODE_KEY = "darkMode";

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

window.toggleMenu = toggleMenu;
window.showWorkTime = showWorkTime;
window.closeWorkTime = closeWorkTime;

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

    const form = document.querySelector("form");
    if (form && !["appointmentForm", "registrationForm", "loginForm"].includes(form.id)) {
        form.addEventListener("submit", (event) => {
            event.preventDefault();
            alert("Paldies! Mēs ar jums drīz sazināsimies.");
            form.reset();
        });
    }
});
