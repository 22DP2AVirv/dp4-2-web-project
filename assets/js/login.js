const loginForm = document.getElementById("loginForm");

function getRequestedRole() {
    const params = new URLSearchParams(window.location.search);
    const requestedRole = params.get("role");
    return requestedRole === "doctor" ? "doctor" : "user";
}

async function submitLogin(event) {
    event.preventDefault();

    const role = document.getElementById("role").value;
    const email = document.getElementById("email").value.trim().toLowerCase();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ role, email, password })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevas pieslegties.");
        }

        window.location.href = "user_cab.html";
    } catch (error) {
        alert(error.message);
    }
}

if (loginForm) {
    const roleField = document.getElementById("role");
    if (roleField) {
        roleField.value = getRequestedRole();
    }

    loginForm.addEventListener("submit", submitLogin);
}
