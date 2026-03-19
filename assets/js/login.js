const loginForm = document.getElementById("loginForm");

async function submitLogin(event) {
    event.preventDefault();

    const email = document.getElementById("email").value.trim().toLowerCase();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
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
    loginForm.addEventListener("submit", submitLogin);
}
