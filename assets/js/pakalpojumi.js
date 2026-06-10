// Pakalpojumu kartīšu skripts: ielādē pakalpojumus no API un attēlo tos lapā.
function safeText(value) {
    // Dinamisko tekstu pārvērš drošā HTML tekstā.
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function resolveCardAction(service, container) {
    // Nosaka, vai kartītes poga ved uz detalizētu lapu vai pieraksta formu.
    const mode = container.dataset.cardMode || "details";
    const meta = service.public_meta || {};

    if (mode === "appointment") {
        return {
            href: "pieteikties.html",
            label: "Pieteikties"
        };
    }

    return {
        href: meta.detail_page || "pieteikties.html",
        label: meta.button_label || "Pieteikties"
    };
}

async function loadServices() {
    // Ielādē pakalpojumu katalogu un izveido kartītes.
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
            const action = resolveCardAction(service, container);

            return `
                <div class="col-md-4 d-flex justify-content-center">
                    <div class="card">
                        <img src="${safeText(imagePath)}" alt="${safeText(service.service_name)}">
                        <div class="card-content">
                            <h3>${safeText(service.service_name)}</h3>
                            <p>${safeText(service.description || "Plašāka informācija pieejama pie mūsu speciālistiem.")}</p>
                            <a href="${safeText(action.href)}">
                                <button>${safeText(action.label)}</button>
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
