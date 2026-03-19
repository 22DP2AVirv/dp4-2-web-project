function safeText(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

async function loadServices() {
    const container = document.getElementById("serviceCards");
    if (!container) {
        return;
    }

    try {
        const response = await fetch("/api/catalog");
        const catalog = await response.json();

        if (!response.ok) {
            throw new Error("Neizdevās ielādēt pakalpojumus.");
        }

        if (!catalog.length) {
            container.innerHTML = "<p>Pakalpojumi pagaidām nav pieejami.</p>";
            return;
        }

        container.innerHTML = catalog.map((service) => {
            const meta = service.public_meta || {};
            const imagePath = meta.image_path || "/images/medicina.webp";
            const detailPage = meta.detail_page || "pieteikties.html";
            const buttonLabel = meta.button_label || "Pieteikties";

            return `
                <div class="col-md-4 d-flex justify-content-center">
                    <div class="card">
                        <img src="${safeText(imagePath)}" alt="${safeText(service.service_name)}">
                        <div class="card-content">
                            <h3>${safeText(service.service_name)}</h3>
                            <p>${safeText(service.description || "Plašāka informācija pieejama pie mūsu speciālistiem.")}</p>
                            <a href="${safeText(detailPage)}">
                                <button>${safeText(buttonLabel)}</button>
                            </a>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    } catch (error) {
        console.error(error);
        container.innerHTML = "<p>Neizdevās ielādēt pakalpojumus. Mēģini vēlreiz vēlāk.</p>";
    }
}

document.addEventListener("DOMContentLoaded", loadServices);
