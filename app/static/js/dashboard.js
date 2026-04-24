const chartColors = {
    green: "#00843D",
    greenDark: "#006B32",
    greenLight: "#EAF8F0",
    red: "#EF4444",
    orange: "#F97316",
    yellow: "#FACC15",
    blue: "#3B82F6",
    purple: "#7C3AED",
    muted: "#E5E7EB",
};

const centerTextPlugin = {
    id: "centerText",
    afterDraw(chart, args, options) {
        if (!options?.text) return;

        const { ctx, chartArea } = chart;
        const x = (chartArea.left + chartArea.right) / 2;
        const y = (chartArea.top + chartArea.bottom) / 2;

        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#101828";
        ctx.font = "800 26px Inter, system-ui, Arial";
        ctx.fillText(options.text, x, y - 8);
        ctx.fillStyle = "#667085";
        ctx.font = "600 12px Inter, system-ui, Arial";
        ctx.fillText(options.label || "Total", x, y + 16);
        ctx.restore();
    },
};

function buildLegend(elementId, labels, values, percentages, colors) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.innerHTML = labels.map((label, index) => `
        <li>
            <span class="legend-name">
                <i class="legend-dot" style="background:${colors[index]}"></i>
                ${label}
            </span>
            <strong>${values[index]} (${percentages[index]}%)</strong>
        </li>
    `).join("");
}

function makeDoughnut(canvasId, legendId, labels, values, percentages, colors, total) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: "#FFFFFF",
                borderWidth: 4,
                hoverOffset: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "72%",
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label(context) {
                            return `${context.label}: ${context.raw} (${percentages[context.dataIndex]}%)`;
                        },
                    },
                },
                centerText: { text: String(total), label: "Total" },
            },
        },
        plugins: [centerTextPlugin],
    });

    buildLegend(legendId, labels, values, percentages, colors);
}

function renderExpirationChart() {
    const canvas = document.getElementById("expirationChart");
    if (!canvas || !window.Chart) return;

    new Chart(canvas, {
        type: "bar",
        data: {
            labels: ["Vencidos", "Até 30 dias", "31 a 60 dias", "61 a 90 dias", "91 a 120 dias", "121 a 150 dias", "+150 dias"],
            datasets: [{
                label: "Contratos",
                data: [7, 15, 28, 34, 22, 12, 10],
                borderRadius: 10,
                backgroundColor: chartColors.green,
                hoverBackgroundColor: chartColors.greenDark,
                maxBarThickness: 42,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: "#667085", font: { weight: 600 } },
                    border: { display: false },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: "#EEF2F6" },
                    ticks: { color: "#667085", precision: 0 },
                    border: { display: false },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#101828",
                    padding: 12,
                    titleFont: { weight: 800 },
                },
            },
        },
    });
}

function setupSearch() {
    const input = document.getElementById("contractSearch");
    const rows = Array.from(document.querySelectorAll("#contractsTable tr"));
    if (!input) return;

    input.addEventListener("input", () => {
        const term = input.value.trim().toLowerCase();
        rows.forEach((row) => {
            const text = row.textContent.toLowerCase();
            row.classList.toggle("is-hidden", term && !text.includes(term));
        });
    });
}

function setupActions() {
    const button = document.getElementById("newContractButton");
    button?.addEventListener("click", () => {
        alert("Fluxo de novo contrato pronto para conectar em /contracts/new.");
    });
}

function renderCharts() {
    renderExpirationChart();

    makeDoughnut(
        "operatorChart",
        "operatorLegend",
        ["Unimed", "Amil", "Bradesco Saúde", "SulAmérica", "Hapvida", "Outras"],
        [32, 24, 18, 16, 14, 24],
        [25, 19, 14, 12, 11, 19],
        [chartColors.green, chartColors.blue, chartColors.purple, chartColors.orange, chartColors.red, "#94A3B8"],
        128,
    );

    makeDoughnut(
        "statusChart",
        "statusLegend",
        ["Ativos", "Vencendo", "Vencidos", "Suspensos", "Rescindidos", "Em negociação"],
        [128, 15, 7, 10, 8, 20],
        [68, 8, 4, 5, 4, 11],
        [chartColors.green, chartColors.orange, chartColors.red, chartColors.blue, chartColors.purple, "#94A3B8"],
        128,
    );

    makeDoughnut(
        "tableTypeChart",
        "tableTypeLegend",
        ["CBHPM", "Tabela própria", "SIMPRO", "Brasíndice", "Outras"],
        [52, 28, 18, 12, 18],
        [41, 22, 14, 9, 14],
        [chartColors.green, chartColors.blue, chartColors.purple, chartColors.orange, "#94A3B8"],
        128,
    );
}

window.addEventListener("DOMContentLoaded", () => {
    setupSearch();
    setupActions();
});

window.addEventListener("load", renderCharts);
