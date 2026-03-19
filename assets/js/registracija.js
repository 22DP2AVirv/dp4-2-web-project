const registrationForm = document.getElementById("registrationForm");

async function submitRegistration(event) {
    event.preventDefault();

    const name = document.getElementById("name").value.trim();
    const surname = document.getElementById("surname").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const email = document.getElementById("email").value.trim().toLowerCase();
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (password !== confirmPassword) {
        alert("Paroles nesakrit.");
        return;
    }

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                surname,
                phone,
                email,
                password
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevas pieregistreties.");
        }

        alert("Registracija pabeigta. Tagad vari pieslegties.");
        window.location.href = "login.html";
    } catch (error) {
        alert(error.message);
    }
}

if (registrationForm) {
    registrationForm.addEventListener("submit", submitRegistration);
}
