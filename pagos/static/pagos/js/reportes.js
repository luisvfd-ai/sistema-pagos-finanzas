document.addEventListener("DOMContentLoaded", () => {
    console.log("[reportes.js] inicializando ✅");

    function safeParse(id) {
        const el = document.getElementById(id);
        if (!el) {
            console.warn(`[reportes.js] no se encontró script JSON: ${id}`);
            return null;
        }

        const raw = (el.textContent || "").trim();

        if (!raw || raw === "{}" || raw === "null" || raw === "undefined" || raw === "None") {
            console.warn(`[reportes.js] JSON vacío para ${id}:`, raw);
            return null;
        }

        try {
            return JSON.parse(raw);
        } catch (e) {
            console.error(`[reportes.js] JSON inválido en ${id}:`, e, raw);
            return null;
        }
    }

    function formatCurrency(value) {
        const num = Number(value || 0);
        return "$" + num.toLocaleString("es-CL");
    }

    function createLineChart(canvasId, payload, label, color, fill = false) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !payload || !Array.isArray(payload.labels) || !Array.isArray(payload.valores) || !payload.labels.length) {
            return;
        }

        new Chart(canvas, {
            type: "line",
            data: {
                labels: payload.labels,
                datasets: [{
                    label: label,
                    data: payload.valores,
                    tension: 0.25,
                    borderWidth: 3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderColor: color,
                    backgroundColor: fill ? "rgba(79,70,229,0.08)" : color,
                    fill: fill
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return formatCurrency(value);
                            }
                        },
                        grid: { color: "#eef2f7" }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    function createBarChart(canvasId, payload, label) {
        const canvas = document.getElementById(canvasId);
        if (!canvas || !payload || !Array.isArray(payload.labels) || !Array.isArray(payload.valores) || !payload.labels.length) {
            return;
        }

        new Chart(canvas, {
            type: "bar",
            data: {
                labels: payload.labels,
                datasets: [{
                    label: label,
                    data: payload.valores
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return formatCurrency(value);
                            }
                        },
                        grid: { color: "#eef2f7" }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    const diario = safeParse("report-diario-data");
    createLineChart("chartDiario", diario, "Total por día", "#3b82f6");

    const metodo = safeParse("report-metodo-data");
    createBarChart("chartMetodo", metodo, "Total por método");

    const proyeccion = safeParse("proyeccion-data");
    if (proyeccion && Array.isArray(proyeccion.labels) && proyeccion.labels.length) {
        createLineChart(
            "chartProyeccionDiaria",
            {
                labels: proyeccion.labels,
                valores: proyeccion.valores || []
            },
            "Egreso diario proyectado",
            "#4f46e5",
            true
        );

        createLineChart(
            "chartProyeccionAcumulado",
            {
                labels: proyeccion.labels,
                valores: proyeccion.acumulado || []
            },
            "Acumulado proyectado",
            "#dc2626",
            false
        );
    }

    console.log("[reportes.js] charts procesados ✅");
});