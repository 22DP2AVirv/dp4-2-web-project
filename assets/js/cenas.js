async function loadCatalog() {
    const catalogContainer = document.getElementById("priceCatalog");
    if (!catalogContainer) {
        return;
    }

    try {
        const response = await fetch("/api/catalog");
        const catalog = await response.json();

        if (!response.ok) {
            throw new Error("Neizdevās ielādēt pakalpojumu cenas.");
        }

        if (!catalog.length) {
            catalogContainer.innerHTML = "<p>Cenas pagaidām nav pieejamas.</p>";
            return;
        }

        catalogContainer.innerHTML = catalog.map((section) => {
            const items = (section.items || []).map((item) => {
                const price = Number(item.price).toFixed(2);
                return `
                    <div class="service-item">
                        <strong>${sectionSafeText(item.title)}</strong>
                        <span class="service-price">${price} €</span>
                    </div>
                `;
            }).join("");

            return `
                <div class="service-list">
                    <h4>${sectionSafeText(section.service_name)}</h4>
                    ${items || "<p>Šajā kategorijā pašlaik nav cenu ierakstu.</p>"}
                </div>
            `;
        }).join("");
    } catch (error) {
        console.error(error);
        catalogContainer.innerHTML = "<p>Neizdevās ielādēt cenas. Mēģini vēlreiz vēlāk.</p>";
    }
}

function sectionSafeText(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", loadCatalog);
