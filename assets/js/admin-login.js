document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginForm");
    const loginInput = document.getElementById("login");
    const passwordInput = document.getElementById("password");
    const errorMessage = document.getElementById("error");

    if (!loginForm) {
        return;
    }

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorMessage.style.display = "none";

        try {
            const response = await fetch("/api/admin/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: loginInput.value.trim(),
                    password: passwordInput.value
                })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Neizdevas pieslegties admin panelim.");
            }

            window.location.href = "admin-panel.html";
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.style.display = "block";
        }
    });
});
