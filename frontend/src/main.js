import './style.css';

const API_BASE = import.meta.env.DEV ? "" : "https://leads-kjne.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
    // Form and Scrape elements
    const scrapeForm = document.getElementById("scrape-form");
    const queryInput = document.getElementById("search-query");
    const limitInput = document.getElementById("search-limit");
    const startBtn = document.getElementById("start-btn");
    const terminalConsole = document.getElementById("terminal-console");
    const statusBadge = document.getElementById("status-badge");
    const resultsSection = document.getElementById("results-section");
    const stopBtn = document.getElementById("stop-btn");
    const locationFilter = document.getElementById("location-filter");

    // Metrics elements
    const statEvaluated = document.getElementById("stat-evaluated");
    const statLeadsFound = document.getElementById("stat-leads-found");
    const statEmails = document.getElementById("stat-emails");

    // Table elements
    const leadsTableBody = document.getElementById("leads-table-body");
    const downloadCsvBtn = document.getElementById("download-csv-btn");
    const openExportModalBtn = document.getElementById("open-export-modal-btn");

    // Export Modal elements
    const exportModal = document.getElementById("export-modal");
    const exportForm = document.getElementById("export-form");
    const sheetNameInput = document.getElementById("sheet-name-input");
    const worksheetNameInput = document.getElementById("worksheet-name-input");
    const closeModalBtn = document.getElementById("close-modal-btn");
    const cancelExportBtn = document.getElementById("cancel-export-btn");
    const modalConsole = document.getElementById("modal-console");

    let currentTaskId = null;
    let pollInterval = null;
    let renderedLogCount = 0;
    let allLeads = [];

    // Helper: Reset UI for a new run
    function resetUI() {
        terminalConsole.innerHTML = '<div class="terminal-line info">&gt; System: Scraper initializing...</div>';
        resultsSection.classList.remove("hide");
        statEvaluated.textContent = "0";
        statLeadsFound.textContent = "0";
        statEmails.textContent = "0";
        leadsTableBody.innerHTML = `
            <tr>
                <td colspan="4" class="empty-table-msg">
                    <i class="fa-solid fa-spinner fa-spin"></i> Initializing crawler agent...
                </td>
            </tr>
        `;
        downloadCsvBtn.disabled = true;
        openExportModalBtn.disabled = true;
        renderedLogCount = 0;
        locationFilter.value = "";
        allLeads = [];
    }

    // Helper: Append log line to console
    function appendTerminalLog(logMessage) {
        const logLower = logMessage.toLowerCase();
        let logClass = "info";

        if (logLower.includes("error") || logLower.includes("failed") || logLower.includes("fatal") || logLower.includes("exception")) {
            logClass = "error";
        } else if (logLower.includes("success") || logLower.includes("completed") || logLower.includes("added") || logLower.includes("finished") || logLower.includes("complete")) {
            logClass = "success";
        } else if (logLower.includes("warning") || logLower.includes("skipping") || logLower.includes("already") || logLower.includes("skip")) {
            logClass = "warning";
        }

        const div = document.createElement("div");
        div.className = `terminal-line ${logClass}`;
        div.textContent = `> ${logMessage}`;
        terminalConsole.appendChild(div);
        terminalConsole.scrollTop = terminalConsole.scrollHeight;
    }

    // Helper: Render Leads Table
    function renderLeads(leads) {
        if (!leads || leads.length === 0) {
            leadsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="empty-table-msg">
                        <i class="fa-solid fa-hourglass-half"></i> Crawling maps. Waiting for website-less leads...
                    </td>
                </tr>
            `;
            return;
        }

        leadsTableBody.innerHTML = "";
        leads.forEach(lead => {
            const tr = document.createElement("tr");

            // Name
            const tdName = document.createElement("td");
            tdName.textContent = lead.Name || lead.name || "Not listed";
            tr.appendChild(tdName);

            // Phone
            const tdPhone = document.createElement("td");
            tdPhone.textContent = lead.Phone || lead.phone || "Not listed";
            tr.appendChild(tdPhone);

            // Address
            const tdAddress = document.createElement("td");
            tdAddress.textContent = lead.Address || lead.address || "Not listed";
            tr.appendChild(tdAddress);

            // Emails (Tags)
            const tdEmails = document.createElement("td");
            const emailStr = lead.Email || lead.email || "";
            if (emailStr && emailStr !== "Not found" && emailStr !== "Not listed") {
                const emails = emailStr.split(",").map(e => e.trim());
                const wrapper = document.createElement("div");
                wrapper.className = "email-tags-wrapper";
                emails.forEach(email => {
                    const tag = document.createElement("span");
                    tag.className = "email-tag";
                    tag.textContent = email;
                    wrapper.appendChild(tag);
                });
                tdEmails.appendChild(wrapper);
            } else {
                tdEmails.innerHTML = `<span class="text-muted" style="font-size:0.88rem; font-style:italic;">None extracted</span>`;
            }
            tr.appendChild(tdEmails);

            leadsTableBody.appendChild(tr);
        });
    }

    // Helper: Parse statistics from logs and leads
    function updateMetrics(logs, leads) {
        // Count lines that begin with "-> " (indicates a business evaluated)
        let evaluatedCount = 0;
        logs.forEach(log => {
            if (log.trim().startsWith("->")) {
                evaluatedCount++;
            }
        });
        statEvaluated.textContent = evaluatedCount;

        // Leads Found
        statLeadsFound.textContent = leads.length;

        // Total Emails Extracted (sum of all emails across leads)
        let emailCount = 0;
        leads.forEach(lead => {
            const emailStr = lead.Email || lead.email || "";
            if (emailStr && emailStr !== "Not found" && emailStr !== "Not listed") {
                emailCount += emailStr.split(",").length;
            }
        });
        statEmails.textContent = emailCount;
    }

    // Helper: Update Badge State
    function updateBadge(status) {
        statusBadge.className = "badge";
        const badgeText = statusBadge.querySelector(".badge-text");

        if (status === "running") {
            statusBadge.classList.add("badge-running");
            badgeText.textContent = "Agent Active";
        } else if (status === "completed") {
            statusBadge.classList.add("badge-completed");
            badgeText.textContent = "Finished";
        } else if (status === "failed") {
            statusBadge.classList.add("badge-failed");
            badgeText.textContent = "Error";
        } else if (status === "stopped") {
            statusBadge.classList.add("badge-failed");
            badgeText.textContent = "Stopped";
        } else {
            statusBadge.classList.add("badge-idle");
            badgeText.textContent = "System Idle";
        }
    }

    // Polling function
    async function pollStatus() {
        try {
            const res = await fetch(`${API_BASE}/api/status/${currentTaskId}`);
            if (!res.ok) throw new Error("Failed to fetch task status.");
            const data = await res.json();

            // Append new logs
            if (data.logs && data.logs.length > renderedLogCount) {
                for (let i = renderedLogCount; i < data.logs.length; i++) {
                    appendTerminalLog(data.logs[i]);
                }
                renderedLogCount = data.logs.length;
            }

            // Render tables & metrics
            allLeads = data.leads || [];
            applyLocationFilter();
            updateMetrics(data.logs, allLeads);
            updateBadge(data.status);

            // Handle completion, failure or stopped
            if (data.status === "completed" || data.status === "failed" || data.status === "stopped") {
                clearInterval(pollInterval);
                startBtn.disabled = false;
                startBtn.querySelector(".btn-text").textContent = "Start Scraping Agent";
                startBtn.querySelector("i").className = "fa-solid fa-play";
                stopBtn.classList.add("hide");
                stopBtn.disabled = false;
                stopBtn.querySelector("i").className = "fa-solid fa-stop";

                if (data.leads && data.leads.length > 0) {
                    downloadCsvBtn.disabled = false;
                    openExportModalBtn.disabled = false;
                } else {
                    leadsTableBody.innerHTML = `
                        <tr>
                            <td colspan="4" class="empty-table-msg">
                                <i class="fa-solid fa-ban"></i> Scraping complete. No leads found that meet criteria (Website-less).
                            </td>
                        </tr>
                    `;
                }
            }
        } catch (err) {
            console.error(err);
            appendTerminalLog(`System Error: ${err.message}`);
            clearInterval(pollInterval);
            startBtn.disabled = false;
            updateBadge("failed");
        }
    }

    // Submit scrape task
    scrapeForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const query = queryInput.value.trim();
        const limit = parseInt(limitInput.value, 10);

        if (!query) return;

        resetUI();
        startBtn.disabled = true;
        startBtn.querySelector(".btn-text").textContent = "Agent Working...";
        startBtn.querySelector("i").className = "fa-solid fa-circle-notch fa-spin";
        stopBtn.classList.remove("hide");
        updateBadge("running");

        try {
            const res = await fetch(`${API_BASE}/api/scrape`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, limit })
            });

            if (!res.ok) throw new Error("Could not start scraping task.");
            const data = await res.json();

            currentTaskId = data.task_id;
            
            // Start polling status
            pollInterval = setInterval(pollStatus, 1000);
        } catch (err) {
            appendTerminalLog(`System Connection Error: ${err.message}`);
            startBtn.disabled = false;
            startBtn.querySelector(".btn-text").textContent = "Start Scraping Agent";
            startBtn.querySelector("i").className = "fa-solid fa-play";
            stopBtn.classList.add("hide");
            updateBadge("failed");
        }
    });

    // Download CSV Action
    downloadCsvBtn.addEventListener("click", () => {
        if (!currentTaskId) return;
        window.location.href = `${API_BASE}/api/download/${currentTaskId}`;
    });

    // --- Modal Export Controller ---
    function openModal() {
        exportModal.classList.remove("hide");
        modalConsole.classList.add("hide");
        modalConsole.innerHTML = "";
        sheetNameInput.value = "";
        sheetNameInput.disabled = false;
        worksheetNameInput.disabled = false;
        document.getElementById("confirm-export-btn").disabled = false;
        document.getElementById("cancel-export-btn").disabled = false;
    }

    function closeModal() {
        exportModal.classList.add("hide");
    }

    openExportModalBtn.addEventListener("click", openModal);
    closeModalBtn.addEventListener("click", closeModal);
    cancelExportBtn.addEventListener("click", closeModal);

    // Close modal clicking outside content
    exportModal.addEventListener("click", (e) => {
        if (e.target === exportModal) {
            closeModal();
        }
    });

    exportForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const spreadsheetName = sheetNameInput.value.trim();
        const sheetName = worksheetNameInput.value.trim();

        if (!spreadsheetName || !currentTaskId) return;

        // Show export log window
        modalConsole.classList.remove("hide");
        modalConsole.innerHTML = '<div class="terminal-line info">&gt; Exporting leads dataset to Google Cloud...</div>';

        // Disable modal fields
        sheetNameInput.disabled = true;
        worksheetNameInput.disabled = true;
        document.getElementById("confirm-export-btn").disabled = true;
        document.getElementById("cancel-export-btn").disabled = true;

        try {
            const res = await fetch(`${API_BASE}/api/export`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    task_id: currentTaskId,
                    spreadsheet_name: spreadsheetName,
                    sheet_name: sheetName
                })
            });

            if (!res.ok) throw new Error("Google Sheets export server request failed.");
            const data = await res.json();

            const lines = data.message.split("\n");
            lines.forEach(line => {
                const logClass = line.toLowerCase().includes("failed") || line.toLowerCase().includes("error") ? "error" : "success";
                const div = document.createElement("div");
                div.className = `terminal-line ${logClass}`;
                div.textContent = `> ${line}`;
                modalConsole.appendChild(div);
            });
            modalConsole.scrollTop = modalConsole.scrollHeight;

            if (data.success) {
                const successDiv = document.createElement("div");
                successDiv.className = "terminal-line success";
                successDiv.textContent = "> Completed successfully! You can close this window.";
                modalConsole.appendChild(successDiv);
                
                // Keep Cancel/Close button enabled to let user close
                document.getElementById("cancel-export-btn").disabled = false;
                document.getElementById("cancel-export-btn").textContent = "Done";
            } else {
                document.getElementById("cancel-export-btn").disabled = false;
                document.getElementById("confirm-export-btn").disabled = false;
                sheetNameInput.disabled = false;
                worksheetNameInput.disabled = false;
            }
        } catch (err) {
            const errDiv = document.createElement("div");
            errDiv.className = "terminal-line error";
            errDiv.textContent = `> Connection failed: ${err.message}`;
            modalConsole.appendChild(errDiv);
            
            document.getElementById("cancel-export-btn").disabled = false;
            document.getElementById("confirm-export-btn").disabled = false;
            sheetNameInput.disabled = false;
            worksheetNameInput.disabled = false;
        }
    });

    // Location filter handler
    function applyLocationFilter() {
        const filterText = locationFilter.value.trim().toLowerCase();
        if (!filterText) {
            renderLeads(allLeads);
        } else {
            const filteredLeads = allLeads.filter(lead => {
                const address = (lead.Address || lead.address || "").toLowerCase();
                return address.includes(filterText);
            });
            renderLeads(filteredLeads);
        }
    }
    locationFilter.addEventListener("input", applyLocationFilter);

    // Stop scraping task
    stopBtn.addEventListener("click", async () => {
        if (!currentTaskId) return;
        
        stopBtn.disabled = true;
        stopBtn.querySelector("i").className = "fa-solid fa-circle-notch fa-spin";
        
        try {
            const res = await fetch(`${API_BASE}/api/stop/${currentTaskId}`, {
                method: "POST"
            });
            if (!res.ok) throw new Error("Stop request failed.");
            appendTerminalLog("Stop request sent. Waiting for browser to clean up...");
        } catch (err) {
            appendTerminalLog(`Stop Error: ${err.message}`);
            stopBtn.disabled = false;
            stopBtn.querySelector("i").className = "fa-solid fa-stop";
        }
    });

    // Theme toggle controller
    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    
    // Load persisted theme preference
    if (localStorage.getItem("theme") === "light") {
        document.documentElement.classList.add("light-theme");
        themeToggleBtn.querySelector("i").className = "fa-regular fa-sun";
    }

    themeToggleBtn.addEventListener("click", () => {
        const isLight = document.documentElement.classList.toggle("light-theme");
        localStorage.setItem("theme", isLight ? "light" : "dark");
        themeToggleBtn.querySelector("i").className = isLight ? "fa-regular fa-sun" : "fa-solid fa-moon";
        appendTerminalLog(`System: Switched to ${isLight ? 'Light' : 'Dark'} theme mode.`);
    });
});
