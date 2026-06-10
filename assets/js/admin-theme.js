// Admin paneļa tēmas skripts: saglabā un pārslēdz gaišo/tumšo režīmu.
const ADMIN_THEME_STORAGE_KEY = "adminThemePreference";

function readAdminThemePreference() {
    // Nolasa iepriekš izvēlēto admin paneļa tēmu.
    try {
        return window.localStorage.getItem(ADMIN_THEME_STORAGE_KEY);
    } catch (error) {
        return null;
    }
}

function writeAdminThemePreference(value) {
    // Saglabā izvēlēto tēmu localStorage.
    try {
        window.localStorage.setItem(ADMIN_THEME_STORAGE_KEY, value);
    } catch (error) {
        // ignore localStorage write errors
    }
}

function applyAdminTheme(theme) {
    // Pielieto tēmu lapai un atjauno pogas tekstu.
    const isDarkMode = theme === "dark";
    document.body.classList.toggle("admin-dark-mode", isDarkMode);

    document.querySelectorAll("[data-admin-theme-toggle]").forEach((button) => {
        button.textContent = isDarkMode ? "Gaišais režīms" : "Tumšais režīms";
    });
}

function toggleAdminTheme() {
    // Pārslēdz starp gaišo un tumšo režīmu.
    const nextTheme = document.body.classList.contains("admin-dark-mode") ? "light" : "dark";
    applyAdminTheme(nextTheme);
    writeAdminThemePreference(nextTheme);
}

document.addEventListener("DOMContentLoaded", () => {
    const initialTheme = readAdminThemePreference() === "dark" ? "dark" : "light";
    applyAdminTheme(initialTheme);

    document.querySelectorAll("[data-admin-theme-toggle]").forEach((button) => {
        button.addEventListener("click", toggleAdminTheme);
    });
});
