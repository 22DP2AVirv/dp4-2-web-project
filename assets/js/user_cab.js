async function fetchCurrentUser() {
    const response = await fetch("/api/me");
    if (!response.ok) {
        throw new Error("AUTH_REQUIRED");
    }

    return response.json();
}

async function logoutUser() {
    await fetch("/api/logout", { method: "POST" });
    window.location.href = "index.html";
}

async function updatePassword() {
    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (!newPassword) {
        alert("Ludzu ievadiet jauno paroli.");
        return;
    }

    if (newPassword !== confirmPassword) {
        alert("Paroles nesakrit.");
        return;
    }

    try {
        const response = await fetch("/api/update-password", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ password: newPassword })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevas atjaunot paroli.");
        }

        document.getElementById("currentPassword").value = "Drosibas nolukos netiek radita";
        document.getElementById("newPassword").value = "";
        document.getElementById("confirmPassword").value = "";
        alert("Parole veiksmigi atjauninata.");
    } catch (error) {
        alert(error.message);
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const user = await fetchCurrentUser();
        document.getElementById("welcome").textContent = `Sveiki, ${user.name || "lietotaj"}!`;
        document.getElementById("currentPassword").value = "Drosibas nolukos netiek radita";

        const logoutButton = document.getElementById("registracija");
        if (logoutButton) {
            logoutButton.textContent = "Iziet";
            logoutButton.onclick = logoutUser;
        }

        const savePasswordButton = document.getElementById("savePassword");
        if (savePasswordButton) {
            savePasswordButton.addEventListener("click", updatePassword);
        }
    } catch (error) {
        if (error.message === "AUTH_REQUIRED") {
            window.location.href = "login.html";
            return;
        }

        alert("Neizdevas ieladet lietotaja profilu.");
    }
});
