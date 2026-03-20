const doctorRegistrationForm = document.getElementById("doctorRegistrationForm");

async function submitDoctorRegistration(event) {
    event.preventDefault();

    const name = document.getElementById("name").value.trim();
    const surname = document.getElementById("surname").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const email = document.getElementById("email").value.trim().toLowerCase();
    const procedure = document.getElementById("procedure").value;
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (password !== confirmPassword) {
        alert("Paroles nesakrīt.");
        return;
    }

    try {
        const response = await fetch("/api/doctors/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                surname,
                phone,
                email,
                procedure,
                password
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Neizdevās reģistrēt ārsta kontu.");
        }

        alert("Ārsta reģistrācija pabeigta. Tagad vari pieslēgties.");
        window.location.href = "login.html?role=doctor";
    } catch (error) {
        alert(error.message);
    }
}

if (doctorRegistrationForm) {
    doctorRegistrationForm.addEventListener("submit", submitDoctorRegistration);
}
