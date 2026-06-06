function normalizeComparisonText(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function renderEmptyComparison() {
    const selected = document.getElementById("selectedContracts");
    const head = document.getElementById("comparisonTableHead");
    const body = document.getElementById("comparisonTableBody");
    const ranking = document.getElementById("comparisonRanking");
    const highlights = document.getElementById("comparisonHighlights");

    if (selected) {
        selected.innerHTML = `
            <article class="comparison-contract-card">
                <div>
                    <strong>Nenhuma comparação criada</strong>
                    <small>Importe contratos reais e crie comparações para visualizar resultados.</small>
                </div>
            </article>
        `;
    }
    if (head) head.innerHTML = "";
    if (body) {
        body.innerHTML = `
            <tr>
                <td colspan="4">
                    <div class="empty-state inline">Nenhum dado real de comparação disponível.</div>
                </td>
            </tr>
        `;
    }
    if (ranking) {
        ranking.innerHTML = "<li><div><strong>Aguardando contratos reais</strong><small>Nenhum ranking calculado.</small></div></li>";
    }
    if (highlights) highlights.innerHTML = "";
}

function setupComparisonTabs() {
    const tabs = Array.from(document.querySelectorAll(".comparison-tabs button"));
    const placeholder = document.getElementById("comparisonPlaceholder");
    const placeholderTitle = document.getElementById("comparisonPlaceholderTitle");
    const summary = document.getElementById("comparisonSummary");
    const titles = {
        resumo: "Resumo Geral",
        clausulas: "Cláusulas removidas ou alteradas",
        reajustes: "Mudanças financeiras",
        prazos: "Mudanças de prazo",
        glosas: "Glosas e pagamento",
        rescisao: "Rescisão",
    };

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            tabs.forEach((item) => item.classList.toggle("active", item === tab));
            if (summary) summary.hidden = target !== "resumo";
            if (placeholder) placeholder.hidden = target === "resumo";
            if (placeholderTitle) placeholderTitle.textContent = titles[target] || "Resultado da comparação";
        });
    });
}

function setupComparisonSearch() {
    const input = document.getElementById("comparisonSearch");
    const items = Array.from(document.querySelectorAll("[data-search]"));
    input?.addEventListener("input", () => {
        const term = normalizeComparisonText(input.value);
        items.forEach((item) => {
            const text = normalizeComparisonText(`${item.dataset.search} ${item.textContent}`);
            item.classList.toggle("is-hidden", Boolean(term && !text.includes(term)));
        });
    });
}

window.addEventListener("DOMContentLoaded", () => {
    renderEmptyComparison();
    setupComparisonTabs();
    setupComparisonSearch();
});
