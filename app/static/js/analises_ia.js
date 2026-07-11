function normalizeAiText(value) {
    return (value || "")
        .toString()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
}

function setupAiUpload() {
    const dropzone = document.getElementById("aiDropzone");
    const input = document.getElementById("aiFileInput");
    const fileName = document.getElementById("aiFileName");
    const replaceFile = document.getElementById("replaceFile");

    const setFile = (file) => {
        if (!file) return;
        fileName.textContent = file.name;

        const formData = new FormData();
        formData.append("file", file);
        fetch("/analises-ia/upload", {
            method: "POST",
            body: formData,
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.analysis_url) {
                    window.location.href = data.analysis_url;
                    return;
                }
                if (data.error) {
                    openAiModal("Falha no upload", data.error);
                }
            })
            .catch(() => {
                openAiModal("Falha no upload", "Não foi possível anexar e analisar este contrato.");
            });
    };

    dropzone?.addEventListener("click", () => input?.click());
    dropzone?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            input?.click();
        }
    });
    replaceFile?.addEventListener("click", () => input?.click());
    input?.addEventListener("change", () => setFile(input.files?.[0]));

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
        setFile(event.dataTransfer?.files?.[0]);
    });
}

function setupAiRun() {
    const button = document.getElementById("runAiAnalysis");
    const progress = document.getElementById("aiProgress");
    const bar = document.getElementById("aiProgressBar");
    const text = document.getElementById("aiProgressText");

    button?.addEventListener("click", () => {
        let value = 0;
        button.disabled = true;
        button.textContent = "Analisando contrato...";
        progress?.classList.add("is-visible");

        const timer = window.setInterval(() => {
            value = Math.min(value + 10, 100);
            if (bar) bar.style.width = `${value}%`;
            if (text) text.textContent = `Analisando contrato... ${value}%`;

            if (value >= 100) {
                window.clearInterval(timer);
                fetch(`/analises-ia/run${window.location.search}`, { method: "POST" })
                    .then((response) => response.json())
                    .then((data) => {
                        button.textContent = "Análise concluída";
                        openAiModal(
                            "Análise concluída",
                            `Score ${data.score}/100. ${data.falhas} falhas, ${data.clausulas_criticas} cláusulas críticas e ${data.oportunidades} oportunidades foram identificadas.`
                        );
                    })
                    .catch(() => {
                        button.textContent = "Reprocessar análise";
                        openAiModal("Análise não reprocessada", "Não foi possível reprocessar a análise neste momento.");
                    })
                    .finally(() => {
                        window.setTimeout(() => {
                            button.disabled = false;
                            button.textContent = "Analisar com IA";
                            progress?.classList.remove("is-visible");
                            if (bar) bar.style.width = "0";
                            if (text) text.textContent = "Analisando contrato... 0%";
                        }, 700);
                    });
            }
        }, 200);
    });
}

function setupAiTabs() {
    const tabs = Array.from(document.querySelectorAll(".ai-tabs button"));
    const panels = Array.from(document.querySelectorAll(".ai-tab-panel"));
    const mainColumn = document.querySelector(".ai-main-column");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            tabs.forEach((item) => item.classList.toggle("active", item === tab));
            panels.forEach((panel) => {
                panel.classList.toggle("active", panel.dataset.panel === target);
            });
            mainColumn?.classList.toggle("is-tab-detail", target !== "executivo");
        });
    });
}

function setupAiSearch() {
    const input = document.getElementById("aiGlobalSearch");
    const items = Array.from(document.querySelectorAll("[data-search]"));

    const applySearch = () => {
        const term = normalizeAiText(input?.value);
        items.forEach((item) => {
            const text = normalizeAiText(`${item.dataset.search} ${item.textContent}`);
            item.classList.toggle("is-hidden", Boolean(term && !text.includes(term)));
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

function openAiModal(title, text) {
    const modal = document.getElementById("aiModal");
    const modalTitle = document.getElementById("aiModalTitle");
    const modalText = document.getElementById("aiModalText");

    if (modalTitle) modalTitle.textContent = title;
    if (modalText) modalText.textContent = text;
    modal?.classList.add("is-open");
    modal?.setAttribute("aria-hidden", "false");
}

function setupAiActions() {
    const modal = document.getElementById("aiModal");
    const close = document.getElementById("closeAiModal");

    document.getElementById("changeContract")?.addEventListener("click", () => {
        window.location.href = "/contracts";
    });

    document.querySelectorAll(".js-new-analysis").forEach((button) => {
        button.addEventListener("click", () => {
            openAiModal("Nova análise", "Selecione ou substitua um arquivo para iniciar uma nova análise por IA.");
        });
    });

    document.querySelectorAll(".js-ai-detail").forEach((button) => {
        button.addEventListener("click", () => {
            const row = button.closest(".ai-failure-row");
            const title = row?.querySelector("strong")?.textContent || "Detalhes da falha";
            openAiModal(title, button.dataset.detail || "Revise esta cláusula, valide o risco com o jurídico e prepare uma proposta de ajuste para proteger o hospital.");
        });
    });

    document.getElementById("openActionPlan")?.addEventListener("click", () => {
        openAiModal(
            "Plano de ação",
            "Priorize pontos críticos, tabelas, reajuste, glosas, pagamento e rescisão. Em seguida, formalize uma contraproposta para a operadora."
        );
    });

    close?.addEventListener("click", () => {
        modal?.classList.remove("is-open");
        modal?.setAttribute("aria-hidden", "true");
    });

    modal?.addEventListener("click", (event) => {
        if (event.target === modal) {
            modal.classList.remove("is-open");
            modal.setAttribute("aria-hidden", "true");
        }
    });
}

window.addEventListener("DOMContentLoaded", () => {
    setupAiUpload();
    setupAiRun();
    setupAiTabs();
    setupAiSearch();
    setupAiActions();
});
