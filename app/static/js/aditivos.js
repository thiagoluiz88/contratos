const aditivoStatusColors = ["#00843D", "#F97316", "#7C3AED", "#3B82F6"];

const aditivoCenterTextPlugin = {
    id: "aditivosCenterText",
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

function normalizeAditivoText(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function renderAditivosStatusChart() {
    const canvas = document.getElementById("aditivosStatusChart");
    const legend = document.getElementById("aditivosStatusLegend");
    if (!canvas || !window.Chart) return;

    const labels = ["Ativos", "Pendentes", "Vencendo", "Vencidos"];
    const values = [44, 7, 5, 2];
    const percents = ["78,6", "12,5", "8,9", "3,6"];

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: aditivoStatusColors,
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
                aditivosCenterText: { text: "56" },
            },
        },
        plugins: [aditivoCenterTextPlugin],
    });

    if (legend) {
        legend.innerHTML = labels.map((label, index) => `
            <li>
                <span class="legend-name">
                    <i class="legend-dot" style="background:${aditivoStatusColors[index]}"></i>
                    ${label}
                </span>
                <strong>${values[index]} (${percents[index]}%)</strong>
            </li>
        `).join("");
    }
}

function setupAditivosFilters() {
    const rows = Array.from(document.querySelectorAll("#aditivosRows tr"));
    const globalSearch = document.getElementById("globalAditivoSearch");
    const tableSearch = document.getElementById("aditivoTableSearch");
    const contractFilter = document.getElementById("contractFilter");
    const operatorFilter = document.getElementById("aditivoOperatorFilter");
    const typeFilter = document.getElementById("aditivoTypeFilter");
    const statusFilter = document.getElementById("aditivoStatusFilter");
    const termFilter = document.getElementById("aditivoTermFilter");
    const clearFilters = document.getElementById("clearAditivoFilters");
    const counter = document.getElementById("aditivoTableCounter");
    const statusBadge = document.getElementById("aditivoStatusBadge");
    const periodBadge = document.getElementById("aditivoPeriodBadge");

    const applyFilters = () => {
        const searchTerm = normalizeAditivoText(tableSearch?.value || globalSearch?.value || "");
        const contract = normalizeAditivoText(contractFilter?.value);
        const operator = normalizeAditivoText(operatorFilter?.value);
        const type = normalizeAditivoText(typeFilter?.value);
        const status = normalizeAditivoText(statusFilter?.value);

        let visible = 0;

        rows.forEach((row) => {
            const searchableText = normalizeAditivoText([
                row.dataset.aditivo,
                row.dataset.contract,
                row.dataset.operator,
                row.dataset.responsible,
                row.dataset.object,
                row.dataset.type,
                row.dataset.status,
                row.textContent,
            ].join(" "));
            const matchesSearch = !searchTerm || searchableText.includes(searchTerm);
            const matchesContract = !contract || normalizeAditivoText(row.dataset.contract) === contract;
            const matchesOperator = !operator || normalizeAditivoText(row.dataset.operator) === operator;
            const matchesType = !type || normalizeAditivoText(row.dataset.type) === type;
            const matchesStatus = !status || normalizeAditivoText(row.dataset.status) === status;
            const show = matchesSearch && matchesContract && matchesOperator && matchesType && matchesStatus;

            row.classList.toggle("is-hidden", !show);
            if (show) visible += 1;
        });

        if (counter) {
            counter.textContent = `Mostrando ${visible ? 1 : 0} a ${visible} de 56 aditivos`;
        }
        if (statusBadge) {
            statusBadge.textContent = `Status: ${statusFilter?.value || "Todos"}`;
        }
        if (periodBadge) {
            periodBadge.textContent = `Período: ${termFilter?.value || "Todos"}`;
        }
    };

    [globalSearch, tableSearch, contractFilter, operatorFilter, typeFilter, statusFilter, termFilter].forEach((element) => {
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
        if (contractFilter) contractFilter.value = "";
        if (operatorFilter) operatorFilter.value = "";
        if (typeFilter) typeFilter.value = "";
        if (statusFilter) statusFilter.value = "";
        if (termFilter) termFilter.value = "";
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

function setupAditivoActions() {
    document.querySelectorAll(".js-new-aditivo").forEach((button) => {
        button.addEventListener("click", () => {
            window.location.href = "/aditivos/new";
        });
    });

    document.querySelectorAll("#aditivosRows .row-actions button").forEach((button) => {
        button.addEventListener("click", () => {
            const action = button.dataset.action;
            const messages = {
                view: "Visualizar aditivo",
                edit: "Editar aditivo",
                more: "Mais opções",
            };
            alert(messages[action] || "Ação do aditivo");
        });
    });
}

window.addEventListener("DOMContentLoaded", () => {
    setupAditivosFilters();
    setupAditivoActions();
});

window.addEventListener("load", renderAditivosStatusChart);
