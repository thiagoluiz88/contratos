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

    const rows = Array.from(document.querySelectorAll("#aditivosRows tr[data-aditivo]"));
    const counts = rows.reduce((acc, row) => {
        const status = row.dataset.status || "Sem status";
        acc[status] = (acc[status] || 0) + 1;
        return acc;
    }, {});
    const labels = Object.keys(counts);
    const values = Object.values(counts);
    const total = values.reduce((sum, value) => sum + value, 0);
    const percents = values.map((value) => (total ? ((value / total) * 100).toFixed(1).replace(".", ",") : "0"));
    if (!labels.length) {
        labels.push("Sem aditivos");
        values.push(0);
        percents.push("0");
    }

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
                aditivosCenterText: { text: String(total) },
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
    const rows = Array.from(document.querySelectorAll("#aditivosRows tr[data-aditivo]"));
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
            counter.textContent = `Mostrando ${visible ? 1 : 0} a ${visible} de ${rows.length} aditivos`;
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
            openAditivoImportModal();
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

function openAditivoImportModal() {
    const modal = document.getElementById("aditivoImportModal");
    modal?.classList.add("is-open");
    modal?.setAttribute("aria-hidden", "false");
}

function closeAditivoImportModal() {
    const modal = document.getElementById("aditivoImportModal");
    modal?.classList.remove("is-open");
    modal?.setAttribute("aria-hidden", "true");
}

function setupAditivoImport() {
    const modal = document.getElementById("aditivoImportModal");
    const form = document.getElementById("aditivoImportForm");
    const dropzone = document.getElementById("aditivoDropzone");
    const input = document.getElementById("aditivoFileInput");
    const operatorSelect = document.getElementById("aditivoOperatorSelect");
    const fileLabel = document.getElementById("aditivoImportFile");
    const message = document.getElementById("aditivoImportMessage");
    const progress = document.getElementById("aditivoImportProgress");
    const progressBar = document.getElementById("aditivoImportProgressBar");
    const progressText = document.getElementById("aditivoImportProgressText");
    const submit = document.getElementById("submitAditivoImport");
    const close = document.getElementById("closeAditivoImport");
    const cancel = document.getElementById("cancelAditivoImport");
    const allowedExtensions = [".pdf", ".docx", ".doc", ".txt", ".md", ".jpg", ".jpeg", ".png", ".tif", ".tiff"];

    const setMessage = (text, type = "") => {
        if (!message) return;
        message.textContent = text;
        message.className = `contract-import-message ${type}`;
    };

    const setFile = (file) => {
        if (!file) return;
        const extension = `.${file.name.split(".").pop().toLowerCase()}`;
        if (!allowedExtensions.includes(extension)) {
            if (input) input.value = "";
            if (fileLabel) fileLabel.textContent = "Nenhum arquivo selecionado";
            setMessage("Formato não suportado. Envie PDF, DOCX, DOC, TXT, MD, JPG, PNG ou TIFF.", "error");
            return;
        }
        if (fileLabel) fileLabel.textContent = `Arquivo selecionado: ${file.name}`;
        setMessage("Arquivo pronto para importação. PDFs e imagens digitalizadas serão lidos com OCR quando necessário.", "success");
    };

    input?.addEventListener("change", () => setFile(input.files?.[0]));
    operatorSelect?.addEventListener("change", () => {
        if (operatorSelect.value && input?.files?.[0]) {
            setMessage("Arquivo pronto para importação. PDFs e imagens digitalizadas serão lidos com OCR quando necessário.", "success");
        }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
        dropzone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropzone.classList.add("is-dragging");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropzone?.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropzone.classList.remove("is-dragging");
        });
    });

    dropzone?.addEventListener("drop", (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (!file || !input) return;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        setFile(file);
    });

    [close, cancel].forEach((button) => {
        button?.addEventListener("click", closeAditivoImportModal);
    });

    modal?.addEventListener("click", (event) => {
        if (event.target === modal) closeAditivoImportModal();
    });

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const file = input?.files?.[0];
        const operatorName = operatorSelect?.value?.trim();

        if (!operatorName) {
            setMessage("Selecione o convênio do aditivo antes de importar.", "error");
            operatorSelect?.focus();
            return;
        }
        if (!file) {
            setMessage("Selecione um arquivo antes de importar.", "error");
            return;
        }

        const formData = new FormData(form);
        formData.set("file", file);
        formData.set("operator_name", operatorName);
        formData.set("import_mode", "additive");

        if (submit) submit.disabled = true;
        progress?.classList.add("is-visible");
        if (progressBar) progressBar.style.width = "35%";
        if (progressText) progressText.textContent = "Salvando aditivo e extraindo texto...";
        setMessage("");

        try {
            const response = await fetch("/contracts/import", {
                method: "POST",
                body: formData,
            });
            const responseText = await response.text();
            let data = {};
            try {
                data = responseText ? JSON.parse(responseText) : {};
            } catch (parseError) {
                data = { error: responseText || "Resposta inesperada do servidor." };
            }
            if (!response.ok) {
                throw new Error(data.error || "Não foi possível importar o aditivo.");
            }
            if (progressBar) progressBar.style.width = "100%";
            if (progressText) progressText.textContent = "Importação concluída.";
            setMessage(
                data.warning
                    ? `Aditivo importado com aviso: ${data.warning}`
                    : `Aditivo importado: ${data.additive_name}`,
                data.warning ? "warning" : "success",
            );
            window.setTimeout(() => {
                window.location.href = "/aditivos";
            }, 900);
        } catch (error) {
            if (progressBar) progressBar.style.width = "0";
            if (progressText) progressText.textContent = "Importação interrompida.";
            setMessage(error.message, "error");
        } finally {
            if (submit) submit.disabled = false;
        }
    });
}

window.addEventListener("DOMContentLoaded", () => {
    setupAditivosFilters();
    setupAditivoActions();
    setupAditivoImport();
});

window.addEventListener("load", renderAditivosStatusChart);
