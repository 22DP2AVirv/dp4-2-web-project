const contactForm = document.getElementById("contactForm");
const contactNameInput = document.getElementById("vards");
const contactEmailInput = document.getElementById("epasts");
const contactMessageInput = document.getElementById("teksts");
const contactPrivacyInput = document.getElementById("privatumaPolitika");
const contactStatus = document.getElementById("contactMessageStatus");

let contactAccount = null;

function setContactStatus(message, type) {
    if (!contactStatus) {
        return;
    }

    contactStatus.textContent = message || "";
    contactStatus.className = "mt-3";

    if (type === "success") {
        contactStatus.classList.add("text-success");
    } else if (type === "error") {
        contactStatus.classList.add("text-danger");
    } else if (type === "info") {
        contactStatus.classList.add("text-muted");
    }
}

function applyContactAccountPrefill() {
    if (!contactNameInput || !contactEmailInput) {
        return;
    }

    if (!contactAccount) {
        contactNameInput.disabled = false;
        contactEmailInput.disabled = false;
        contactNameInput.readOnly = false;
        contactEmailInput.readOnly = false;
        contactNameInput.required = true;
        contactEmailInput.required = true;
        return;
    }

    const fullName = [contactAccount.name, contactAccount.surname]
        .filter(Boolean)
        .join(" ")
        .trim();

    contactNameInput.value = fullName || contactAccount.name || "";
    contactEmailInput.value = contactAccount.email || "";
    contactNameInput.disabled = true;
    contactEmailInput.disabled = true;
    contactNameInput.readOnly = true;
    contactEmailInput.readOnly = true;
    contactNameInput.required = false;
    contactEmailInput.required = false;

    setContactStatus("Vārds un e-pasts aizpildīts automātiski no Tava konta.", "info");
}

async function loadContactAccount() {
    try {
        const response = await fetch("/api/me", {
            headers: {
                Accept: "application/json"
            }
        });

        if (!response.ok) {
            contactAccount = null;
            applyContactAccountPrefill();
            return;
        }

        contactAccount = await response.json();
        applyContactAccountPrefill();
    } catch (error) {
        contactAccount = null;
        applyContactAccountPrefill();
    }
}

async function submitContactForm(event) {
    event.preventDefault();
    setContactStatus("", "");

    const payload = {
        message: contactMessageInput?.value.trim() || ""
    };

    if (!contactAccount) {
        payload.name = contactNameInput?.value.trim() || "";
        payload.email = contactEmailInput?.value.trim().toLowerCase() || "";
    }

    try {
        const response = await fetch("/api/contact-messages", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās nosūtīt ziņojumu.");
        }

        contactForm.reset();
        if (contactPrivacyInput) {
            contactPrivacyInput.checked = false;
        }
        if (contactMessageInput) {
            contactMessageInput.value = "";
        }

        await loadContactAccount();
        setContactStatus("Ziņojums tika veiksmīgi nosūtīts!", "success");
    } catch (error) {
        setContactStatus(error.message || "Neizdevās nosūtīt ziņojumu.", "error");
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    if (!contactForm) {
        return;
    }

    await loadContactAccount();
    contactForm.addEventListener("submit", submitContactForm);
});
