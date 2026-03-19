document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector("header");
    if (!header) {
        return;
    }

    window.addEventListener("scroll", () => {
        header.classList.toggle("sticky-active", window.scrollY > 30);
    });
});
