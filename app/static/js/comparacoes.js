const comparisonContracts = [
    {
        id: "CT-2024-0021",
        operadora: "Unimed São Paulo",
        score: 82,
        equilibrio: 80,
        seguranca: 78,
        protecao: 75,
        prazoPagamento: "30 dias",
        reajuste: "IPCA",
        vigencia: "12 meses",
        multa: "10%",
        clausulasCriticas: 8,
        lgpd: "Atende",
        color: "#00843D",
        markerClass: "green",
        logo: "□",
    },
    {
        id: "CT-2024-0018",
        operadora: "Amil Assistência",
        score: 75,
        equilibrio: 70,
        seguranca: 65,
        protecao: 68,
        prazoPagamento: "45 dias",
        reajuste: "Sem índice definido",
        vigencia: "12 meses",
        multa: "20%",
        clausulasCriticas: 12,
        lgpd: "Atende",
        color: "#7C3AED",
        markerClass: "purple",
        logo: "amil",
    },
    {
        id: "CT-2024-0033",
        operadora: "Bradesco Saúde",
        score: 85,
        equilibrio: 85,
        seguranca: 80,
        protecao: 78,
        prazoPagamento: "28 dias",
        reajuste: "IPCA",
        vigencia: "12 meses",
        multa: "15%",
        clausulasCriticas: 6,
        lgpd: "Atende",
        color: "#F59E0B",
        markerClass: "orange",
        logo: "B",
    },
    {
        id: "CT-2024-0042",
        operadora: "SulAmérica Saúde",
        score: 79,
        equilibrio: 76,
        seguranca: 74,
        protecao: 72,
        prazoPagamento: "35 dias",
        reajuste: "IPCA",
        vigencia: "24 meses",
        multa: "12%",
        clausulasCriticas: 9,
        lgpd: "Atende",
        color: "#3B82F6",
        markerClass: "blue",
        logo: "S",
    },
];

let activeContracts = comparisonContracts.slice(0, 3);
let comparisonChart;

const criteria = [
    { label: "Score geral", key: "score", type: "score", best: "max" },
    { label: "Equilíbrio contratual", key: "equilibrio", type: "score", best: "max" },
    { label: "Segurança jurídica", key: "seguranca", type: "score", best: "max" },
    { label: "Proteção financeira", key: "protecao", type: "score", best: "max" },
    { label: "Prazos de pagamento média", key: "prazoPagamento", type: "days", best: "min" },
    { label: "Reajuste anual", key: "reajuste", type: "text", best: "tie" },
    { label: "Vigência contratual", key: "vigencia", type: "text", best: "tie" },
    { label: "Multa contratual rescisão", key: "multa", type: "percent", best: "min" },
    { label: "Cláusulas críticas identificadas", key: "clausulasCriticas", type: "number", best: "min" },
    { label: "Conformidade legal LGPD", key: "lgpd", type: "text", best: "tie" },
];

function normalizeComparisonText(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function numericValue(contract, criterion) {
    const value = contract[criterion.key];
    if (criterion.type === "days") return Number.parseInt(value, 10);
    if (criterion.type === "percent") return Number.parseInt(value, 10);
    return Number(value);
}

function getBestLabel(criterion) {
    if (!activeContracts.length || criterion.best === "tie") return "Empate";

    const values = activeContracts.map((contract) => numericValue(contract, criterion));
    const bestValue = criterion.best === "max" ? Math.max(...values) : Math.min(...values);
    const winners = activeContracts.filter((contract) => numericValue(contract, criterion) === bestValue);
    return winners.length === 1 ? winners[0].id : "Empate";
}

function isBestValue(contract, criterion) {
    return getBestLabel(criterion) === contract.id;
}

function getAttentionClass(contract, criterion) {
    if (isBestValue(contract, criterion)) return "best";
    if (criterion.type === "score" && contract[criterion.key] < 70) return "critical";
    if (criterion.key === "reajuste" && contract.reajuste.includes("Sem")) return "critical";
    if (criterion.key === "clausulasCriticas" && contract.clausulasCriticas >= 10) return "critical";
    if (criterion.type === "score" && contract[criterion.key] < 78) return "attention";
    if (criterion.type === "days" && numericValue(contract, criterion) > 35) return "attention";
    if (criterion.type === "percent" && numericValue(contract, criterion) >= 15) return "attention";
    return "neutral";
}

function formatCell(contract, criterion) {
    const value = contract[criterion.key];
    const className = getAttentionClass(contract, criterion);

    if (criterion.type === "score") {
        return `
            <div class="comparison-score-cell ${className}">
                <span><b style="width:${value}%"></b></span>
                <strong>${value}/100</strong>
            </div>
        `;
    }

    return `<span class="comparison-value-pill ${className}">${value}</span>`;
}

function renderSelectedContracts() {
    const container = document.getElementById("selectedContracts");
    if (!container) return;

    const cards = activeContracts.map((contract, index) => `
        <article class="comparison-contract-card" data-search="${contract.id} ${contract.operadora}">
            <span class="comparison-marker ${contract.markerClass}">${index + 1}</span>
            <span class="comparison-contract-logo">${contract.logo}</span>
            <div>
                <strong>${contract.id}</strong>
                <small>${contract.operadora}</small>
            </div>
            <button type="button" data-remove="${contract.id}" aria-label="Remover ${contract.id}">×</button>
        </article>
    `).join("");

    const addCard = activeContracts.length < 4 ? `
        <button id="addContract" class="comparison-add-card" type="button">
            <strong>+ Adicionar contrato</strong>
            <small>Máx. 4 contratos</small>
        </button>
    ` : "";

    container.innerHTML = cards + addCard;

    container.querySelectorAll("[data-remove]").forEach((button) => {
        button.addEventListener("click", () => {
            activeContracts = activeContracts.filter((contract) => contract.id !== button.dataset.remove);
            renderComparison();
        });
    });

    container.querySelector("#addContract")?.addEventListener("click", () => {
        const next = comparisonContracts.find((contract) => !activeContracts.some((active) => active.id === contract.id));
        if (!next) {
            alert("Limite máximo de 4 contratos atingido.");
            return;
        }
        activeContracts.push(next);
        renderComparison();
    });
}

function renderComparisonTable() {
    const head = document.getElementById("comparisonTableHead");
    const body = document.getElementById("comparisonTableBody");
    if (!head || !body) return;

    head.innerHTML = `
        <tr>
            <th>Critério</th>
            ${activeContracts.map((contract) => `<th>${contract.id}<small>${contract.operadora}</small></th>`).join("")}
            <th>Melhor opção</th>
        </tr>
    `;

    body.innerHTML = criteria.map((criterion) => {
        const best = getBestLabel(criterion);
        return `
            <tr data-search="${criterion.label} ${activeContracts.map((contract) => `${contract.id} ${contract.operadora} ${contract[criterion.key]}`).join(" ")} ${best}">
                <td><strong>${criterion.label}</strong></td>
                ${activeContracts.map((contract) => `<td>${formatCell(contract, criterion)}</td>`).join("")}
                <td><span class="comparison-best-pill ${best === "Empate" ? "tie" : "best"}">${best}</span></td>
            </tr>
        `;
    }).join("");
}

function renderRanking() {
    const ranking = document.getElementById("comparisonRanking");
    if (!ranking) return;

    const medals = ["ouro", "prata", "bronze", "azul"];
    const sorted = [...activeContracts].sort((a, b) => b.score - a.score);

    ranking.innerHTML = sorted.map((contract, index) => `
        <li data-search="${contract.id} ${contract.operadora} ${contract.score}">
            <span class="medal ${medals[index] || "azul"}">${index + 1}</span>
            <div><strong>${contract.id}</strong><small>${contract.operadora}</small></div>
            <b>${contract.score}/100</b>
        </li>
    `).join("");
}

function renderChart() {
    const canvas = document.getElementById("comparisonScoreChart");
    if (!canvas || !window.Chart) return;

    const data = {
        labels: activeContracts.map((contract) => `${contract.id} ${contract.operadora.split(" ")[0]}`),
        datasets: [{
            label: "Score",
            data: activeContracts.map((contract) => contract.score),
            backgroundColor: activeContracts.map((contract) => contract.color),
            borderRadius: 10,
        }],
    };

    if (comparisonChart) {
        comparisonChart.data = data;
        comparisonChart.update();
        return;
    }

    comparisonChart = new Chart(canvas, {
        type: "bar",
        data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: "#EEF2F6" },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: "#667085", font: { weight: "700" } },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label(context) {
                            return `Score: ${context.raw}/100`;
                        },
                    },
                },
            },
        },
    });
}

function setupComparisonTabs() {
    const buttons = document.querySelectorAll(".comparison-tabs button");
    const summary = document.getElementById("comparisonSummary");
    const highlights = document.getElementById("comparisonHighlights");
    const placeholder = document.getElementById("comparisonPlaceholder");
    const placeholderTitle = document.getElementById("comparisonPlaceholderTitle");

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            buttons.forEach((item) => item.classList.toggle("active", item === button));
            const isSummary = button.dataset.tab === "resumo";
            if (summary) summary.hidden = !isSummary;
            if (highlights) highlights.hidden = !isSummary;
            if (placeholder) placeholder.hidden = isSummary;
            if (placeholderTitle) placeholderTitle.textContent = isSummary ? "" : `${button.textContent} em desenvolvimento`;
            if (!isSummary) alert("Conteúdo da aba em desenvolvimento");
        });
    });
}

function setupComparisonSearch() {
    const input = document.getElementById("comparisonSearch");

    const applySearch = () => {
        const term = normalizeComparisonText(input?.value);
        document.querySelectorAll("[data-search]").forEach((element) => {
            const text = normalizeComparisonText(`${element.dataset.search} ${element.textContent}`);
            element.classList.toggle("is-hidden", Boolean(term && !text.includes(term)));
        });
    };

    input?.addEventListener("input", applySearch);
    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            input?.focus();
        }
    });
}

function setupComparisonActions() {
    document.getElementById("newComparison")?.addEventListener("click", () => {
        activeContracts = [];
        renderComparison();
        alert("Nova comparação iniciada. Adicione contratos para comparar.");
    });

    document.getElementById("exportComparison")?.addEventListener("click", () => {
        alert("Exportação da comparação simulada.");
    });
}

function renderComparison() {
    renderSelectedContracts();
    renderComparisonTable();
    renderRanking();
    renderChart();
}

window.addEventListener("DOMContentLoaded", () => {
    setupComparisonTabs();
    setupComparisonSearch();
    setupComparisonActions();
});

window.addEventListener("load", renderComparison);
