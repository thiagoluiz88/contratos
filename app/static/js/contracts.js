const statusColors = ["#00843D", "#F97316", "#EF4444", "#94A3B8", "#7C3AED"];

const centerTextPlugin = {
    id: "contractsCenterText",
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
        ctx.fillText("Total", x, y + 16);
        ctx.restore();
    },
};

function normalizeText(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function renderStatusChart() {
    const canvas = document.getElementById("contractsStatusChart");
    const legend = document.getElementById("contractsStatusLegend");
    if (!canvas || !window.Chart) return;

    const labels = ["Ativos", "Vencendo", "Vencidos", "Suspensos", "Rescindidos"];
    const values = [102, 15, 7, 3, 1];
    const percents = ["79,7", "11,7", "5,5", "2,3", "0,8"];

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: statusColors,
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
                            return `${context.label}: ${context.raw} (${percents[context.dataIndex]}%)`;
                        },
                    },
                },
                contractsCenterText: { text: "128" },
            },
        },
        plugins: [centerTextPlugin],
    });

    if (legend) {
        legend.innerHTML = labels.map((label, index) => `
            <li>
                <span class="legend-name">
                    <i class="legend-dot" style="background:${statusColors[index]}"></i>
                    ${label}
                </span>
                <strong>${values[index]} (${percents[index]}%)</strong>
            </li>
        `).join("");
    }
}

function setupContractsFilters() {
    const rows = Array.from(document.querySelectorAll("#contractsRows tr"));
    const globalSearch = document.getElementById("globalContractSearch");
    const tableSearch = document.getElementById("tableSearch");
    const operatorFilter = document.getElementById("operatorFilter");
    const statusFilter = document.getElementById("statusFilter");
    const clearFilters = document.getElementById("clearFilters");
    const counter = document.getElementById("tableCounter");
    const statusBadge = document.getElementById("statusBadge");
    const periodBadge = document.getElementById("periodBadge");
    const termFilter = document.getElementById("termFilter");

    const applyFilters = () => {
        const searchTerm = normalizeText(tableSearch?.value || globalSearch?.value || "");
        const operator = normalizeText(operatorFilter?.value);
        const status = normalizeText(statusFilter?.value);

        let visible = 0;

        rows.forEach((row) => {
            const rowText = normalizeText(row.textContent);
            const rowOperator = normalizeText(row.dataset.operator);
            const rowStatus = normalizeText(row.dataset.status);
            const matchesSearch = !searchTerm || rowText.includes(searchTerm);
            const matchesOperator = !operator || rowOperator === operator;
            const matchesStatus = !status || rowStatus === status;
            const show = matchesSearch && matchesOperator && matchesStatus;

            row.classList.toggle("is-hidden", !show);
            if (show) visible += 1;
        });

        if (counter) {
            counter.textContent = `Mostrando ${visible ? 1 : 0} a ${visible} de 128 contratos`;
        }
        if (statusBadge) {
            statusBadge.textContent = `Status: ${statusFilter?.value || "Todos"}`;
        }
        if (periodBadge) {
            periodBadge.textContent = `Período: ${termFilter?.value || "Todos"}`;
        }
    };

    [globalSearch, tableSearch, operatorFilter, statusFilter, termFilter].forEach((element) => {
        element?.addEventListener("input", applyFilters);
        element?.addEventListener("change", applyFilters);
    });

    globalSearch?.addEventListener("input", () => {
        if (tableSearch && tableSearch.value !== globalSearch.value) {
            tableSearch.value = globalSearch.value;
        }
    });

    tableSearch?.addEventListener("input", () => {
        if (globalSearch && globalSearch.value !== tableSearch.value) {
            globalSearch.value = tableSearch.value;
        }
    });

    clearFilters?.addEventListener("click", () => {
        if (globalSearch) globalSearch.value = "";
        if (tableSearch) tableSearch.value = "";
        if (operatorFilter) operatorFilter.value = "";
        if (statusFilter) statusFilter.value = "";
        if (termFilter) termFilter.value = "Todas";
        applyFilters();
    });

    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            globalSearch?.focus();
        }
    });

    applyFilters();
}

function setupContractActions() {
    document.querySelectorAll(".js-new-contract").forEach((button) => {
        button.addEventListener("click", () => {
            alert("Fluxo de novo contrato pronto para conectar em /contracts/new.");
        });
    });

    document.querySelectorAll(".row-actions button").forEach((button) => {
        button.addEventListener("click", () => {
            const contract = button.closest("tr")?.dataset.contract || "contrato";
            const action = button.dataset.action;
            const messages = {
                view: `Visualizar contrato ${contract}`,
                edit: `Editar contrato ${contract}`,
                more: `Mais opções para ${contract}`,
            };
            alert(messages[action] || `Ação em ${contract}`);
        });
    });
}

window.addEventListener("DOMContentLoaded", () => {
    setupContractsFilters();
    setupContractActions();
});

window.addEventListener("load", renderStatusChart);
