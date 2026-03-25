function safeAboutHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function renderAboutContentBlock(section) {
    const content = String(section.content || "").trim();
    const format = section.content_format || "paragraph";

    if (format === "list") {
        const items = content
            .split(/\r?\n/)
            .map((item) => item.trim())
            .filter(Boolean);

        return `
            <ul class="with-dots">
                ${items.map((item) => `<li>${safeAboutHtml(item)}</li>`).join("")}
            </ul>
        `;
    }

    return `<p>${safeAboutHtml(content)}</p>`;
}

async function loadAboutPage() {
    const titleElement = document.getElementById("aboutPageTitle");
    const sectionsContainer = document.getElementById("aboutSections");
    if (!titleElement || !sectionsContainer) {
        return;
    }

    try {
        const response = await fetch("/api/about");
        const data = await response.json();

        if (!response.ok) {
            throw new Error((data && data.error) || "Neizdevās ielādēt sadaļu “Par mums”.");
        }

        const sections = Array.isArray(data.sections) ? data.sections : [];
        titleElement.textContent = data.page_title || "Par mums";

        if (!sections.length) {
            sectionsContainer.innerHTML = `
                <section class="mb-5 row parmumsContent">
                    <div class="col-md-12">
                        <p>Sadaļas “Par mums” saturs pagaidām nav pieejams.</p>
                    </div>
                </section>
            `;
            return;
        }

        sectionsContainer.innerHTML = sections.map((section) => `
            <section class="mb-5 row parmumsContent">
                <div class="col-md-6">
                    <h2>${safeAboutHtml(section.title || "")}</h2>
                    ${renderAboutContentBlock(section)}
                </div>
                <div class="col-md-6">
                    <img
                        src="${safeAboutHtml(section.image_path || "/images/medicina.webp")}"
                        alt="${safeAboutHtml(section.image_alt || section.title || "Par mums")}"
                        class="img-fluid"
                    >
                </div>
            </section>
        `).join("");
    } catch (error) {
        console.error(error);
        sectionsContainer.innerHTML = `
            <section class="mb-5 row parmumsContent">
                <div class="col-md-12">
                    <p>Neizdevās ielādēt sadaļu “Par mums”. Mēģini vēlreiz vēlāk.</p>
                </div>
            </section>
        `;
    }
}

document.addEventListener("DOMContentLoaded", loadAboutPage);
